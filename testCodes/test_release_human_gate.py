"""Real detached fixture PASS/FAIL and exact-artifact rejection matrix."""
import copy
import os
import subprocess
import unittest

from testCodes.test_release_workflow import Fixture, retained_root, approval, artifact, human, state


class HumanGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = retained_root()

    def test_valid_independent_fixture_pass_and_signed_fail_have_distinct_results(self):
        f = Fixture(self.root)
        value = f.make_artifact()
        result = human.validate_human_gate(f.policy, f.auth, value)
        self.assertEqual(result['receipt_id'], f.human_receipt['id'])
        f.sign('artifact-human', {**f.human_receipt, 'decision': 'FAIL'})
        with self.assertRaises(approval.Stop) as caught:
            human.validate_human_gate(f.policy, f.auth, value)
        self.assertEqual(caught.exception.code, 'HUMAN_FAIL')

    def test_wrong_receipt_purpose_namespace_signature_trust_and_revocation(self):
        f = Fixture(self.root)
        value = f.make_artifact()
        original = copy.deepcopy(f.human_receipt)
        for key, item in (('purpose', approval.RECEIPT_PURPOSES['integration']),
                           ('decision', True), ('schema_version', True),
                           ('config_epoch', True), ('config_sha256', 'a' * 64),
                           ('trust_sha256', 'a' * 64), ('repository', 'other/repo'),
                           ('version', '1.0.0'), ('decision_reference', None)):
            f.sign('artifact-human', {**original, key: item})
            with self.subTest(key=key), self.assertRaises(approval.Stop):
                human.validate_human_gate(f.policy, f.auth, value)
        f.sign('artifact-human', original, namespace=f.policy.namespace + '-integration')
        with self.assertRaises(approval.Stop):
            human.validate_human_gate(f.policy, f.auth, value)
        counterfeit = f.root / 'counterfeit-fixture-key'
        subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(counterfeit)],
                       check=True, capture_output=True)
        f.sign('artifact-human', original, key=counterfeit)
        with self.assertRaises(approval.Stop):
            human.validate_human_gate(f.policy, f.auth, value)
        f.sign('artifact-human', original)
        f.write('revoked.json', approval.canonical({'schema_version': 1, 'ids': [original['id']]}))
        with self.assertRaises(approval.Stop):
            human.validate_human_gate(f.policy, f.auth, value)

    def test_signed_wrong_source_attempt_zip_extraction_app_and_omitted_tools_refuse(self):
        f = Fixture(self.root)
        value = f.make_artifact()
        original = copy.deepcopy(f.human_receipt)
        for key, item in (('source_commit', f.accepted), ('attempt', 'attempt-old'),
                           ('zip_path', str(f.root / artifact.ASSET)), ('zip_bytes', value['zip_bytes'] + 1),
                           ('zip_sha256', 'a' * 64), ('extraction_path', str(f.root)),
                           ('bundle_identifier', 'wrong'), ('app_tree_sha256', 'a' * 64),
                           ('tools', {}), ('schema_version', True)):
            changed = copy.deepcopy(original)
            changed['artifact'][key] = item
            changed['artifact']['artifact_id'] = artifact.artifact_checksum(changed['artifact'])
            f.sign('artifact-human', changed)
            with self.subTest(key=key), self.assertRaises(approval.Stop):
                human.validate_human_gate(f.policy, f.auth, value)

    def test_rehashed_state_provenance_integration_approval_and_boolean_never_grant_pass(self):
        f = Fixture(self.root)
        value = f.make_artifact()
        (f.policy.root / 'artifact-human.json').unlink()
        forged = {**f.state, 'state': 'HUMAN_RECORDED', 'human_receipt': {
            'receipt_id': 'forged-PASS', 'receipt_sha256': 'a' * 64, 'decision_reference': 'forged-owner'}}
        f.store.path.write_bytes(approval.canonical(state.with_checksum(forged)))
        self.assertEqual(f.cli('human-gate')[0], 1)
        for payload in (f.integration_receipt, {'human_pass': True}, {'decision': 'PASS'}):
            f.sign('artifact-human', payload)
            with self.assertRaises(approval.Stop):
                human.validate_human_gate(f.policy, f.auth, value)

    def test_post_pass_replacement_with_recomputed_artifact_still_requires_new_owner_receipt(self):
        f = Fixture(self.root)
        value = f.make_artifact()
        self.assertTrue(human.validate_human_gate(f.policy, f.auth, value))
        executable = f.metadata.extracted_app_path / 'Contents/MacOS/ClassroomTranscriber'
        executable.write_bytes(b'replaced after PASS\n')
        with self.assertRaises(approval.Stop):
            human.validate_human_gate(f.policy, f.auth, value)
        changed = copy.deepcopy(value)
        changed['app_tree_sha256'] = artifact.safe_app(f.metadata.extracted_app_path)
        changed['artifact_id'] = artifact.artifact_checksum(changed)
        with self.assertRaises(approval.Stop):
            human.validate_human_gate(f.policy, f.auth, changed)


if __name__ == '__main__':
    unittest.main()
