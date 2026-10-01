"""C1 retained Downloads fixtures: real signatures/Git/ZIP, synthetic App only.

No fixture tests run the formal build or a packaged executable. Build is blocked
pending an accepted stage-checkpoint interface; this is an explicit coverage gap.
"""
from __future__ import annotations

import contextlib
import copy
import io
import os
import plistlib
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


class Fixture:
    def __init__(self, root):
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

    def test_source_receipt_does_not_use_journal_complete_and_build_is_explicitly_blocked(self):
        f = Fixture(self.root)
        (f.managed / 'journal.json').write_text('{"state":"COMPLETE","gate":"PASS"}\n')
        actual, _ = artifact.accepted_source(f.policy, f.auth, remote=True)
        self.assertEqual(actual['source_commit'], f.final)
        before = snapshot(f.root)
        result, text = f.cli('build')
        self.assertEqual(result, 1)
        self.assertIn('BUILD_PROTOCOL_REVIEW_REQUIRED', text)
        self.assertEqual(snapshot(f.root), before)
        self.assertFalse((f.root / 'workflow').exists())

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
