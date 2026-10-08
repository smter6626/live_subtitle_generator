"""Fixed GitHub publication; immutable decisions, mutable hints, actual bytes."""
from __future__ import annotations

import datetime
import hashlib
import os
import re
import signal
import stat
import subprocess
import uuid
import shutil
from pathlib import Path

from release_approval import (SHA, Stop, absolute, authenticated_receipt,
                              authorize_workflow, canonical, decode, digest, fields,
                              hex_value, inspect_path, read_file, require)
import release_artifact as artifact
import release_human_gate as human
import release_integration as integration
from release_publication_state import PublicationStore
from release_journal import fsync_directory
from release_approval import LightweightPolicy

REPOSITORY = 'smter6626/live_subtitle_generator'
HOST = 'github.com'
BASE = 'repos/' + REPOSITORY
TAG = '1.1.0'
TITLE = 'Classroom Transcriber 1.1.0'
NOTES_HASH = '69013bcae2de876202b3c6d2633fcb75a659b1f5f413cd905295eb6431a12703'
PLAN_FIELDS = ('artifact_id', 'human_receipt_sha256', 'source_commit', 'source_tree',
               'notes_sha256', 'tag_timestamp', 'tag_oid', 'transport')
RECONCILE_FIELDS = ('plan_sha256', 'artifact_id', 'human_receipt_sha256', 'source_commit',
                    'tag_oid', 'release_id', 'asset_id', 'phase')


def positive_id(value):
    require(type(value) is int and value > 0, 'REMOTE_SCHEMA_INVALID')
    return value


def tag_bytes(source, timestamp):
    require(type(timestamp) is int and 0 < timestamp < 4102444800, 'PUBLICATION_PLAN_INVALID')
    hex_value(source, SHA)
    return (f'object {source}\ntype commit\ntag {TAG}\n'
            f'tagger Classroom Release Controller <release-controller@localhost> {timestamp} +0000\n\n'
            f'{TITLE}\n').encode()


