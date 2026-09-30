"""External fixture-signature and closed production trust rejection cases."""
import copy
import os
import unittest
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


if __name__ == '__main__':
    unittest.main()
