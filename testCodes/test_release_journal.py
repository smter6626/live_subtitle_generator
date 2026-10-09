"""Atomic persistence and recomputed-checksum rejection/revalidation."""
import copy
import os
import unittest
from unittest import mock

from testCodes.test_release_controller import Fixture, retained_root, approval, journal


class JournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = retained_root()

    def make(self):
        f = Fixture(self.root)
        auth = approval.authorize(f.policy)
        store = journal.Journal(auth)
        value = store.create()
        return f, store, value

    def test_mode_atomic_write_and_strict_schema(self):
        f, store, value = self.make()
        self.assertEqual(store.root.stat().st_mode & 0o777, 0o700)
        self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(store.inspect(), value)
        for key, item in (('sequence', True), ('schema_version', True), ('state', 'PUBLISHED'),
                          ('intent', 'BUILD'), ('gate', {'passed': True}), ('future', None),
                          ('merge_commit', 'x'), ('state', [])):
            altered = copy.deepcopy(value)
            altered[key] = item
            with self.subTest(key=key), self.assertRaises(approval.Stop):
                journal.validate(journal.with_checksum(altered), store.auth)

    def test_recomputed_bindings_cannot_change_authority(self):
        f, store, value = self.make()
        cases = {
            'accepted_commit': 'a' * 40, 'tools': {**value['tools'], 'uv.lock': 'b' * 64},
            'origin': '/SECRET', 'main_ref': 'refs/heads/other', 'feature_ref': 'refs/heads/other',
            'managed': '/Users/smterpro/Downloads/other', 'approval_sha256': 'c' * 64,
            'trust_sha256': 'd' * 64, 'feature_receipt': 'e' * 40, 'main_receipt': 'f' * 40,
        }
        for key, item in cases.items():
            with self.subTest(key=key):
                altered = copy.deepcopy(value)
                altered[key] = item
                store.path.write_bytes(approval.canonical(journal.with_checksum(altered)))
                code, output = f.cli('resume')
                self.assertEqual(code, 1)
                self.assertEqual(f.ref(), f.main)
                self.assertFalse((store.root / 'clone').exists())

    def test_recomputed_future_states_and_push_receipts_never_enable_operations(self):
        f, store, value = self.make()
        for state in ('BUILT', 'HUMAN_PASS', 'TAGGED', 'DRAFT', 'UPLOADED', 'PUBLISHED'):
            store.path.write_bytes(approval.canonical(journal.with_checksum({**value, 'state': state})))
            self.assertEqual(f.cli('resume')[0], 1)
            self.assertEqual(f.ref(), f.main)

    def test_atomic_replace_failure_keeps_preimage_and_stops_partial_resume(self):
        f, store, value = self.make()
        before = store.path.read_bytes()
        with mock.patch.object(journal.os, 'replace', side_effect=OSError('SECRET')):
            with self.assertRaises(approval.Stop) as caught:
                store.change(value, intent='CLONE')
        self.assertEqual(caught.exception.code, 'PERSISTENCE_FAILED')
        self.assertEqual(store.path.read_bytes(), before)
        self.assertEqual(f.cli('resume')[0], 1)
        self.assertEqual(f.ref(), f.main)

    def test_file_fsync_failure_keeps_preimage(self):
        f, store, value = self.make()
        before = store.path.read_bytes()
        with mock.patch.object(journal.os, 'fsync', side_effect=OSError('SECRET')):
            with self.assertRaises(approval.Stop):
                store.change(value, intent='CLONE')
        self.assertEqual(store.path.read_bytes(), before)
        self.assertEqual(f.cli('status')[0], 1)

    def test_directory_fsync_after_replace_reports_uncertain_complete_bytes(self):
        f, store, value = self.make()
        with mock.patch.object(journal, 'fsync_directory', side_effect=OSError('SECRET')):
            with self.assertRaises(approval.Stop) as caught:
                store.change(value, intent='CLONE')
        self.assertEqual(caught.exception.code, 'PERSISTENCE_UNCERTAIN')
        self.assertEqual(store.inspect()['intent'], 'CLONE')

    def test_partial_duplicate_and_missing_journal_refuse_repair(self):
        for kind in ('partial', 'duplicate', 'missing'):
            with self.subTest(kind=kind):
                f, store, value = self.make()
                if kind == 'partial':
                    store.path.write_bytes(b'{')
                elif kind == 'duplicate':
                    store.path.write_bytes(b'{"state":"NEW","state":"COMPLETE"}')
                else:
                    store.path.unlink()
                code, output = f.cli('status')
                self.assertEqual(code, 1)
                self.assertEqual(f.ref(), f.main)
                self.assertFalse((store.root / 'clone').exists())

    def test_symlink_hardlink_wrong_modes_and_preexisting_root(self):
        for kind in ('symlink', 'parent', 'hardlink', 'file-mode', 'root-mode'):
            with self.subTest(kind=kind):
                f, store, value = self.make()
                if kind == 'symlink':
                    store.path.rename(store.root / 'copy')
                    store.path.symlink_to(store.root / 'copy')
                elif kind == 'parent':
                    store.root.rename(f.root / 'managed-copy')
                    store.root.symlink_to(f.root / 'managed-copy', target_is_directory=True)
                elif kind == 'hardlink':
                    os.link(store.path, f.root / 'journal-link')
                elif kind == 'file-mode':
                    store.path.chmod(0o644)
                else:
                    store.root.chmod(0o755)
                self.assertEqual(f.cli('resume')[0], 1)
                self.assertEqual(f.ref(), f.main)
        f = Fixture(self.root)
        (f.root / 'managed').mkdir(mode=0o700)
        self.assertEqual(f.cli()[0], 1)
        self.assertFalse(f.journal_path.exists())


if __name__ == '__main__':
    unittest.main()