def tag_identity(source, timestamp):
    raw = tag_bytes(source, timestamp)
    return hashlib.sha1(b'tag ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def parse_http(raw, returncode, *, optional=False, expected=200):
    # gh --include returns one final HTTP status/header block plus raw bytes.
    header, separator, body = raw.partition(b'\r\n\r\n')
    if not separator:
        header, separator, body = raw.partition(b'\n\n')
    require(separator and len(header) < 65536, 'REMOTE_RESPONSE_INVALID')
    first = header.splitlines()[0]
    match = re.fullmatch(rb'HTTP/(?:1\.0|1\.1|2(?:\.0)?|3(?:\.0)?) ([0-9]{3})(?: [^\r\n]*)?', first)
    require(match is not None, 'REMOTE_RESPONSE_INVALID')
    code = int(match[1])
    if code == 404 and optional:
        return None
    require(returncode == 0 and code == expected, 'REMOTE_HTTP_FAILED')
    require(body, 'REMOTE_RESPONSE_INVALID')
    return body


class GhTransport:
    """Exact signed executable/config directory; never extract or pass tokens."""
    def __init__(self, policy, transport, *, revalidate):
        self.policy, self.value, self.revalidate = policy, transport, revalidate
        if type(policy) is LightweightPolicy:
            fields(transport, ('executable', 'sha256'))
            self.executable = absolute(transport['executable'])
            hex_value(transport['sha256'])
            self.check()
            return
        fields(transport, ('executable', 'sha256', 'config_dir', 'config_gid'))
        self.executable = absolute(transport['executable'])
        self.config = absolute(transport['config_dir'])
        hex_value(transport['sha256'])
        require(type(transport['config_gid']) is int and transport['config_gid'] >= 0,
                'TRANSPORT_UNAVAILABLE')
        if policy.fixture_root is not None:
            require(self.executable == policy.fixture_root / 'fake-gh' and
                    self.config == policy.fixture_root / 'gh-config', 'FIXTURE_BOUNDARY')
        else:
            # The independent Owner chooses/approves a dedicated directory in
            # the signed plan. Do not inherit ambient gh login or token variables.
            require(self.config == policy.root / 'github-auth' and
                    not self.executable.is_relative_to(policy.root / 'entry'), 'TRANSPORT_UNAVAILABLE')
        self.check()

    def check(self):
        inspect_path(self.executable)
        require(os.access(self.executable, os.X_OK) and self.executable.resolve(strict=True) == self.executable and
                digest(read_file(self.executable, limit=128 * 1024 * 1024)) == self.value['sha256'], 'TRANSPORT_CHANGED')
        if type(self.policy) is LightweightPolicy:
            self.policy.check_fixture()
            if self.policy.fixture_root is not None:
                require(self.executable == self.policy.fixture_root / 'fake-gh', 'FIXTURE_BOUNDARY')
            else:
                found = shutil.which('gh', path=integration.native_environment(self.policy)['PATH'])
                require(found is not None and Path(found).resolve(strict=True) == self.executable,
                        'TRANSPORT_UNAVAILABLE')
            return
        if self.policy.fixture_root is not None:
            inspect_path(self.config, owner=os.getuid(), mode=0o700, directory=True)
            require(self.value['config_gid'] == os.getgid(), 'FIXTURE_BOUNDARY')
        else:
            # Owner-deployed read-only credential directory. Executing uid can
            # read through an explicitly approved group, but cannot edit it.
            # No token bytes are read by this Python controller.
            gid = self.value['config_gid']
            require(gid in (os.getgid(), *os.getgroups()), 'TRANSPORT_UNAVAILABLE')
            inspect_path(self.config, owner=0, mode=0o750, directory=True, protected=True)
            require(self.config.lstat().st_gid == gid and os.access(self.config, os.R_OK | os.X_OK),
                    'TRANSPORT_UNAVAILABLE')
            require(sorted(p.name for p in self.config.iterdir()) == ['config.yml', 'hosts.yml'],
                    'TRANSPORT_UNAVAILABLE')
            for path in self.config.iterdir():
                inspect_path(path, owner=0, mode=0o440, protected=True)
                require(path.lstat().st_gid == gid and os.access(path, os.R_OK), 'TRANSPORT_UNAVAILABLE')

    def environment(self):
        if type(self.policy) is LightweightPolicy:
            env = integration.native_environment(self.policy)
            env.update({'GH_HOST': HOST, 'GH_PROMPT_DISABLED': '1', 'GH_NO_UPDATE_NOTIFIER': '1',
                        'GH_NO_EXTENSION_UPDATE_NOTIFIER': '1', 'NO_COLOR': '1'})
            return env
        return {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C', 'GH_CONFIG_DIR': str(self.config),
                'GH_HOST': HOST, 'GH_PROMPT_DISABLED': '1', 'GH_NO_UPDATE_NOTIFIER': '1',
                'GH_NO_EXTENSION_UPDATE_NOTIFIER': '1', 'NO_COLOR': '1'}

    def request(self, method, endpoint, *, payload=None, upload=None, optional=False):
        require(method in ('GET', 'POST', 'PATCH'), 'TRANSPORT_REQUEST_INVALID')
        require(type(endpoint) is str and ('\n' not in endpoint and '\r' not in endpoint), 'TRANSPORT_REQUEST_INVALID')
        # All endpoints originate from this module's fixed constants/positive IDs.
        if upload is not None:
            require(method == 'POST' and endpoint.startswith(
                'https://uploads.github.com/' + BASE + '/releases/'), 'TRANSPORT_REQUEST_INVALID')
        else:
            require(endpoint.startswith(BASE + '/releases'), 'TRANSPORT_REQUEST_INVALID')
        if method != 'GET':
            self.revalidate()
        self.check()
        argv = [str(self.executable), 'api', endpoint, '--hostname', HOST,
                '--method', method, '--include', '--header', 'X-GitHub-Api-Version: 2022-11-28',
                '--header', 'Accept: application/vnd.github+json']
        data = None
        if payload is not None:
            require(upload is None and method in ('POST', 'PATCH'), 'TRANSPORT_REQUEST_INVALID')
            argv += ['--header', 'Content-Type: application/json', '--input', '-']
            data = (__import__('json').dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n').encode('utf-8')
        if upload is not None:
            argv += ['--header', 'Content-Type: application/zip', '--input', str(upload)]
        try:
            result = subprocess.run(argv, cwd=self.policy.root, env=self.environment(), input=data,
                                    capture_output=True, timeout=120, check=False)
        except subprocess.TimeoutExpired:
            raise Stop('REMOTE_OUTCOME_UNKNOWN') from None
        self.check()
        if method != 'GET':
            self.revalidate()
        body = parse_http(result.stdout, result.returncode, optional=optional,
                          expected=201 if method == 'POST' else 200)
        if body is None:
            return body
        return decode(body)

    def download(self, asset_id, path, expected_bytes, expected_hash):
        """Stream raw HTTP output to disk, then copy only validated body bytes.

        Memory is bounded independently of ZIP size. Partial responses/files
        remain local evidence; no overwrite or automatic deletion is performed.
        """
        positive_id(asset_id)
        self.revalidate()
        self.check()
        inspect_path(path.parent, owner=os.getuid(), mode=0o700, directory=True)
        response_path = path.parent / ('.response-' + uuid.uuid4().hex)
        fd = os.open(response_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        process = None
        try:
            with os.fdopen(fd, 'wb') as output:
                argv = [str(self.executable), 'api', BASE + '/releases/assets/' + str(asset_id),
                        '--hostname', HOST, '--method', 'GET', '--include',
                        '--header', 'Accept: application/octet-stream',
                        '--header', 'X-GitHub-Api-Version: 2022-11-28']
                process = subprocess.Popen(argv, cwd=self.policy.root, env=self.environment(),
                    stdout=output, stderr=subprocess.DEVNULL, start_new_session=True)
                try:
                    process.wait(timeout=120)
                except subprocess.TimeoutExpired:
                    raise Stop('REMOTE_OUTCOME_UNKNOWN') from None
                output.flush()
                os.fsync(output.fileno())
            require(process.returncode == 0, 'REMOTE_HTTP_FAILED')
        finally:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=2)
        fsync_directory(path.parent)
        require(response_path.lstat().st_size <= expected_bytes + 65536, 'REMOTE_ARTIFACT_CHANGED')
        fd = os.open(response_path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as response:
            header = bytearray()
            for _ in range(100):
                line = response.readline(65537 - len(header))
                header.extend(line)
                require(len(header) <= 65536 and line, 'REMOTE_RESPONSE_INVALID')
                if line in (b'\n', b'\r\n'):
                    break
            else:
                raise Stop('REMOTE_RESPONSE_INVALID')
            parse_http(bytes(header) + b'x', 0)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            checksum, size = hashlib.sha256(), 0
            with os.fdopen(descriptor, 'wb') as output:
                for chunk in iter(lambda: response.read(1024 * 1024), b''):
                    size += len(chunk)
                    require(size <= expected_bytes, 'REMOTE_ARTIFACT_CHANGED')
                    checksum.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
        fsync_directory(path.parent)
        require(size == expected_bytes and checksum.hexdigest() == expected_hash, 'REMOTE_ARTIFACT_CHANGED')
        self.check()
        self.revalidate()
        return size, checksum.hexdigest()

    def pages(self, endpoint):
        result, seen = [], set()
        for page in range(1, 1001):
            value = self.request('GET', endpoint + '?per_page=100&page=' + str(page))
            require(type(value) is list and len(value) <= 100, 'REMOTE_SCHEMA_INVALID')
            for item in value:
                require(type(item) is dict and 'id' in item, 'REMOTE_SCHEMA_INVALID')
                identifier = positive_id(item['id'])
                require(identifier not in seen, 'REMOTE_PAGINATION_INVALID')
                seen.add(identifier)
                result.append(item)
            if len(value) < 100:
                return result
        raise Stop('REMOTE_PAGINATION_INVALID')


class Publisher:
    def __init__(self, policy, *, checkpoint=None):
        require(policy.fixture_root is not None or checkpoint is None, 'FIXTURE_BOUNDARY')
        self.policy, self.checkpoint = policy, checkpoint or (lambda _: None)
        self.auth = authorize_workflow(policy)
        from release_workflow_state import StateStore
        value = StateStore(self.auth).inspect()
        require(value is not None and value['state'] in ('ARTIFACT', 'HUMAN_RECORDED') and
                value['intent'] is None, 'ARTIFACT_MISSING')
        self.artifact = value['artifact']
        self.source, self.source_hash = artifact.accepted_source(policy, self.auth, remote=True)
        self.human = human.validate_human_gate(policy, self.auth, self.artifact)
        self.plan, self.plan_hash = authenticated_receipt(policy, self.auth, 'publication-plan', PLAN_FIELDS)
        require(self.plan['artifact_id'] == self.artifact['artifact_id'] and
                self.plan['human_receipt_sha256'] == self.human['receipt_sha256'] and
                self.plan['source_commit'] == self.source['source_commit'] and
                self.plan['source_tree'] == self.source['source_tree'] and
                self.plan['notes_sha256'] == NOTES_HASH and
                self.plan['tag_oid'] == tag_identity(self.source['source_commit'], self.plan['tag_timestamp']),
                'PUBLICATION_PLAN_INVALID')
        self.tag_oid = self.plan['tag_oid']
        self.notes = read_file(self.auth.implementation / 'RELEASE_NOTES_1.1.0.md')
        require(digest(self.notes) == NOTES_HASH, 'NOTES_CHANGED')
        try:
            self.notes_text = self.notes.decode('utf-8')
        except UnicodeError:
            raise Stop('NOTES_CHANGED') from None
        self.store = PublicationStore(self.auth, self.plan_hash, self.artifact['artifact_id'], self.tag_oid)
        self.transport = GhTransport(policy, self.plan['transport'], revalidate=self.revalidate)
        # Never serialize authority inferred from one successful live response.
        self.owned_release = self.owned_asset = None

    def revalidate(self):
        # accepted_source/authenticated_receipt each reauthenticate workflow;
        # compose one complete source/Human/artifact/plan boundary here rather
        # than repeat the entire source/tree/ZIP scan through the C1 helper.
        # Nothing is cached across a boundary or reconstructed from journal.
        source, checksum = artifact.accepted_source(self.policy, self.auth, remote=True)
        require(source == self.source and checksum == self.source_hash, 'SOURCE_RECEIPT_CHANGED')
        receipt, human_hash = authenticated_receipt(self.policy, self.auth, 'artifact-human',
            ('decision', 'integration_receipt_sha256', 'artifact'))
        require(type(receipt['decision']) is str and receipt['decision'] == 'PASS', 'HUMAN_FAIL')
        artifact.artifact_schema(receipt['artifact'], self.auth)
        require(receipt['integration_receipt_sha256'] == checksum and
                canonical(receipt['artifact']) == canonical(self.artifact), 'HUMAN_ARTIFACT_BINDING')
        require({'receipt_id': receipt['id'], 'receipt_sha256': human_hash,
                 'decision_reference': receipt['decision_reference']} == self.human, 'RECEIPT_CHANGED')
        artifact.validate_artifact(self.artifact, self.auth, source, checksum)
        plan, checksum = authenticated_receipt(self.policy, self.auth, 'publication-plan', PLAN_FIELDS)
        require(plan == self.plan and checksum == self.plan_hash, 'PUBLICATION_PLAN_CHANGED')
        require(read_file(self.auth.implementation / 'RELEASE_NOTES_1.1.0.md') == self.notes, 'NOTES_CHANGED')

    def intent(self, value, name):
        self.revalidate()
        value = self.store.change(value, intent=name)
        self.checkpoint('before_' + name.lower())
        self.revalidate()
        return value

    def remote_tag(self):
        data = integration.git(None, 'ls-remote', self.auth.payload['origin'], 'refs/tags/' + TAG,
                               'refs/tags/' + TAG + '^{}')
        refs = {}
        for line in data.splitlines():
            parts = line.split('\t')
            require(len(parts) == 2 and parts[1] in ('refs/tags/' + TAG, 'refs/tags/' + TAG + '^{}') and
                    parts[1] not in refs, 'REMOTE_TAG_INVALID')
            hex_value(parts[0], SHA)
            refs[parts[1]] = parts[0]
        if not refs:
            return None
        require(refs == {'refs/tags/' + TAG: self.tag_oid,
                        'refs/tags/' + TAG + '^{}': self.source['source_commit']}, 'REMOTE_TAG_CONFLICT')
        return self.tag_oid

    def ensure_tag(self, value):
        actual = self.remote_tag()
        if actual is None:
            require(value['intent'] in (None, 'TAG_PUSH'), 'PUBLICATION_RECONCILIATION_REQUIRED')
            value = self.intent(value, 'TAG_PUSH')
            require(self.remote_tag() is None, 'REMOTE_TAG_CONFLICT')
            repo = absolute(self.source['source_repository'])
            raw = tag_bytes(self.source['source_commit'], self.plan['tag_timestamp'])
            # run_git has no stdin interface. Use the same sanitized fixed Git
            # command arguments directly for the one deterministic object write.
            result = subprocess.run([integration.GIT, '-c', 'core.hooksPath=/dev/null', '-C', str(repo),
                                     'hash-object', '-t', 'tag', '-w', '--stdin'], input=raw,
                                    capture_output=True, env=integration.environment(), check=False)
            require(result.returncode == 0 and result.stdout.strip().decode() == self.tag_oid, 'TAG_OBJECT_INVALID')
            self.revalidate()
            result = integration.run_git(repo, 'push', '--porcelain', 'origin',
                                         self.tag_oid + ':refs/tags/' + TAG, allow_failure=True)
            self.checkpoint('after_tag_push')
            self.revalidate()
            require(self.remote_tag() == self.tag_oid, 'TAG_PUSH_UNKNOWN')
        return self.store.change(value, state='TAGGED', intent=None)

    def release(self, value, *, published):
        require(type(value) is dict, 'REMOTE_SCHEMA_INVALID')
        identifier = positive_id(value.get('id'))
        require(value.get('tag_name') == TAG and value.get('name') == TITLE and
                value.get('body') == self.notes_text and value.get('target_commitish') == self.source['source_commit'] and
                type(value.get('draft')) is bool and value['draft'] is not published and
                type(value.get('prerelease')) is bool and not value['prerelease'] and
                value.get('url') == f'https://api.github.com/{BASE}/releases/{identifier}' and
                value.get('html_url') == f'https://github.com/{REPOSITORY}/releases/tag/{TAG}', 'REMOTE_RELEASE_CONFLICT')
        timestamp = value.get('published_at')
        if published:
            require(type(timestamp) is str, 'REMOTE_RELEASE_CONFLICT')
            try:
                parsed = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except ValueError:
                raise Stop('REMOTE_RELEASE_CONFLICT') from None
            require(parsed.tzinfo is not None, 'REMOTE_RELEASE_CONFLICT')
        else:
            require(timestamp is None, 'REMOTE_RELEASE_CONFLICT')
        return identifier

    def asset(self, value, release_id):
        require(type(value) is dict, 'REMOTE_SCHEMA_INVALID')
        identifier = positive_id(value.get('id'))
        require(value.get('name') == artifact.ASSET and value.get('state') == 'uploaded' and
                type(value.get('size')) is int and value['size'] == self.artifact['zip_bytes'] and
                value.get('content_type') == 'application/zip' and
                value.get('url') == f'https://api.github.com/{BASE}/releases/assets/{identifier}' and
                value.get('browser_download_url') ==
                f'https://github.com/{REPOSITORY}/releases/download/{TAG}/{artifact.ASSET}', 'REMOTE_ASSET_CONFLICT')
        return identifier

    def reconcile(self, release_id, asset_id, phase):
        value, _ = authenticated_receipt(self.policy, self.auth, 'publication-reconciliation', RECONCILE_FIELDS)
        expected = {'plan_sha256': self.plan_hash, 'artifact_id': self.artifact['artifact_id'],
                    'human_receipt_sha256': self.human['receipt_sha256'], 'source_commit': self.source['source_commit'],
                    'tag_oid': self.tag_oid, 'release_id': release_id, 'asset_id': asset_id, 'phase': phase}
        require(all(value[key] == item for key, item in expected.items()) and
                type(value['release_id']) is int and
                (value['asset_id'] is None or type(value['asset_id']) is int), 'PUBLICATION_RECONCILIATION_INVALID')
        return value

    def download(self, value, release_id, asset_id, phase):
        value = self.intent(value, 'DOWNLOAD_' + ('DRAFT' if phase == 'draft' else 'PUBLIC'))
        # Fixed asset ID endpoint; never follow a response-supplied arbitrary URL.
        name = 'download-' + uuid.uuid4().hex + '.zip'
        path = self.store.root / 'downloads' / name
        size, checksum = self.transport.download(asset_id, path, self.artifact['zip_bytes'], self.artifact['zip_sha256'])
        require(artifact.file_hash(path) == (self.artifact['zip_bytes'], self.artifact['zip_sha256']), 'REMOTE_ARTIFACT_CHANGED')
        self.checkpoint('after_download_' + phase)
        self.revalidate()
        proof = {'phase': phase, 'file': name, 'bytes': size, 'sha256': checksum}
        return self.store.change(value, intent=None, downloads=[*value['downloads'], proof])

    def remote_release(self, release_id, asset_id, *, published):
        require(self.remote_tag() == self.tag_oid, 'REMOTE_TAG_CONFLICT')
        require(self.release(self.transport.request('GET', BASE + '/releases/' + str(release_id)),
                             published=published) == release_id, 'REMOTE_RELEASE_CONFLICT')
        assets = self.transport.pages(BASE + '/releases/' + str(release_id) + '/assets')
        if asset_id is None:
            require(not assets, 'REMOTE_ASSET_CONFLICT')
        else:
            require(len(assets) == 1 and self.asset(assets[0], release_id) == asset_id,
                    'REMOTE_ASSET_CONFLICT')

    def execute(self):
        self.revalidate()
        value = self.store.inspect()
        if value is None:
            value = self.store.create()
        # Discover all candidate objects before writing. No same-name adoption.
        releases = self.transport.pages(BASE + '/releases')
        candidates = [item for item in releases if item.get('tag_name') == TAG or item.get('name') == TITLE]
        require(len(candidates) <= 1, 'REMOTE_RELEASE_CONFLICT')
        if candidates:
            require(self.remote_tag() == self.tag_oid, 'REMOTE_TAG_CONFLICT')
            found = candidates[0]
            published = found.get('draft') is False
            release_id = self.release(found, published=published)
            assets = self.transport.pages(BASE + '/releases/' + str(release_id) + '/assets')
            require(len(assets) <= 1, 'REMOTE_ASSET_CONFLICT')
            asset_id = self.asset(assets[0], release_id) if assets else None
            phase = 'PUBLISHED' if published else ('UPLOADED' if assets else 'DRAFT')
            try:
                self.reconcile(release_id, asset_id, phase)
            except (OSError, Stop):
                raise Stop('PUBLICATION_RECONCILIATION_REQUIRED') from None
            require(value['release_id'] in (None, release_id) and value['asset_id'] in (None, asset_id),
                    'PUBLICATION_STATE_FACTS')
            self.owned_release, self.owned_asset = release_id, asset_id
            value = self.store.change(value, state=phase if phase != 'UPLOADED' else 'UPLOADED',
                                      intent=None, release_id=release_id, asset_id=asset_id)
        else:
            require(value['release_id'] is None and value['asset_id'] is None and
                    value['intent'] in (None, 'TAG_PUSH'), 'PUBLICATION_RECONCILIATION_REQUIRED')
            value = self.ensure_tag(value)
            value = self.intent(value, 'CREATE')
            require(not any(item.get('tag_name') == TAG or item.get('name') == TITLE
                            for item in self.transport.pages(BASE + '/releases')), 'REMOTE_RELEASE_CONFLICT')
            require(self.remote_tag() == self.tag_oid, 'REMOTE_TAG_CONFLICT')
            found = self.transport.request('POST', BASE + '/releases', payload={
                'tag_name': TAG, 'target_commitish': self.source['source_commit'], 'name': TITLE,
                'body': self.notes_text, 'draft': True, 'prerelease': False, 'make_latest': 'false'})
            release_id = self.release(found, published=False)
            self.checkpoint('after_create')
            again = self.transport.request('GET', BASE + '/releases/' + str(release_id))
            require(self.release(again, published=False) == release_id, 'REMOTE_RELEASE_CONFLICT')
            self.owned_release = release_id
            asset_id, published = None, False
            value = self.store.change(value, state='DRAFT', intent=None, release_id=release_id)
        require(self.owned_release == release_id, 'PUBLICATION_RECONCILIATION_REQUIRED')
        assets = self.transport.pages(BASE + '/releases/' + str(release_id) + '/assets')
        if asset_id is None:
            require(not published and not assets and value['intent'] is None, 'REMOTE_ASSET_CONFLICT')
            value = self.intent(value, 'UPLOAD')
            self.remote_release(release_id, None, published=False)
            uploaded = self.transport.request('POST',
                'https://uploads.github.com/' + BASE + '/releases/' + str(release_id) + '/assets?name=' + artifact.ASSET,
                upload=absolute(self.artifact['zip_path']))
            asset_id = self.asset(uploaded, release_id)
            self.checkpoint('after_upload')
            assets = self.transport.pages(BASE + '/releases/' + str(release_id) + '/assets')
            require(len(assets) == 1 and self.asset(assets[0], release_id) == asset_id, 'REMOTE_ASSET_CONFLICT')
            self.owned_asset = asset_id
            value = self.store.change(value, state='UPLOADED', intent=None, release_id=release_id, asset_id=asset_id)
        else:
            require(len(assets) == 1 and self.asset(assets[0], release_id) == asset_id and
                    self.owned_asset == asset_id, 'REMOTE_ASSET_CONFLICT')
            value = self.store.change(value, state='PUBLISHED' if published else 'UPLOADED', intent=None,
                                      release_id=release_id, asset_id=asset_id)
        if not published:
            require(self.release(self.transport.request('GET', BASE + '/releases/' + str(release_id)),
                                 published=False) == release_id, 'REMOTE_RELEASE_CONFLICT')
            value = self.download(value, release_id, asset_id, 'draft')
            value = self.store.change(value, state='VERIFIED', intent=None)
            value = self.intent(value, 'PUBLISH')
            self.remote_release(release_id, asset_id, published=False)
            # Validate the retained draft proof and actual remote bytes again
            # after the intent/checkpoint boundary, immediately before PATCH.
            proof = next((item for item in reversed(value['downloads']) if item['phase'] == 'draft'), None)
            require(proof is not None and artifact.file_hash(self.store.root / 'downloads' / proof['file']) ==
                    (self.artifact['zip_bytes'], self.artifact['zip_sha256']), 'REMOTE_ARTIFACT_CHANGED')
            path = self.store.root / 'downloads' / ('download-' + uuid.uuid4().hex + '.zip')
            self.transport.download(asset_id, path, self.artifact['zip_bytes'], self.artifact['zip_sha256'])
            self.remote_release(release_id, asset_id, published=False)
            result = self.transport.request('PATCH', BASE + '/releases/' + str(release_id),
                                            payload={'draft': False, 'prerelease': False, 'make_latest': 'true'})
            require(self.release(result, published=True) == release_id, 'REMOTE_RELEASE_CONFLICT')
            self.checkpoint('after_publish')
            value = self.store.change(value, state='PUBLISHED', intent=None)
        require(self.remote_tag() == self.tag_oid, 'REMOTE_TAG_CONFLICT')
        public = self.transport.request('GET', BASE + '/releases/' + str(release_id))
        latest = self.transport.request('GET', BASE + '/releases/latest')
        require(self.release(public, published=True) == release_id and
                self.release(latest, published=True) == release_id, 'REMOTE_LATEST_CONFLICT')
        assets = self.transport.pages(BASE + '/releases/' + str(release_id) + '/assets')
        require(len(assets) == 1 and self.asset(assets[0], release_id) == asset_id, 'REMOTE_ASSET_CONFLICT')
        value = self.download(value, release_id, asset_id, 'public')
        self.revalidate()
        self.store.change(value, state='COMPLETE', intent=None)
        return 'PUBLICATION_VERIFIED_SAME_ARTIFACT'
