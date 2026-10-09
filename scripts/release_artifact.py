"""C1 signed source acceptance and retained artifact facts; hashes grant no approval."""
from __future__ import annotations

import hashlib
import os
import plistlib
import stat
import zipfile
from pathlib import PurePosixPath
from pathlib import Path

from release_approval import (
    Authorization, SHA, TOKEN, WORKFLOW_REQUIRED_TOOLS, WorkflowPolicy,
    absolute, authenticated_receipt, canonical, digest, fields, hex_value,
    inspect_path, read_file, require,
)
from release_integration import (
    audit_git, check_remote, check_source, clean, git, run_git, worktree_bytes,
)
from release_identity import app_tree_sha256, validate_build_provenance
from release_approval import LIGHTWEIGHT_PURPOSE, LIGHTWEIGHT_REQUIRED_TOOLS
from build_release_zip import BundleEntry, ReleaseMetadata, snapshot_bundle, validate_archive, verify_round_trip

APP = 'ClassroomTranscriber.app'
ASSET = 'ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip'
BUNDLE_ID = 'com.local.classroomtranscriber'
SOURCE_FIELDS = ('decision', 'source_repository', 'source_commit', 'source_tree', 'parents',
                 'baseline', 'main_ref', 'feature_ref', 'final_main', 'final_feature',
                 'evidence_sha256')
ARTIFACT_FIELDS = ('schema_version', 'artifact_id', 'attempt', 'repository', 'version',
                   'source_commit', 'source_tree', 'integration_receipt_sha256',
                   'accepted_commit', 'tools', 'contracts', 'zip_path', 'zip_bytes',
                   'zip_sha256', 'extraction_path', 'app_name', 'bundle_identifier',
                   'short_version', 'bundle_version', 'app_tree_sha256', 'evidence')


def verify_implementation(auth: Authorization):
    check_source(auth)
    worktree_bytes(auth.implementation)
    verify_tools(auth.implementation, auth)


def verify_tools(repo: Path, auth: Authorization, revision=None):
    required = (LIGHTWEIGHT_REQUIRED_TOOLS if auth.payload.get('purpose') == LIGHTWEIGHT_PURPOSE
                else WORKFLOW_REQUIRED_TOOLS)
    for relative in required:
        if revision is None:
            data = read_file(repo / relative)
        else:
            entry = git(repo, 'ls-tree', revision, '--', relative)
            require(entry.startswith(('100644 blob ', '100755 blob ')), 'TOOL_CHANGED')
            data = run_git(repo, 'cat-file', 'blob', revision + ':' + relative).stdout
        require(digest(data) == auth.payload['tools'][relative], 'TOOL_CHANGED')


def accepted_source(policy: WorkflowPolicy, auth: Authorization, *, remote=False):
    """Independent signature plus actual Git objects/bytes, never journal COMPLETE.

    Remote refs are checked only for a requested mutating stage. Local status
    does not call this validator or consult a Human decision.
    """
    value, checksum = authenticated_receipt(policy, auth, 'integration', SOURCE_FIELDS)
    require(type(value['decision']) is str and value['decision'] == 'ACCEPT', 'SOURCE_NOT_ACCEPTED')
    p = auth.payload
    repo = absolute(value['source_repository'])
    require(repo == auth.managed / 'clone', 'SOURCE_RECEIPT_BINDING')
    for key in ('source_commit', 'source_tree', 'baseline', 'final_main', 'final_feature'):
        hex_value(value[key], SHA)
    require(type(value['parents']) is list and value['parents'] ==
            [p['main'], p['accepted_commit']] and value['baseline'] == p['baseline'] and
            value['main_ref'] == p['main_ref'] and value['feature_ref'] == p['feature_ref'] and
            value['final_main'] == value['source_commit'] and
            value['final_feature'] == p['accepted_commit'], 'SOURCE_RECEIPT_BINDING')
    hex_value(value['evidence_sha256'])
    evidence = policy.trust_file('integration-evidence.json')
    require(digest(evidence) == value['evidence_sha256'] and evidence.strip(), 'EVIDENCE_INVALID')
    verify_implementation(auth)
    audit_git(repo, p['origin'])
    clean(repo)
    source = value['source_commit']
    for revision in (source, *value['parents'], value['baseline']):
        require(git(repo, 'cat-file', '-t', revision) == 'commit', 'GIT_OBJECT_INVALID')
    require(git(repo, 'cat-file', '-t', value['source_tree']) == 'tree' and
            git(repo, 'rev-parse', 'HEAD') == source and
            git(repo, 'rev-parse', source + '^{tree}') == value['source_tree'] and
            git(repo, 'show', '-s', '--format=%P', source).split() == value['parents'], 'SOURCE_RECEIPT_FACTS')
    require(git(repo, 'merge-base', '--all', *value['parents']) == value['baseline'], 'ANCESTRY_INVALID')
    for parent in value['parents']:
        require(run_git(repo, 'merge-base', '--is-ancestor', parent, source,
                        allow_failure=True).returncode == 0, 'ANCESTRY_INVALID')
    verify_tools(repo, auth, p['accepted_commit'])
    verify_tools(repo, auth, source)
    verify_tools(repo, auth)
    worktree_bytes(repo)
    if remote:
        actual = check_remote(policy, auth)
        require(actual[p['main_ref']] == source and
                actual[p['feature_ref']] == p['accepted_commit'], 'REMOTE_DRIFT')
    return value, checksum


