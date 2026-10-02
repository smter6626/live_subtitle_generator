#!/usr/bin/env python3
"""C1 candidate status/build/resume/human-gate. Fresh staged build, retained package and independent Human gate."""
from __future__ import annotations

# The production CLI refuses before importing any repo/control/helper code.
# Launching Python with -I is part of the eventual protected-entry deployment.
# Strip caller paths as well, and compile verified bytes instead of trusting pyc.
import sys
if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('status', 'build', 'resume', 'human-gate'):
        print('release-workflow: STOP ARGUMENTS_INVALID', file=sys.stderr)
        raise SystemExit(2)
    _stdlib = sys.base_prefix + '/lib/python' + str(sys.version_info.major) + '.' + str(sys.version_info.minor)
    _stdlib_zip = sys.base_prefix + '/lib/python' + str(sys.version_info.major) + str(sys.version_info.minor) + '.zip'
    sys.path[:] = [p for p in sys.path if p in (_stdlib, _stdlib + '/lib-dynload', _stdlib_zip)]
    import hashlib as _hashlib
    import json as _json
    import os as _os
    import stat as _stat
    import subprocess as _subprocess
    from pathlib import Path as _Path
    import importlib.abc as _abc
    import importlib.util as _util
    import importlib as _importlib

    def _entry_bootstrap():
        root = _Path('/Library/Application Support/ClassroomTranscriberRelease/1.1.0')
        if not root.exists():
            raise RuntimeError('TRUST_UNAVAILABLE')
        entry = root / 'entry'
        controls = tuple('scripts/' + name + '.py' for name in (
            'release_controller', 'release_approval', 'release_journal', 'release_integration',
            'release_workflow', 'release_workflow_state', 'release_artifact', 'release_human_gate'))
        helpers = ('scripts/release_identity.py', 'scripts/build_release_zip.py',
                   'scripts/verify_packaged_runtime.py', 'model_integrity.py', 'resource_paths.py')
        def read(path):
            for item in (*reversed(path.parents), path):
                info = item.lstat()
                if info.st_uid != 0 or _stat.S_ISLNK(info.st_mode) or info.st_mode & 0o022 or _os.access(item, _os.W_OK):
                    raise RuntimeError('ENTRY_INVALID')
            info = path.lstat()
            if not _stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or _stat.S_IMODE(info.st_mode) != 0o644:
                raise RuntimeError('ENTRY_INVALID')
            with path.open('rb') as handle:
                return handle.read()
        if _Path(__file__) != entry / 'scripts/release_workflow.py':
            raise RuntimeError('ENTRY_INVALID')
        def decode(raw):
            def pairs(items):
                value = {}
                for key, item in items:
                    if key in value:
                        raise RuntimeError('ENTRY_INVALID')
                    value[key] = item
                return value
            return _json.loads(raw, object_pairs_hook=pairs)
        config = decode(read(root / 'workflow-config.json'))
        payload_raw = read(root / 'workflow-approval.json')
        payload = decode(payload_raw)
        read(root / 'allowed_signers')
        read(root / 'workflow-approval.json.sig')
        result = _subprocess.run(['/usr/bin/ssh-keygen', '-Y', 'verify', '-f', str(root / 'allowed_signers'),
                                  '-I', 'classroom-transcriber-release-owner',
                                  '-n', 'classroom-transcriber-release-1.1.0-production',
                                  '-s', str(root / 'workflow-approval.json.sig')], input=payload_raw,
                                 capture_output=True, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, check=False)
        if result.returncode != 0:
            raise RuntimeError('SIGNATURE_INVALID')
        sources = {}
        for relative in (*controls, *helpers, 'packaging/model_manifest.json',
                         'packaging/runtime_manifest.json', 'packaging/release_contract.json'):
            raw = read(entry / relative)
            checksum = _hashlib.sha256(raw).hexdigest()
            if payload['tools'][relative] != checksum:
                raise RuntimeError('ENTRY_INVALID')
            if relative.endswith('.py'):
                if config['entry_sha256'][relative] != checksum:
                    raise RuntimeError('ENTRY_INVALID')
                sources[_Path(relative).stem] = (entry / relative, raw)
        # Preload every stdlib dependency before a helper adjusts sys.path.
        for name in ('argparse', 'pwd', 're', 'shutil', 'tempfile', 'uuid', 'dataclasses',
                     'typing', 'platform', 'plistlib', 'tomllib', 'zipfile', 'contextlib',
                     'select', 'signal', 'time', 'io'):
            _importlib.import_module(name)
        class Loader(_abc.MetaPathFinder, _abc.Loader):
            def find_spec(self, fullname, path=None, target=None):
                if fullname in sources:
                    return _util.spec_from_loader(fullname, self, origin=str(sources[fullname][0]))
                return None
            def create_module(self, spec):
                return None
            def exec_module(self, module):
                path, approved = sources[module.__name__]
                if read(path) != approved:
                    raise RuntimeError('ENTRY_INVALID')
                module.__file__ = str(path)
                exec(compile(approved, str(path), 'exec'), module.__dict__)
        if any(name in sys.modules for name in sources):
            raise RuntimeError('ENTRY_INVALID')
        sys.meta_path.insert(0, Loader())
    try:
        _entry_bootstrap()
    except (OSError, RuntimeError, ValueError, KeyError, TypeError) as _error:
        _code = str(_error) if type(_error) is RuntimeError and str(_error) in (
            'TRUST_UNAVAILABLE', 'ENTRY_INVALID', 'SIGNATURE_INVALID') else 'ENTRY_INVALID'
        print('release-workflow: STOP ' + _code, file=sys.stderr)
        raise SystemExit(1)

