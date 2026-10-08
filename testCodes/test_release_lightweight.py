"""Lightweight local decisions/real local Git, original checkpoints/ZIP, fake gh.

No signing keys or production credentials. Runtime/App and the fast integration
gate are synthetic; they never establish formal-build or Human acceptance.
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

from testCodes.test_release_workflow import (Fixture as BaseFixture, REPO, synthetic_stages,
    synthetic_controller, snapshot, approval, artifact, integration, workflow)
from testCodes.test_release_publication import FAKE_GH
import release_lightweight as lightweight
import release_lightweight_approval as local
import release_pipeline as pipeline
import release_publication as publication
import release_publication_state as publication_state


class Fixture(BaseFixture):
    """Reuse only data/ZIP helpers; no old Policy, signatures or keys are made."""
    def __init__(self, root, *, integrated=True, native_python=False):
        self.root = root / ('case-' + uuid.uuid4().hex)
        self.root.mkdir(mode=0o700)
        decisions = self.root / 'decisions'
        decisions.mkdir(mode=0o700)
        self.policy = approval.LightweightPolicy(decisions / 'approval.json', self.root)
        self.source, self.remote = self.root / 'source', self.root / 'remote.git'
        self.source.mkdir(mode=0o700)
        integration.git(None, 'init', '--bare', '--template=', str(self.remote))
        integration.git(self.remote, 'symbolic-ref', 'HEAD', approval.MAIN)
        integration.git(None, 'init', '--template=', '--initial-branch=main', str(self.source))
        integration.git(self.source, 'remote', 'add', 'origin', str(self.remote))
        paths = list(approval.LIGHTWEIGHT_REQUIRED_TOOLS) + ['.gitignore']
        if native_python:
            paths += [p for p in integration.run_git(REPO, 'ls-files', '-z').stdout.decode().split('\0') if p]
        for relative in set(paths):
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / relative, target)
        stages = synthetic_stages()
        if native_python:
            stages['bootstrap_python_env.sh'] = (REPO / 'scripts/bootstrap_python_env.sh').read_text()
        for name, text in stages.items():
            (self.source / 'scripts' / name).write_text(text)
        self.baseline = self.commit('Lightweight fixture baseline')
        (self.source / 'main-only.txt').write_text('main preserved\n')
        self.main = self.commit('Fixture independent main')
        integration.git(self.source, 'push', 'origin', self.main + ':' + approval.MAIN)
        integration.git(self.source, 'checkout', '-b', approval.FEATURE.removeprefix('refs/heads/'), self.baseline)
        (self.source / 'feature-only.txt').write_text('accepted feature preserved\n')
        self.accepted = self.commit('Fixture independent implementation')
        for name, path in self.policy.contracts.items():
            path.write_text('Lightweight fixture contract ' + name + '\n')
        self.payload = {'schema_version': 1, 'mode': 'lightweight', 'id': 'lightweight-' + uuid.uuid4().hex,
            'accepted_commit': self.accepted,
            'tools': {p: approval.digest((self.source / p).read_bytes()) for p in approval.LIGHTWEIGHT_REQUIRED_TOOLS},
            'contracts': {k: approval.digest(p.read_bytes()) for k, p in self.policy.contracts.items()},
            'reviewer_reference': 'fixture-independent-review',
            'integration_authorization_reference': 'fixture-owner-scope',
            'repository': approval.REPOSITORY, 'origin': str(self.remote), 'main_ref': approval.MAIN,
            'feature_ref': approval.FEATURE, 'main': self.main, 'feature_prior': None, 'baseline': self.baseline,
            'implementation': str(self.source), 'managed': str(self.root / 'managed'),
            'workflow': str(self.root / 'workflow'), 'uid': os.getuid()}
        self.write('approval.json', approval.canonical(self.payload))
        self.auth = approval.authorize_workflow(self.policy)
        self.managed = self.root / 'managed'
        self.calls = []
        reader = self.root / 'git-reader.config'
        reader.write_bytes(integration.fixture_reader_config(str(self.remote)))
        reader.chmod(0o600)
        if not integrated:
            return
        integration.git(self.source, 'push', 'origin', self.accepted + ':' + approval.FEATURE)
        self.managed.mkdir(mode=0o700)
        self.clone = self.managed / 'clone'
        integration.git(None, 'clone', '--no-local', '--no-hardlinks', '--no-tags', '--template=',
                        str(self.remote), str(self.clone))
        self.clone.chmod(0o700)
        integration.git(self.clone, 'checkout', '--detach', self.main)
        integration.git(self.clone, 'merge', '--no-ff', '--no-edit', '-m', 'Fixture independent integration', self.accepted)
        self.final, self.tree = integration.git(self.clone, 'rev-parse', 'HEAD'), integration.git(self.clone, 'rev-parse', 'HEAD^{tree}')
        integration.git(self.clone, 'push', 'origin', self.final + ':' + approval.MAIN)
        self.source_decision()

    def common(self, kind):
        return {'schema_version': 1, 'id': kind + '-' + uuid.uuid4().hex,
                'purpose': approval.RECEIPT_PURPOSES[kind], 'authorization_sha256': self.auth.sha256,
                'decision_reference': 'fixture-external-' + kind}

    def sign(self, kind, payload, **_):
        # Historical helper name only. No signature, key or old fixture policy.
        if kind == 'artifact-human':
            payload = {**payload, 'publish_allowed': payload.get('publish_allowed', True)}
        self.write(kind + '.json', approval.canonical(payload))

    def source_decision(self):
        self.write('integration-evidence.json', approval.canonical({'fixture_only': True, 'source': self.final}))
        self.integration_receipt = {**self.common('integration'), 'decision': 'ACCEPT',
            'source_repository': str(self.clone), 'source_commit': self.final, 'source_tree': self.tree,
            'parents': [self.main, self.accepted], 'baseline': self.baseline, 'main_ref': approval.MAIN,
            'feature_ref': approval.FEATURE, 'final_main': self.final, 'final_feature': self.accepted,
            'evidence_sha256': approval.digest(self.policy.trust_file('integration-evidence.json'))}
        self.sign('integration', self.integration_receipt)

    def publisher_setup(self):
        self.make_artifact()
        self.fake = self.root / 'fake-gh'
        self.fake.write_text(FAKE_GH.replace('PYTHON', str(Path(sys.executable).resolve())))
        self.fake.chmod(0o700)
        self.remote_api = self.root / 'fake-remote.json'
        self.remote_api.write_text(json.dumps({'release': None, 'assets': []}))
        stamp = 1791028800
        self.plan = {**self.common('publication-plan'), 'artifact_id': self.artifact['artifact_id'],
            'human_receipt_sha256': approval.digest((self.policy.root / 'artifact-human.json').read_bytes()),
            'source_commit': self.final, 'source_tree': self.tree, 'notes_sha256': publication.NOTES_HASH,
            'tag_timestamp': stamp, 'tag_oid': publication.tag_identity(self.final, stamp),
            'transport': {'executable': str(self.fake), 'sha256': approval.digest(self.fake.read_bytes())}}
        self.sign('publication-plan', self.plan)

    def publisher(self, checkpoint=None):
        return publication.Publisher(self.policy, checkpoint=checkpoint)

    def writes(self):
        path = self.root / 'fake-gh-calls.jsonl'
        calls = [] if not path.exists() else [json.loads(p) for p in path.read_text().splitlines()]
        return [p for p in calls if p['argv'][p['argv'].index('--method') + 1] != 'GET']

    def reconcile(self, phase):
        remote = json.loads(self.remote_api.read_text())
        self.sign('publication-reconciliation', {**self.common('publication-reconciliation'),
            'plan_sha256': approval.digest((self.policy.root / 'publication-plan.json').read_bytes()),
            'artifact_id': self.artifact['artifact_id'], 'human_receipt_sha256': self.plan['human_receipt_sha256'],
            'source_commit': self.final, 'tag_oid': self.plan['tag_oid'], 'release_id': remote['release']['id'],
            'asset_id': remote['assets'][0]['id'] if remote['assets'] else None, 'phase': phase})


class LightweightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp(prefix='rel1c-lightweight-fixtures.', dir=approval.downloads()))

    def test_plain_schema_references_and_tools_not_signatures(self):
        f = Fixture(self.root)
        self.assertEqual(approval.authorize_integration(f.policy), f.auth)
        self.assertFalse(any('key' in p.name or p.suffix == '.sig' for p in f.root.rglob('*')))
        self.assertFalse(any(p in f.payload for p in ('signers', 'config_epoch', 'revoked', 'trust_root')))
        for key, value in (('reviewer_reference', ''), ('schema_version', True), ('mode', 'fixture'),
                           ('config_epoch', 1), ('repository', 'foreign/repo')):
            f.write('approval.json', approval.canonical({**f.payload, key: value}))
            with self.subTest(key=key), self.assertRaises(approval.Stop): approval.authorize_workflow(f.policy)
        f.write('approval.json', approval.canonical(f.payload))
        (f.source / 'scripts/release_lightweight.py').write_text('changed\n')
        with self.assertRaises(approval.Stop): approval.authorize_workflow(f.policy)

    def test_production_cli_refuses_fixture_local_origin_and_no_fixture_flags(self):
        f = Fixture(self.root)
        result = subprocess.run([sys.executable, '-B', str(REPO / 'scripts/release_lightweight.py'),
            '--approval', str(f.policy.approval_path), 'publish'], capture_output=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(b'SYNTHETIC', result.stdout + result.stderr)
        self.assertFalse((f.root / 'fake-gh-calls.jsonl').exists())
        bad = subprocess.run([sys.executable, str(REPO / 'scripts/release_lightweight.py'),
            '--approval', str(f.policy.approval_path), '--fixture-root', str(f.root), 'status'], capture_output=True)
        self.assertEqual(bad.returncode, 2)
        self.assertNotIn(str(f.root).encode(), bad.stderr)

    def test_native_context_reset_and_legacy_nested_policy_refuses(self):
        f = Fixture(self.root)
        previous = integration.environment()
        with self.assertRaises(KeyboardInterrupt):
            with integration.native_authentication(f.policy):
                self.assertEqual(integration.environment()['HOME'], str(f.root))
                for policy in (approval.Policy(), approval.WorkflowPolicy()):
                    with self.assertRaises(approval.Stop) as caught: approval.authorize_integration(policy)
                    self.assertEqual(caught.exception.code, 'TRANSPORT_POLICY')
                with self.assertRaises(approval.Stop):
                    with integration.native_authentication(f.policy): pass
                raise KeyboardInterrupt()
        self.assertEqual(integration.environment(), previous)

    def test_native_environment_filters_secret_and_redirect_overrides(self):
        f = Fixture(self.root)
        values = {'GH_TOKEN': 'SECRET', 'GITHUB_TOKEN': 'SECRET', 'OPENAI_API_KEY': 'SECRET',
                  'CODEX_ACCESS_TOKEN': 'SECRET', 'GIT_CONFIG_GLOBAL': '/SECRET',
                  'GIT_SSH_COMMAND': 'SECRET', 'PYTHONPATH': '/SECRET', 'DYLD_INSERT_LIBRARIES': '/SECRET'}
        with mock.patch.dict(os.environ, values):
            env = integration.native_environment(f.policy)
        self.assertFalse(any('SECRET' in value for value in env.values()))
        self.assertEqual(env['GIT_CONFIG_GLOBAL'], '/dev/null')
        self.assertEqual(env['GIT_SSH_COMMAND'], '/usr/bin/false')

    def test_readonly_status_and_no_checkpoint_resume(self):
        f = Fixture(self.root, integrated=False)
        before = snapshot(f.root)
        self.assertEqual(lightweight.run('status', f.policy), 'MISSING')
        with self.assertRaises(approval.Stop): lightweight.run('resume', f.policy)
        self.assertEqual(snapshot(f.root), before)

    def test_real_divergent_local_git_original_integration_and_wait_source_review(self):
        f = Fixture(self.root, integrated=False)
        calls = []
        def gate(runner, kind, env):
            calls.append(kind)
            return runner.log_command(kind, ['/bin/sh', '-c', 'printf "SYNTHETIC strict gate only\\n"'], env)
        with integration.native_authentication(f.policy):
            self.assertEqual(pipeline.prepare(f.policy, fixture_gate=gate), 'FINAL_MAIN_REVIEW_REQUIRED')
        f.clone = f.managed / 'clone'
        f.final = integration.git(f.clone, 'rev-parse', 'HEAD')
        self.assertEqual(integration.git(f.clone, 'show', '-s', '--format=%P', f.final), f.main + ' ' + f.accepted)
        self.assertEqual(integration.git(f.remote, 'rev-parse', approval.MAIN), f.final)
        self.assertTrue((f.clone / 'main-only.txt').exists() and (f.clone / 'feature-only.txt').exists())
        self.assertEqual(calls, ['bootstrap', 'strict'])
        self.assertFalse((f.policy.root / 'integration.json').exists())
        before = snapshot(f.root)
        with integration.native_authentication(f.policy), self.assertRaises(approval.Stop) as caught:
            pipeline.prepare(f.policy, fixture_gate=gate)
        self.assertEqual(caught.exception.code, 'FINAL_MAIN_REVIEW_REQUIRED')
        self.assertEqual(snapshot(f.root), before)

    def test_original_six_checkpoints_and_real_zip_wait_human_no_keys(self):
        f = Fixture(self.root)
        with integration.native_authentication(f.policy), contextlib.redirect_stdout(io.StringIO()):
            controller = synthetic_controller(f)
            self.assertEqual(pipeline.prepare(f.policy, fixture_build=lambda _: controller), 'EXACT_ARTIFACT_HUMAN_REVIEW_REQUIRED')
        self.assertEqual(controller.events, list(workflow.EVENTS))
        self.assertFalse((f.policy.root / 'artifact-human.json').exists())
        before = snapshot(f.root)
        self.assertEqual(lightweight.run('prepare', f.policy), 'EXACT_ARTIFACT_HUMAN_REVIEW_REQUIRED')
        self.assertEqual(snapshot(f.root), before)

    def test_exact_plain_human_pass_without_explicit_publish_allow_has_zero_writes(self):
        for kind in ('missing', 'no-allow', 'false-allow', 'fail', 'wrong-artifact', 'wrong-source', 'wrong-purpose'):
            f = Fixture(self.root)
            f.publisher_setup()
            receipt = approval.decode((f.policy.root / 'artifact-human.json').read_bytes())
            if kind == 'missing': (f.policy.root / 'artifact-human.json').unlink()
            else:
                if kind == 'no-allow': receipt.pop('publish_allowed')
                elif kind == 'false-allow': receipt['publish_allowed'] = False
                elif kind == 'fail': receipt['decision'] = 'FAIL'
                elif kind == 'wrong-artifact': receipt['artifact'] = {**receipt['artifact'], 'zip_sha256': 'a' * 64}
                elif kind == 'wrong-source': receipt['integration_receipt_sha256'] = 'a' * 64
                else: receipt['purpose'] = approval.RECEIPT_PURPOSES['integration']
                f.write('artifact-human.json', approval.canonical(receipt))
            with self.subTest(kind=kind), self.assertRaises((approval.Stop, OSError)):
                lightweight.run('publish', f.policy)
            self.assertEqual(f.writes(), [])
            self.assertEqual(integration.run_git(f.remote, 'rev-parse', '--verify', 'refs/tags/1.1.0', allow_failure=True).returncode, 128)

    def test_publication_fake_gh_binary_tag_draft_verify_public_and_same_bytes(self):
        f = Fixture(self.root)
        f.publisher_setup()
        self.assertEqual(lightweight.run('publish', f.policy), 'PUBLICATION_VERIFIED_SAME_ARTIFACT')
        self.assertEqual(integration.git(f.remote, 'rev-parse', 'refs/tags/1.1.0^{}'), f.final)
        self.assertEqual((f.root / 'fake-upload.zip').read_bytes(), Path(f.artifact['zip_path']).read_bytes())
        self.assertEqual([p['argv'][p['argv'].index('--method') + 1] for p in f.writes()], ['POST', 'POST', 'PATCH'])
        before = snapshot(f.root)
        self.assertEqual(lightweight.run('status', f.policy), 'PUBLICATION_COMPLETE_RECORDED_UNVERIFIED')
        self.assertEqual(snapshot(f.root), before)
        # Same-name/byte-matching remote and an honestly rehashed advanced hint
        # still do not establish task ownership on a later invocation.
        store = f.publisher().store
        value = store.inspect()
        store.path.write_bytes(approval.canonical(publication_state.with_checksum({**value, 'sequence': value['sequence'] + 100})))
        with self.assertRaises(approval.Stop) as caught: lightweight.run('resume', f.policy)
        self.assertEqual(caught.exception.code, 'PUBLICATION_RECONCILIATION_REQUIRED')
        self.assertEqual(len(f.writes()), 3)

    def test_crash_after_create_upload_publish_requires_explicit_plain_reconciliation(self):
        for point, phase in (('after_create', 'DRAFT'), ('after_upload', 'UPLOADED'), ('after_publish', 'PUBLISHED')):
            f = Fixture(self.root)
            f.publisher_setup()
            def crash(name):
                if name == point: raise KeyboardInterrupt()
            with integration.native_authentication(f.policy), self.assertRaises(KeyboardInterrupt):
                f.publisher(crash).execute()
            count = len(f.writes())
            with self.assertRaises(approval.Stop): lightweight.run('resume', f.policy)
            self.assertEqual(len(f.writes()), count)
            f.reconcile(phase)
            self.assertEqual(lightweight.run('resume', f.policy), 'PUBLICATION_VERIFIED_SAME_ARTIFACT')
            self.assertEqual(len(f.writes()), 3)

    def test_changed_zip_and_app_after_pass_stops_without_remote_writes(self):
        for target in ('zip', 'app'):
            f = Fixture(self.root)
            f.publisher_setup()
            path = (Path(f.artifact['zip_path']) if target == 'zip' else
                    Path(f.artifact['extraction_path']) / artifact.APP / 'Contents/MacOS/ClassroomTranscriber')
            path.write_bytes(b'replaced after Human PASS\n')
            with self.subTest(target=target), self.assertRaises(approval.Stop): lightweight.run('publish', f.policy)
            self.assertEqual(f.writes(), [])

    def test_local_schema_duplicate_unknown_symlink_and_wrong_modes_reject(self):
        for kind in ('duplicate', 'unknown', 'symlink', 'mode'):
            f = Fixture(self.root)
            path = f.policy.approval_path
            if kind == 'duplicate': path.write_bytes(b'{"a":1,"a":2}\n')
            elif kind == 'unknown': f.write('approval.json', approval.canonical({**f.payload, 'human_pass': True}))
            elif kind == 'mode': path.chmod(0o644)
            else:
                other = f.policy.root / 'saved.json'
                path.rename(other)
                path.symlink_to(other)
            with self.subTest(kind=kind), self.assertRaises(approval.Stop): approval.authorize_workflow(f.policy)

    def test_plain_human_record_typed_allow_reference_purpose_and_schema(self):
        f = Fixture(self.root)
        names = ('decision', 'integration_receipt_sha256', 'artifact')
        original = {**f.common('artifact-human'), 'decision': 'PASS', 'publish_allowed': True,
                    'integration_receipt_sha256': 'a' * 64, 'artifact': {}}
        for key, value in (('publish_allowed', 1), ('schema_version', True), ('decision_reference', ''),
                           ('purpose', approval.RECEIPT_PURPOSES['integration']), ('unknown', 'value')):
            f.write('artifact-human.json', approval.canonical({**original, key: value}))
            with self.subTest(key=key), self.assertRaises(approval.Stop):
                local.local_receipt(f.policy, f.auth, 'artifact-human', names)
        for value in (True, 0, -1, '101'):
            with self.subTest(identifier=value), self.assertRaises(approval.Stop): publication.positive_id(value)


if __name__ == '__main__':
    unittest.main()