def file_hash(path: Path):
    inspect_path(path, owner=os.getuid())
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        checksum = hashlib.file_digest(handle, 'sha256').hexdigest()
        after = os.fstat(handle.fileno())
    identity = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_nlink,
                             info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    require(identity(before) == identity(after) == identity(path.lstat()), 'ARTIFACT_CHANGED')
    return before.st_size, checksum


def safe_app(path: Path):
    inspect_path(path, owner=os.getuid(), directory=True)
    for item in path.rglob('*'):
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode):
            inspect_path(item.parent, owner=os.getuid(), directory=True)
            target = item.resolve(strict=True)
            require(target.is_relative_to(path), 'ARTIFACT_PATH')
            inspect_path(target, owner=os.getuid(), directory=target.is_dir())
        else:
            inspect_path(item, owner=os.getuid(), directory=stat.S_ISDIR(info.st_mode))
    # The accepted ZIP snapshot also rejects prohibited payload/model paths and
    # escaping/broken symlinks. No executable in the bundle is run here.
    snapshot_bundle(path)
    info = plistlib.loads(read_file(path / 'Contents/Info.plist'))
    require(type(info) is dict and info.get('CFBundleIdentifier') == BUNDLE_ID and
            info.get('CFBundleShortVersionString') == '1.1.0' and
            info.get('CFBundleVersion') == '1.1.0', 'ARTIFACT_APP_IDENTITY')
    return app_tree_sha256(path)


def verify_zip_app(archive: Path, app: Path):
    """Compare actual ZIP members with REL1A's retained bundle definition.

    No extraction, scratch writes or executable invocation. CRC/hash alone and
    a separately hashed App do not prove correspondence. Reject aliases and
    duplicates before comparing bytes, types, permissions and link targets.
    """
    expected = snapshot_bundle(app)
    actual = {}
    validate_archive(archive, APP)
    with zipfile.ZipFile(archive) as opened:
        seen = set()
        root_seen = False
        for info in opened.infolist():
            name = info.filename
            path = PurePosixPath(name)
            require(name == path.as_posix() + ('/' if info.is_dir() else '') and
                    path not in seen and not info.flag_bits & 1 and
                    info.create_system == 3, 'ZIP_APP_MISMATCH')
            seen.add(path)
            mode = info.external_attr >> 16
            if path == PurePosixPath(APP):
                require(info.is_dir() and stat.S_ISDIR(mode) and info.file_size == 0 and
                        stat.S_IMODE(mode) == stat.S_IMODE(app.lstat().st_mode), 'ZIP_APP_MISMATCH')
                root_seen = True
                continue
            relative = PurePosixPath(*path.parts[1:])
            require(relative in expected, 'ZIP_APP_MISMATCH')
            if stat.S_ISDIR(mode):
                require(info.is_dir() and info.file_size == 0, 'ZIP_APP_MISMATCH')
                entry = BundleEntry('directory', stat.S_IMODE(mode))
            elif stat.S_ISLNK(mode):
                require(not info.is_dir() and info.file_size <= 4096, 'ZIP_APP_MISMATCH')
                entry = BundleEntry('symlink', stat.S_IMODE(mode),
                                    link_target=opened.read(info).decode('utf-8'))
            else:
                require(stat.S_ISREG(mode) and not info.is_dir(), 'ZIP_APP_MISMATCH')
                require(info.file_size == expected[relative].size, 'ZIP_APP_MISMATCH')
                with opened.open(info) as member:
                    checksum = hashlib.file_digest(member, 'sha256').hexdigest()
                entry = BundleEntry('file', stat.S_IMODE(mode), info.file_size, checksum)
            actual[relative] = entry
        require(root_seen and actual == expected, 'ZIP_APP_MISMATCH')
    require(snapshot_bundle(app) == expected, 'ARTIFACT_CHANGED')


def artifact_checksum(value):
    return digest(canonical({key: item for key, item in value.items() if key != 'artifact_id'}))