import os
import sys
import contextlib
import hashlib
import select
import signal
import stat
import subprocess
import time
from pathlib import Path

# Load the entire protected legacy-plus-C1 control set before authorization.
import release_controller
import release_integration
import release_journal
import release_artifact
import release_human_gate
import release_workflow_state
from release_approval import (WorkflowPolicy, Stop, authorize_workflow, require,
                              inspect_path, read_file, digest, decode, absolute)
import build_release_zip
import verify_packaged_runtime
from release_journal import fsync_directory


def build_parser():
    parser = release_controller.Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument('command', choices=('status', 'build', 'resume', 'human-gate'))
    return parser


def status(policy):
    auth = authorize_workflow(policy)
    release_artifact.verify_implementation(auth)
    value = release_workflow_state.StateStore(auth).inspect()
    # No independent source/Human decision is accepted or promoted here. Never
    # execute App/interpreter, create directories, repair, fetch or write state.
    return 'MISSING' if value is None else value['state'] + '_RECORDED_UNVERIFIED'


def fresh_source(repo: Path):
    release_integration.clean(repo)
    release_integration.worktree_bytes(repo)
    # Even ignored dist or an apparently correct .venv is untrusted until fresh
    # pinned acquisition in this invocation. Do not execute or remove it.
    require(not release_integration.git(repo, 'ls-files', '--others', '--ignored', '--exclude-standard'),
            'ENVIRONMENT_UNTRUSTED')
    require(not any(os.path.lexists(repo / name) for name in ('.tools', '.venv', 'dist', 'build', 'external')),
            'ENVIRONMENT_UNTRUSTED')


EVENTS = ('before:python', 'after:python', 'before:runtime', 'after:runtime',
          'before:app', 'after:app')


