"""REL1B independent authorization. No CLI or environment trust overrides."""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

TRUST_ROOT = Path('/Library/Application Support/ClassroomTranscriberRelease/1.1.0')
REPOSITORY = 'smter6626/live_subtitle_generator'
ORIGINS = ('git@github.com:smter6626/live_subtitle_generator.git',
           'https://github.com/smter6626/live_subtitle_generator.git')
MAIN = 'refs/heads/main'
FEATURE = 'refs/heads/codex/release-1-1-0-automation'
SIGNER = 'classroom-transcriber-release-owner'
NAMESPACE = 'classroom-transcriber-release-1.1.0-production'
CONTROL_TOOLS = tuple('scripts/' + name + '.py' for name in (
    'release_controller', 'release_approval', 'release_journal', 'release_integration'))
# This is a code-defined minimum, never an approval-selected subset.
REQUIRED_TOOLS = CONTROL_TOOLS + (
    'scripts/release_identity.py', 'scripts/build_release_zip.py',
    'scripts/build_macos.sh', 'scripts/build_app_icon.py', 'scripts/package_runtime.py',
    'scripts/verify_packaged_runtime.py', 'scripts/bootstrap_python_env.sh',
    'scripts/bootstrap_and_build.sh', 'scripts/bootstrap_whisper_runtime.sh',
    'scripts/whisper_runtime_contract.py', 'packaging/ClassroomTranscriber.spec',
    'packaging/runtime_manifest.json', 'packaging/release_contract.json',
    '.python-version', 'pyproject.toml', 'uv.lock', 'testCodes/test_python_environment.py',
)
WORKLOAD = Path('/Users/smterpro/Workspace/framework-loop/1PCloop/workloads/whisper_release_1_1_0_v1')
CONTRACTS = {'parent': WORKLOAD / 'workload_static.md', 'rel1b': WORKLOAD / 'rel1b_static.md'}
SHA = re.compile(r'[0-9a-f]{40}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')
TOKEN = re.compile(r'[a-zA-Z0-9_-]{1,80}\Z')


class Stop(RuntimeError):
    """Only fixed codes reach the terminal; never exception/JSON/subprocess text."""
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def require(condition: bool, code: str = 'INPUT_INVALID') -> None:
    if not condition:
        raise Stop(code)


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True) + '\n').encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fields(value, names) -> None:
    require(type(value) is dict and set(value) == set(names), 'SCHEMA_INVALID')


def hex_value(value, pattern=HASH) -> None:
    require(type(value) is str and pattern.fullmatch(value) is not None, 'SCHEMA_INVALID')


def decode(data: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, 'SCHEMA_DUPLICATE')
            result[key] = value
        return result
    try:
        value = json.loads(data, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(Stop('SCHEMA_INVALID')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise Stop('SCHEMA_INVALID') from exc
    return value


def absolute(value) -> Path:
    require(type(value) is str and '\x00' not in value, 'PATH_INVALID')
    path = Path(value)
    require(path.is_absolute() and str(path) == value and '..' not in path.parts, 'PATH_INVALID')
    return path


def inspect_path(path: Path, *, owner: int | None = None, mode: int | None = None,
                 directory: bool = False, missing: bool = False, protected: bool = False) -> bool:
    """No symlink ancestors, unsafe owners/modes or regular-file hard links.

    Parent directories may belong to root or the real uid. A protected tree must
    belong to root all the way up and be unwritable by the executing identity.
    Single writer is assumed; O_NOFOLLOW/fstat also protect leaf opens.
    """
    absolute(str(path))
    uid = os.getuid()
    for item in (*reversed(path.parents), path):
        try:
            info = item.lstat()
        except FileNotFoundError:
            require(missing and item == path, 'PATH_MISSING')
            return False
        leaf = item == path
        require(not stat.S_ISLNK(info.st_mode), 'PATH_SYMLINK')
        require(info.st_uid in ((0,) if protected else (0, uid)), 'PATH_OWNER')
        require(not info.st_mode & 0o022, 'PATH_MODE')
        if not leaf or directory:
            require(stat.S_ISDIR(info.st_mode), 'PATH_TYPE')
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'PATH_TYPE')
        if protected:
            require(not os.access(item, os.W_OK), 'TRUST_WRITABLE')
        if leaf:
            require(owner is None or info.st_uid == owner, 'PATH_OWNER')
            require(mode is None or stat.S_IMODE(info.st_mode) == mode, 'PATH_MODE')
    return True


def read_file(path: Path, *, owner=None, mode=None, protected=False, limit=4 * 1024 * 1024) -> bytes:
    inspect_path(path, owner=owner, mode=mode, protected=protected)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit, 'PATH_TYPE')
        require(owner is None or info.st_uid == owner, 'PATH_OWNER')
        require(mode is None or stat.S_IMODE(info.st_mode) == mode, 'PATH_MODE')
        return handle.read(limit + 1)