def artifact_schema(value, auth: Authorization):
    fields(value, ARTIFACT_FIELDS)
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            type(value['zip_bytes']) is int and value['zip_bytes'] > 0 and
            type(value['attempt']) is str and TOKEN.fullmatch(value['attempt']), 'ARTIFACT_SCHEMA')
    for key in ('source_commit', 'source_tree', 'accepted_commit'):
        hex_value(value[key], SHA)
    for key in ('artifact_id', 'integration_receipt_sha256', 'zip_sha256', 'app_tree_sha256'):
        hex_value(value[key])
    expected = {'repository': auth.payload['repository'], 'version': '1.1.0',
                'accepted_commit': auth.payload['accepted_commit'], 'tools': auth.payload['tools'],
                'contracts': auth.payload['contracts'], 'app_name': APP,
                'bundle_identifier': BUNDLE_ID, 'short_version': '1.1.0', 'bundle_version': '1.1.0'}
    require(all(value[key] == item for key, item in expected.items()), 'ARTIFACT_BINDING')
    root = absolute(auth.payload['workflow'])
    attempt = value['attempt']
    require(absolute(value['zip_path']) == root / 'artifacts' / attempt / ASSET and
            absolute(value['extraction_path']) == root / 'human' / attempt, 'ARTIFACT_PATH')
    fields(value['evidence'], ('build', 'package'))
    for key, item in value['evidence'].items():
        fields(item, ('path', 'sha256'))
        hex_value(item['sha256'])
        require(absolute(item['path']) == root / 'evidence' / attempt / (key + '.log'), 'ARTIFACT_PATH')
    require(value['artifact_id'] == artifact_checksum(value), 'ARTIFACT_CHECKSUM')
    return value


def validate_artifact(value, auth: Authorization, source, receipt_sha256):
    artifact_schema(value, auth)
    require(value['source_commit'] == source['source_commit'] and
            value['source_tree'] == source['source_tree'] and
            value['integration_receipt_sha256'] == receipt_sha256, 'ARTIFACT_SOURCE')
    root = absolute(auth.payload['workflow'])
    for name in ('artifacts', 'human', 'evidence'):
        inspect_path(root / name, owner=os.getuid(), mode=0o700, directory=True)
        inspect_path(root / name / value['attempt'], owner=os.getuid(), mode=0o700, directory=True)
    archive = absolute(value['zip_path'])
    require(file_hash(archive) == (value['zip_bytes'], value['zip_sha256']), 'ARTIFACT_CHANGED')
    validate_archive(archive, APP)
    extraction = absolute(value['extraction_path'])
    require(sorted(item.name for item in extraction.iterdir()) == [APP], 'ARTIFACT_PATH')
    require(safe_app(extraction / APP) == value['app_tree_sha256'], 'ARTIFACT_CHANGED')
    verify_zip_app(archive, extraction / APP)
    require(file_hash(archive) == (value['zip_bytes'], value['zip_sha256']), 'ARTIFACT_CHANGED')
    for item in value['evidence'].values():
        raw = read_file(absolute(item['path']), owner=os.getuid(), mode=0o600, limit=64 * 1024 * 1024)
        require(digest(raw) == item['sha256'], 'ARTIFACT_EVIDENCE_CHANGED')
    return value


def fix_metadata(metadata: ReleaseMetadata, *, auth: Authorization, source,
                 receipt_sha256: str, attempt: str, workspace: Path, evidence: dict):
    """Consume the accepted ZIP helper's machine result, never printed prose.

    This fixes package facts only. It cannot establish a fresh build or Owner
    approval; the pending orchestrator must additionally supply a live build
    proof before persisting a production ARTIFACT outcome.
    """
    require(type(metadata) is ReleaseMetadata and type(attempt) is str and
            TOKEN.fullmatch(attempt), 'ARTIFACT_SCHEMA')
    root = absolute(auth.payload['workflow'])
    require(workspace == root / 'attempts' / attempt / 'source', 'ARTIFACT_PATH')
    inspect_path(workspace, owner=os.getuid(), mode=0o700, directory=True)
    audit_git(workspace, auth.payload['origin'])
    clean(workspace)
    verify_tools(workspace, auth)
    worktree_bytes(workspace)
    require(git(workspace, 'rev-parse', 'HEAD') == source['source_commit'], 'ARTIFACT_SOURCE')
    app = workspace / 'dist' / APP
    safe_app(app)
    provenance = workspace / 'dist' / (APP + '.provenance.json')
    inspect_path(provenance, owner=os.getuid())
    validate_build_provenance(provenance, app, source['source_commit'], repo_root=workspace)
    require(metadata.version == '1.1.0' and metadata.source_commit == source['source_commit'] and
            metadata.artifact_path == root / 'artifacts' / attempt / ASSET and
            metadata.extracted_app_path == root / 'human' / attempt / APP, 'ARTIFACT_BINDING')
    verify_round_trip(snapshot_bundle(app), metadata.extracted_app_path)
    value = {'schema_version': 1, 'attempt': attempt, 'repository': auth.payload['repository'],
             'version': '1.1.0', 'source_commit': source['source_commit'],
             'source_tree': source['source_tree'], 'integration_receipt_sha256': receipt_sha256,
             'accepted_commit': auth.payload['accepted_commit'], 'tools': auth.payload['tools'],
             'contracts': auth.payload['contracts'], 'zip_path': str(metadata.artifact_path),
             'zip_bytes': metadata.artifact_bytes, 'zip_sha256': metadata.sha256,
             'extraction_path': str(metadata.extracted_app_path.parent), 'app_name': APP,
             'bundle_identifier': BUNDLE_ID, 'short_version': '1.1.0', 'bundle_version': '1.1.0',
             'app_tree_sha256': app_tree_sha256(metadata.extracted_app_path), 'evidence': evidence}
    value['artifact_id'] = artifact_checksum(value)
    return validate_artifact(value, auth, source, receipt_sha256)
