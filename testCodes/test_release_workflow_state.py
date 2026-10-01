"""C1 atomic persistence, strict schemas and conservative interruption hints."""
import copy
import os
import unittest
from unittest import mock

from testCodes.test_release_workflow import Fixture, retained_root, snapshot, approval, state


class WorkflowStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = retained_root()

    def test_separate_root_atomic_sequence_modes_and_unique_attempts_preserve_evidence(self):
        f = Fixture(self.root)
        store = state.StateStore(f.auth)
        value = store.create()
        self.assertEqual(value['sequence'], 1)
        self.assertEqual(store.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
        first = store.new_attempt(value)
        old = store.root / 'evidence' / first['attempt'] / 'failed.log'
        old.write_bytes(b'failed attempt retained\n')
        old.chmod(0o600)
        review = store.change(first, state='REVIEW_REQUIRED', intent=None)
        second = store.new_attempt(review)
        self.assertNotEqual(first['attempt'], second['attempt'])
        self.assertEqual(old.read_bytes(), b'failed attempt retained\n')
        self.assertFalse((store.root / 'human' / second['attempt']).exists())
        self.assertNotEqual(store.root, f.managed)
        self.assertEqual(sorted(p.name for p in f.managed.iterdir()), ['clone'])
        self.assertEqual(store.inspect(), second)

    def test_schema_duplicate_unknown_boolean_versions_and_legitimate_rehash(self):
        f = Fixture(self.root)
        store = state.StateStore(f.auth)
        original = store.create()
        for key, value in (('sequence', True), ('schema_version', True), ('schema_version', 2),
                           ('state', 'PUBLISHED'), ('intent', False), ('human_pass', True),
                           ('authorization_sha256', 'a' * 64), ('attempt', [])):
            changed = {**original, key: value}
            with self.subTest(key=key), self.assertRaises(approval.Stop):
                state.validate(state.with_checksum(changed), f.auth)
        with self.assertRaises(approval.Stop):
            approval.decode(b'{"sequence":1,"sequence":2}')
        # A legitimately recomputed advanced state is only a hint. It cannot
        # recover an environment proof or skip the build stop.
        advanced = {**original, 'state': 'BUILT', 'attempt': 'attempt-forged', 'sequence': 100}
        store.path.write_bytes(approval.canonical(state.with_checksum(advanced)))
        self.assertIn('RECOVERY_REVIEW_REQUIRED', f.cli('resume')[1])

    def test_replace_failure_retains_preimage_and_partial_temporary_stops_recovery(self):
        f = Fixture(self.root)
        store = state.StateStore(f.auth)
        value = store.create()
        before = store.path.read_bytes()
        with mock.patch.object(state.os, 'replace', side_effect=OSError('fixture crash')):
            with self.assertRaises(approval.Stop) as caught:
                store.write(value)
        self.assertEqual(caught.exception.code, 'PERSISTENCE_FAILED')
        self.assertEqual(store.path.read_bytes(), before)
        self.assertTrue(any(p.name.startswith('.state-') for p in store.root.iterdir()))
        with self.assertRaises(approval.Stop):
            store.inspect()

    def test_post_replace_fsync_failure_reports_uncertainty_without_replay(self):
        f = Fixture(self.root)
        store = state.StateStore(f.auth)
        value = store.create()
        with mock.patch.object(state, 'fsync_directory', side_effect=OSError('fixture durability uncertainty')):
            with self.assertRaises(approval.Stop) as caught:
                store.write(value)
        self.assertEqual(caught.exception.code, 'PERSISTENCE_UNCERTAIN')
        self.assertEqual(store.inspect()['sequence'], value['sequence'] + 1)

    def test_missing_state_permissions_symlink_hardlink_and_partial_root_refuse(self):
        for kind in ('missing', 'permission', 'symlink', 'hardlink', 'partial', 'foreign'):
            f = Fixture(self.root)
            store = state.StateStore(f.auth)
            store.create()
            if kind == 'missing':
                store.path.unlink()
            elif kind == 'permission':
                store.path.chmod(0o644)
            elif kind == 'symlink':
                store.path.rename(f.root / 'state-copy')
                store.path.symlink_to(f.root / 'state-copy')
            elif kind == 'hardlink':
                os.link(store.path, f.root / 'state-link')
            elif kind == 'partial':
                (store.root / 'tmp').rmdir()
            else:
                (store.root / 'unknown').write_text('foreign file\n')
            before = snapshot(f.root)
            with self.subTest(kind=kind), self.assertRaises(approval.Stop):
                store.inspect()
            self.assertEqual(snapshot(f.root), before)

    def test_exclusive_collision_and_file_fsync_failure_preserve_failed_attempt(self):
        f = Fixture(self.root)
        store = state.StateStore(f.auth)
        value = store.create()
        with self.assertRaises(approval.Stop):
            store.create()
        with mock.patch.object(state.os, 'fsync', side_effect=OSError('fixture file fsync failed')):
            with self.assertRaises(approval.Stop):
                store.write(value)
        with self.assertRaises(approval.Stop):
            store.inspect()


if __name__ == '__main__':
    unittest.main()
