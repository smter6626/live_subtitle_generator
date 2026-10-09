"""Actual stage routing/local Git/signed receipts and fake-gh; no real release."""
import contextlib
import io
import os
import sys
import subprocess
import unittest

from testCodes.test_release_workflow import (Fixture, retained_root, synthetic_controller,
                                           snapshot, approval, artifact, integration, workflow)
from testCodes.test_release_publication import Fixture as PublicationFixture
import release_pipeline as pipeline


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.root = retained_root()

    def test_existing_valid_source_builds_once_then_waits_exact_human_gate(self):
        f = Fixture(self.root, synthetic=True)
        self.assertEqual(pipeline.prepare(f.policy, fixture_build=lambda _:synthetic_controller(f)),
                         'EXACT_ARTIFACT_HUMAN_REVIEW_REQUIRED')
        before = snapshot(f.root)
        self.assertEqual(pipeline.prepare(f.policy), 'EXACT_ARTIFACT_HUMAN_REVIEW_REQUIRED')
        self.assertEqual(snapshot(f.root), before)
        self.assertFalse((f.policy.root/'artifact-human.json').exists())

    def test_actual_cli_integration_waits_independent_source_without_signing_or_replay(self):
        f = Fixture(self.root, synthetic=True, integrated=False)
        calls = []
        def gate(runner, kind, env):
            calls.append(kind)
            return runner.log_command(kind,['/bin/sh','-c','printf "synthetic integration gate only\\n"'],env)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.assertEqual(workflow._run(['prepare'], f.policy,fixture_gate=gate),0)
        self.assertIn('FINAL_MAIN_REVIEW_REQUIRED',output.getvalue())
        clone=f.managed/'clone'
        final=integration.git(clone,'rev-parse','HEAD')
        self.assertEqual(integration.git(clone,'show','-s','--format=%P',final), f.main+' '+f.accepted)
        self.assertTrue((clone/'main-only.txt').exists() and (clone/'feature-only.txt').exists())
        self.assertEqual(calls,['bootstrap','strict'])
        self.assertFalse((f.policy.root/'integration.json').exists())
        before=snapshot(f.root)
        with self.assertRaises(approval.Stop) as caught: pipeline.prepare(f.policy,fixture_gate=gate)
        self.assertEqual(caught.exception.code,'FINAL_MAIN_REVIEW_REQUIRED')
        self.assertEqual(snapshot(f.root),before)
        self.assertEqual(calls,['bootstrap','strict'])

    def test_full_local_pipeline_with_original_python_acquisition_six_checkpoints_and_publication(self):
        # Real integration/Git and actual CLI route. Its strict callback is a
        # labelled synthetic local gate, not a recursive full-suite claim.
        # Python stage remains the original fixed bootstrap, with 5 real smoke
        # tests. Runtime/App are synthetic; original controller/ZIP are actual.
        from testCodes.test_release_publication import FAKE_GH
        from pathlib import Path
        import json
        import release_publication as publication
        f=Fixture(self.root,synthetic=True,full_source=True,integrated=False,
                  stage_overrides={'bootstrap_python_env.sh':(workflow.Path(__file__).resolve().parents[1]/
                      'scripts/bootstrap_python_env.sh').read_text()})
        def gate(runner,kind,env):
            return runner.log_command(kind,['/bin/sh','-c','printf "synthetic integration gate only\\n"'],env)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(workflow._run(['prepare'],f.policy,fixture_gate=gate),0)
        clone=f.managed/'clone'
        f.final=integration.git(clone,'rev-parse','HEAD')
        f.tree=integration.git(clone,'rev-parse','HEAD^{tree}')
        f.write('integration-evidence.json',approval.canonical({'scope':'independent fixture review','source':f.final}))
        f.sign('integration',{**f.common('integration'),'decision':'ACCEPT',
            'source_repository':str(clone),'source_commit':f.final,'source_tree':f.tree,
            'parents':[f.main,f.accepted],'baseline':f.baseline,'main_ref':approval.MAIN,
            'feature_ref':approval.FEATURE,'final_main':f.final,'final_feature':f.accepted,
            'evidence_sha256':approval.digest(f.policy.trust_file('integration-evidence.json'))})
        controller=synthetic_controller(f)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(workflow._run(['prepare'],f.policy,fixture_build=lambda _:controller),0)
        fixed=controller.store.inspect()['artifact']
        self.assertEqual(controller.events,list(workflow.EVENTS))
        self.assertIn(b'[python-bootstrap] smoke PASS',Path(fixed['evidence']['build']['path']).read_bytes())
        self.assertFalse((f.policy.root/'artifact-human.json').exists())
        f.sign('artifact-human',{**f.common('artifact-human'),'decision':'PASS',
            'integration_receipt_sha256':controller.source_hash,'artifact':fixed})
        fake=f.root/'fake-gh'
        fake.write_text(FAKE_GH.replace('PYTHON',str(Path(sys.executable).resolve())))
        fake.chmod(0o700)
        (f.root/'gh-config').mkdir(mode=0o700)
        (f.root/'fake-remote.json').write_text(json.dumps({'release':None,'assets':[]}))
        stamp=1791028800
        f.sign('publication-plan',{**f.common('publication-plan'),'artifact_id':fixed['artifact_id'],
            'human_receipt_sha256':approval.digest(f.policy.trust_file('artifact-human.json')),
            'source_commit':f.final,'source_tree':f.tree,'notes_sha256':publication.NOTES_HASH,
            'tag_timestamp':stamp,'tag_oid':publication.tag_identity(f.final,stamp),
            'transport':{'executable':str(fake),'sha256':approval.digest(fake.read_bytes()),
                         'config_dir':str(f.root/'gh-config'),'config_gid':os.getgid()}})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(workflow._run(['publish'],f.policy),0)
        before=snapshot(f.root)
        self.assertEqual(pipeline.status(f.policy),'PUBLICATION_COMPLETE_RECORDED_UNVERIFIED')
        self.assertEqual(pipeline.status(f.policy),'PUBLICATION_COMPLETE_RECORDED_UNVERIFIED')
        self.assertEqual(snapshot(f.root),before)
        report={'scope':'local bare integration plus synthetic integration gate; original Python/bootstrap smoke, '
                       'actual six checkpoints/ZIP with synthetic Runtime/App; independent fixture decisions/fake-gh',
                'source':f.final,'parents':[f.main,f.accepted],'events':controller.events,'artifact':fixed,
                'publication_state':publication.Publisher(f.policy).store.inspect(),
                'original_python_smoke':True,'readonly_status':True}
        (f.root/'combined-pipeline-report.json').write_bytes(approval.canonical(report))

    def test_invalid_existing_source_receipt_never_falls_back_to_integration(self):
        f=Fixture(self.root,synthetic=True)
        f.write('integration.json',b'{"decision":"ACCEPT"}\n')
        before=snapshot(f.root)
        with self.assertRaises(approval.Stop):pipeline.prepare(f.policy)
        self.assertEqual(snapshot(f.root),before)

    def test_production_new_cli_missing_trust_has_no_remote_or_repo_import_bypass(self):
        from pathlib import Path
        repo=Path(__file__).resolve().parents[1]
        before=integration.git(repo,'show-ref')
        for command in ('prepare','pipeline-status','pipeline-resume','publish'):
            result=subprocess.run([str(repo/'.venv/bin/python'),'-B',str(repo/'scripts/release_workflow.py'),command],
                                  capture_output=True,check=False)
            self.assertEqual(result.returncode,1)
            self.assertEqual(result.stderr,b'release-workflow: STOP TRUST_UNAVAILABLE\n')
        self.assertEqual(integration.git(repo,'show-ref'),before)

    def test_pipeline_resume_missing_and_unknown_build_never_starts_new_work(self):
        from release_workflow_state import StateStore
        f=Fixture(self.root,synthetic=True,integrated=False)
        before=snapshot(f.root)
        with self.assertRaises(approval.Stop) as caught:pipeline.resume(f.policy)
        self.assertEqual(caught.exception.code,'RECOVERY_PROOF_MISSING')
        self.assertEqual(snapshot(f.root),before)
        g=Fixture(self.root,synthetic=True)
        store=StateStore(g.auth)
        store.new_attempt(store.create())
        self.assertEqual(pipeline.resume(g.policy),'RECOVERY_REVIEW_REQUIRED')
        before=snapshot(g.root)
        with self.assertRaises(approval.Stop) as caught:pipeline.resume(g.policy)
        self.assertEqual(caught.exception.code,'EXPLICIT_PREPARE_REQUIRED')
        self.assertEqual(snapshot(g.root),before)

    def test_pipeline_resume_existing_artifact_only_validates_without_rebuild(self):
        f=PublicationFixture(self.root)
        before=snapshot(f.root)
        self.assertEqual(pipeline.resume(f.policy),'ARTIFACT_RECORDED_UNVERIFIED')
        self.assertEqual(snapshot(f.root),before)
        self.assertEqual(f.call_records(),[])

    def test_pipeline_resume_complete_integration_stops_before_next_build(self):
        from release_journal import Journal
        f=Fixture(self.root,synthetic=True,integrated=False)
        def gate(runner,kind,env):
            return runner.log_command(kind,['/bin/sh','-c','printf "synthetic integration gate only\\n"'],env)
        self.assertEqual(pipeline.prepare(f.policy,fixture_gate=gate),'FINAL_MAIN_REVIEW_REQUIRED')
        self.assertEqual(Journal(f.auth).inspect()['state'],'COMPLETE')
        before=snapshot(f.root)
        self.assertEqual(pipeline.resume(f.policy),'FINAL_MAIN_REVIEW_AND_EXPLICIT_PREPARE_REQUIRED')
        self.assertEqual(snapshot(f.root),before)
        self.assertFalse((f.root/'workflow').exists())


if __name__ == '__main__':unittest.main()