def execution_snapshot(repo):
    """Identity and bytes of every input/output, with no broad cache exclusions."""
    inspect_path(repo, owner=os.getuid(), directory=True)
    result = {}
    cache_targets = {}
    def cache_link(path, relative, text, target):
        cache = repo / '.tools/cache'
        # Resolve must not hide another alias in the target's ancestry. Native
        # uv wheel entries point directly at archive-v0/<id>, using relative
        # text. Both the link's ancestry and the target tree are scanned below.
        require(not Path(text).is_absolute() and target.is_relative_to(cache) and
                Path(os.path.abspath(path.parent / text)) == target,
                'ENVIRONMENT_INVALID')
        parts = Path(relative).parts
        if target.is_dir():
            native = (parts[:4] == ('.tools', 'cache', 'wheels-v6', 'pypi') and len(parts) == 6 or
                      parts[:4] == ('.tools', 'cache', 'wheels-v6', 'url') and len(parts) == 7)
            require(native and target.parent == cache / 'archive-v0', 'ENVIRONMENT_INVALID')
        for item in (*reversed(target.relative_to(cache).parents), target.relative_to(cache)):
            info = (cache / item).lstat()
            require(info.st_uid == os.getuid() and not info.st_mode & 0o022 and
                    (stat.S_ISDIR(info.st_mode) or
                     item == target.relative_to(cache) and stat.S_ISREG(info.st_mode) and info.st_nlink == 1),
                    'ENVIRONMENT_INVALID')
        cache_targets[relative] = target.relative_to(repo).as_posix()
    def visit(directory):
        with os.scandir(directory) as iterator:
            entries = sorted(iterator, key=lambda entry: entry.name)
        for entry in entries:
            path = Path(entry.path)
            relative = path.relative_to(repo).as_posix()
            if relative == '.git':
                continue  # Independently audited Git metadata at every boundary.
            info = path.lstat()
            advisory = (relative in ('.venv/.lock', '.tools/python/.lock', '.tools/cache/.lock') and
                        stat.S_ISREG(info.st_mode) and info.st_size == 0 and
                        info.st_nlink == 1 and
                        stat.S_IMODE(info.st_mode) == 0o666)
            # uv's cache lock is advisory, never an alias or cache exclusion.
            # Its containing directories must also be real, safe directories.
            if relative in ('.tools', '.tools/cache'):
                require(stat.S_ISDIR(info.st_mode), 'ENVIRONMENT_INVALID')
            if relative == '.tools/cache/.lock':
                require(advisory, 'ENVIRONMENT_INVALID')
            require(info.st_uid == os.getuid() and
                    (stat.S_ISLNK(info.st_mode) or advisory or not info.st_mode & 0o022),
                    'ENVIRONMENT_INVALID')
            identity = (info.st_dev, info.st_ino, info.st_mode, info.st_uid)
            if stat.S_ISDIR(info.st_mode):
                result[relative] = ('directory', identity)
                visit(path)
            elif stat.S_ISLNK(info.st_mode):
                try:
                    target = path.resolve(strict=True)
                except (OSError, RuntimeError):
                    raise Stop('ENVIRONMENT_INVALID') from None
                require(target.is_relative_to(repo), 'ENVIRONMENT_INVALID')
                text = os.readlink(path)
                if relative.startswith('.tools/cache/'):
                    cache_link(path, relative, text, target)
                require(path.lstat() == info and os.readlink(path) == text, 'ENVIRONMENT_CHANGED')
                result[relative] = ('symlink', identity, text, info.st_nlink,
                                    info.st_size, info.st_mtime_ns, info.st_ctime_ns)
            else:
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'ENVIRONMENT_INVALID')
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, 'rb') as handle:
                    require(os.fstat(handle.fileno()) == info, 'ENVIRONMENT_CHANGED')
                    checksum = hashlib.file_digest(handle, 'sha256').hexdigest()
                after = path.lstat()
                require((after.st_dev, after.st_ino, after.st_mode, after.st_uid, after.st_nlink,
                         after.st_size, after.st_mtime_ns, after.st_ctime_ns) ==
                        (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
                         info.st_size, info.st_mtime_ns, info.st_ctime_ns), 'ENVIRONMENT_CHANGED')
                result[relative] = ('file', identity, info.st_size,
                                    info.st_mtime_ns, info.st_ctime_ns, checksum)
    visit(repo)
    # Target directories and every descendant byte are covered under their real
    # paths, never by following directory aliases or excluding cache contents.
    require(all(target in result and result[target][0] in ('directory', 'file')
                for target in cache_targets.values()), 'ENVIRONMENT_INVALID')
    return result


def permitted_creation(relative, stage):
    # Only creations are permitted: previously acquired bytes remain immutable.
    # These are the original chain's reviewed destinations, not exclusions from
    # the snapshot. Cache contents are acquired during Python and then frozen.
    roots = {
        'python': ('.tools/uv', '.tools/python', '.tools/cache', '.venv'),
        'runtime': ('.tools/cmake/4.2.3', 'external/whisper.cpp'),
        'app': ('build', 'dist'),
    }[stage]
    parents = {'.tools'} if stage == 'python' else (
        {'.tools/cmake', 'external'} if stage == 'runtime' else set())
    return relative in parents or any(relative == root or relative.startswith(root + '/') for root in roots)


