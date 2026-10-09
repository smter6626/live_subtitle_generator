"""Independent Owner decision on exact retained bytes; no signing or publishing."""
from __future__ import annotations

from release_approval import authenticated_receipt, require
from release_artifact import accepted_source, artifact_schema, validate_artifact
from release_approval import canonical


def validate_human_gate(policy, auth, artifact):
    """Callable C2 gate. Reauthenticate and recheck every binding on every call.

    A true return proves only the purpose-specific external PASS and current
    artifact facts. C1 exposes no tag, draft, upload or publication action.
    """
    source, source_hash = accepted_source(policy, auth)
    validate_artifact(artifact, auth, source, source_hash)
    receipt, checksum = authenticated_receipt(
        policy, auth, 'artifact-human', ('decision', 'integration_receipt_sha256', 'artifact'))
    require(type(receipt['decision']) is str and receipt['decision'] in ('PASS', 'FAIL'), 'HUMAN_DECISION_INVALID')
    artifact_schema(receipt['artifact'], auth)
    require(receipt['integration_receipt_sha256'] == source_hash and
            canonical(receipt['artifact']) == canonical(artifact), 'HUMAN_ARTIFACT_BINDING')
    # Even a correctly signed FAIL stops. Implementation/integration decisions,
    # recomputed metadata, local logs and state are never consulted as PASS.
    require(receipt['decision'] == 'PASS', 'HUMAN_FAIL')
    validate_artifact(artifact, auth, source, source_hash)
    return {'receipt_id': receipt['id'], 'receipt_sha256': checksum,
            'decision_reference': receipt['decision_reference']}
