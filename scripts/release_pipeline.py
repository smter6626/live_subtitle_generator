"""Stage routing over accepted integration/build/Human/publication controllers.

No decision signing, no new implementation loop, no recovery from self-reports.
"""
from __future__ import annotations

import os

from release_approval import authorize_workflow, require, Stop
import release_artifact as artifact
from release_journal import Journal
from release_workflow_state import StateStore


def status(policy):
    """Strictly local hints; no API, remote refs, receipt acceptance or writes."""
    auth = authorize_workflow(policy)
    artifact.verify_implementation(auth)
    built = StateStore(auth).inspect()
    # Accepted C1 can consume an independent final-source receipt without a
    # REL1B journal. Observe that legitimate artifact layout as unverified;
    # never synthesize integration logs or infer mutation permission from it.
    integrated = (Journal(auth).inspect() if built is None or
                  os.path.lexists(auth.managed / 'journal.json') else None)
    if built is not None:
        stage = built['state']
        if os.path.lexists(StateStore(auth).root / 'publication'):
            # Without accepting a plan/Human receipt, only validate local shape
            # and return an explicitly unverified publication hint.
            from release_approval import decode, read_file, canonical
            from release_publication_state import PublicationStore
            raw = read_file(StateStore(auth).root / 'publication/state.json', owner=os.getuid(), mode=0o600)
            value = decode(raw)
            require(type(value) is dict and all(key in value for key in ('plan_sha256', 'artifact_id', 'tag_oid')),
                    'PUBLICATION_STATE_SCHEMA')
            store = PublicationStore(auth, value['plan_sha256'], value['artifact_id'], value['tag_oid'])
            value = store.inspect()
            require(canonical(value) == raw and built['artifact'] is not None and
                    value['artifact_id'] == built['artifact']['artifact_id'], 'PUBLICATION_STATE_BINDING')
            return 'PUBLICATION_' + value['state'] + '_RECORDED_UNVERIFIED'
        return stage + '_RECORDED_UNVERIFIED'
    return ('INTEGRATION_' + integrated['state'] + '_RECORDED_UNVERIFIED'
            if integrated is not None else 'MISSING')


def prepare(policy, *, fixture_gate=None, fixture_integration_checkpoint=None, fixture_build=None):
    """Run safe next stage only. Separate external source acceptance is mandatory."""
    require(policy.fixture_root is not None or
            all(item is None for item in (fixture_gate, fixture_integration_checkpoint, fixture_build)),
            'FIXTURE_BOUNDARY')
    auth = authorize_workflow(policy)
    artifact.verify_implementation(auth)
    # An existing but invalid receipt must fail, not be interpreted as absent.
    receipt = policy.root / 'integration.json'
    if not os.path.lexists(receipt):
        recorded = Journal(auth).inspect()
        if recorded is not None and recorded['state'] == 'COMPLETE':
            raise Stop('FINAL_MAIN_REVIEW_REQUIRED')
        from release_integration import Integration
        Integration(policy, fixture_gate=fixture_gate, checkpoint=fixture_integration_checkpoint).execute()
        return 'FINAL_MAIN_REVIEW_REQUIRED'
    source, source_hash = artifact.accepted_source(policy, auth, remote=True)
    built = StateStore(auth).inspect()
    if built is not None and built['state'] in ('ARTIFACT', 'HUMAN_RECORDED'):
        artifact.validate_artifact(built['artifact'], auth, source, source_hash)
        return 'EXACT_ARTIFACT_HUMAN_REVIEW_REQUIRED'
    if built is not None and built['state'] not in ('NEW', 'REVIEW_REQUIRED'):
        raise Stop('RECOVERY_REVIEW_REQUIRED')
    from release_workflow import BuildController
    controller = (BuildController(policy) if fixture_build is None else fixture_build(policy))
    require(type(controller) is BuildController, 'FIXTURE_BOUNDARY')
    controller.execute()
    return 'EXACT_ARTIFACT_HUMAN_REVIEW_REQUIRED'


def publish(policy):
    from release_publication import Publisher
    return Publisher(policy).execute()


def resume(policy, *, fixture_gate=None, fixture_integration_checkpoint=None):
    """Resume only an existing stage, never automatically start a new stage."""
    require(policy.fixture_root is not None or
            all(item is None for item in (fixture_gate, fixture_integration_checkpoint)), 'FIXTURE_BOUNDARY')
    auth = authorize_workflow(policy)
    artifact.verify_implementation(auth)
    store = StateStore(auth)
    built = store.inspect()
    if os.path.lexists(store.root / 'publication'):
        require(built is not None and built['state'] in ('ARTIFACT', 'HUMAN_RECORDED'),
                'RECOVERY_PROOF_MISSING')
        # Publisher disregards advanced hints, reauthenticates all decisions,
        # and requires external exact-ID ownership for cross-invocation objects.
        return publish(policy)
    if built is not None:
        require(built['state'] in ('BUILDING', 'BUILT', 'PACKAGING', 'ARTIFACT', 'HUMAN_RECORDED'),
                'EXPLICIT_PREPARE_REQUIRED')
        from release_workflow import resume as build_resume
        return build_resume(policy)
    recorded = Journal(auth).inspect()
    require(recorded is not None, 'RECOVERY_PROOF_MISSING')
    if recorded['state'] == 'COMPLETE':
        return 'FINAL_MAIN_REVIEW_AND_EXPLICIT_PREPARE_REQUIRED'
    from release_integration import Integration
    Integration(policy, fixture_gate=fixture_gate, checkpoint=fixture_integration_checkpoint).execute()
    return 'FINAL_MAIN_REVIEW_REQUIRED'
