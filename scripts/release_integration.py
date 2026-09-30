"""Fixed Git integration and live bootstrap/strict gate; no build/publication."""
from __future__ import annotations

import hashlib
import os
import pwd
import stat
import subprocess
import uuid
from pathlib import Path

from release_approval import (Authorization, FEATURE, MAIN, ORIGINS, REQUIRED_TOOLS, Policy,
                              SHA, Stop, authorize, decode, digest, hex_value,
                              inspect_path, read_file, require)
from release_journal import Journal, fsync_directory

GIT = '/usr/bin/git'
MESSAGE = 'Integrate independently accepted Classroom Transcriber release implementation'
IDENTITY = 'Classroom Release Controller <release-controller@localhost>'
STRICT_ARGS = ('-B', '-W', 'error::ResourceWarning', '-m', 'unittest', 'discover', '-s', 'testCodes', '-v')
ENV_PROBE = (
    'import json,sys,platform; print(json.dumps({"prefix":sys.prefix,'
    '"base_prefix":sys.base_prefix,"base_executable":sys._base_executable,'
    '"version":platform.python_version()}))'
)


def environment():
    # Do not inherit GIT_*, DYLD_*, PYTHON*, credential helpers or UV_*.
    return {
        'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
        'HOME': pwd.getpwuid(os.getuid()).pw_dir, 'LC_ALL': 'C',
        'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null',
        'GIT_CONFIG_SYSTEM': '/dev/null', 'GIT_TERMINAL_PROMPT': '0',
        'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_ATTR_NOSYSTEM': '1',
        'GIT_OPTIONAL_LOCKS': '0',
        'GIT_SSH_COMMAND': '/usr/bin/ssh -F /dev/null -oBatchMode=yes -oIdentityFile=none -oIdentityAgent=none',
        'GIT_AUTHOR_NAME': 'Classroom Release Controller', 'GIT_AUTHOR_EMAIL': 'release-controller@localhost',
        'GIT_COMMITTER_NAME': 'Classroom Release Controller', 'GIT_COMMITTER_EMAIL': 'release-controller@localhost',
    }


def run_git(repo: Path | None, *args: str, env=None, allow_failure=False):
    command = [GIT, '-c', 'core.hooksPath=/dev/null', '-c', 'core.attributesFile=/dev/null',
               '-c', 'credential.helper=', '-c', 'commit.gpgsign=false',
               '-c', 'protocol.allow=never', '-c', 'protocol.file.allow=always',
               '-c', 'protocol.ssh.allow=always', '-c', 'protocol.https.allow=always',
               '-c', 'http.followRedirects=false', '-c', 'maintenance.auto=false',
               '-c', 'gc.auto=0']
    if repo is not None:
        command += ['-C', str(repo)]
    result = subprocess.run([*command, *args], capture_output=True, env=env or environment(), check=False)
    if not allow_failure:
        require(result.returncode == 0, 'GIT_FAILED')
    return result


def git(repo: Path | None, *args: str, env=None) -> str:
    try:
        return run_git(repo, *args, env=env).stdout.decode('utf-8').strip()
    except UnicodeError as exc:
        raise Stop('GIT_OUTPUT_INVALID') from exc


