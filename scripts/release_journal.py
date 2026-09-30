"""Closed REL1B recovery hints. Checksums are not authorization or gate proof."""
from __future__ import annotations

import os
import stat
import uuid
from pathlib import Path

from release_approval import (Authorization, Stop, SHA, canonical, decode, digest,
                              fields, hex_value, inspect_path, read_file, require)

STATES = ('NEW', 'READY', 'MERGED', 'GATED', 'COMPLETE')
INTENTS = {
    'NEW': (None, 'CLONE', 'FETCH'),
    'READY': (None, 'FEATURE_PUSH', 'MERGE'),
    'MERGED': (None, 'BOOTSTRAP', 'STRICT'),
    'GATED': (None, 'MAIN_PUSH', 'BOOTSTRAP'),
    'COMPLETE': (None,),
}
KEYS = ('schema_version', 'sequence', 'approval_sha256', 'trust_sha256',
        'accepted_commit', 'tools', 'origin', 'main_ref', 'feature_ref', 'managed',
        'state', 'intent', 'merge_commit', 'merge_tree', 'gate', 'feature_receipt',
        'main_receipt', 'checksum')


def initial(auth: Authorization):
    p = auth.payload
    return {
        'schema_version': 1, 'sequence': 0, 'approval_sha256': auth.sha256,
        'trust_sha256': auth.trust_sha256, 'accepted_commit': p['accepted_commit'],
        'tools': p['tools'], 'origin': p['origin'], 'main_ref': p['main_ref'],
        'feature_ref': p['feature_ref'], 'managed': p['managed'], 'state': 'NEW',
        'intent': None, 'merge_commit': None, 'merge_tree': None, 'gate': None,
        'feature_receipt': None, 'main_receipt': None,
    }


def with_checksum(value):
    payload = {key: item for key, item in value.items() if key != 'checksum'}
    return {**payload, 'checksum': digest(canonical(payload))}


def validate(value, auth: Authorization):
    fields(value, KEYS)
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            type(value['sequence']) is int and value['sequence'] >= 0, 'JOURNAL_SCHEMA')
    require(type(value['state']) is str and value['state'] in STATES, 'JOURNAL_STATE')
    require(value['intent'] is None or type(value['intent']) is str, 'JOURNAL_SCHEMA')
    require(value['intent'] in INTENTS[value['state']], 'JOURNAL_STATE')
    hex_value(value['checksum'])
    require(value == with_checksum(value), 'JOURNAL_CHECKSUM')
    for key, expected in initial(auth).items():
        if key not in ('sequence', 'state', 'intent', 'merge_commit', 'merge_tree',
                       'gate', 'feature_receipt', 'main_receipt'):
            require(value[key] == expected, 'JOURNAL_BINDING')
    for name in ('merge_commit', 'merge_tree', 'feature_receipt', 'main_receipt'):
        if value[name] is not None:
            hex_value(value[name], SHA)
    require((value['merge_commit'] is None) == (value['merge_tree'] is None), 'JOURNAL_STATE')
    if value['state'] in ('NEW', 'READY'):
        require(value['merge_commit'] is None and value['gate'] is None and value['main_receipt'] is None, 'JOURNAL_STATE')
    else:
        require(value['merge_commit'] is not None, 'JOURNAL_STATE')
    if value['state'] in ('GATED', 'COMPLETE'):
        require(value['gate'] is not None, 'JOURNAL_STATE')
    else:
        require(value['gate'] is None, 'JOURNAL_STATE')
    require((value['main_receipt'] is not None) == (value['state'] == 'COMPLETE'), 'JOURNAL_STATE')
    require(value['feature_receipt'] is None or value['feature_receipt'] == auth.payload['accepted_commit'], 'JOURNAL_BINDING')
    require(value['main_receipt'] is None or value['main_receipt'] == value['merge_commit'], 'JOURNAL_BINDING')
    if value['gate'] is not None:
        gate = value['gate']
        fields(gate, ('source', 'bootstrap', 'strict'))
        require(gate['source'] == value['merge_commit'], 'JOURNAL_BINDING')
        for kind in ('bootstrap', 'strict'):
            fields(gate[kind], ('file', 'sha256'))
            require(type(gate[kind]['file']) is str and
                    gate[kind]['file'].startswith(kind + '-') and
                    gate[kind]['file'].endswith('.log') and
                    Path(gate[kind]['file']).name == gate[kind]['file'] and
                    len(gate[kind]['file']) < 100, 'JOURNAL_SCHEMA')
            hex_value(gate[kind]['sha256'])
    return value


def fsync_directory(path: Path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Journal:
    def __init__(self, auth: Authorization):
        self.auth = auth
        self.root = auth.managed
        self.path = self.root / 'journal.json'

    def inspect(self, *, missing=True):
        if not inspect_path(self.root, owner=os.getuid(), mode=0o700, directory=True, missing=missing):
            return None
        require(not any(item.name.startswith('.journal-') for item in self.root.iterdir()), 'PERSISTENCE_INCOMPLETE')
        # No repairing or inferring a lost journal from an existing managed root.
        if not inspect_path(self.path, owner=os.getuid(), mode=0o600, missing=True):
            raise Stop('PERSISTENCE_INCOMPLETE')
        raw = read_file(self.path, owner=os.getuid(), mode=0o600)
        value = validate(decode(raw), self.auth)
        require(raw == canonical(value), 'JOURNAL_SCHEMA')
        for name in ('evidence', 'tmp'):
            inspect_path(self.root / name, owner=os.getuid(), mode=0o700, directory=True)
        allowed = {'journal.json', 'evidence', 'tmp', 'clone'}
        require(all(item.name in allowed for item in self.root.iterdir()), 'PERSISTENCE_INCOMPLETE')
        return value

    def create(self):
        require(not os.path.lexists(self.root), 'PERSISTENCE_EXISTS')
        inspect_path(self.root.parent, owner=os.getuid(), directory=True)
        self.root.mkdir(mode=0o700)
        fsync_directory(self.root.parent)
        (self.root / 'evidence').mkdir(mode=0o700)
        (self.root / 'tmp').mkdir(mode=0o700)
        return self.write(initial(self.auth), creating=True)

    def write(self, value, *, creating=False):
        inspect_path(self.root, owner=os.getuid(), mode=0o700, directory=True)
        if not creating:
            self.inspect(missing=False)
        else:
            require(not os.path.lexists(self.path), 'PERSISTENCE_EXISTS')
        next_value = dict(value)
        next_value['sequence'] += 1
        next_value = validate(with_checksum(next_value), self.auth)
        temporary = self.root / ('.journal-' + uuid.uuid4().hex)
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
            # Keep failed temporary data/preimage as evidence. Never silently repair.
            raise Stop('PERSISTENCE_UNCERTAIN' if replaced else 'PERSISTENCE_FAILED') from exc
        return next_value

    def change(self, value, **updates):
        return self.write({**value, **updates})

    def validate_logs(self, value):
        if value['gate'] is not None:
            for kind in ('bootstrap', 'strict'):
                item = value['gate'][kind]
                actual = read_file(self.root / 'evidence' / item['file'], owner=os.getuid(), mode=0o600,
                                   limit=64 * 1024 * 1024)
                require(digest(actual) == item['sha256'], 'GATE_EVIDENCE_CHANGED')
        # Deliberately returns no PASS authority.