def downloads() -> Path:
    # Not HOME, TMPDIR, journal, argv or Path.home().
    path = Path(pwd.getpwuid(os.getuid()).pw_dir) / 'Downloads'
    inspect_path(path, owner=os.getuid(), directory=True)
    return path


@dataclass(frozen=True)
class Policy:
    """Fixture policy is a Python test seam, absent from production argparse.

    A fixture cannot address network remotes, production namespaces, deployment
    files, or any path outside a newly named disposable Downloads fixture root.
    """
    fixture_root: Path | None = None

    @property
    def root(self):
        return TRUST_ROOT if self.fixture_root is None else self.fixture_root / 'trust'

    @property
    def namespace(self):
        return NAMESPACE if self.fixture_root is None else 'classroom-transcriber-rel1b-fixture'

    @property
    def signer(self):
        return SIGNER if self.fixture_root is None else 'rel1b-fixture-owner'

    @property
    def contracts(self):
        if self.fixture_root is None:
            return CONTRACTS
        return {key: self.fixture_root / (key + '.md') for key in CONTRACTS}

    def check_fixture(self):
        if self.fixture_root is not None:
            path = self.fixture_root
            require(path.name.startswith('case-') and path.parent.name.startswith('rel1b-fixtures.'), 'FIXTURE_BOUNDARY')
            require(path.is_relative_to(downloads()), 'FIXTURE_BOUNDARY')
            inspect_path(path, owner=os.getuid(), mode=0o700, directory=True)
            inspect_path(path.parent, owner=os.getuid(), mode=0o700, directory=True)

    def trust_file(self, name):
        protected = self.fixture_root is None
        return read_file(self.root / name, owner=0 if protected else os.getuid(),
                         mode=0o644 if protected else 0o600, protected=protected)


@dataclass(frozen=True)
class Authorization:
    payload: dict
    sha256: str
    trust_sha256: str

    @property
    def implementation(self):
        return Path(self.payload['implementation'])

    @property
    def managed(self):
        return Path(self.payload['managed'])