@contextlib.contextmanager
def subprocess_environment(env):
    # The unchanged helpers launch synchronous subprocesses without an env
    # argument. Apply the same sanitized invocation environment around them.
    previous = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(previous)


class BuildController:
    def __init__(self, policy, *, fixture_checkpoint=None, fixture_runtime=None, fixture_verifier=None):
        require(policy.fixture_root is not None or
                all(value is None for value in (fixture_checkpoint, fixture_runtime, fixture_verifier)),
                'FIXTURE_BOUNDARY')
        self.policy = policy
        self.auth = authorize_workflow(policy)
        self.source, self.source_hash = release_artifact.accepted_source(policy, self.auth, remote=True)
        self.store = release_workflow_state.StateStore(self.auth)
        self.proof = None  # Never serialized or reconstructed from a state label.
        self.events = []
        self.fixture_checkpoint = fixture_checkpoint
        self.fixture_runtime = fixture_runtime
        self.fixture_verifier = fixture_verifier

    def revalidate(self):
        require(authorize_workflow(self.policy) == self.auth, 'APPROVAL_CHANGED')
        source, checksum = release_artifact.accepted_source(self.policy, self.auth, remote=True)
        require(source == self.source and checksum == self.source_hash, 'SOURCE_RECEIPT_CHANGED')
        if hasattr(self, 'workspace'):
            repo = self.workspace
            release_integration.audit_git(repo, self.auth.payload['origin'])
            release_integration.clean(repo)
            release_integration.worktree_bytes(repo)
            release_artifact.verify_tools(repo, self.auth)
            require(release_integration.git(repo, 'rev-parse', 'HEAD') == self.source['source_commit'] and
                    release_integration.git(repo, 'rev-parse', 'HEAD^{tree}') == self.source['source_tree'],
                    'SOURCE_CHANGED')

    def environment(self):
        env = release_integration.environment()
        env.update({'TMPDIR': str(self.store.root / 'tmp'), 'QT_QPA_PLATFORM': 'offscreen',
                    'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONWARNINGS': 'error::ResourceWarning',
                    'UV_PYTHON_INSTALL_DIR': str(self.workspace / '.tools/python'),
                    'UV_CACHE_DIR': str(self.workspace / '.tools/cache'), 'UV_MANAGED_PYTHON': '1',
                    'UV_NO_CONFIG': '1', 'UV_LINK_MODE': 'copy',
                    'PYINSTALLER_CONFIG_DIR': str(self.workspace / 'build/pyinstaller-cache')})
        # Deny hooks/helpers/includes for Git invoked by the original shell
        # stages too. No user credentials, agent, user configs or tools copied.
        config = (('core.hooksPath', '/dev/null'), ('core.attributesFile', '/dev/null'),
                  ('credential.helper', ''), ('http.followRedirects', 'false'),
                  ('protocol.allow', 'never'), ('protocol.https.allow', 'always'),
                  ('protocol.ssh.allow', 'always'), ('protocol.file.allow', 'always'),
                  ('maintenance.auto', 'false'), ('gc.auto', '0'))
        env['GIT_CONFIG_COUNT'] = str(len(config))
        for index, (key, value) in enumerate(config):
            env['GIT_CONFIG_KEY_' + str(index)] = key
            env['GIT_CONFIG_VALUE_' + str(index)] = value
        return env

    def check_environment_proof(self):
        require(self.proof is not None and execution_snapshot(self.workspace) == self.proof,
                'ENVIRONMENT_CHANGED')

    def check_environment_paths(self, *, present=False):
        # Reuse REL1B's acquired Python path definition, never its journal/gate.
        release_integration.Integration.check_environment_paths(self, present=present)

    @property
    def clone(self):
        return self.workspace

    def verify_environment(self):
        release_integration.Integration.verify_environment(self, self.env)

    def verify_runtime(self):
        self.check_environment_proof()
        if self.fixture_runtime is not None:
            self.fixture_runtime(self)
        else:
            manifest = decode(read_file(self.workspace / 'packaging/runtime_manifest.json'))
            runtime = manifest['frozen']['whisper_cpp']
            repo = self.workspace / runtime['local_rebuild_root_path']
            # The original chain intentionally fetches this pin shallowly.
            # Validate all actual source bytes including hidden index changes.
            inspect_path(repo / '.git', owner=os.getuid(), directory=True)
            require(release_integration.git(repo, 'remote', 'get-url', '--all', 'origin') == runtime['repository'] and
                    release_integration.git(repo, 'rev-parse', 'HEAD') == runtime['commit'] and
                    release_integration.run_git(repo, 'symbolic-ref', '-q', 'HEAD', allow_failure=True).returncode == 1,
                    'RUNTIME_SOURCE_CHANGED')
            release_integration.clean(repo)
            release_integration.worktree_bytes(repo)
            tracked = set(release_integration.git(repo, 'ls-files').splitlines())
            for relative in self.proof:
                prefix = 'external/whisper.cpp/'
                if relative.startswith(prefix):
                    item = relative[len(prefix):]
                    require(item == '.git' or item.startswith('.git/') or item == 'build' or
                            item.startswith('build/') or item in tracked or
                            any(path.startswith(item + '/') for path in tracked), 'RUNTIME_SOURCE_CHANGED')
            # Original verifier entry, using the freshly acquired interpreter.
            result = subprocess.run([str(self.workspace / '.venv/bin/python'), '-B',
                                     str(self.workspace / 'scripts/whisper_runtime_contract.py'), 'verify-runtime'],
                                    cwd=self.workspace, env=self.env, stdout=self.build_log,
                                    stderr=subprocess.STDOUT, check=False)
            require(result.returncode == 0, 'RUNTIME_VERIFY_FAILED')
        self.check_environment_proof()

    def checkpoint(self, event):
        require(len(self.events) < len(EVENTS) and event == EVENTS[len(self.events)], 'BUILD_PROTOCOL_INVALID')
        if self.fixture_checkpoint is not None:
            self.fixture_checkpoint(self, event)
        self.revalidate()
        current = execution_snapshot(self.workspace)
        if event.startswith('before:'):
            require(current == self.proof, 'ENVIRONMENT_CHANGED')
            if event != 'before:python':
                self.verify_environment()
        else:
            stage = event.split(':')[1]
            require(all(current.get(key) == value for key, value in self.proof.items()), 'ENVIRONMENT_CHANGED')
            require(all(key in self.proof or permitted_creation(key, stage) for key in current),
                    'BUILD_OUTPUT_UNEXPECTED')
            self.proof = current
            if stage == 'python':
                self.verify_environment()
            elif stage == 'runtime':
                self.verify_runtime()
            else:
                self.verify_environment()
                app = self.workspace / 'dist' / release_artifact.APP
                release_artifact.safe_app(app)
                release_artifact.validate_build_provenance(
                    self.workspace / 'dist' / (release_artifact.APP + '.provenance.json'),
                    app, self.source['source_commit'], repo_root=self.workspace)
        self.check_environment_proof()
        self.events.append(event)
        self.build_log.write(('checkpoint ' + event + ' verified\n').encode())
        self.build_log.flush()
        os.fsync(self.build_log.fileno())

    def controlled_build(self):
        # Requests, acknowledgements and parent lifetime are distinct pipes.
        request_read, request_write = os.pipe()
        ack_read, ack_write = os.pipe()
        life_read, life_write = os.pipe()
        descriptors = {request_read, request_write, ack_read, ack_write, life_read, life_write}
        process = None
        try:
            env = {**self.env, 'REL1C_EVENT_FD': str(request_write), 'REL1C_ACK_FD': str(ack_read),
                   'REL1C_LIFETIME_FD': str(life_read)}
            self.revalidate()
            self.check_environment_proof()
            process = subprocess.Popen(['/bin/bash', str(self.workspace / 'scripts/bootstrap_and_build.sh')],
                                       cwd=self.workspace, env=env, start_new_session=True,
                                       pass_fds=(request_write, ack_read, life_read),
                                       stdout=self.build_log, stderr=subprocess.STDOUT)
            for fd in (request_write, ack_read, life_read):
                os.close(fd)
                descriptors.remove(fd)
            buffer = b''
            deadline = time.monotonic() + 3600
            while True:
                require(time.monotonic() < deadline, 'BUILD_TIMEOUT')
                ready, _, _ = select.select([request_read], [], [], 0.1)
                if ready:
                    chunk = os.read(request_read, 128)
                    if not chunk:
                        require(not buffer and len(self.events) == len(EVENTS), 'BUILD_PROTOCOL_EOF')
                        break
                    buffer += chunk
                    require(len(buffer) <= 128, 'BUILD_PROTOCOL_INVALID')
                    while b'\n' in buffer:
                        raw, buffer = buffer.split(b'\n', 1)
                        require(raw in tuple(event.encode() for event in EVENTS), 'BUILD_PROTOCOL_INVALID')
                        self.checkpoint(raw.decode('ascii'))
                        os.write(ack_write, b'allow:' + raw + b'\n')
                if process.poll() is not None:
                    require(not buffer and len(self.events) == len(EVENTS), 'BUILD_OUTCOME_UNKNOWN')
                    break
            require(process.wait(timeout=10) == 0, 'BUILD_FAILED')
            self.revalidate()
            self.check_environment_proof()
        finally:
            # Close acknowledgements/lifetime first, then stop the entire session
            # on denial, EOF, malformed events, exceptions or parent interruption.
            for fd in descriptors:
                os.close(fd)
            if process is not None:
                # Darwin can return EPERM for a process group containing only
                # zombies. Poll/reap the owned leader before interpreting that
                # result, and always wait even when signaling races with exit.
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    except PermissionError:
                        if process.poll() is None:
                            process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        process.kill()
                    process.wait(timeout=2)
                # The group belongs solely to this uid/session and the reviewed
                # chain has no setuid transitions. EPERM after leader reaping is
                # Darwin's zombie-only group case; no live child remains there.
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(process.pid, signal.SIGKILL)

    def package(self, attempt):
        self.revalidate()
        self.check_environment_proof()
        self.verify_environment()
        app = self.workspace / 'dist' / release_artifact.APP
        manifest = build_release_zip.load_manifest(self.workspace / 'packaging/runtime_manifest.json')
        keywords = {} if self.fixture_verifier is None else {'verifier': self.fixture_verifier}
        with subprocess_environment(self.env):
            metadata = build_release_zip.create_release_zip(
                version='1.1.0', app_path=app,
                artifact_path=self.store.root / 'artifacts' / attempt / release_artifact.ASSET,
                extraction_dir=self.store.root / 'human' / attempt, task_root=self.store.root,
                build_provenance_path=self.workspace / 'dist' / (release_artifact.APP + '.provenance.json'),
                manifest=manifest, commit=self.source['source_commit'], repo_root=self.workspace, **keywords)
        metadata.extracted_app_path.parent.chmod(0o700)
        self.revalidate()
        self.check_environment_proof()
        return metadata

    def execute(self):
        self.revalidate()
        value = self.store.inspect()
        if value is None:
            value = self.store.create()
        # An explicit later build from REVIEW_REQUIRED authorizes a fresh retry.
        # Recorded success is never a license to overwrite or reuse old outputs.
        value = self.store.new_attempt(value)
        attempt = value['attempt']
        candidate = self.store.root / 'attempts' / attempt / 'source'
        require(not os.path.lexists(candidate), 'ATTEMPT_COLLISION')
        self.revalidate()
        release_integration.git(None, 'clone', '--no-local', '--no-hardlinks', '--no-checkout', '--no-tags',
                                '--template=', self.auth.payload['origin'], str(candidate))
        candidate.chmod(0o700)
        fsync_directory(candidate.parent)
        release_integration.audit_git(candidate, self.auth.payload['origin'])
        release_integration.git(candidate, 'checkout', '--detach', self.source['source_commit'])
        self.workspace = candidate
        self.revalidate()
        fresh_source(candidate)
        self.proof = execution_snapshot(candidate)
        self.env = self.environment()
        evidence = {}
        for kind in ('build', 'package'):
            self.revalidate()
            path = self.store.root / 'evidence' / attempt / (kind + '.log')
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as log:
                if kind == 'build':
                    self.build_log = log
                    self.controlled_build()
                    value = self.store.change(value, state='BUILT', intent=None)
                else:
                    value = self.store.change(value, state='PACKAGING', intent='PACKAGE')
                    # Helper stdout is package evidence, never parsed as authority.
                    with contextlib.redirect_stdout(__import__('io').TextIOWrapper(log, write_through=True)) as output:
                        try:
                            metadata = self.package(attempt)
                        finally:
                            output.flush()
                            output.detach()
                log.flush()
                os.fsync(log.fileno())
            evidence[kind] = {'path': str(path), 'sha256': digest(read_file(path, owner=os.getuid(),
                                                                         mode=0o600, limit=64*1024*1024))}
        self.revalidate()
        self.check_environment_proof()
        fixed = release_artifact.fix_metadata(metadata, auth=self.auth, source=self.source,
                                             receipt_sha256=self.source_hash, attempt=attempt,
                                             workspace=self.workspace, evidence=evidence)
        self.store.change(value, state='ARTIFACT', intent=None, artifact=fixed)
        return 'ARTIFACT_RECORDED_C1_ONLY'


