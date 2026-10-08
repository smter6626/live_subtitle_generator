"""Ordinary local decisions for the Human-authorized lightweight workflow.

References record real Reviewer/Human decisions. Hashes bind facts, not powers:
this mode intentionally does not resist a malicious writer with the same uid.
"""
from __future__ import annotations

import os
from pathlib import Path

from release_approval import (Authorization, LightweightPolicy, LIGHTWEIGHT_PURPOSE,
    LIGHTWEIGHT_REQUIRED_TOOLS, MAIN, FEATURE, ORIGINS, REPOSITORY, RECEIPT_PURPOSES,
    SHA, TOKEN, absolute, canonical, decode, digest, downloads, fields, hex_value,
    inspect_path, read_file, require)

APPROVAL_FIELDS = ('schema_version', 'mode', 'id', 'accepted_commit', 'tools', 'contracts',
    'reviewer_reference', 'integration_authorization_reference', 'repository', 'origin',
    'main_ref', 'feature_ref', 'main', 'feature_prior', 'baseline', 'implementation',
    'managed', 'workflow', 'uid')


def reference(value):
    require(type(value) is str and TOKEN.fullmatch(value), 'DECISION_REFERENCE_INVALID')


def local_authorization(policy):
    require(type(policy) is LightweightPolicy, 'APPROVAL_POLICY')
    policy.check_fixture()
    path = absolute(str(policy.approval_path))
    inspect_path(policy.root, owner=os.getuid(), mode=0o700, directory=True)
    raw = read_file(path, owner=os.getuid(), mode=0o600)
    value = decode(raw)
    fields(value, APPROVAL_FIELDS)
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            value['mode'] == 'lightweight' and type(value['uid']) is int and value['uid'] == os.getuid(),
            'APPROVAL_IDENTITY')
    for name in ('id', 'reviewer_reference', 'integration_authorization_reference'):
        reference(value[name])
    require(value['repository'] == REPOSITORY and value['main_ref'] == MAIN and
            value['feature_ref'] == FEATURE, 'APPROVAL_IDENTITY')
    for name in ('accepted_commit', 'main', 'baseline'):
        hex_value(value[name], SHA)
    if value['feature_prior'] is not None:
        hex_value(value['feature_prior'], SHA)
    implementation = absolute(value['implementation'])
    managed, workflow = absolute(value['managed']), absolute(value['workflow'])
    inspect_path(implementation, owner=os.getuid(), directory=True)
    for root in (managed, workflow):
        require(root.is_relative_to(downloads()) and root != downloads() and
                not root.is_relative_to(implementation) and not implementation.is_relative_to(root),
                'MANAGED_BOUNDARY')
        inspect_path(root.parent, owner=os.getuid(), directory=True)
    require(not managed.is_relative_to(workflow) and not workflow.is_relative_to(managed) and
            not policy.root.is_relative_to(managed) and not policy.root.is_relative_to(workflow),
            'MANAGED_BOUNDARY')
    if policy.fixture_root is None:
        require(value['origin'] in ORIGINS, 'ORIGIN_INVALID')
    else:
        root = policy.fixture_root
        require(value['origin'] == str(root / 'remote.git') and implementation == root / 'source' and
                managed == root / 'managed' and workflow == root / 'workflow', 'FIXTURE_BOUNDARY')
    fields(value['tools'], LIGHTWEIGHT_REQUIRED_TOOLS)
    for relative, checksum in value['tools'].items():
        hex_value(checksum)
        require(digest(read_file(implementation / relative)) == checksum, 'TOOL_CHANGED')
    fields(value['contracts'], policy.contracts)
    for name, contract in policy.contracts.items():
        require(value['contracts'][name] == digest(read_file(contract)), 'CONTRACT_CHANGED')
    require(raw == canonical(value), 'SCHEMA_INVALID')
    # Existing stores retain their historical key names. Neither checksum is a
    # signed trust root in this mode; both merely fix local input identities.
    payload = {**value, 'purpose': LIGHTWEIGHT_PURPOSE}
    return Authorization(payload, digest(raw), digest(canonical(value['contracts'])))


def local_receipt(policy, auth, kind, names):
    require(kind in RECEIPT_PURPOSES and local_authorization(policy) == auth, 'APPROVAL_CHANGED')
    raw = read_file(policy.root / (kind + '.json'), owner=os.getuid(), mode=0o600)
    value = decode(raw)
    common = ('schema_version', 'id', 'purpose', 'authorization_sha256', 'decision_reference')
    extra = ('publish_allowed',) if kind == 'artifact-human' else ()
    fields(value, (*common, *names, *extra))
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            value['purpose'] == RECEIPT_PURPOSES[kind] and
            value['authorization_sha256'] == auth.sha256, 'RECEIPT_BINDING')
    reference(value['id'])
    reference(value['decision_reference'])
    if kind == 'artifact-human':
        require(type(value['publish_allowed']) is bool and value['publish_allowed'], 'HUMAN_PUBLICATION_NOT_ALLOWED')
    require(raw == canonical(value), 'SCHEMA_INVALID')
    return value, digest(raw)