def validate_payload(value, policy: Policy, config: dict, config_bytes: bytes, signers: bytes):
    fields(value, ('schema_version', 'id', 'policy', 'config_epoch', 'config_sha256',
                   'signers_sha256', 'accepted_commit', 'tools', 'contracts', 'review',
                   'human', 'repository', 'origin', 'main_ref', 'feature_ref', 'main',
                   'feature_prior', 'baseline', 'implementation', 'managed', 'uid'))
    require(type(value['schema_version']) is int and value['schema_version'] == 1, 'SCHEMA_INVALID')
    require(type(value['uid']) is int and value['uid'] == os.getuid(), 'APPROVAL_IDENTITY')
    require(type(value['config_epoch']) is int and value['config_epoch'] == config['epoch'], 'TRUST_CHANGED')
    require(type(value['id']) is str and TOKEN.fullmatch(value['id']) is not None, 'SCHEMA_INVALID')
    require(value['policy'] == policy.namespace, 'APPROVAL_POLICY')
    require(value['config_sha256'] == digest(config_bytes) and value['signers_sha256'] == digest(signers), 'TRUST_CHANGED')
    for name in ('accepted_commit', 'main', 'baseline'):
        hex_value(value[name], SHA)
    if value['feature_prior'] is not None:
        hex_value(value['feature_prior'], SHA)
    require(value['main_ref'] == MAIN and value['feature_ref'] == FEATURE and value['repository'] == REPOSITORY, 'APPROVAL_IDENTITY')
    require(type(value['origin']) is str, 'SCHEMA_INVALID')
    if policy.fixture_root is None:
        require(value['origin'] in ORIGINS, 'ORIGIN_INVALID')
    else:
        require(value['origin'] == str(policy.fixture_root / 'remote.git'), 'FIXTURE_BOUNDARY')
    fields(value['tools'], REQUIRED_TOOLS)
    for hash_value in value['tools'].values():
        hex_value(hash_value)
    require(all(value['tools'][key] == config['entry_sha256'][key] for key in CONTROL_TOOLS), 'ENTRY_INVALID')
    fields(value['contracts'], policy.contracts)
    for key, path in policy.contracts.items():
        require(value['contracts'][key] == digest(read_file(path)), 'CONTRACT_CHANGED')
    for kind in ('review', 'human'):
        fields(value[kind], ('locator', 'sha256'))
        require(value[kind]['locator'] == str(policy.root / (kind + '.json')) and
                value[kind]['sha256'] == config[kind + '_sha256'], 'EVIDENCE_INVALID')
        evidence_bytes = policy.trust_file(kind + '.json')
        require(digest(evidence_bytes) == config[kind + '_sha256'], 'EVIDENCE_INVALID')
        evidence = decode(evidence_bytes)
        fields(evidence, ('schema_version', 'accepted_commit', 'scope', 'reference'))
        require(type(evidence['schema_version']) is int and evidence['schema_version'] == 1 and
                evidence['accepted_commit'] == value['accepted_commit'] and
                evidence['scope'] == ('step1-final-independent-review' if kind == 'review' else 'step1-final-owner-integration') and
                type(evidence['reference']) is str and TOKEN.fullmatch(evidence['reference']) is not None, 'EVIDENCE_INVALID')
    implementation = absolute(value['implementation'])
    managed = absolute(value['managed'])
    require(managed.is_relative_to(downloads()) and managed != downloads() and
            not managed.is_relative_to(implementation) and not implementation.is_relative_to(managed), 'MANAGED_BOUNDARY')
    inspect_path(implementation, owner=os.getuid(), directory=True)
    inspect_path(managed.parent, owner=os.getuid(), directory=True)
    if policy.fixture_root is not None:
        require(implementation == policy.fixture_root / 'source' and managed == policy.fixture_root / 'managed', 'FIXTURE_BOUNDARY')
    return value


