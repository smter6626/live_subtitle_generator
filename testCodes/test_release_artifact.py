"""Signed exact source facts and real ZIP round trip of a labelled synthetic App."""
import copy
import os
import unittest
from pathlib import Path
from unittest import mock

from testCodes.test_release_workflow import (
    Fixture, retained_root, approval, artifact, integration, identity, release_zip,
)


class ArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = retained_root()

    def test_signed_exact_source_receipt_checks_real_merge_and_app_zip_machine_metadata(self):
        f = Fixture(self.root)
        source, checksum = artifact.accepted_source(f.policy, f.auth, remote=True)
        self.assertEqual(source['parents'], [f.main, f.accepted])
        self.assertNotEqual(source['source_commit'], f.accepted)
        value = f.make_artifact()
        self.assertEqual(len(f.calls), 2)
        self.assertTrue(f.assert_manifest)
        self.assertEqual(f.calls[0][1], str(f.workspace / 'dist' / artifact.APP))
        self.assertEqual(f.calls[1][1], str(f.metadata.extracted_app_path))
        self.assertTrue(f.metadata.extracted_app_path.is_dir())
        self.assertEqual(artifact.validate_artifact(value, f.auth, source, checksum), value)
        self.assertEqual(value['zip_sha256'], release_zip.sha256_file(f.metadata.artifact_path))

    def test_signed_wrong_source_tree_parents_tool_contract_scope_or_ref_rejected(self):
        f = Fixture(self.root)
        original = copy.deepcopy(f.integration_receipt)
        changes = [('source_commit', f.accepted), ('source_tree', 'a' * 40),
                   ('parents', [f.accepted, f.main]), ('baseline', f.main),
                   ('final_main', f.main), ('final_feature', f.baseline),
                   ('main_ref', 'refs/heads/foreign'), ('purpose', approval.WORKFLOW_PURPOSE),
                   ('accepted_commit', f.main), ('tools', {}), ('contracts', {}),
                   ('source_repository', str(f.source)), ('schema_version', True), ('decision', 'PASS')]
        for key, value in changes:
            f.sign('integration', {**original, key: value})
            with self.subTest(key=key), self.assertRaises(approval.Stop):
                artifact.accepted_source(f.policy, f.auth)
        f.sign('integration', original)
        integration.git(f.remote, 'update-ref', approval.MAIN, f.main)
        with self.assertRaises(approval.Stop):
            artifact.accepted_source(f.policy, f.auth, remote=True)

    def test_hidden_source_bytes_and_required_control_tool_drift_stop_without_execution(self):
        for where, relative in (('source', 'scripts/release_workflow.py'),
                                ('clone', 'scripts/build_macos.sh')):
            f = Fixture(self.root)
            repo = getattr(f, where)
            path = repo / relative
            integration.git(repo, 'update-index', '--assume-unchanged', relative)
            path.write_bytes(path.read_bytes() + b'\n# hidden drift\n')
            with self.subTest(where=where), self.assertRaises(approval.Stop):
                artifact.accepted_source(f.policy, f.auth)
            self.assertFalse((f.root / 'workflow').exists())

    def test_fresh_source_refuses_ignored_environment_or_old_dist_before_program(self):
        from testCodes.test_release_workflow import workflow
        for name in ('.venv', '.tools', 'dist', 'build', 'external/whisper.cpp'):
            f = Fixture(self.root)
            directory = f.clone / name
            directory.mkdir(parents=True)
            fake = directory / 'counterfeit'
            fake.write_text('#!/bin/sh\ntouch COUNTERFEIT_EXECUTED\n')
            fake.chmod(0o755)
            with self.subTest(name=name), self.assertRaises(approval.Stop):
                workflow.fresh_source(f.clone)
            self.assertFalse((f.clone / 'COUNTERFEIT_EXECUTED').exists())

    def test_changed_zip_app_evidence_and_unsafe_output_ancestry_refuse(self):
        for kind in ('zip', 'app', 'evidence', 'ancestor', 'hardlink', 'app-escape', 'extraction-extra'):
            f = Fixture(self.root)
            value = f.make_artifact()
            source, checksum = artifact.accepted_source(f.policy, f.auth)
            if kind == 'zip':
                f.metadata.artifact_path.write_bytes(b'changed zip')
            elif kind == 'app':
                (f.metadata.extracted_app_path / 'Contents/MacOS/ClassroomTranscriber').write_bytes(b'changed app')
            elif kind == 'evidence':
                Path(value['evidence']['build']['path']).write_bytes(b'changed log')
            elif kind == 'ancestor':
                directory = f.metadata.artifact_path.parent
                directory.rename(directory.parent / 'replacement')
                directory.symlink_to(directory.parent / 'replacement', target_is_directory=True)
            elif kind == 'hardlink':
                os.link(f.metadata.artifact_path, f.root / 'zip-link')
            elif kind == 'app-escape':
                (f.metadata.extracted_app_path / 'Contents/Resources/escape').symlink_to(f.source)
            else:
                (f.metadata.extracted_app_path.parent / 'foreign').write_text('unexpected\n')
            with self.subTest(kind=kind), self.assertRaises((approval.Stop, release_zip.ReleaseError)):
                artifact.validate_artifact(value, f.auth, source, checksum)

    def test_round_trip_failure_collision_or_stale_provenance_cannot_fix_metadata(self):
        f = Fixture(self.root)
        value = f.make_artifact()
        before = f.metadata.artifact_path.read_bytes()
        source, checksum = artifact.accepted_source(f.policy, f.auth)
        app = f.workspace / 'dist' / artifact.APP
        manifest = release_zip.load_manifest(f.workspace / 'packaging/runtime_manifest.json')
        with self.assertRaises(release_zip.ReleaseError):
            release_zip.create_release_zip(
                version='1.1.0', app_path=app, artifact_path=f.metadata.artifact_path,
                extraction_dir=f.metadata.extracted_app_path.parent, task_root=f.store.root,
                build_provenance_path=f.workspace / 'dist' / (artifact.APP + '.provenance.json'),
                manifest=manifest, commit=f.final, repo_root=f.workspace, verifier=lambda *_: None)
        self.assertEqual(f.metadata.artifact_path.read_bytes(), before)
        provenance = f.workspace / 'dist' / (artifact.APP + '.provenance.json')
        provenance.write_text('{"source_commit":"fake","PASS":true}\n')
        with self.assertRaises(identity.IdentityError):
            artifact.fix_metadata(f.metadata, auth=f.auth, source=source, receipt_sha256=checksum,
                                  attempt=value['attempt'], workspace=f.workspace, evidence=value['evidence'])


if __name__ == '__main__':
    unittest.main()