def audit_git(repo: Path, origin: str | None, *, bare=False):
    """Inspect bytes before any repository command could interpret config.

    A small config allowlist also rejects includes, aliases, URL rewrites,
    filters, hooks, SSH commands, proxy/redirects, extra remotes and transports.
    No linked worktree, shared objects, replacements, grafts or partial clones.
    """
    inspect_path(repo, owner=os.getuid(), directory=True)
    gitdir = repo if bare else repo / '.git'
    inspect_path(gitdir, owner=os.getuid(), directory=True)
    for path in gitdir.rglob('*'):
        inspect_path(path, owner=os.getuid(), directory=path.is_dir() and not path.is_symlink())
        relative = path.relative_to(gitdir).as_posix()
        require(relative not in ('commondir', 'gitdir', 'shallow', 'info/grafts', 'objects/info/alternates',
                                 'objects/info/http-alternates') and
                not relative.startswith(('refs/replace/', 'worktrees/')) and
                not relative.endswith(('.lock', '.promisor')), 'GIT_OBJECT_SOURCE')
        if path.parent == gitdir / 'hooks' and path.is_file():
            require(path.name.endswith('.sample'), 'GIT_HOOK')
        if relative in ('info/attributes',):
            require(not read_file(path).strip(), 'GIT_ATTRIBUTES')
    config = gitdir / 'config'
    read_file(config)
    result = run_git(None, 'config', '--null', '--no-includes', '--file', str(config), '--list')
    items = {}
    for item in result.stdout.split(b'\0'):
        if not item:
            continue
        try:
            key, value = item.decode().split('\n', 1)
        except (ValueError, UnicodeError) as exc:
            raise Stop('GIT_CONFIG') from exc
        require(key not in items, 'GIT_CONFIG')
        items[key] = value
    allowed = {
        'core.repositoryformatversion': ('0',), 'core.filemode': ('true', 'false'),
        'core.bare': ('true',) if bare else ('false',), 'core.logallrefupdates': ('true',),
        'core.ignorecase': ('true', 'false'), 'core.precomposeunicode': ('true', 'false'),
    }
    if not bare:
        allowed.update({
            'remote.origin.url': (origin,), 'remote.origin.pushurl': (origin,),
            'remote.origin.tagopt': ('--no-tags',),
            'remote.origin.fetch': ('+refs/heads/*:refs/remotes/origin/*',
                                    '+refs/heads/codex/release-1-1-0-automation:refs/remotes/origin/codex/release-1-1-0-automation',
                                    '+refs/heads/codex/clean-toolbar-rename-v1:refs/remotes/origin/codex/clean-toolbar-rename-v1'),
            'branch.main.remote': ('origin',), 'branch.main.merge': (MAIN,),
            'branch.codex/release-1-1-0-automation.remote': ('origin',),
            'branch.codex/release-1-1-0-automation.merge': (FEATURE,),
            'branch.codex/clean-toolbar-rename-v1.remote': ('origin',),
            'branch.codex/clean-toolbar-rename-v1.merge': ('refs/heads/codex/clean-toolbar-rename-v1',),
        })
    require(all(key in allowed and value in allowed[key] for key, value in items.items()), 'GIT_CONFIG')
    require(items.get('core.repositoryformatversion') == '0' and
            items.get('core.bare') == ('true' if bare else 'false'), 'GIT_CONFIG')
    if not bare:
        require(items.get('remote.origin.url') == origin, 'ORIGIN_INVALID')
        # No attributes/submodules, including ignored working-tree attributes.
        for path in repo.rglob('*'):
            if path.name in ('.gitattributes', '.gitmodules') and not path.is_relative_to(gitdir):
                raise Stop('GIT_ATTRIBUTES')
        require(git(repo, 'rev-parse', '--show-toplevel') == str(repo) and
                git(repo, 'rev-parse', '--git-common-dir') == '.git', 'GIT_STANDALONE')
        require(git(repo, 'remote', 'get-url', '--all', 'origin') == origin and
                git(repo, 'remote', 'get-url', '--push', '--all', 'origin') == origin, 'ORIGIN_INVALID')


def clean(repo: Path):
    require(not git(repo, 'status', '--porcelain=v1', '--untracked-files=all'), 'SOURCE_DIRTY')
    for name in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-apply', 'rebase-merge'):
        require(not os.path.lexists(repo / '.git' / name), 'GIT_INCOMPLETE')


def tools(repo: Path, auth: Authorization, revision: str | None = None):
    for relative in REQUIRED_TOOLS:
        if revision is None:
            data = read_file(repo / relative)
        else:
            entry = git(repo, 'ls-tree', revision, '--', relative)
            require(entry.startswith(('100644 blob ', '100755 blob ')), 'TOOL_CHANGED')
            data = run_git(repo, 'cat-file', 'blob', revision + ':' + relative).stdout
        require(digest(data) == auth.payload['tools'][relative], 'TOOL_CHANGED')


