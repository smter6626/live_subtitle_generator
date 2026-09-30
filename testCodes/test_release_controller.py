"""Real OpenSSH signatures/argparse/Git. All retained fixtures stay in Downloads.

The deterministic fixture gate executes local subprocesses and records logs. It
does not prove production Python bootstrap or product regression completion.
Production gate rejection and fixed argv are separately exercised; the Executor
also runs the real target-local full strict suite outside this harness.
Independent real-gate smoke launchers remain outside discovery. Full-source
fixtures retain REL1A's canonical-origin reader contract through a subprocess
identity view that denies network Git; actual controller URLs/refs remain local.
"""
from __future__ import annotations

import contextlib
import copy
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import release_approval as approval
import release_controller as controller
import release_integration as integration
import release_journal as journal


def retained_root():
    temporary = Path(tempfile.gettempdir())
    # Real-gate discovery runs inside managed/tmp. Retain nested test fixtures
    # under the same recorded root rather than scattering them across Downloads.
    for candidate in (temporary, *temporary.parents):
        if candidate.name.startswith('rel1b-fixtures.') and candidate.is_relative_to(approval.downloads()):
            approval.inspect_path(candidate, owner=os.getuid(), mode=0o700, directory=True)
            return candidate
    # Direct reviewer test invocation also creates only this bounded root.
    return Path(tempfile.mkdtemp(prefix='rel1b-fixtures.', dir=approval.downloads()))


class Crash(Exception):
    pass