def authorize(policy: Policy, *, entry: bool = True) -> Authorization:
    policy.check_fixture()
    try:
        inspect_path(policy.root, owner=0 if policy.fixture_root is None else os.getuid(),
                     mode=0o755 if policy.fixture_root is None else 0o700,
                     directory=True, protected=policy.fixture_root is None)
    except (OSError, Stop) as exc:
        raise Stop('TRUST_UNAVAILABLE') from exc
    config_bytes = policy.trust_file('config.json')
    config = decode(config_bytes)
    fields(config, ('schema_version', 'epoch', 'entry_sha256', 'review_sha256', 'human_sha256'))
    require(type(config['schema_version']) is int and config['schema_version'] == 1 and
            type(config['epoch']) is int and config['epoch'] > 0, 'SCHEMA_INVALID')
    fields(config['entry_sha256'], CONTROL_TOOLS)
    for item in (*config['entry_sha256'].values(), config['review_sha256'], config['human_sha256']):
        hex_value(item)
    if policy.fixture_root is None and entry:
        entry_root = policy.root / 'entry'
        for relative in CONTROL_TOOLS:
            path = entry_root / relative
            require(config['entry_sha256'][relative] == digest(read_file(path, owner=0, mode=0o644, protected=True)), 'ENTRY_INVALID')
        require(Path(__file__) == entry_root / 'scripts/release_approval.py', 'ENTRY_INVALID')
        # All control modules must already be loaded from the protected entry.
        import sys
        for relative in CONTROL_TOOLS:
            module_name = Path(relative).stem
            module = sys.modules.get(module_name)
            if module_name == 'release_controller':
                module = module or sys.modules.get('__main__')
            require(module is not None and Path(module.__file__) == entry_root / relative, 'ENTRY_INVALID')
    signers = policy.trust_file('allowed_signers')
    raw = policy.trust_file('approval.json')
    signature = policy.root / 'approval.json.sig'
    policy.trust_file('approval.json.sig')
    result = subprocess.run(['/usr/bin/ssh-keygen', '-Y', 'verify', '-f', str(policy.root / 'allowed_signers'),
                             '-I', policy.signer, '-n', policy.namespace, '-s', str(signature)],
                            input=raw, capture_output=True, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, check=False)
    require(result.returncode == 0, 'SIGNATURE_INVALID')
    value = validate_payload(decode(raw), policy, config, config_bytes, signers)
    revoked = decode(policy.trust_file('revoked.json'))
    fields(revoked, ('schema_version', 'ids'))
    require(type(revoked['schema_version']) is int and revoked['schema_version'] == 1 and type(revoked['ids']) is list, 'SCHEMA_INVALID')
    require(all(type(item) is str and TOKEN.fullmatch(item) is not None for item in revoked['ids']) and
            len(set(revoked['ids'])) == len(revoked['ids']), 'SCHEMA_INVALID')
    require(value['id'] not in revoked['ids'], 'APPROVAL_REVOKED')
    return Authorization(value, digest(raw), digest(config_bytes + signers + policy.trust_file('revoked.json')))


# C1 has its own fixed scope/configuration. The REL1B entry and default minimum
# above deliberately remain unchanged: a signed payload cannot choose a scope.
WORKFLOW_HELPERS = ('scripts/release_identity.py', 'scripts/build_release_zip.py',
                    'scripts/verify_packaged_runtime.py', 'model_integrity.py', 'resource_paths.py')
WORKFLOW_DATA = ('packaging/model_manifest.json',)
WORKFLOW_CONTROL_TOOLS = CONTROL_TOOLS + WORKFLOW_HELPERS + tuple('scripts/' + name + '.py' for name in (
    'release_workflow', 'release_workflow_state', 'release_artifact', 'release_human_gate'))
WORKFLOW_REQUIRED_TOOLS = REQUIRED_TOOLS + tuple(
    item for item in WORKFLOW_CONTROL_TOOLS if item not in REQUIRED_TOOLS
) + ('RELEASE_NOTES_1.1.0.md',) + tuple(
    item for item in (*WORKFLOW_HELPERS, *WORKFLOW_DATA) if item not in REQUIRED_TOOLS
)
WORKFLOW_CONTRACTS = {**CONTRACTS, 'rel1c': WORKLOAD / 'rel1c_static.md'}
WORKFLOW_PURPOSE = 'release-workflow-control'
RECEIPT_PURPOSES = {
    'integration': 'independent-final-main-source',
    'artifact-human': 'owner-exact-artifact-decision',
}