def worktree_bytes(repo: Path):
    # git status alone can miss modifications hidden by index flags. Bind every
    # tracked execution input to the actual HEAD tree before bootstrap/imports.
    entries = run_git(repo, 'ls-tree', '-rz', 'HEAD').stdout.split(b'\0')
    for entry in entries:
        if not entry:
            continue
        metadata, raw_path = entry.split(b'\t', 1)
        mode, kind, object_id = metadata.split(b' ')
        require(kind == b'blob' and mode in (b'100644', b'100755', b'120000'), 'SOURCE_CHANGED')
        path = repo / raw_path.decode('utf-8')
        if mode == b'120000':
            inspect_path(path.parent, owner=os.getuid(), directory=True)
            require(path.is_symlink(), 'SOURCE_CHANGED')
            data = os.fsencode(os.readlink(path))
            actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        else:
            inspect_path(path, owner=os.getuid())
            info = path.lstat()
            require(bool(info.st_mode & 0o111) == (mode == b'100755'), 'SOURCE_CHANGED')
            checksum = hashlib.sha1(b'blob ' + str(info.st_size).encode() + b'\0')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                    checksum.update(chunk)
            actual = checksum.hexdigest()
        require(actual.encode() == object_id, 'SOURCE_CHANGED')


def check_source(auth: Authorization):
    repo = auth.implementation
    audit_git(repo, auth.payload['origin'])
    clean(repo)
    require(git(repo, 'symbolic-ref', 'HEAD') == FEATURE and
            git(repo, 'rev-parse', 'HEAD') == auth.payload['accepted_commit'], 'SOURCE_COMMIT')
    tools(repo, auth)
    tools(repo, auth, auth.payload['accepted_commit'])


def check_remote(policy: Policy, auth: Authorization):
    origin = auth.payload['origin']
    if policy.fixture_root is not None:
        require(origin == str(policy.fixture_root / 'remote.git'), 'FIXTURE_BOUNDARY')
        audit_git(Path(origin), None, bare=True)
    data = git(None, 'ls-remote', '--refs', origin, MAIN, FEATURE)
    refs = {MAIN: None, FEATURE: None}
    for line in data.splitlines():
        parts = line.split('\t')
        require(len(parts) == 2 and parts[1] in refs and refs[parts[1]] is None, 'REMOTE_INVALID')
        hex_value(parts[0], SHA)
        refs[parts[1]] = parts[0]
    require(refs[MAIN] is not None, 'REMOTE_DRIFT')
    return refs


