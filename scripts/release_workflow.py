#!/usr/bin/env python3
"""C1 candidate status/build/resume/human-gate. Build awaits boundary review."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Load the entire protected legacy-plus-C1 control set before authorization.
import release_controller
import release_integration
import release_journal
import release_artifact
import release_human_gate
import release_workflow_state
from release_approval import WorkflowPolicy, Stop, authorize_workflow, require


def build_parser():
    parser = release_controller.Parser(description=__doc__, allow_abbrev=False)
    parser.add_argument('command', choices=('status', 'build', 'resume', 'human-gate'))
    return parser


def status(policy):
    auth = authorize_workflow(policy)
    release_artifact.verify_implementation(auth)
    value = release_workflow_state.StateStore(auth).inspect()
    # No independent source/Human decision is accepted or promoted here. Never
    # execute App/interpreter, create directories, repair, fetch or write state.
    return 'MISSING' if value is None else value['state'] + '_RECORDED_UNVERIFIED'


def fresh_source(repo: Path):
    release_integration.clean(repo)
    release_integration.worktree_bytes(repo)
    # Even ignored dist or an apparently correct .venv is untrusted until fresh
    # pinned acquisition in this invocation. Do not execute or remove it.
    require(not release_integration.git(repo, 'ls-files', '--others', '--ignored', '--exclude-standard'),
            'ENVIRONMENT_UNTRUSTED')
    require(not any(os.path.lexists(repo / name) for name in ('.tools', '.venv', 'dist', 'build', 'external')),
            'ENVIRONMENT_UNTRUSTED')


def build(policy):
    auth = authorize_workflow(policy)
    source, _ = release_artifact.accepted_source(policy, auth, remote=True)
    release_artifact.verify_implementation(auth)
    # Do not create an attempt or execute the indivisible build chain before its
    # stage checkpoints have been reviewed. The allowlist excludes that script.
    # A whole-chain before/after hash is insufficient for the required checks.
    require(source['source_commit'] != auth.payload['accepted_commit'], 'SOURCE_RECEIPT_BINDING')
    raise Stop('BUILD_PROTOCOL_REVIEW_REQUIRED')


def resume(policy):
    auth = authorize_workflow(policy)
    release_artifact.verify_implementation(auth)
    value = release_workflow_state.StateStore(auth).inspect()
    require(value is not None, 'RECOVERY_PROOF_MISSING')
    # Never infer a successful process or recover invocation-local environment
    # trust from checksummed records, provenance or a surviving dist/App.
    if value['state'] in ('ARTIFACT', 'HUMAN_RECORDED') and value['intent'] is None:
        source, checksum = release_artifact.accepted_source(policy, auth)
        release_artifact.validate_artifact(value['artifact'], auth, source, checksum)
        return value['state'] + '_RECORDED_UNVERIFIED'
    raise Stop('RECOVERY_REVIEW_REQUIRED')


def human_gate(policy):
    auth = authorize_workflow(policy)
    release_artifact.verify_implementation(auth)
    store = release_workflow_state.StateStore(auth)
    value = store.inspect()
    require(value is not None and value['state'] in ('ARTIFACT', 'HUMAN_RECORDED'), 'ARTIFACT_MISSING')
    # Validate before recording intent, then again before/after the outcome.
    decision = release_human_gate.validate_human_gate(policy, auth, value['artifact'])
    if value['state'] == 'HUMAN_RECORDED':
        require(value['human_receipt'] == decision, 'RECEIPT_CHANGED')
        return 'HUMAN_RECORDED_C1_ONLY'
    require(value['intent'] is None, 'RECOVERY_REVIEW_REQUIRED')
    value = store.change(value, intent='HUMAN_CHECK')
    require(authorize_workflow(policy) == auth, 'APPROVAL_CHANGED')
    require(release_human_gate.validate_human_gate(policy, auth, value['artifact']) == decision, 'RECEIPT_CHANGED')
    value = store.change(value, state='HUMAN_RECORDED', intent=None, human_receipt=decision)
    require(release_human_gate.validate_human_gate(policy, auth, value['artifact']) == decision, 'RECEIPT_CHANGED')
    return 'HUMAN_RECORDED_C1_ONLY'


def _run(argv, policy):
    args = build_parser().parse_args(argv)
    try:
        stage = {'status': status, 'build': build, 'resume': resume, 'human-gate': human_gate}[args.command](policy)
        print('release-workflow: ' + stage)
        return 0
    except Stop as exc:
        print('release-workflow: STOP ' + exc.code, file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError):
        print('release-workflow: STOP OPERATION_FAILED', file=sys.stderr)
        return 1


def main(argv=None):
    return _run(sys.argv[1:] if argv is None else argv, WorkflowPolicy())


if __name__ == '__main__':
    raise SystemExit(main())
