"""C1 retained Downloads fixtures: real signatures/Git/ZIP, synthetic App only.

The actual controller and original shell entry run signed synthetic children.
No formal build or packaged executable is run.
"""
from __future__ import annotations

import contextlib
import copy
import io
import os
import plistlib
import shutil
import shlex
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
import release_artifact as artifact
import release_human_gate as human
import release_integration as integration
import release_workflow as workflow
import release_workflow_state as state
import release_identity as identity
import build_release_zip as release_zip


def retained_root():
    temporary = Path(tempfile.gettempdir())
    for candidate in (temporary, *temporary.parents):
        if candidate.name.startswith('rel1c1-fixtures.') and candidate.is_relative_to(approval.downloads()):
            approval.inspect_path(candidate, owner=os.getuid(), mode=0o700, directory=True)
            return candidate
    return Path(tempfile.mkdtemp(prefix='rel1c1-fixtures.', dir=approval.downloads()))


def synthetic_stages():
    python_stage = r'''#!/bin/bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p .tools/uv/0.12.5 .tools/python/bin .tools/cache .venv/bin
cat > .tools/python/bin/python <<'PYTHON'
#!/bin/bash
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
printf '{"prefix":"%s/.venv","base_prefix":"%s/.tools/python","base_executable":"%s/.tools/python/bin/python","version":"3.12.14"}\n' "$ROOT_DIR" "$ROOT_DIR" "$ROOT_DIR"
PYTHON
cat > .tools/uv/0.12.5/uv <<'UV'
#!/bin/bash
if [[ "${1:-}" == --version ]]; then printf 'uv 0.12.5 synthetic\n'; fi
UV
chmod 755 .tools/python/bin/python .tools/uv/0.12.5/uv
ln -s ../../.tools/python/bin/python .venv/bin/python
printf 'SYNTHETIC acquisition; no formal build\n'
'''
    runtime_stage = r'''#!/bin/bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
mkdir -p .tools/cmake/4.2.3/CMake.app/Contents/bin external/whisper.cpp/build/bin
printf 'SYNTHETIC pinned Runtime fixture\n' > external/whisper.cpp/fixture-source
printf 'SYNTHETIC Runtime; never execute\n' > external/whisper.cpp/build/bin/whisper-cli
printf '#!/bin/bash\nexit 0\n' > .tools/cmake/4.2.3/CMake.app/Contents/bin/cmake
chmod 755 .tools/cmake/4.2.3/CMake.app/Contents/bin/cmake
'''
    app_stage = r'''#!/bin/bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"
SYNTHETIC_TEST_PYTHON -B - <<'APP'
from pathlib import Path
import sys, plistlib, json
sys.path.insert(0, str(Path.cwd() / 'scripts'))
import release_identity
root = Path.cwd()
app = root / 'dist/ClassroomTranscriber.app'
executable = app / 'Contents/MacOS/ClassroomTranscriber'
executable.parent.mkdir(parents=True)
executable.write_bytes(b'SYNTHETIC APP - DO NOT EXECUTE\n')
executable.chmod(0o755)
resources = app / 'Contents/Resources'
resources.mkdir()
(app / 'Contents/Frameworks').mkdir()
(app / 'Contents/Frameworks/fixture').write_bytes(b'synthetic framework\n')
(resources / 'fixture').symlink_to('../Frameworks/fixture')
manifest = json.loads((root / 'packaging/runtime_manifest.json').read_text())
icon = manifest['frozen']['app_icon']['bundle_filename']
(resources / icon).write_bytes(b'icns' + (12).to_bytes(4, 'big') + b'TEST')
(app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
    'CFBundleIdentifier': 'com.local.classroomtranscriber',
    'CFBundleShortVersionString': '1.1.0', 'CFBundleVersion': '1.1.0', 'CFBundleIconFile': icon}))
(root / 'build/app-icon').mkdir(parents=True)
(root / 'build/app-icon' / icon).write_bytes((resources / icon).read_bytes())
commit = release_identity.git_output(root, 'rev-parse', 'HEAD')
release_identity.write_build_provenance(root / 'dist/ClassroomTranscriber.app.provenance.json',
                                        app, commit, repo_root=root)
APP
'''.replace('SYNTHETIC_TEST_PYTHON', shlex.quote(sys.executable))
    return {'bootstrap_python_env.sh': python_stage, 'bootstrap_whisper_runtime.sh': runtime_stage,
            'build_macos.sh': app_stage}


