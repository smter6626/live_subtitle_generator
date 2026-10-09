"""Signed exact source facts and real ZIP round trip of a labelled synthetic App."""
import copy
import dataclasses
import hashlib
import io
import stat
import zipfile
import warnings
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

    def test_independent_mismatched_zip_counterexample_and_recomputed_signed_state_are_refused(self):
        from testCodes.test_release_workflow import human
        f = Fixture(self.root)
        original_artifact = f.make_artifact()
        source, checksum = artifact.accepted_source(f.policy, f.auth)
        original_zip = f.metadata.artifact_path.read_bytes()
        executable = artifact.APP + '/Contents/MacOS/ClassroomTranscriber'
        link = artifact.APP + '/Contents/Resources/fixture'
        directory = artifact.APP + '/Contents/Resources/'
        for kind in ('executable', 'mode', 'link', 'link-mode', 'type', 'directory-mode',
                     'missing', 'extra', 'duplicate', 'root-mode', 'missing-root'):
            with warnings.catch_warnings(), zipfile.ZipFile(io.BytesIO(original_zip)) as before:
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(f.metadata.artifact_path, 'w') as after:
                    for raw_info in before.infolist():
                        info = copy.copy(raw_info)
                        data = before.read(info)
                        if kind == 'missing' and info.filename == executable:
                            continue
                        if kind == 'missing-root' and info.filename == artifact.APP + '/':
                            continue
                        if kind == 'executable' and info.filename == executable:
                            data = b'SYNTHETIC DIFFERENT ZIP EXECUTABLE - NEVER EXECUTE\n'
                        if kind == 'mode' and info.filename == executable:
                            info.external_attr = (stat.S_IFREG | 0o744) << 16
                        if kind == 'link' and info.filename == link:
                            data = b'../Frameworks/other'
                        if kind == 'link-mode' and info.filename == link:
                            info.external_attr = ((info.external_attr >> 16) ^ 0o100) << 16
                        if kind == 'type' and info.filename == link:
                            info.external_attr = (stat.S_IFREG | 0o644) << 16
                        if kind == 'directory-mode' and info.filename == directory:
                            info.external_attr = ((stat.S_IFDIR | 0o700) << 16) | 0x10
                        if kind == 'root-mode' and info.filename == artifact.APP + '/':
                            info.external_attr = ((stat.S_IFDIR | 0o700) << 16) | 0x10
                        after.writestr(info, data)
                        if kind == 'duplicate' and info.filename == executable:
                            after.writestr(info, data)
                    if kind == 'extra':
                        extra = zipfile.ZipInfo(artifact.APP + '/Contents/extra')
                        extra.create_system = 3
                        extra.external_attr = (stat.S_IFREG | 0o644) << 16
                        after.writestr(extra, b'extra')
            metadata = dataclasses.replace(f.metadata, artifact_bytes=f.metadata.artifact_path.stat().st_size,
                                           sha256=hashlib.sha256(f.metadata.artifact_path.read_bytes()).hexdigest())
            with self.assertRaises(approval.Stop, msg=kind) as caught:
                artifact.fix_metadata(metadata, auth=f.auth, source=source, receipt_sha256=checksum,
                                      attempt=original_artifact['attempt'], workspace=f.workspace,
                                      evidence=original_artifact['evidence'])
            self.assertEqual(caught.exception.code, 'ZIP_APP_MISMATCH')
            # Recompute all local metadata/state and obtain a correctly signed
            # exact fixture receipt. Neither removes the automatic mismatch.
            forged = {**original_artifact, 'zip_bytes': metadata.artifact_bytes, 'zip_sha256': metadata.sha256}
            forged['artifact_id'] = artifact.artifact_checksum(forged)
            f.store.change(f.store.inspect(), artifact=forged)
            f.sign('artifact-human', {**f.human_receipt, 'artifact': forged})
            with self.assertRaises(approval.Stop, msg=kind) as caught:
                human.validate_human_gate(f.policy, f.auth, forged)
            self.assertEqual(caught.exception.code, 'ZIP_APP_MISMATCH')
        f.metadata.artifact_path.write_bytes(original_zip)
        f.store.change(f.store.inspect(), artifact=original_artifact)
        f.sign('artifact-human', f.human_receipt)
        self.assertTrue(human.validate_human_gate(f.policy, f.auth, original_artifact))

    def test_self_consistent_app_provenance_and_metadata_cannot_hide_zip_correspondence_failure(self):
        from testCodes.test_release_workflow import human
        f = Fixture(self.root)
        original = f.make_artifact()
        source_app = f.workspace / 'dist' / artifact.APP
        retained = f.metadata.extracted_app_path
        for app in (source_app, retained):
            (app / 'Contents/MacOS/ClassroomTranscriber').write_bytes(b'changed self-consistent App\n')
        provenance = f.workspace / 'dist' / (artifact.APP + '.provenance.json')
        # Canonical regenerated provenance is still local fact, not ZIP identity.
        provenance.unlink()
        identity.write_build_provenance(provenance, source_app, f.final, repo_root=f.workspace)
        source, checksum = artifact.accepted_source(f.policy, f.auth)
        with self.assertRaises(approval.Stop):
            artifact.fix_metadata(f.metadata, auth=f.auth, source=source, receipt_sha256=checksum,
                                  attempt=original['attempt'], workspace=f.workspace, evidence=original['evidence'])
        forged = {**original, 'app_tree_sha256': identity.app_tree_sha256(retained)}
        forged['artifact_id'] = artifact.artifact_checksum(forged)
        f.store.change(f.state, artifact=forged)
        f.sign('artifact-human', {**f.human_receipt, 'artifact': forged})
        with self.assertRaises(approval.Stop) as caught:
            human.validate_human_gate(f.policy, f.auth, forged)
        self.assertEqual(caught.exception.code, 'ZIP_APP_MISMATCH')

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