@dataclass(frozen=True)
class WorkflowPolicy(Policy):
    @property
    def namespace(self):
        return NAMESPACE if self.fixture_root is None else 'classroom-transcriber-rel1c1-fixture'

    @property
    def signer(self):
        return SIGNER if self.fixture_root is None else 'rel1c1-fixture-owner'

    @property
    def contracts(self):
        if self.fixture_root is None:
            return WORKFLOW_CONTRACTS
        return {key: self.fixture_root / (key + '.md') for key in WORKFLOW_CONTRACTS}

    def check_fixture(self):
        if self.fixture_root is not None:
            path = self.fixture_root
            require(path.name.startswith('case-') and
                    path.parent.name.startswith('rel1c1-fixtures.') and
                    path.is_relative_to(downloads()), 'FIXTURE_BOUNDARY')
            inspect_path(path, owner=os.getuid(), mode=0o700, directory=True)
            inspect_path(path.parent, owner=os.getuid(), mode=0o700, directory=True)


def _workflow_trust(policy: WorkflowPolicy):
    require(type(policy) is WorkflowPolicy, 'APPROVAL_POLICY')
    policy.check_fixture()
    try:
        inspect_path(policy.root, owner=0 if policy.fixture_root is None else os.getuid(),
                     mode=0o755 if policy.fixture_root is None else 0o700,
                     directory=True, protected=policy.fixture_root is None)
    except (OSError, Stop) as exc:
        raise Stop('TRUST_UNAVAILABLE') from exc
    raw = policy.trust_file('workflow-config.json')
    config = decode(raw)
    fields(config, ('schema_version', 'epoch', 'entry_sha256', 'review_sha256', 'human_sha256'))
    require(type(config['schema_version']) is int and config['schema_version'] == 1 and
            type(config['epoch']) is int and config['epoch'] > 0, 'SCHEMA_INVALID')
    fields(config['entry_sha256'], WORKFLOW_CONTROL_TOOLS)
    for value in (*config['entry_sha256'].values(), config['review_sha256'], config['human_sha256']):
        hex_value(value)
    signers = policy.trust_file('allowed_signers')
    revoked_raw = policy.trust_file('revoked.json')
    revoked = decode(revoked_raw)
    fields(revoked, ('schema_version', 'ids'))
    require(type(revoked['schema_version']) is int and revoked['schema_version'] == 1 and
            type(revoked['ids']) is list and
            all(type(item) is str and TOKEN.fullmatch(item) for item in revoked['ids']) and
            len(set(revoked['ids'])) == len(revoked['ids']), 'SCHEMA_INVALID')
    return raw, config, signers, revoked_raw, revoked['ids']


def _verify_workflow_signature(policy: WorkflowPolicy, name: str, namespace: str) -> bytes:
    # All names and namespaces come from this module, never argv or the payload.
    raw = policy.trust_file(name + '.json')
    policy.trust_file(name + '.json.sig')
    result = subprocess.run(
        ['/usr/bin/ssh-keygen', '-Y', 'verify', '-f', str(policy.root / 'allowed_signers'),
         '-I', policy.signer, '-n', namespace, '-s', str(policy.root / (name + '.json.sig'))],
        input=raw, capture_output=True, env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}, check=False)
    require(result.returncode == 0, 'SIGNATURE_INVALID')
    return raw


def _workflow_entry(policy: WorkflowPolicy, config):
    if policy.fixture_root is not None:
        return
    import sys
    root = policy.root / 'entry'
    for relative in WORKFLOW_CONTROL_TOOLS:
        path = root / relative
        require(digest(read_file(path, owner=0, mode=0o644, protected=True)) ==
                config['entry_sha256'][relative], 'ENTRY_INVALID')
        name = Path(relative).stem
        module = sys.modules.get(name)
        if name == 'release_workflow':
            module = module or sys.modules.get('__main__')
        require(module is not None and Path(module.__file__) == path, 'ENTRY_INVALID')
    require(Path(__file__) == root / 'scripts/release_approval.py', 'ENTRY_INVALID')