class Integration:
    def __init__(self, policy: Policy, *, fixture_gate=None, checkpoint=None):
        require(policy.fixture_root is not None or (fixture_gate is None and checkpoint is None), 'FIXTURE_BOUNDARY')
        self.policy = policy
        self.fixture_gate = fixture_gate
        self.checkpoint = checkpoint or (lambda _: None)
        self.auth = authorize(policy)
        self.journal = Journal(self.auth)
        self.clone = self.auth.managed / 'clone'
        # Never persisted: journal bytes cannot prove where an executable came
        # from. Only a fresh pinned bootstrap in this invocation establishes it.
        self.environment_proof = None

    def revalidate(self):
        latest = authorize(self.policy)
        require(latest == self.auth, 'APPROVAL_CHANGED')
        check_source(self.auth)
        if os.path.lexists(self.clone):
            inspect_path(self.clone, owner=os.getuid(), mode=0o700, directory=True)
            audit_git(self.clone, self.auth.payload['origin'])
            clean(self.clone)
        return check_remote(self.policy, self.auth)

    def intent(self, value, name):
        # Validation before durable intent and again immediately before action.
        self.revalidate()
        value = self.journal.change(value, intent=name)
        self.checkpoint('before_' + name.lower())
        self.revalidate()
        return value

    def refs(self, *, main, feature):
        actual = self.revalidate()
        require(actual[MAIN] == main and actual[FEATURE] == feature, 'REMOTE_DRIFT')
        return actual

    def objects(self):
        p = self.auth.payload
        for commit in (p['main'], p['accepted_commit'], p['baseline'], p['feature_prior']):
            if commit is not None:
                require(git(self.clone, 'cat-file', '-t', commit) == 'commit', 'GIT_OBJECT_INVALID')
        for commit in (p['main'], p['accepted_commit']):
            require(run_git(self.clone, 'merge-base', '--is-ancestor', p['baseline'], commit,
                            allow_failure=True).returncode == 0, 'ANCESTRY_INVALID')
        require(git(self.clone, 'merge-base', '--all', p['main'], p['accepted_commit']) == p['baseline'], 'ANCESTRY_INVALID')
        # This protocol intentionally requires an actual divergent integration.
        require(run_git(self.clone, 'merge-base', '--is-ancestor', p['main'], p['accepted_commit'],
                        allow_failure=True).returncode == 1 and
                run_git(self.clone, 'merge-base', '--is-ancestor', p['accepted_commit'], p['main'],
                        allow_failure=True).returncode == 1, 'DIVERGENCE_REQUIRED')
        if p['feature_prior'] is not None:
            require(run_git(self.clone, 'merge-base', '--is-ancestor', p['feature_prior'], p['accepted_commit'],
                            allow_failure=True).returncode == 0, 'FEATURE_NOT_FAST_FORWARD')
        tools(self.clone, self.auth, p['accepted_commit'])
        require(not git(self.clone, 'ls-tree', '-r', '--name-only', p['accepted_commit'], '--',
                        '.gitattributes', '.gitmodules'), 'GIT_ATTRIBUTES')

    def expected_merge(self):
        p = self.auth.payload
        tree = git(self.clone, 'merge-tree', '--write-tree', p['main'], p['accepted_commit']).splitlines()[0]
        hex_value(tree, SHA)
        tools(self.clone, self.auth, tree)
        timestamp = max(int(git(self.clone, 'show', '-s', '--format=%ct', commit))
                        for commit in (p['main'], p['accepted_commit'])) + 1
        raw = (f'tree {tree}\nparent {p["main"]}\nparent {p["accepted_commit"]}\n'
               f'author {IDENTITY} {timestamp} +0000\ncommitter {IDENTITY} {timestamp} +0000\n\n{MESSAGE}\n').encode()
        commit = hashlib.sha1(b'commit ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        return commit, tree, timestamp, raw

    def verify_merge(self, expected):
        commit, tree, _, raw = expected
        require(git(self.clone, 'rev-parse', 'HEAD') == commit and
                git(self.clone, 'rev-parse', 'HEAD^{tree}') == tree and
                run_git(self.clone, 'cat-file', 'commit', commit).stdout == raw, 'MERGE_INVALID')
        for parent in (self.auth.payload['main'], self.auth.payload['accepted_commit']):
            require(run_git(self.clone, 'merge-base', '--is-ancestor', parent, commit,
                            allow_failure=True).returncode == 0, 'ANCESTRY_INVALID')
        tools(self.clone, self.auth)
        worktree_bytes(self.clone)
        clean(self.clone)

    def log_command(self, kind, argv, env):
        directory = self.auth.managed / 'evidence'
        inspect_path(directory, owner=os.getuid(), mode=0o700, directory=True)
        path = directory / (kind + '-' + uuid.uuid4().hex + '.log')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            result = subprocess.run(argv, cwd=self.clone, env=env, stdout=handle, stderr=subprocess.STDOUT, check=False)
            handle.flush()
            os.fsync(handle.fileno())
        fsync_directory(directory)
        require(result.returncode == 0, 'BOOTSTRAP_FAILED' if kind == 'bootstrap' else 'STRICT_FAILED')
        return {'file': path.name, 'sha256': digest(read_file(path, owner=os.getuid(), mode=0o600, limit=64 * 1024 * 1024))}

    def gate_environment(self):
        env = environment()
        env.update({'TMPDIR': str(self.auth.managed / 'tmp'), 'QT_QPA_PLATFORM': 'offscreen',
                    'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONWARNINGS': 'error::ResourceWarning',
                    'UV_PYTHON_INSTALL_DIR': str(self.clone / '.tools/python'),
                    'UV_CACHE_DIR': str(self.clone / '.tools/cache'), 'UV_MANAGED_PYTHON': '1',
                    'UV_NO_CONFIG': '1'})
        if self.policy.fixture_root is not None:
            # REL1A's unchanged full suite checks canonical origin identity.
            # Present that read-only identity to its subprocesses, while denying
            # every network transport and keeping any push URL local. Controller
            # Git commands use their own sanitized environment and still audit
            # the real local fetch/push URLs. Never used by production Policy.
            config = (('remote.origin.url', ORIGINS[1]),
                      ('remote.origin.pushurl', self.auth.payload['origin']),
                      ('protocol.allow', 'never'), ('protocol.file.allow', 'always'),
                      ('core.hooksPath', '/dev/null'))
            env['GIT_CONFIG_COUNT'] = str(len(config))
            for index, (key, value) in enumerate(config):
                env['GIT_CONFIG_KEY_' + str(index)] = key
                env['GIT_CONFIG_VALUE_' + str(index)] = value
        inspect_path(self.auth.managed / 'tmp', owner=os.getuid(), mode=0o700, directory=True)
        return env

    def check_environment_paths(self, *, present=False):
        # Never bootstrap over an untrusted ignored .tools/.venv replacement.
        for relative in ('.tools', '.tools/python', '.tools/uv', '.tools/uv/0.12.5',
                         '.tools/cache', '.venv', '.venv/bin'):
            path = self.clone / relative
            if os.path.lexists(path):
                inspect_path(path, owner=os.getuid(), directory=True)
        python = self.clone / '.venv/bin/python'
        if os.path.lexists(python):
            # Legitimate uv Python links are the sole leaf-symlink exception.
            inspect_path(python.parent, owner=os.getuid(), directory=True)
            target = python.resolve(strict=True)
            require(target.is_relative_to(self.clone / '.tools/python'), 'ENVIRONMENT_INVALID')
            inspect_path(target, owner=os.getuid())
            require(os.access(target, os.X_OK), 'ENVIRONMENT_INVALID')
        else:
            require(not present, 'ENVIRONMENT_INVALID')

    def execution_snapshot(self):
        """Hash all executable/import inputs without running any of them.

        Include managed Python's stdlib, site packages, .pth/pyc/native libraries,
        uv, venv config/links, and the entire worktree (including ignored code).
        Cache is not an execution input after bootstrap; no sync/install follows.
        Symlinks may point only inside this clone and are never traversed here.
        Metadata additionally detects replacement with identical bytes.
        """
        result = {}
        def visit(directory):
            with os.scandir(directory) as entries:
                children = sorted(entries, key=lambda item: item.name)
            for entry in children:
                path = Path(entry.path)
                relative = path.relative_to(self.clone).as_posix()
                if relative in ('.git', '.tools/cache'):
                    continue
                info = path.lstat()
                # Pinned uv creates these two empty advisory locks as 0666.
                # They cannot execute/import code, remain inside the 0700 clone,
                # and their type/identity/bytes are still covered by the proof.
                advisory_lock = (relative in ('.venv/.lock', '.tools/python/.lock') and
                                 stat.S_ISREG(info.st_mode) and info.st_size == 0 and
                                 stat.S_IMODE(info.st_mode) == 0o666)
                require(info.st_uid == os.getuid() and
                        (stat.S_ISLNK(info.st_mode) or advisory_lock or not info.st_mode & 0o022),
                        'ENVIRONMENT_INVALID')
                identity = (info.st_dev, info.st_ino, info.st_mode, info.st_uid)
                if stat.S_ISDIR(info.st_mode):
                    result[relative] = ('directory', identity)
                    visit(path)
                elif stat.S_ISLNK(info.st_mode):
                    require(path.resolve(strict=True).is_relative_to(self.clone), 'ENVIRONMENT_INVALID')
                    result[relative] = ('symlink', identity, os.readlink(path), info.st_ctime_ns)
                else:
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'ENVIRONMENT_INVALID')
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                    with os.fdopen(fd, 'rb') as handle:
                        require(os.fstat(handle.fileno()) == info, 'ENVIRONMENT_CHANGED')
                        checksum = hashlib.file_digest(handle, 'sha256').hexdigest()
                    after = path.lstat()
                    require((after.st_dev, after.st_ino, after.st_mode, after.st_size,
                             after.st_mtime_ns, after.st_ctime_ns) ==
                            (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                             info.st_mtime_ns, info.st_ctime_ns), 'ENVIRONMENT_CHANGED')
                    result[relative] = ('file', identity, info.st_size,
                                        info.st_mtime_ns, info.st_ctime_ns, checksum)
        visit(self.clone)
        return result

    def fresh_environment(self):
        # A version self-report (even from a clone-local executable) is never
        # provenance. Do not execute, remove, or repair preexisting environments.
        require(self.environment_proof is None, 'ENVIRONMENT_UNTRUSTED')
        require(not any(os.path.lexists(self.clone / name) for name in ('.tools', '.venv')),
                'ENVIRONMENT_UNTRUSTED')
        require(not git(self.clone, 'ls-files', '--others', '--ignored', '--exclude-standard'),
                'ENVIRONMENT_UNTRUSTED')
        return self.execution_snapshot()

    def check_environment_proof(self):
        require(self.environment_proof is not None, 'ENVIRONMENT_UNTRUSTED')
        require(self.execution_snapshot() == self.environment_proof, 'ENVIRONMENT_CHANGED')

    def verify_environment(self, env):
        # Must precede the first Python/uv invocation, including --version.
        self.check_environment_proof()
        self.check_environment_paths(present=True)
        python = self.clone / '.venv/bin/python'
        result = subprocess.run([str(python), '-B', '-I', '-c', ENV_PROBE], cwd=self.clone,
                                env=env, capture_output=True, check=False)
        require(result.returncode == 0, 'ENVIRONMENT_INVALID')
        value = decode(result.stdout)
        require(type(value) is dict and set(value) == {'prefix', 'base_prefix', 'base_executable', 'version'} and
                value['prefix'] == str(self.clone / '.venv') and value['version'] == '3.12.14', 'ENVIRONMENT_INVALID')
        for key in ('base_prefix', 'base_executable'):
            require(type(value[key]) is str and Path(value[key]).is_relative_to(self.clone / '.tools/python'), 'ENVIRONMENT_INVALID')
            inspect_path(Path(value[key]), owner=os.getuid(), directory=key == 'base_prefix')
        uv = self.clone / '.tools/uv/0.12.5/uv'
        inspect_path(uv, owner=os.getuid())
        result = subprocess.run([str(uv), '--version'], env=env, capture_output=True, check=False)
        # Official pinned uv includes build/platform metadata after the version.
        # This is an identity check only after byte provenance has been proved.
        require(result.returncode == 0 and result.stdout.split()[:2] == [b'uv', b'0.12.5'], 'ENVIRONMENT_INVALID')
        # Frozen lock and exact imports are also tested by the fixed strict suite.
        result = subprocess.run([str(uv), 'lock', '--check', '--offline'], cwd=self.clone, env=env,
                                capture_output=True, check=False)
        require(result.returncode == 0, 'LOCK_INVALID')
        self.check_environment_proof()

    def gate(self, value, expected, feature):
        value = self.journal.change(value, state='MERGED', intent=None, gate=None, main_receipt=None)
        env = self.gate_environment()
        value = self.intent(value, 'BOOTSTRAP')
        self.refs(main=self.auth.payload['main'], feature=feature)
        self.verify_merge(expected)
        if self.fixture_gate is None:
            source_proof = self.fresh_environment()
            bootstrap = self.log_command('bootstrap', ['/bin/bash', str(self.clone / 'scripts/bootstrap_python_env.sh')], env)
            proof = self.execution_snapshot()
            source_after = {key: item for key, item in proof.items()
                            if key not in ('.tools', '.venv') and
                            not key.startswith(('.tools/', '.venv/'))}
            require(source_after == source_proof, 'ENVIRONMENT_CHANGED')
            self.environment_proof = proof
        else:
            bootstrap = self.fixture_gate(self, 'bootstrap', env)
        self.checkpoint('after_bootstrap')
        self.revalidate()
        self.verify_merge(expected)
        if self.fixture_gate is None:
            self.verify_environment(env)
        value = self.intent(value, 'STRICT')
        self.refs(main=self.auth.payload['main'], feature=feature)
        self.verify_merge(expected)
        if self.fixture_gate is None:
            self.check_environment_proof()
            strict = self.log_command('strict', [str(self.clone / '.venv/bin/python'), *STRICT_ARGS], env)
        else:
            strict = self.fixture_gate(self, 'strict', env)
        self.checkpoint('after_strict')
        self.refs(main=self.auth.payload['main'], feature=feature)
        self.verify_merge(expected)
        if self.fixture_gate is None:
            self.verify_environment(env)
        gate = {'source': expected[0], 'bootstrap': bootstrap, 'strict': strict}
        value = self.journal.change(value, state='GATED', intent=None, gate=gate)
        self.journal.validate_logs(value)
        return value

    def push(self, value, name, commit, ref, prior, feature):
        value = self.intent(value, name)
        self.refs(main=self.auth.payload['main'], feature=feature)
        require(ref in (MAIN, FEATURE) and SHA.fullmatch(commit), 'PUSH_INVALID')
        if ref == MAIN:
            require(git(self.clone, 'rev-parse', 'HEAD') == commit and
                    git(self.clone, 'rev-parse', 'HEAD^{tree}') == value['merge_tree'], 'MERGE_INVALID')
            tools(self.clone, self.auth)
            self.journal.validate_logs(value)
            if self.fixture_gate is None:
                self.verify_environment(self.gate_environment())
        # No force/lease/wildcard/default push. Unknown result never blindly retries.
        result = run_git(self.clone, 'push', '--porcelain', 'origin', commit + ':' + ref, allow_failure=True)
        self.checkpoint('after_' + name.lower())
        actual = self.revalidate()
        if actual[ref] != commit:
            raise Stop('PUSH_UNKNOWN' if actual[ref] == prior else 'REMOTE_DRIFT')
        other = FEATURE if ref == MAIN else MAIN
        require(actual[other] == (feature if ref == MAIN else self.auth.payload['main']), 'REMOTE_DRIFT')
        # A nonzero transport exit may still mean success; exact ref is authority.
        if ref == FEATURE:
            value = self.journal.change(value, intent=None, feature_receipt=commit)
        else:
            value = self.journal.change(value, state='COMPLETE', intent=None, main_receipt=commit)
        self.checkpoint('recorded_' + name.lower())
        return value

    def execute(self):
        p = self.auth.payload
        value = self.journal.inspect()
        refs = self.revalidate()
        if refs[MAIN] != p['main']:
            # Read-only reconciliation only. A journal cannot prove a past gate.
            if value is not None and os.path.lexists(self.clone):
                self.objects()
                if value['merge_commit'] is not None and refs[MAIN] == value['merge_commit']:
                    raw = run_git(self.clone, 'cat-file', 'commit', refs[MAIN]).stdout
                    require(raw.startswith((f'tree {value["merge_tree"]}\nparent {p["main"]}\nparent {p["accepted_commit"]}\n').encode()), 'REMOTE_DRIFT')
                    raise Stop('MAIN_PRESENT_HUMAN_RECONCILIATION')
            raise Stop('REMOTE_DRIFT')
        require(refs[FEATURE] in (p['feature_prior'], p['accepted_commit']), 'REMOTE_DRIFT')
        if value is None:
            require(refs[FEATURE] == p['feature_prior'], 'RECOVERY_PROOF_MISSING')
            value = self.journal.create()
        # Advanced journal states never skip acquisition, merge or the live gate.
        if not os.path.lexists(self.clone):
            require(value['state'] == 'NEW' and value['intent'] in (None, 'CLONE'), 'RECOVERY_PROOF_MISSING')
            value = self.intent(value, 'CLONE')
            self.refs(main=p['main'], feature=p['feature_prior'])
            git(None, 'clone', '--no-local', '--no-hardlinks', '--no-checkout', '--no-tags',
                '--template=', p['origin'], str(self.clone))
            # chmod only our just-created directory; never repair existing paths.
            self.clone.chmod(0o700)
            fsync_directory(self.auth.managed)
            self.checkpoint('after_clone')
            # A no-checkout clone is deliberately dirty until FETCH completes.
            audit_git(self.clone, p['origin'])
        elif value['state'] == 'NEW' and value['intent'] == 'CLONE':
            # Interrupted clone cannot be assumed complete or overwritten.
            raise Stop('CLONE_INCOMPLETE')
        if value['state'] == 'NEW':
            # During no-checkout acquisition do not invoke worktree-clean checks.
            latest = authorize(self.policy)
            require(latest == self.auth, 'APPROVAL_CHANGED')
            check_source(self.auth)
            audit_git(self.clone, p['origin'])
            require(check_remote(self.policy, self.auth) == refs, 'REMOTE_DRIFT')
            value = self.journal.change(value, intent='FETCH')
            self.checkpoint('before_fetch')
            require(authorize(self.policy) == self.auth, 'APPROVAL_CHANGED')
            check_source(self.auth)
            audit_git(self.clone, p['origin'])
            require(check_remote(self.policy, self.auth) == refs, 'REMOTE_DRIFT')
            # Read implementation object through the Git protocol, not shared dirs.
            git(self.clone, 'fetch', '--no-tags', '--no-write-fetch-head', p['implementation'], p['accepted_commit'])
            git(self.clone, 'fetch', '--no-tags', '--no-write-fetch-head', p['origin'], p['main'])
            self.objects()
            git(self.clone, 'checkout', '--detach', p['main'])
            self.checkpoint('after_fetch')
            value = self.journal.change(value, state='READY', intent=None)
        self.revalidate()
        self.objects()
        if value['state'] == 'READY' and refs[FEATURE] == p['feature_prior']:
            value = self.push(value, 'FEATURE_PUSH', p['accepted_commit'], FEATURE, p['feature_prior'], p['feature_prior'])
        else:
            require(self.revalidate()[FEATURE] == p['accepted_commit'], 'REMOTE_DRIFT')
            # Success after lost receipt is derived from the exact remote ref.
            if value['feature_receipt'] is None:
                value = self.journal.change(value, feature_receipt=p['accepted_commit'])
        if value['state'] == 'READY':
            value = self.intent(value, 'MERGE')
        else:
            self.revalidate()
        expected = self.expected_merge()
        head = git(self.clone, 'rev-parse', 'HEAD')
        if head == p['main']:
            require(value['state'] == 'READY', 'JOURNAL_FACTS')
            env = environment()
            env.update({'GIT_AUTHOR_DATE': str(expected[2]) + ' +0000',
                        'GIT_COMMITTER_DATE': str(expected[2]) + ' +0000'})
            self.refs(main=p['main'], feature=p['accepted_commit'])
            git(self.clone, 'merge', '--no-ff', '--no-edit', '-m', MESSAGE, p['accepted_commit'], env=env)
            self.checkpoint('after_merge')
        self.verify_merge(expected)
        require(value['merge_commit'] in (None, expected[0]) and value['merge_tree'] in (None, expected[1]), 'JOURNAL_FACTS')
        if value['state'] in ('GATED', 'COMPLETE'):
            self.journal.validate_logs(value)
        value = self.journal.change(value, state='MERGED', intent=None,
                                    merge_commit=expected[0], merge_tree=expected[1], gate=None, main_receipt=None)
        value = self.gate(value, expected, p['accepted_commit'])
        # Only this invocation's successful gate can reach the main push below.
        self.refs(main=p['main'], feature=p['accepted_commit'])
        self.verify_merge(expected)
        value = self.push(value, 'MAIN_PUSH', expected[0], MAIN, p['main'], p['accepted_commit'])
        return value