def synthetic_runtime(controller):
    assert (controller.workspace / 'external/whisper.cpp/fixture-source').read_bytes() == b'SYNTHETIC pinned Runtime fixture\n'


def synthetic_controller(fixture, checkpoint=None):
    calls = []
    def verifier(app, manifest):
        calls.append(str(app))
        assert manifest == release_zip.load_manifest(fixture.source / 'packaging/runtime_manifest.json')
    value = workflow.BuildController(fixture.policy, fixture_checkpoint=checkpoint,
                                    fixture_runtime=synthetic_runtime, fixture_verifier=verifier)
    value.fixture_verifier_calls = calls
    return value


class Fixture:
    def __init__(self, root, *, synthetic=False, stage_overrides=None):
        self.root = root / ('case-' + uuid.uuid4().hex)
        self.root.mkdir(mode=0o700)
        self.policy = approval.WorkflowPolicy(self.root)
        self.source = self.root / 'source'
        self.source.mkdir(mode=0o700)
        self.remote = self.root / 'remote.git'
        integration.git(None, 'init', '--bare', '--template=', str(self.remote))
        integration.git(self.remote, 'symbolic-ref', 'HEAD', approval.MAIN)
        integration.git(None, 'init', '--template=', '--initial-branch=main', str(self.source))
        integration.git(self.source, 'remote', 'add', 'origin', str(self.remote))
        for relative in (*approval.WORKFLOW_REQUIRED_TOOLS, '.gitignore'):
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / relative, target)
        if synthetic:
            for name, text in {**synthetic_stages(), **(stage_overrides or {})}.items():
                (self.source / 'scripts' / name).write_text(text)
        self.baseline = self.commit('fixture baseline')
        (self.source / 'main-only.txt').write_text('main only\n')
        self.main = self.commit('fixture main')
        integration.git(self.source, 'push', 'origin', self.main + ':' + approval.MAIN)
        integration.git(self.source, 'checkout', '-b', approval.FEATURE.removeprefix('refs/heads/'), self.baseline)
        (self.source / 'feature-only.txt').write_text('independently reviewed fixture\n')
        self.accepted = self.commit('fixture implementation')
        integration.git(self.source, 'push', 'origin', self.accepted + ':' + approval.FEATURE)
        self.policy.root.mkdir(mode=0o700)
        for name in approval.WORKFLOW_CONTRACTS:
            (self.root / (name + '.md')).write_text('C1 independent fixture contract ' + name + '\n')
        self.key = self.root / 'fixture-approval-key'
        subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(self.key)],
                       capture_output=True, check=True)
        public = (self.root / 'fixture-approval-key.pub').read_text().split()
        self.write('allowed_signers', (self.policy.signer + ' ' + ' '.join(public[:2]) + '\n').encode())
        for kind, scope in (('review', 'step1-final-independent-review'), ('human', 'step1-final-owner-integration')):
            self.write(kind + '.json', approval.canonical({'schema_version': 1, 'accepted_commit': self.accepted,
                                                         'scope': scope, 'reference': 'fixture-' + kind}))
        self.config = {'schema_version': 1, 'epoch': 1,
                       'entry_sha256': {p: approval.digest((self.source / p).read_bytes())
                                        for p in approval.WORKFLOW_CONTROL_TOOLS},
                       'review_sha256': approval.digest(self.policy.trust_file('review.json')),
                       'human_sha256': approval.digest(self.policy.trust_file('human.json'))}
        self.write('workflow-config.json', approval.canonical(self.config))
        self.write('revoked.json', approval.canonical({'schema_version': 1, 'ids': []}))
        self.payload = {
            'schema_version': 1, 'id': 'workflow-' + uuid.uuid4().hex,
            'purpose': approval.WORKFLOW_PURPOSE, 'policy': self.policy.namespace,
            'config_epoch': 1, 'config_sha256': approval.digest(self.policy.trust_file('workflow-config.json')),
            'signers_sha256': approval.digest(self.policy.trust_file('allowed_signers')),
            'accepted_commit': self.accepted,
            'tools': {p: approval.digest((self.source / p).read_bytes()) for p in approval.WORKFLOW_REQUIRED_TOOLS},
            'contracts': {k: approval.digest(p.read_bytes()) for k, p in self.policy.contracts.items()},
            'review': {'locator': str(self.policy.root / 'review.json'), 'sha256': self.config['review_sha256']},
            'human': {'locator': str(self.policy.root / 'human.json'), 'sha256': self.config['human_sha256']},
            'repository': approval.REPOSITORY, 'origin': str(self.remote), 'main_ref': approval.MAIN,
            'feature_ref': approval.FEATURE, 'main': self.main, 'feature_prior': None, 'baseline': self.baseline,
            'implementation': str(self.source), 'managed': str(self.root / 'managed'),
            'workflow': str(self.root / 'workflow'), 'uid': os.getuid(),
        }
        self.sign('workflow-approval', self.payload)
        self.auth = approval.authorize_workflow(self.policy)
        self.managed = self.root / 'managed'
        self.managed.mkdir(mode=0o700)
        self.clone = self.managed / 'clone'
        integration.git(None, 'clone', '--no-local', '--no-hardlinks', '--no-tags', '--template=',
                        str(self.remote), str(self.clone))
        self.clone.chmod(0o700)
        integration.git(self.clone, 'checkout', '--detach', self.main)
        integration.git(self.clone, 'merge', '--no-ff', '--no-edit', '-m', 'fixture accepted integration', self.accepted)
        self.final = integration.git(self.clone, 'rev-parse', 'HEAD')
        self.tree = integration.git(self.clone, 'rev-parse', 'HEAD^{tree}')
        integration.git(self.clone, 'push', 'origin', self.final + ':' + approval.MAIN)
        self.write('integration-evidence.json', approval.canonical({'fixture_only': True, 'source': self.final,
                                                                  'decision': 'independent-fixture-integration'}))
        self.integration_receipt = {**self.common('integration'), 'decision': 'ACCEPT',
            'source_repository': str(self.clone), 'source_commit': self.final, 'source_tree': self.tree,
            'parents': [self.main, self.accepted], 'baseline': self.baseline,
            'main_ref': approval.MAIN, 'feature_ref': approval.FEATURE,
            'final_main': self.final, 'final_feature': self.accepted,
            'evidence_sha256': approval.digest(self.policy.trust_file('integration-evidence.json'))}
        self.sign('integration', self.integration_receipt)
        self.calls = []

    def commit(self, message):
        integration.git(self.source, 'add', '--all')
        integration.git(self.source, 'commit', '-m', message)
        return integration.git(self.source, 'rev-parse', 'HEAD')

    def write(self, name, data):
        path = self.policy.root / name
        path.write_bytes(data)
        path.chmod(0o600)

    def sign(self, kind, payload, *, key=None, namespace=None):
        self.write(kind + '.json', approval.canonical(payload))
        signature = self.policy.root / (kind + '.json.sig')
        if signature.exists():
            signature.unlink()
        default = self.policy.namespace if kind == 'workflow-approval' else self.policy.namespace + '-' + kind
        subprocess.run(['/usr/bin/ssh-keygen', '-Y', 'sign', '-f', str(key or self.key), '-n', namespace or default,
                        str(self.policy.root / (kind + '.json'))], capture_output=True, check=True)
        signature.chmod(0o600)

    def common(self, kind):
        return {'schema_version': 1, 'id': kind + '-' + uuid.uuid4().hex,
                'purpose': approval.RECEIPT_PURPOSES[kind], 'policy': self.policy.namespace,
                'config_epoch': 1, 'config_sha256': self.payload['config_sha256'],
                'signers_sha256': self.payload['signers_sha256'], 'trust_sha256': self.auth.trust_sha256,
                'authorization_sha256': self.auth.sha256, 'repository': approval.REPOSITORY,
                'version': '1.1.0', 'accepted_commit': self.accepted, 'tools': self.payload['tools'],
                'contracts': self.payload['contracts'], 'decision_reference': 'external-fixture-' + kind}

    def cli(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = workflow._run(list(argv), self.policy)
        return result, output.getvalue()

    def make_artifact(self):
        source, checksum = artifact.accepted_source(self.policy, self.auth, remote=True)
        store = state.StateStore(self.auth)
        value = store.new_attempt(store.create())
        attempt = value['attempt']
        workspace = store.root / 'attempts' / attempt / 'source'
        integration.git(None, 'clone', '--no-local', '--no-hardlinks', '--no-tags', '--template=',
                        str(self.remote), str(workspace))
        workspace.chmod(0o700)
        integration.git(workspace, 'checkout', '--detach', self.final)
        app = workspace / 'dist' / artifact.APP
        executable = app / 'Contents/MacOS/ClassroomTranscriber'
        executable.parent.mkdir(parents=True)
        executable.write_bytes(b'SYNTHETIC APP - DO NOT EXECUTE\n')
        executable.chmod(0o755)
        resources = app / 'Contents/Resources'
        resources.mkdir()
        (app / 'Contents/Frameworks').mkdir()
        (app / 'Contents/Frameworks/fixture').write_bytes(b'synthetic framework\n')
        (resources / 'fixture').symlink_to('../Frameworks/fixture')
        manifest = release_zip.load_manifest(workspace / 'packaging/runtime_manifest.json')
        (resources / manifest['frozen']['app_icon']['bundle_filename']).write_bytes(
            b'icns' + (12).to_bytes(4, 'big') + b'TEST')
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({
            'CFBundleIdentifier': artifact.BUNDLE_ID, 'CFBundleShortVersionString': '1.1.0',
            'CFBundleVersion': '1.1.0', 'CFBundleIconFile': manifest['frozen']['app_icon']['bundle_filename']}))
        provenance = workspace / 'dist' / (artifact.APP + '.provenance.json')
        identity.write_build_provenance(provenance, app, self.final, repo_root=workspace)
        evidence = {}
        for kind in ('build', 'package'):
            path = store.root / 'evidence' / attempt / (kind + '.log')
            path.write_text('SYNTHETIC fixture ' + kind + '; no formal build or Runtime executable\n')
            path.chmod(0o600)
            evidence[kind] = {'path': str(path), 'sha256': approval.digest(path.read_bytes())}
        def synthetic_verifier(path, supplied):
            self.calls.append(('synthetic-verifier', str(path)))
            self.assert_manifest = supplied == manifest
        with contextlib.redirect_stdout(io.StringIO()):
            metadata = release_zip.create_release_zip(
                version='1.1.0', app_path=app, artifact_path=store.root / 'artifacts' / attempt / artifact.ASSET,
                extraction_dir=store.root / 'human' / attempt, task_root=store.root,
                build_provenance_path=provenance, manifest=manifest, commit=self.final,
                repo_root=workspace, verifier=synthetic_verifier)
        metadata.extracted_app_path.parent.chmod(0o700)
        self.artifact = artifact.fix_metadata(metadata, auth=self.auth, source=source, receipt_sha256=checksum,
                                              attempt=attempt, workspace=workspace, evidence=evidence)
        self.metadata = metadata
        self.workspace = workspace
        self.store = store
        self.state = store.change(value, state='ARTIFACT', intent=None, artifact=self.artifact)
        self.human_receipt = {**self.common('artifact-human'), 'decision': 'PASS',
                              'integration_receipt_sha256': checksum, 'artifact': self.artifact}
        self.sign('artifact-human', self.human_receipt)
        return self.artifact


