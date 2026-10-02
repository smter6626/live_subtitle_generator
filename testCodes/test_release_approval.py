"""External fixture-signature and closed production trust rejection cases."""
import copy
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from testCodes.test_release_controller import Fixture, retained_root, approval


class ApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = retained_root()

    def test_real_detached_signature_and_complete_tool_set(self):
        f = Fixture(self.root)
        auth = approval.authorize(f.policy)
        self.assertEqual(auth.payload, f.payload)
        del f.payload['tools']['scripts/build_release_zip.py']
        f.sign()
        with self.assertRaises(approval.Stop):
            approval.authorize(f.policy)
        self.assertFalse((f.root / 'managed').exists())

    def test_caller_signer_and_wrong_namespace_are_rejected(self):
        f = Fixture(self.root)
        f.write_trust('allowed_signers', (f.policy.root / 'allowed_signers').read_bytes().replace(
            f.policy.signer.encode(), b'caller-signer'))
        f.payload['signers_sha256'] = approval.digest((f.policy.root / 'allowed_signers').read_bytes())
        f.sign()
        with self.assertRaises(approval.Stop) as caught:
            approval.authorize(f.policy)
        self.assertEqual(caught.exception.code, 'SIGNATURE_INVALID')
        g = Fixture(self.root)
        g.sign(namespace=approval.NAMESPACE)
        with self.assertRaises(approval.Stop) as caught:
            approval.authorize(g.policy)
        self.assertEqual(caught.exception.code, 'SIGNATURE_INVALID')

    def test_fixture_policy_cannot_be_production_or_point_outside_disposable(self):
        f = Fixture(self.root)
        f.payload['policy'] = approval.NAMESPACE
        f.sign()
        with self.assertRaises(approval.Stop) as caught:
            approval.authorize(f.policy)
        self.assertEqual(caught.exception.code, 'APPROVAL_POLICY')
        for key, value in (('origin', approval.ORIGINS[0]), ('managed', '/Users/smterpro/Downloads/foreign'),
                           ('implementation', str(f.root.parent)), ('main_ref', 'refs/heads/other')):
            with self.subTest(key=key):
                g = Fixture(self.root)
                g.payload[key] = value
                g.sign()
                with self.assertRaises(approval.Stop):
                    approval.authorize(g.policy)
                self.assertFalse((g.root / 'managed').exists())

    def test_approval_contract_entry_config_evidence_and_revocation_replacements(self):
        for kind in ('approval', 'contract', 'config', 'evidence', 'revoke'):
            with self.subTest(kind=kind):
                f = Fixture(self.root)
                if kind == 'approval':
                    data = (f.policy.root / 'approval.json').read_bytes().replace(f.accepted.encode(), b'a' * 40)
                    f.write_trust('approval.json', data)
                elif kind == 'contract':
                    (f.root / 'parent.md').write_text('changed\n')
                elif kind == 'config':
                    config = approval.decode((f.policy.root / 'config.json').read_bytes())
                    config['epoch'] = 2
                    f.write_trust('config.json', approval.canonical(config))
                elif kind == 'evidence':
                    f.write_trust('human.json', b'{"PASS":true}\n')
                else:
                    f.write_trust('revoked.json', approval.canonical({'schema_version': 1, 'ids': [f.payload['id']]}))
                with self.assertRaises(approval.Stop):
                    approval.authorize(f.policy)
                self.assertFalse((f.root / 'managed').exists())

    def test_signed_schema_rejects_bool_unknown_duplicate_and_future_inputs(self):
        for key, value in (('schema_version', True), ('uid', True), ('config_epoch', True),
                           ('build', True), ('accepted_commit', 'abc'), ('feature_prior', False)):
            with self.subTest(key=key):
                f = Fixture(self.root)
                f.payload[key] = value
                f.sign()
                with self.assertRaises(approval.Stop):
                    approval.authorize(f.policy)
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{', b'[]'):
            with self.subTest(raw=raw):
                if raw == b'[]':
                    with self.assertRaises(approval.Stop):
                        approval.fields(approval.decode(raw), ('a',))
                else:
                    with self.assertRaises(approval.Stop):
                        approval.decode(raw)

    def test_trust_permissions_symlink_and_hardlink_rejected(self):
        for kind in ('mode', 'leaf', 'ancestor', 'hardlink'):
            with self.subTest(kind=kind):
                f = Fixture(self.root)
                path = f.policy.root / 'config.json'
                if kind == 'mode':
                    path.chmod(0o666)
                elif kind == 'leaf':
                    path.rename(f.root / 'config-copy')
                    path.symlink_to(f.root / 'config-copy')
                elif kind == 'ancestor':
                    f.policy.root.rename(f.root / 'trust-copy')
                    f.policy.root.symlink_to(f.root / 'trust-copy', target_is_directory=True)
                else:
                    os.link(path, f.root / 'config-link')
                with self.assertRaises(approval.Stop):
                    approval.authorize(f.policy)

    def test_protected_path_requires_independent_root_control(self):
        f = Fixture(self.root)
        # A caller-owned directory cannot establish independence by self-hash.
        with self.assertRaises(approval.Stop):
            approval.inspect_path(f.policy.root, owner=0, directory=True, protected=True)

    def test_downloads_identity_ignores_home_and_journal(self):
        expected = approval.downloads()
        with mock.patch.dict(os.environ, {'HOME': '/SECRET', 'TMPDIR': '/SECRET'}):
            self.assertEqual(approval.downloads(), expected)


class WorkflowApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from testCodes.test_release_workflow import retained_root
        cls.root = retained_root()

    def test_fixed_scope_cannot_be_smaller_or_select_legacy_entry(self):
        from testCodes.test_release_workflow import Fixture
        f = Fixture(self.root)
        self.assertEqual(approval.authorize_workflow(f.policy), f.auth)
        for relative in approval.WORKFLOW_CONTROL_TOOLS:
            value = copy.deepcopy(f.payload)
            del value['tools'][relative]
            f.sign('workflow-approval', value)
            with self.subTest(relative=relative), self.assertRaises(approval.Stop):
                approval.authorize_workflow(f.policy)
        f.sign('workflow-approval', {**f.payload, 'purpose': 'integration-only'})
        with self.assertRaises(approval.Stop):
            approval.authorize_workflow(f.policy)

    def test_c1_tool_contract_config_evidence_replacements_and_revocation_refuse(self):
        from testCodes.test_release_workflow import Fixture
        for kind in ('tool', 'contract', 'epoch', 'review', 'revoke', 'legacy-root', 'namespace'):
            f = Fixture(self.root)
            if kind == 'tool':
                f.payload['tools']['scripts/release_human_gate.py'] = 'a' * 64
                f.sign('workflow-approval', f.payload)
            elif kind == 'contract':
                (f.root / 'rel1c.md').write_text('replacement contract\n')
            elif kind == 'epoch':
                f.config['epoch'] = 2
                f.write('workflow-config.json', approval.canonical(f.config))
            elif kind == 'review':
                f.write('review.json', approval.canonical({'scope': 'rel1c1-only-review', 'PASS': True}))
            elif kind == 'revoke':
                f.write('revoked.json', approval.canonical({'schema_version': 1, 'ids': [f.payload['id']]}))
            elif kind == 'legacy-root':
                f.sign('workflow-approval', {**f.payload, 'workflow': f.payload['managed']})
            else:
                f.sign('workflow-approval', f.payload, namespace=approval.NAMESPACE)
            with self.subTest(kind=kind), self.assertRaises(approval.Stop):
                approval.authorize_workflow(f.policy)
            self.assertFalse((f.root / 'workflow').exists())

    def test_workflow_protected_entry_checks_complete_loaded_helper_closure_and_bytes(self):
        # The test seam substitutes the protected file reader only for this unit
        # check. No fixture config/key or mock is reachable from production CLI.
        config = {'entry_sha256': {p: approval.digest(p.encode()) for p in approval.WORKFLOW_CONTROL_TOOLS}}
        root = approval.TRUST_ROOT / 'entry'
        modules = {Path(p).stem: type('Module', (), {'__file__': str(root / p)})()
                   for p in approval.WORKFLOW_CONTROL_TOOLS}
        with (mock.patch.object(approval, '__file__', str(root / 'scripts/release_approval.py')),
              mock.patch.dict(sys.modules, modules),
              mock.patch.object(approval, 'read_file', side_effect=lambda p, **_: p.relative_to(root).as_posix().encode())):
            approval._workflow_entry(approval.WorkflowPolicy(), config)
            for relative in approval.WORKFLOW_CONTROL_TOOLS:
                name = Path(relative).stem
                module = modules[name]
                old = module.__file__
                module.__file__ = '/caller/' + relative
                with self.subTest(relative=relative), self.assertRaises(approval.Stop):
                    approval._workflow_entry(approval.WorkflowPolicy(), config)
                module.__file__ = old


if __name__ == '__main__':
    unittest.main()