def build(policy):
    return BuildController(policy).execute()


def resume(policy):
    auth = authorize_workflow(policy)
    release_artifact.verify_implementation(auth)
    value = release_workflow_state.StateStore(auth).inspect()
    require(value is not None, 'RECOVERY_PROOF_MISSING')
    # Never infer a successful process or recover invocation-local environment
    # trust from checksummed records, provenance or a surviving dist/App.
    if value['state'] in ('ARTIFACT', 'HUMAN_RECORDED') and value['intent'] is None:
        source, checksum = release_artifact.accepted_source(policy, auth)
        release_artifact.validate_artifact(value['artifact'], auth, source, checksum)
        return value['state'] + '_RECORDED_UNVERIFIED'
    # Reconciliation retires an unknown attempt without executing it or
    # promoting surviving dist/package bytes. Explicit build uses a new ID.
    if value['state'] in ('BUILDING', 'BUILT', 'PACKAGING'):
        release_artifact.accepted_source(policy, auth, remote=True)
        store = release_workflow_state.StateStore(auth)
        store.change(value, state='REVIEW_REQUIRED', intent=None, artifact=None, human_receipt=None)
        return 'RECOVERY_REVIEW_REQUIRED'
    raise Stop('RECOVERY_REVIEW_REQUIRED')