def snapshot(root):
    result = {}
    for path in (root, *sorted(root.rglob('*'))):
        info = path.lstat()
        data = os.readlink(path) if path.is_symlink() else (
            approval.digest(path.read_bytes()) if path.is_file() else None)
        result[str(path.relative_to(root))] = (info.st_ino, info.st_mode, info.st_mtime_ns, info.st_ctime_ns, data)
    return result


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = retained_root()

    def test_actual_controller_original_entry_and_zip_chain_success_with_synthetic_children(self):
        f = Fixture(self.root, synthetic=True)
        (f.managed / 'journal.json').write_text('{"state":"COMPLETE","gate":"PASS"}\n')
        controller = synthetic_controller(f)
        self.assertEqual(controller.execute(), 'ARTIFACT_RECORDED_C1_ONLY')
        self.assertEqual(controller.events, list(workflow.EVENTS))
        value = controller.store.inspect()
        self.assertEqual(value['state'], 'ARTIFACT')
        self.assertEqual(len(controller.fixture_verifier_calls), 2)
        self.assertEqual(controller.fixture_verifier_calls[0], str(controller.workspace / 'dist' / artifact.APP))
        self.assertEqual(controller.fixture_verifier_calls[1], str(Path(value['artifact']['extraction_path']) / artifact.APP))
        artifact.validate_artifact(value['artifact'], controller.auth, controller.source, controller.source_hash)
        # No receipt is fabricated by the controller. The independent fixture
        # signer supplies the exact decision only after the retained tuple exists.
        f.sign('artifact-human', {**f.common('artifact-human'), 'decision': 'PASS',
            'integration_receipt_sha256': controller.source_hash, 'artifact': value['artifact']})
        self.assertEqual(f.cli('human-gate'), (0, 'release-workflow: HUMAN_RECORDED_C1_ONLY\n'))
        before = snapshot(f.root)
        with self.assertRaises(approval.Stop):
            synthetic_controller(f).execute()
        self.assertEqual(snapshot(f.root), before)

    def test_controller_denies_mutated_source_interpreter_helpers_and_cache_before_runtime(self):
        for relative in ('scripts/build_macos.sh', 'model_integrity.py',
                         '.tools/python/bin/python', '.tools/cache/counterfeit.py'):
            f = Fixture(self.root, synthetic=True)
            def corrupt(controller, event):
                if event == 'before:runtime':
                    path = controller.workspace / relative
                    if not relative.startswith('.tools/'):
                        integration.git(controller.workspace, 'update-index', '--assume-unchanged', relative)
                    path.write_bytes(b'COUNTERFEIT INPUT - NEVER EXECUTE\n')
            controller = synthetic_controller(f, corrupt)
            with self.subTest(relative=relative), self.assertRaises(approval.Stop):
                controller.execute()
            self.assertEqual(controller.events, ['before:python', 'after:python'])
            self.assertFalse((controller.workspace / 'external').exists())
            self.assertEqual(controller.store.inspect()['state'], 'BUILDING')

    def test_actual_controller_malformed_duplicate_order_crash_and_unexpected_creations(self):
        base = synthetic_stages()['bootstrap_python_env.sh']
        for suffix in ("printf 'bad\\n' >&\"$REL1C_EVENT_FD\"\n",
                       "printf 'before:python\\n' >&\"$REL1C_EVENT_FD\"\n",
                       "printf 'before:app\\n' >&\"$REL1C_EVENT_FD\"\n",
                       'exit 19\n', 'mkdir -p .tools/counterfeit; touch .tools/counterfeit/code\n'):
            f = Fixture(self.root, synthetic=True, stage_overrides={'bootstrap_python_env.sh': base + suffix})
            controller = synthetic_controller(f)
            with self.subTest(suffix=suffix), self.assertRaises(approval.Stop):
                controller.execute()
            self.assertEqual(controller.events, ['before:python'])
            self.assertFalse((controller.workspace / 'external').exists())
            self.assertEqual(controller.store.inspect()['state'], 'BUILDING')

    def test_package_failure_and_parent_interruption_retire_without_reexecution_then_fresh_retry(self):
        for kind in ('package', 'interrupt'):
            f = Fixture(self.root, synthetic=True)
            def interrupt(controller, event):
                if kind == 'interrupt' and event == 'after:runtime':
                    raise KeyboardInterrupt()
            controller = synthetic_controller(f, interrupt)
            if kind == 'package':
                controller.fixture_verifier = lambda *_: (_ for _ in ()).throw(RuntimeError('SYNTHETIC PACKAGE FAIL'))
            with self.subTest(kind=kind), self.assertRaises((RuntimeError, KeyboardInterrupt)):
                controller.execute()
            old = controller.store.inspect()
            self.assertEqual(old['state'], 'PACKAGING' if kind == 'package' else 'BUILDING')
            retained = snapshot(controller.store.root / 'attempts' / old['attempt'])
            before_log = (controller.store.root / 'evidence' / old['attempt'] / 'build.log').read_bytes()
            self.assertEqual(f.cli('resume'), (0, 'release-workflow: RECOVERY_REVIEW_REQUIRED\n'))
            retry = synthetic_controller(f)
            self.assertEqual(retry.execute(), 'ARTIFACT_RECORDED_C1_ONLY')
            self.assertNotEqual(retry.store.inspect()['attempt'], old['attempt'])
            self.assertEqual(snapshot(controller.store.root / 'attempts' / old['attempt']), retained)
            self.assertEqual((controller.store.root / 'evidence' / old['attempt'] / 'build.log').read_bytes(), before_log)

    def test_production_preimport_refusal_does_not_execute_path_substituted_code(self):
        root = Path(tempfile.mkdtemp(prefix='preimport-', dir=self.root))
        scripts = root / 'scripts'
        scripts.mkdir()
        shutil.copy2(REPO / 'scripts/release_workflow.py', scripts / 'release_workflow.py')
        marker = root / 'COUNTERFEIT_EXECUTED'
        payload = 'from pathlib import Path; Path(' + repr(str(marker)) + ').write_text("executed")\n'
        for name in ('release_approval.py', 'release_identity.py', 'build_release_zip.py', 'json.py'):
            (scripts / name).write_text(payload)
            (root / name).write_text(payload)
        result = subprocess.run([sys.executable, '-B', str(scripts / 'release_workflow.py'), 'build'],
                                env={**os.environ, 'PYTHONPATH': str(root)}, capture_output=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b'TRUST_UNAVAILABLE', result.stderr)
        self.assertFalse(marker.exists())

    def test_missing_independent_source_acceptance_refuses_build_without_process(self):
        f = Fixture(self.root)
        (f.policy.root / 'integration.json').unlink()
        with mock.patch.object(subprocess, 'Popen', wraps=subprocess.Popen) as calls:
            result, _ = f.cli('build')
        self.assertEqual(result, 1)
        self.assertTrue(all('bootstrap' not in str(call) for call in calls.call_args_list))
        self.assertFalse((f.root / 'workflow').exists())

    def test_read_only_missing_and_advanced_status_does_not_accept_decisions(self):
        f = Fixture(self.root)
        for _ in range(2):
            before = snapshot(f.root)
            self.assertEqual(f.cli('status'), (0, 'release-workflow: MISSING\n'))
            self.assertEqual(snapshot(f.root), before)
        f.make_artifact()
        (f.policy.root / 'artifact-human.json').unlink()
        (f.policy.root / 'integration.json').unlink()
        for _ in range(2):
            before = snapshot(f.root)
            self.assertEqual(f.cli('status'), (0, 'release-workflow: ARTIFACT_RECORDED_UNVERIFIED\n'))
            self.assertEqual(snapshot(f.root), before)

    def test_real_fixture_human_pass_records_only_c1_then_receipt_loss_stops(self):
        f = Fixture(self.root)
        f.make_artifact()
        self.assertEqual(f.cli('human-gate'), (0, 'release-workflow: HUMAN_RECORDED_C1_ONLY\n'))
        self.assertEqual(f.store.inspect()['state'], 'HUMAN_RECORDED')
        before = snapshot(f.root)
        self.assertEqual(f.cli('human-gate'), (0, 'release-workflow: HUMAN_RECORDED_C1_ONLY\n'))
        self.assertEqual(snapshot(f.root), before)
        (f.policy.root / 'artifact-human.json').unlink()
        self.assertEqual(f.cli('human-gate')[0], 1)
        for command in ('tag', 'draft', 'upload', 'publish'):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                workflow.build_parser().parse_args([command])

    def test_unknown_build_or_package_outcome_does_not_reexecute_or_repair(self):
        for stage, intent in (('BUILDING', 'BUILD'), ('BUILT', None), ('PACKAGING', 'PACKAGE')):
            f = Fixture(self.root)
            store = state.StateStore(f.auth)
            value = store.new_attempt(store.create())
            store.change(value, state=stage, intent=intent)
            before = snapshot(f.root)
            self.assertIn('RECOVERY_REVIEW_REQUIRED', f.cli('resume')[1])
            retired = store.inspect()
            self.assertEqual(retired['state'], 'REVIEW_REQUIRED')
            before = snapshot(f.root)
            self.assertIn('RECOVERY_REVIEW_REQUIRED', f.cli('resume')[1])
            self.assertEqual(snapshot(f.root), before)

    def test_production_cli_refuses_missing_trust_and_every_override_without_echo(self):
        for command in ('status', 'build', 'resume', 'human-gate'):
            result = subprocess.run([str(REPO / '.venv/bin/python'), '-B', str(REPO / 'scripts/release_workflow.py'),
                                     command], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn('TRUST_UNAVAILABLE', result.stderr)
        for option in ('--fixture', '--trust-root', '--signer', '--approval', '--source', '--human-pass'):
            result = subprocess.run([str(REPO / '.venv/bin/python'), '-B', str(REPO / 'scripts/release_workflow.py'),
                                     'build', option, 'PRIVATE_MARKER'], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('PRIVATE_MARKER', result.stderr + result.stdout)


if __name__ == '__main__':
    unittest.main()
