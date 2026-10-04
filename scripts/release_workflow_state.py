"""C1 durable recovery hints, separate from REL1B's closed journal root."""
from __future__ import annotations

import os
import uuid
from pathlib import Path

from release_approval import (
    TOKEN, Stop, absolute, canonical, decode, digest, fields, hex_value,
    inspect_path, read_file, require,
)
from release_artifact import artifact_schema
from release_journal import fsync_directory

DIRECTORIES = ('attempts', 'artifacts', 'human', 'evidence', 'tmp')
STATES = ('NEW', 'BUILDING', 'BUILT', 'PACKAGING', 'ARTIFACT', 'HUMAN_RECORDED', 'REVIEW_REQUIRED')
FIELDS = ('schema_version', 'sequence', 'authorization_sha256', 'trust_sha256',
          'state', 'intent', 'attempt', 'artifact', 'human_receipt', 'checksum')


def initial(auth):
    return {'schema_version': 1, 'sequence': 0, 'authorization_sha256': auth.sha256,
            'trust_sha256': auth.trust_sha256, 'state': 'NEW', 'intent': None,
            'attempt': None, 'artifact': None, 'human_receipt': None}


def with_checksum(value):
    payload = {key: item for key, item in value.items() if key != 'checksum'}
    return {**payload, 'checksum': digest(canonical(payload))}


def validate(value, auth):
    fields(value, FIELDS)
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            type(value['sequence']) is int and value['sequence'] >= 0, 'STATE_SCHEMA')
    require(type(value['state']) is str and value['state'] in STATES, 'STATE_SCHEMA')
    require(value['authorization_sha256'] == auth.sha256 and
            value['trust_sha256'] == auth.trust_sha256, 'STATE_BINDING')
    hex_value(value['checksum'])
    require(value == with_checksum(value), 'STATE_CHECKSUM')
    allowed_intent = {'NEW': (None,), 'BUILDING': ('BUILD',), 'BUILT': (None,),
                      'PACKAGING': ('PACKAGE',), 'ARTIFACT': (None, 'HUMAN_CHECK'),
                      'HUMAN_RECORDED': (None,), 'REVIEW_REQUIRED': (None,)}
    require(value['intent'] is None or type(value['intent']) is str, 'STATE_SCHEMA')
    require(value['intent'] in allowed_intent[value['state']], 'STATE_SCHEMA')
    require(value['attempt'] is None or
            (type(value['attempt']) is str and TOKEN.fullmatch(value['attempt'])), 'STATE_SCHEMA')
    require((value['attempt'] is None) == (value['state'] == 'NEW'), 'STATE_SCHEMA')
    has_artifact = value['state'] in ('ARTIFACT', 'HUMAN_RECORDED')
    require((value['artifact'] is not None) == has_artifact, 'STATE_SCHEMA')
    if has_artifact:
        artifact_schema(value['artifact'], auth)
        require(value['artifact']['attempt'] == value['attempt'], 'STATE_BINDING')
    require((value['human_receipt'] is not None) == (value['state'] == 'HUMAN_RECORDED'), 'STATE_SCHEMA')
    if value['human_receipt'] is not None:
        receipt = value['human_receipt']
        fields(receipt, ('receipt_id', 'receipt_sha256', 'decision_reference'))
        for key in ('receipt_id', 'decision_reference'):
            require(type(receipt[key]) is str and TOKEN.fullmatch(receipt[key]), 'STATE_SCHEMA')
        hex_value(receipt['receipt_sha256'])
    return value


class StateStore:
    def __init__(self, auth):
        self.auth = auth
        self.root = absolute(auth.payload['workflow'])
        self.path = self.root / 'state.json'

    def inspect(self, *, missing=True):
        if not inspect_path(self.root, owner=os.getuid(), mode=0o700, directory=True, missing=missing):
            return None
        require(all(item.name in ('state.json', 'publication', *DIRECTORIES) for item in self.root.iterdir()),
                'PERSISTENCE_INCOMPLETE')
        if os.path.lexists(self.root / 'publication'):
            inspect_path(self.root / 'publication', owner=os.getuid(), mode=0o700, directory=True)
        for name in DIRECTORIES:
            inspect_path(self.root / name, owner=os.getuid(), mode=0o700, directory=True)
        require(inspect_path(self.path, owner=os.getuid(), mode=0o600, missing=True), 'PERSISTENCE_INCOMPLETE')
        raw = read_file(self.path, owner=os.getuid(), mode=0o600)
        value = validate(decode(raw), self.auth)
        require(raw == canonical(value), 'STATE_SCHEMA')
        return value

    def create(self):
        require(not os.path.lexists(self.root), 'PERSISTENCE_EXISTS')
        inspect_path(self.root.parent, owner=os.getuid(), directory=True)
        self.root.mkdir(mode=0o700)
        fsync_directory(self.root.parent)
        for name in DIRECTORIES:
            (self.root / name).mkdir(mode=0o700)
            fsync_directory(self.root)
        return self.write(initial(self.auth), creating=True)

    def write(self, value, *, creating=False):
        inspect_path(self.root, owner=os.getuid(), mode=0o700, directory=True)
        if creating:
            require(not os.path.lexists(self.path), 'PERSISTENCE_EXISTS')
        else:
            self.inspect(missing=False)
        next_value = dict(value)
        require(type(next_value.get('sequence')) is int, 'STATE_SCHEMA')
        next_value['sequence'] += 1
        next_value = validate(with_checksum(next_value), self.auth)
        temporary = self.root / ('.state-' + uuid.uuid4().hex)
        replaced = False
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(canonical(next_value))
                handle.flush()
                os.fsync(handle.fileno())
            inspect_path(temporary, owner=os.getuid(), mode=0o600)
            if not creating:
                inspect_path(self.path, owner=os.getuid(), mode=0o600)
            os.replace(temporary, self.path)
            replaced = True
            fsync_directory(self.root)
        except OSError as exc:
            # Keep partial bytes/preimage. Inspect stops; no silent repair.
            raise Stop('PERSISTENCE_UNCERTAIN' if replaced else 'PERSISTENCE_FAILED') from exc
        return next_value

    def change(self, value, **updates):
        return self.write({**value, **updates})

    def new_attempt(self, value):
        """Persist intent before creating a unique, never reused attempt path.

        The live controller executes only after independent revalidation.
        Retries use a new ID; no old workspace or artifact is removed.
        """
        require(value['state'] in ('NEW', 'REVIEW_REQUIRED'), 'RECOVERY_REVIEW_REQUIRED')
        attempt = 'attempt-' + uuid.uuid4().hex
        value = self.change(value, state='BUILDING', intent='BUILD', attempt=attempt,
                            artifact=None, human_receipt=None)
        for name in ('attempts', 'artifacts', 'evidence'):
            parent = self.root / name
            inspect_path(parent, owner=os.getuid(), mode=0o700, directory=True)
            target = parent / attempt
            require(not os.path.lexists(target), 'ATTEMPT_COLLISION')
            target.mkdir(mode=0o700)
            fsync_directory(parent)
        # Human extraction must remain absent for the accepted ZIP helper.
        return value