def human_gate(policy):
    auth = authorize_workflow(policy)
    release_artifact.verify_implementation(auth)
    store = release_workflow_state.StateStore(auth)
    value = store.inspect()
    require(value is not None and value['state'] in ('ARTIFACT', 'HUMAN_RECORDED'), 'ARTIFACT_MISSING')
    # Validate before recording intent, then again before/after the outcome.
    decision = release_human_gate.validate_human_gate(policy, auth, value['artifact'])
    if value['state'] == 'HUMAN_RECORDED':
        require(value['human_receipt'] == decision, 'RECEIPT_CHANGED')
        return 'HUMAN_RECORDED_C1_ONLY'
    require(value['intent'] is None, 'RECOVERY_REVIEW_REQUIRED')
    value = store.change(value, intent='HUMAN_CHECK')
    require(authorize_workflow(policy) == auth, 'APPROVAL_CHANGED')
    require(release_human_gate.validate_human_gate(policy, auth, value['artifact']) == decision, 'RECEIPT_CHANGED')
    value = store.change(value, state='HUMAN_RECORDED', intent=None, human_receipt=decision)
    require(release_human_gate.validate_human_gate(policy, auth, value['artifact']) == decision, 'RECEIPT_CHANGED')
    return 'HUMAN_RECORDED_C1_ONLY'


def _run(argv, policy):
    args = build_parser().parse_args(argv)
    try:
        stage = {'status': status, 'build': build, 'resume': resume, 'human-gate': human_gate}[args.command](policy)
        print('release-workflow: ' + stage)
        return 0
    except Stop as exc:
        print('release-workflow: STOP ' + exc.code, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('release-workflow: STOP INTERRUPTED', file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, subprocess.SubprocessError):
        print('release-workflow: STOP OPERATION_FAILED', file=sys.stderr)
        return 1


def main(argv=None):
    return _run(sys.argv[1:] if argv is None else argv, WorkflowPolicy())


if __name__ == '__main__':
    raise SystemExit(main())
