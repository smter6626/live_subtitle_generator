"""Closed publication-hint shape, atomic persistence and readonly snapshots."""
import copy
import os
import unittest
from unittest import mock

from testCodes.test_release_publication import Fixture, retained_root, approval, publication, state, snapshot


class PublicationStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.root = retained_root()

    def test_state_intent_id_download_matrix_and_rehashed_hints(self):
        f = Fixture(self.root)
        store = f.publisher().store
        original = store.create()
        for changes in ({'schema_version':True}, {'sequence':True}, {'state':'PUBLISHED'},
                        {'state':'NEW','intent':'PUBLISH'}, {'state':'COMPLETE'},
                        {'release_id':True}, {'asset_id':12}, {'extra':1}, {'plan_sha256':'bad'}):
            with self.subTest(changes=changes), self.assertRaises(approval.Stop):
                store.validate(state.with_checksum({**original, **changes}))
        valid = {**original, 'state':'DRAFT', 'intent':'UPLOAD','release_id':101}
        self.assertEqual(store.validate(state.with_checksum(valid))['release_id'],101)
        with self.assertRaises(approval.Stop):
            store.validate(state.with_checksum({**valid,'state':'VERIFIED','asset_id':201,'intent':'PUBLISH'}))

    def test_atomic_write_crash_modes_no_repair_and_strict_readonly(self):
        for kind in ('replace','fsync','mode','symlink','hardlink'):
            f = Fixture(self.root)
            store = f.publisher().store
            value = store.create()
            original = store.path.read_bytes()
            if kind == 'replace':
                with mock.patch.object(state.os,'replace',side_effect=OSError('fixture failure')):
                    with self.assertRaises(approval.Stop): store.change(value,state='TAGGED')
                self.assertEqual(store.path.read_bytes(),original)
            elif kind == 'fsync':
                with mock.patch.object(state,'fsync_directory',side_effect=OSError('fixture uncertainty')):
                    with self.assertRaises(approval.Stop): store.change(value,state='TAGGED')
                self.assertEqual(store.inspect()['sequence'],value['sequence']+1)
                continue
            elif kind == 'mode': store.path.chmod(0o644)
            elif kind == 'symlink':
                store.path.rename(f.root/'state-retained')
                store.path.symlink_to(f.root/'state-retained')
            else: os.link(store.path,f.root/'hardlink')
            before = snapshot(f.root)
            with self.subTest(kind=kind), self.assertRaises(approval.Stop): store.inspect()
            self.assertEqual(snapshot(f.root),before)

    def test_status_records_are_local_readonly_and_do_not_consult_human_plan(self):
        from release_pipeline import status
        f = Fixture(self.root)
        f.publisher().store.create()
        (f.policy.root/'artifact-human.json').unlink()
        (f.policy.root/'publication-plan.json').unlink()
        before = snapshot(f.root)
        for _ in range(2): self.assertEqual(status(f.policy),'PUBLICATION_NEW_RECORDED_UNVERIFIED')
        self.assertEqual(snapshot(f.root),before)
        self.assertEqual(f.call_records(),[])


if __name__ == '__main__': unittest.main()