def authorize_workflow(policy: WorkflowPolicy) -> Authorization:
    config_raw, config, signers, revoked_raw, revoked = _workflow_trust(policy)
    _workflow_entry(policy, config)
    raw = _verify_workflow_signature(policy, 'workflow-approval', policy.namespace)
    value = decode(raw)
    require(type(value) is dict and value.get('purpose') == WORKFLOW_PURPOSE, 'APPROVAL_SCOPE')
    require('workflow' in value and 'tools' in value, 'SCHEMA_INVALID')
    fields(value['tools'], WORKFLOW_REQUIRED_TOOLS)
    for checksum in value['tools'].values():
        hex_value(checksum)
    require(all(value['tools'][key] == config['entry_sha256'][key]
                for key in WORKFLOW_CONTROL_TOOLS), 'ENTRY_INVALID')
    if policy.fixture_root is None:
        for relative in (*WORKFLOW_DATA, 'packaging/runtime_manifest.json', 'packaging/release_contract.json'):
            require(digest(read_file(policy.root / 'entry' / relative, owner=0,
                                     mode=0o644, protected=True)) == value['tools'][relative], 'ENTRY_INVALID')
    # Reuse the accepted common approval/evidence validator. Project only the
    # code-defined legacy minimum; this does not alter or weaken its default.
    common = {key: item for key, item in value.items() if key not in ('purpose', 'workflow')}
    common['tools'] = {key: value['tools'][key] for key in REQUIRED_TOOLS}
    validate_payload(common, policy, config, config_raw, signers)
    root = absolute(value['workflow'])
    legacy = absolute(value['managed'])
    implementation = absolute(value['implementation'])
    require(root.is_relative_to(downloads()) and root != downloads() and
            all(root != other and not root.is_relative_to(other) and
                not other.is_relative_to(root) for other in (legacy, implementation)), 'WORKFLOW_BOUNDARY')
    inspect_path(root.parent, owner=os.getuid(), directory=True)
    if policy.fixture_root is not None:
        require(root == policy.fixture_root / 'workflow', 'FIXTURE_BOUNDARY')
    require(value['id'] not in revoked, 'APPROVAL_REVOKED')
    return Authorization(value, digest(raw), digest(config_raw + signers + revoked_raw))


def authenticated_receipt(policy: WorkflowPolicy, auth: Authorization, kind: str, names):
    """Read a separately signed, purpose-specific external decision; never sign it."""
    require(kind in RECEIPT_PURPOSES, 'RECEIPT_PURPOSE')
    require(authorize_workflow(policy) == auth, 'APPROVAL_CHANGED')
    config_raw, config, signers, _, revoked = _workflow_trust(policy)
    raw = _verify_workflow_signature(policy, kind, policy.namespace + '-' + kind)
    value = decode(raw)
    common = ('schema_version', 'id', 'purpose', 'policy', 'config_epoch', 'config_sha256',
              'signers_sha256', 'trust_sha256', 'authorization_sha256', 'repository',
              'version', 'accepted_commit', 'tools', 'contracts', 'decision_reference')
    fields(value, (*common, *names))
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            type(value['config_epoch']) is int and value['config_epoch'] == config['epoch'], 'SCHEMA_INVALID')
    for key in ('id', 'decision_reference'):
        require(type(value[key]) is str and TOKEN.fullmatch(value[key]), 'SCHEMA_INVALID')
    require(value['id'] not in revoked, 'RECEIPT_REVOKED')
    expected = {
        'purpose': RECEIPT_PURPOSES[kind], 'policy': policy.namespace,
        'config_sha256': digest(config_raw), 'signers_sha256': digest(signers),
        'trust_sha256': auth.trust_sha256, 'authorization_sha256': auth.sha256,
        'repository': REPOSITORY, 'version': '1.1.0',
        'accepted_commit': auth.payload['accepted_commit'],
        'tools': auth.payload['tools'], 'contracts': auth.payload['contracts'],
    }
    require(all(value[key] == item for key, item in expected.items()), 'RECEIPT_BINDING')
    require(raw == canonical(value), 'SCHEMA_INVALID')
    return value, digest(raw)