class Fixture:
    def __init__(self, root, *, conflict=False, prior=False, bootstrap=None, full_source=False):
        self.root = root / ('case-' + uuid.uuid4().hex)
        self.root.mkdir(mode=0o700)
        self.policy = approval.Policy(self.root)
        self.source = self.root / 'source'
        self.remote = self.root / 'remote.git'
        reader = self.root / 'git-reader.config'
        reader.write_bytes(integration.fixture_reader_config(str(self.remote)))
        reader.chmod(0o600)
        self.source.mkdir(mode=0o700)
        self.calls = []
        self.operations = []
        integration.git(None, 'init', '--bare', '--template=', str(self.remote))
        integration.git(self.remote, 'symbolic-ref', 'HEAD', approval.MAIN)
        integration.git(None, 'init', '--template=', '--initial-branch=main', str(self.source))
        integration.git(self.source, 'remote', 'add', 'origin', str(self.remote))
        paths = approval.REQUIRED_TOOLS
        if full_source:
            paths = [item.decode('utf-8') for item in integration.run_git(
                REPO, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').stdout.split(b'\0') if item]
        for relative in paths:
            path = self.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPO / relative, path)
            path.chmod((REPO / relative).stat().st_mode & 0o777)
        if bootstrap is not None:
            (self.source / 'scripts/bootstrap_python_env.sh').write_text(bootstrap)
        if not full_source:
            (self.source / '.gitignore').write_text('.venv/\n.tools/\n')
        (self.source / 'common.txt').write_text('common\n')
        self.baseline = self.commit('baseline')
        if conflict:
            (self.source / 'common.txt').write_text('main conflict\n')
        docs = self.source / 'docs/streaming_backend_upgrade'
        docs.mkdir(parents=True)
        for name in ('README', 'runtime', 'static', 'update_plan'):
            (docs / (name + '.md')).write_text('main document ' + name + '\n')
        for name in ('README.md', 'README.zh-CN.md', 'docs/repo_map.md'):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text((path.read_text() if full_source and path.exists() else '') + 'main navigation\n')
        self.main = self.commit('main-only documentation')
        integration.git(self.source, 'push', 'origin', self.main + ':' + approval.MAIN)
        integration.git(self.source, 'checkout', '-b', approval.FEATURE.removeprefix('refs/heads/'), self.baseline)
        self.prior = None
        if prior:
            (self.source / 'prior.txt').write_text('prior\n')
            self.prior = self.commit('feature prior')
            integration.git(self.source, 'push', 'origin', self.prior + ':' + approval.FEATURE)
        if conflict:
            (self.source / 'common.txt').write_text('feature conflict\n')
        (self.source / 'feature.txt').write_text('accepted feature\n')
        self.accepted = self.commit('accepted implementation')
        # Prove main object can be absent in implementation. Re-clone only feature.
        self.seed = self.root / 'seed'
        self.source.rename(self.seed)
        integration.git(None, 'clone', '--no-local', '--no-hardlinks', '--no-tags', '--template=',
                        '--single-branch', '--branch', approval.FEATURE.removeprefix('refs/heads/'),
                        str(self.seed), str(self.source))
        integration.git(self.source, 'remote', 'set-url', 'origin', str(self.remote))
        for key in approval.CONTRACTS:
            (self.root / (key + '.md')).write_text('fixture contract ' + key + '\n')
        trust = self.policy.root
        trust.mkdir(mode=0o700)
        self.key = self.root / 'fixture_key'
        subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(self.key)],
                       check=True, capture_output=True)
        public = (self.root / 'fixture_key.pub').read_text().split()
        self.write_trust('allowed_signers', (self.policy.signer + ' ' + ' '.join(public[:2]) + '\n').encode())
        for kind, scope in (('review', 'step1-final-independent-review'), ('human', 'step1-final-owner-integration')):
            self.write_trust(kind + '.json', approval.canonical({'schema_version': 1, 'accepted_commit': self.accepted,
                                                               'scope': scope, 'reference': 'fixture-only-' + kind}))
        config = {'schema_version': 1, 'epoch': 1,
                  'entry_sha256': {p: approval.digest((REPO / p).read_bytes()) for p in approval.CONTROL_TOOLS},
                  'review_sha256': approval.digest((trust / 'review.json').read_bytes()),
                  'human_sha256': approval.digest((trust / 'human.json').read_bytes())}
        self.write_trust('config.json', approval.canonical(config))
        self.write_trust('revoked.json', approval.canonical({'schema_version': 1, 'ids': []}))
        self.payload = {
            'schema_version': 1, 'id': 'fixture-' + uuid.uuid4().hex, 'policy': self.policy.namespace,
            'config_epoch': 1, 'config_sha256': approval.digest((trust / 'config.json').read_bytes()),
            'signers_sha256': approval.digest((trust / 'allowed_signers').read_bytes()),
            'accepted_commit': self.accepted,
            'tools': {p: approval.digest((self.source / p).read_bytes()) for p in approval.REQUIRED_TOOLS},
            'contracts': {k: approval.digest(p.read_bytes()) for k, p in self.policy.contracts.items()},
            'review': {'locator': str(trust / 'review.json'), 'sha256': config['review_sha256']},
            'human': {'locator': str(trust / 'human.json'), 'sha256': config['human_sha256']},
            'repository': approval.REPOSITORY, 'origin': str(self.remote), 'main_ref': approval.MAIN,
            'feature_ref': approval.FEATURE, 'main': self.main, 'feature_prior': self.prior,
            'baseline': self.baseline, 'implementation': str(self.source),
            'managed': str(self.root / 'managed'), 'uid': os.getuid(),
        }
        self.sign()

    def commit(self, message):
        integration.git(self.source, 'add', '--all')
        integration.git(self.source, 'commit', '-m', message)
        return integration.git(self.source, 'rev-parse', 'HEAD')

    def write_trust(self, name, data):
        path = self.policy.root / name
        path.write_bytes(data)
        path.chmod(0o600)

    def sign(self, namespace=None):
        self.write_trust('approval.json', approval.canonical(self.payload))
        signature = self.policy.root / 'approval.json.sig'
        if signature.exists():
            signature.unlink()
        subprocess.run(['/usr/bin/ssh-keygen', '-Y', 'sign', '-f', str(self.key), '-n',
                        namespace or self.policy.namespace, str(self.policy.root / 'approval.json')],
                       check=True, capture_output=True)
        signature.chmod(0o600)

    def gate(self, runner, kind, env):
        self.calls.append(kind)
        # Real deterministic subprocess, without faking Git/approval validation.
        return runner.log_command(kind, ['/bin/sh', '-c', 'printf "fixture gate only\\n"'], env)

    def cli(self, command='integrate', *, gate='fixture', checkpoint=None):
        output = io.StringIO()
        with self.record_operations(), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = controller._run([command], self.policy,
                                     fixture_gate=self.gate if gate == 'fixture' else gate,
                                     checkpoint=checkpoint)
        text = output.getvalue()
        path = self.root / ('cli-' + uuid.uuid4().hex + '.txt')
        path.write_text(text)
        return result, text

    def ref(self, name=approval.MAIN):
        result = integration.run_git(self.remote, 'rev-parse', '--verify', name, allow_failure=True)
        return result.stdout.decode().strip() if result.returncode == 0 else None

    @property
    def journal_path(self):
        return self.root / 'managed/journal.json'

    def edit_journal(self, **changes):
        value = approval.decode(self.journal_path.read_bytes())
        value.update(changes)
        self.journal_path.write_bytes(approval.canonical(journal.with_checksum(value)))

    def stop_at(self, point):
        def stop(name):
            if name == point:
                raise Crash(point)
        with self.record_operations(), self._capture(), unittest.TestCase().assertRaises(Crash):
            controller._run(['integrate'], self.policy, fixture_gate=self.gate, checkpoint=stop)

    @contextlib.contextmanager
    def record_operations(self):
        actual_run = integration.run_git
        def recorded(repo, *args, **kwargs):
            result = actual_run(repo, *args, **kwargs)
            if repo == self.root / 'managed/clone' and args[0] in ('push', 'merge'):
                self.operations.append({'args': list(args), 'returncode': result.returncode})
                (self.root / 'operations.json').write_bytes(approval.canonical(self.operations))
            return result
        with mock.patch.object(integration, 'run_git', side_effect=recorded):
            yield

    def push_count(self, ref):
        return sum(item['args'][0] == 'push' and item['args'][-1].endswith(':' + ref)
                   for item in self.operations)

    @contextlib.contextmanager
    def _capture(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            yield


class ControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = retained_root()

    def fixture(self, **kwargs):
        return Fixture(self.root, **kwargs)

    def test_real_signed_cli_divergent_merge_preserves_history_and_docs(self):
        f = self.fixture(prior=True)
        self.assertNotEqual(integration.run_git(f.source, 'cat-file', '-e', f.main, allow_failure=True).returncode, 0)
        code, output = f.cli()
        self.assertEqual((code, output), (0, 'release-controller: COMPLETE_AWAITING_INDEPENDENT_REVIEW\n'))
        clone = f.root / 'managed/clone'
        merge = f.ref()
        self.assertEqual(integration.git(clone, 'show', '-s', '--format=%P', merge), f.main + ' ' + f.accepted)
        self.assertEqual(f.ref(approval.FEATURE), f.accepted)
        for name in ('README', 'runtime', 'static', 'update_plan'):
            self.assertEqual((clone / 'docs/streaming_backend_upgrade' / (name + '.md')).read_text(), 'main document ' + name + '\n')
        for name in ('README.md', 'README.zh-CN.md', 'docs/repo_map.md'):
            self.assertEqual((clone / name).read_text(), 'main navigation\n')
        self.assertTrue((clone / 'feature.txt').is_file())
        self.assertEqual(f.calls, ['bootstrap', 'strict'])
        value = approval.decode(f.journal_path.read_bytes())
        self.assertEqual(value['merge_tree'], integration.git(clone, 'merge-tree', '--write-tree', f.main, f.accepted))
        (f.root / 'git-facts.json').write_bytes(approval.canonical({'main_before': f.main, 'accepted': f.accepted,
                    'main_after': merge, 'tree': value['merge_tree'], 'parents': [f.main, f.accepted]}))

    def test_production_missing_trust_has_no_mutation_and_no_override_cli(self):
        before = integration.git(REPO, 'show-ref')
        for arg in ('status', 'integrate', 'resume'):
            result = subprocess.run([sys.executable, '-B', str(REPO / 'scripts/release_controller.py'), arg],
                                    capture_output=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, b'release-controller: STOP TRUST_UNAVAILABLE\n')
        for args in (['status', '--allowed-signers', 'SECRET'], ['status', '--test-mode'],
                     ['status', '--approval', 'SECRET'], ['build'], ['package'], ['human-pass'],
                     ['tag'], ['draft'], ['upload'], ['publish']):
            result = subprocess.run([sys.executable, '-B', str(REPO / 'scripts/release_controller.py'), *args],
                                    capture_output=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(b'SECRET', result.stderr)
        self.assertEqual(integration.git(REPO, 'show-ref'), before)

    def test_status_missing_and_repeat_are_strictly_read_only(self):
        f = self.fixture()
        for _ in range(2):
            self.assertEqual(f.cli('status'), (0, 'release-controller: MISSING\n'))
            self.assertFalse((f.root / 'managed').exists())
        f.stop_at('before_main_push')
        def snapshot():
            return {str(p.relative_to(f.root)): (p.stat().st_mode, p.read_bytes())
                    for p in (f.root / 'managed').rglob('*') if p.is_file()}
        before, refs = snapshot(), f.ref()
        for _ in range(2):
            self.assertEqual(f.cli('status'), (0, 'release-controller: GATED_RECORDED_UNVERIFIED\n'))
        self.assertEqual(snapshot(), before)
        self.assertEqual(f.ref(), refs)

    def test_crashes_before_and_after_each_local_stage_reconcile_or_stop(self):
        for point in ('before_clone', 'after_clone', 'before_fetch', 'after_fetch', 'before_merge',
                      'after_merge', 'before_bootstrap', 'after_bootstrap', 'before_strict', 'after_strict',
                      'before_feature_push', 'after_feature_push', 'recorded_feature_push', 'before_main_push'):
            with self.subTest(point=point):
                f = self.fixture()
                f.stop_at(point)
                self.assertEqual(f.ref(), f.main)
                result, output = f.cli('resume')
                if point in ('after_clone', 'before_fetch'):
                    self.assertEqual(result, 1)
                    self.assertIn('STOP', output)
                    self.assertEqual(f.ref(), f.main)
                else:
                    self.assertEqual(result, 0, output)
                    self.assertEqual(f.ref(approval.FEATURE), f.accepted)
                    self.assertNotEqual(f.ref(), f.main)

    def test_main_push_success_crash_or_receipt_loss_never_replays(self):
        for point in ('after_main_push', 'recorded_main_push'):
            with self.subTest(point=point):
                f = self.fixture()
                f.stop_at(point)
                before = f.ref()
                self.assertNotEqual(before, f.main)
                self.assertEqual(f.push_count(approval.MAIN), 1)
                code, output = f.cli('resume')
                self.assertEqual(code, 1)
                self.assertIn('MAIN_PRESENT_HUMAN_RECONCILIATION', output)
                self.assertEqual(f.ref(), before)
                self.assertEqual(f.push_count(approval.MAIN), 1)
                f.journal_path.unlink()
                code, output = f.cli('resume')
                self.assertEqual(code, 1)
                self.assertIn('PERSISTENCE_INCOMPLETE', output)
                self.assertEqual(f.ref(), before)
                self.assertEqual(f.push_count(approval.MAIN), 1)

    def test_rehashed_advanced_state_and_forged_pass_cannot_skip_gate(self):
        f = self.fixture()
        f.stop_at('before_main_push')
        value = approval.decode(f.journal_path.read_bytes())
        # Real logs/hash plus GATED state still do not authorize a later gate.
        self.assertEqual(value['state'], 'GATED')
        f.calls.clear()
        def failed_gate(runner, kind, env):
            f.calls.append(kind)
            return runner.log_command(kind, ['/bin/sh', '-c', 'exit 19'], env)
        code, output = f.cli('resume', gate=failed_gate)
        self.assertEqual(code, 1)
        self.assertIn('BOOTSTRAP_FAILED', output)
        self.assertEqual(f.calls, ['bootstrap'])
        self.assertEqual(f.ref(), f.main)

    def test_failed_strict_or_post_test_source_drift_does_not_push_main(self):
        for action in ('fail', 'source', 'hidden-source', 'remote', 'config', 'approval', 'revoke'):
            with self.subTest(action=action):
                f = self.fixture()
                def gate(runner, kind, env):
                    if kind == 'strict' and action == 'fail':
                        return runner.log_command(kind, ['/bin/sh', '-c', 'exit 21'], env)
                    result = f.gate(runner, kind, env)
                    if kind == 'strict':
                        if action == 'source':
                            (runner.clone / 'feature.txt').write_text('post-test drift\n')
                        elif action == 'hidden-source':
                            integration.git(runner.clone, 'update-index', '--assume-unchanged', 'feature.txt')
                            (runner.clone / 'feature.txt').write_text('index-hidden post-test drift\n')
                        elif action == 'remote':
                            integration.git(f.remote, 'update-ref', approval.MAIN, f.baseline)
                        elif action == 'config':
                            integration.git(runner.clone, 'config', 'core.hooksPath', '/SECRET')
                        elif action == 'approval':
                            f.payload['id'] = 'changed'
                            f.sign()
                        elif action == 'revoke':
                            f.write_trust('revoked.json', approval.canonical({'schema_version': 1, 'ids': [f.payload['id']]}))
                    return result
                code, output = f.cli(gate=gate)
                self.assertEqual(code, 1, output)
                self.assertNotEqual(f.ref(), f.accepted)
                self.assertEqual(f.ref(), f.baseline if action == 'remote' else f.main)

    def test_actual_production_bootstrap_failure_and_environment_rejection(self):
        f = self.fixture(bootstrap='#!/bin/bash\nprintf "bootstrap called\\n"\nexit 23\n')
        code, output = f.cli(gate=None)
        self.assertEqual(code, 1)
        self.assertIn('BOOTSTRAP_FAILED', output)
        self.assertEqual(f.ref(), f.main)
        logs = list((f.root / 'managed/evidence').glob('bootstrap-*.log'))
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].read_bytes(), b'bootstrap called\n')
        runner = integration.Integration(f.policy)
        venv = runner.clone / '.venv/bin'
        venv.mkdir(parents=True)
        (venv / 'python').symlink_to(REPO / '.venv/bin/python')
        with self.assertRaises(approval.Stop) as caught:
            runner.verify_environment(runner.gate_environment())
        self.assertEqual(caught.exception.code, 'ENVIRONMENT_UNTRUSTED')
        self.assertEqual(integration.STRICT_ARGS, ('-B', '-W', 'error::ResourceWarning', '-m', 'unittest', 'discover', '-s', 'testCodes', '-v'))

    def test_counterfeit_clone_local_environment_never_executes_on_resume_or_initial_gate(self):
        for resumed in (False, True):
            with self.subTest(resumed=resumed):
                f = self.fixture()
                def counterfeit(point):
                    if point != 'before_bootstrap':
                        return
                    clone = f.root / 'managed/clone'
                    uv = clone / '.tools/uv/0.12.5/uv'
                    python = clone / '.tools/python/forged/bin/python3.12'
                    marker = f.root / 'counterfeit-executed'
                    for path in (uv, python):
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.touch()
                        path.chmod(0o755)
                    uv.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\n'
                                  'if [ "$1" = --version ]; then printf "uv 0.12.5\\n"; fi\nexit 0\n')
                    probe = approval.canonical({'prefix': str(clone / '.venv'),
                                                'base_prefix': str(python.parent.parent),
                                                'base_executable': str(python), 'version': '3.12.14'}).decode().strip()
                    python.write_text('#!/bin/sh\ntouch "' + str(marker) + '"\ncase "$*" in\n'
                                      '*json,sys,platform*) printf \'%s\\n\' \'' + probe + '\';;\n'
                                      '*platform.python_version*) printf "3.12.14\\n";;\n'
                                      '*) exit 0;;\nesac\n')
                    venv = clone / '.venv/bin'
                    venv.mkdir(parents=True)
                    (venv / 'python').symlink_to(python)
                if resumed:
                    f.stop_at('before_bootstrap')
                    counterfeit('before_bootstrap')
                code, output = f.cli('resume' if resumed else 'integrate', gate=None,
                                     checkpoint=None if resumed else counterfeit)
                self.assertEqual(code, 1, output)
                self.assertIn('ENVIRONMENT_UNTRUSTED', output)
                self.assertFalse((f.root / 'counterfeit-executed').exists())
                self.assertEqual(f.ref(), f.main)
                self.assertEqual(f.push_count(approval.MAIN), 0)
                self.assertEqual(list((f.root / 'managed/evidence').glob('bootstrap-*.log')), [])
                (f.root / 'counterfeit-facts.json').write_bytes(approval.canonical({
                    'resumed': resumed, 'output': output, 'main_before': f.main, 'main_after': f.ref(),
                    'main_pushes': f.push_count(approval.MAIN), 'counterfeit_executed': False}))

    def test_environment_replacements_invalidate_invocation_proof_before_execution(self):
        # Fast fault tests: synthetic bootstrap output, real in-memory snapshot
        # checks and controller/Git pipeline. The independent smoke runs the
        # original bootstrap, probes and strict suite without these seams.
        for point in ('after_bootstrap', 'before_strict', 'after_strict', 'before_main_push'):
            for relative in ('.tools/uv/0.12.5/uv', '.tools/python/bin/python3.12',
                             '.venv/lib/site-packages/sitecustomize.py'):
                with self.subTest(point=point, relative=relative):
                    f = self.fixture()
                    original_log = integration.Integration.log_command
                    def synthetic(runner, kind, argv, env):
                        if kind == 'bootstrap':
                            for name in ('.tools/uv/0.12.5/uv', '.tools/python/bin/python3.12',
                                         '.venv/lib/site-packages/sitecustomize.py'):
                                path = runner.clone / name
                                path.parent.mkdir(parents=True, exist_ok=True)
                                path.write_bytes(b'fresh synthetic bootstrap input\n')
                        return original_log(runner, kind, ['/bin/sh', '-c', 'printf "synthetic fault test only\\n"'], env)
                    def replace(name):
                        if name == point:
                            path = f.root / 'managed/clone' / relative
                            path.write_bytes(b'replaced environment\n')
                    with mock.patch.object(integration.Integration, 'log_command', synthetic), \
                         mock.patch.object(integration.Integration, 'verify_environment',
                                           lambda runner, env: runner.check_environment_proof()):
                        code, output = f.cli(gate=None, checkpoint=replace)
                    self.assertEqual(code, 1, output)
                    self.assertIn('ENVIRONMENT_CHANGED', output)
                    self.assertEqual(f.ref(), f.main)
                    self.assertEqual(f.push_count(approval.MAIN), 0)

    def test_real_content_conflict_stops_and_keeps_both_refs(self):
        f = self.fixture(conflict=True)
        code, output = f.cli()
        self.assertEqual(code, 1, output)
        self.assertEqual(f.ref(), f.main)
        self.assertEqual(f.ref(approval.FEATURE), f.accepted)
        self.assertEqual(f.calls, [])
        self.assertEqual(f.push_count(approval.MAIN), 0)
        self.assertEqual(sum(item['args'][0] == 'merge' for item in f.operations), 0)

    def test_fetch_push_url_hooks_and_dangerous_config_stop_before_push(self):
        for kind in ('fetch-url', 'push-url', 'hook', 'include', 'ssh-command', 'url-rewrite'):
            with self.subTest(kind=kind):
                f = self.fixture()
                f.stop_at('after_fetch')
                clone = f.root / 'managed/clone'
                if kind == 'hook':
                    path = clone / '.git/hooks/pre-push'
                    path.parent.mkdir(exist_ok=True)
                    path.write_text('#!/bin/sh\ntouch "' + str(f.root / 'hook-executed') + '"\n')
                    path.chmod(0o755)
                else:
                    key = {'fetch-url': 'remote.origin.url', 'push-url': 'remote.origin.pushurl',
                           'include': 'include.path', 'ssh-command': 'core.sshCommand',
                           'url-rewrite': 'url.file:///foreign.insteadOf'}[kind]
                    integration.git(clone, 'config', key, str(f.root / 'foreign'))
                self.assertEqual(f.cli('resume')[0], 1)
                self.assertEqual(f.ref(), f.main)
                self.assertIsNone(f.ref(approval.FEATURE))
                self.assertEqual(f.push_count(approval.FEATURE), 0)
                self.assertEqual(f.push_count(approval.MAIN), 0)
                self.assertFalse((f.root / 'hook-executed').exists())

    def test_nonzero_push_after_side_effect_is_reconciled_exactly_once(self):
        for ref in (approval.FEATURE, approval.MAIN):
            with self.subTest(ref=ref):
                f = self.fixture()
                actual_run = integration.run_git
                def uncertain(repo, *args, **kwargs):
                    result = actual_run(repo, *args, **kwargs)
                    if args[0] == 'push' and args[-1].endswith(':' + ref):
                        self.assertEqual(result.returncode, 0)
                        return subprocess.CompletedProcess(result.args, 75, result.stdout, b'transport failed after update')
                    return result
                with mock.patch.object(integration, 'run_git', side_effect=uncertain):
                    self.assertEqual(f.cli()[0], 0)
                after = f.ref()
                self.assertNotEqual(after, f.main)
                self.assertEqual(f.ref(approval.FEATURE), f.accepted)
                self.assertEqual(f.push_count(approval.FEATURE), 1)
                self.assertEqual(f.push_count(approval.MAIN), 1)
                self.assertEqual(f.cli('resume')[0], 1)
                self.assertEqual(f.ref(), after)
                self.assertEqual(f.push_count(approval.FEATURE), 1)
                self.assertEqual(f.push_count(approval.MAIN), 1)

    def test_lost_feature_receipt_reconciles_without_duplicate_push(self):
        f = self.fixture()
        f.stop_at('after_feature_push')
        self.assertEqual(f.ref(approval.FEATURE), f.accepted)
        self.assertEqual(f.push_count(approval.FEATURE), 1)
        self.assertEqual(f.cli('resume')[0], 0)
        self.assertEqual(f.push_count(approval.FEATURE), 1)
        self.assertEqual(f.push_count(approval.MAIN), 1)
        self.assertNotEqual(f.ref(), f.main)

    def test_remote_main_advance_before_feature_push_stops_without_side_effect(self):
        f = self.fixture()
        f.stop_at('after_fetch')
        integration.git(f.seed, 'checkout', '--detach', f.main)
        (f.seed / 'remote-change.txt').write_text('another writer\n')
        integration.git(f.seed, 'add', '--all')
        integration.git(f.seed, 'commit', '-m', 'remote main drift')
        drift = integration.git(f.seed, 'rev-parse', 'HEAD')
        integration.git(f.seed, 'push', 'origin', drift + ':' + approval.MAIN)
        code, output = f.cli('resume')
        self.assertEqual(code, 1)
        self.assertIn('REMOTE_DRIFT', output)
        self.assertEqual(f.ref(), drift)
        self.assertIsNone(f.ref(approval.FEATURE))
        self.assertEqual(f.operations, [])

    def test_fixture_gate_identity_view_denies_network_and_preserves_real_urls(self):
        f = self.fixture()
        f.stop_at('before_clone')
        runner = integration.Integration(f.policy)
        env = runner.gate_environment()
        self.assertEqual(env['UV_NO_CONFIG'], '1')
        actual = integration.git(f.source, 'remote', 'get-url', 'origin')
        self.assertEqual(actual, str(f.remote))
        visible = subprocess.run([integration.GIT, '-C', str(f.source), 'remote', 'get-url', 'origin'],
                                 env=env, capture_output=True, check=True)
        self.assertEqual(visible.stdout.decode().strip(), approval.ORIGINS[1])
        denied = subprocess.run([integration.GIT, 'ls-remote', approval.ORIGINS[1]],
                                env=env, capture_output=True, check=False)
        self.assertNotEqual(denied.returncode, 0)
        self.assertIn(b'transport', denied.stderr)
        self.assertEqual(f.ref(), f.main)
        self.assertIsNone(f.ref(approval.FEATURE))


if __name__ == '__main__':
    unittest.main()
