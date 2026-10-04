"""Atomic publication hints. Remote IDs/checksums never prove object ownership."""
from __future__ import annotations

import os
import uuid

from release_approval import (SHA, canonical, decode, digest, fields, hex_value,
                              inspect_path, read_file, require, Stop)
from release_journal import fsync_directory

STATES = ('NEW', 'TAGGED', 'DRAFT', 'UPLOADED', 'VERIFIED', 'PUBLISHED', 'COMPLETE')
INTENTS = {'NEW': (None, 'TAG_PUSH'), 'TAGGED': (None, 'CREATE'),
           'DRAFT': (None, 'UPLOAD'), 'UPLOADED': (None, 'DOWNLOAD_DRAFT'),
           'VERIFIED': (None, 'PUBLISH'), 'PUBLISHED': (None, 'DOWNLOAD_PUBLIC'),
           'COMPLETE': (None,)}
FIELDS = ('schema_version', 'sequence', 'authorization_sha256', 'trust_sha256',
          'plan_sha256', 'artifact_id', 'state', 'intent', 'tag_oid', 'release_id',
          'asset_id', 'downloads', 'checksum')


def with_checksum(value):
    payload = {k: v for k, v in value.items() if k != 'checksum'}
    return {**payload, 'checksum': digest(canonical(payload))}


def initial(auth, plan_hash, artifact_id, tag_oid):
    return {'schema_version': 1, 'sequence': 0, 'authorization_sha256': auth.sha256,
            'trust_sha256': auth.trust_sha256, 'plan_sha256': plan_hash,
            'artifact_id': artifact_id, 'state': 'NEW', 'intent': None,
            'tag_oid': tag_oid, 'release_id': None, 'asset_id': None, 'downloads': []}


def validate(value, auth, plan_hash, artifact_id, tag_oid):
    fields(value, FIELDS)
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and
            type(value['sequence']) is int and value['sequence'] > 0, 'PUBLICATION_STATE_SCHEMA')
    require(type(value['state']) is str and value['state'] in STATES and
            (value['intent'] is None or type(value['intent']) is str) and
            value['intent'] in INTENTS[value['state']], 'PUBLICATION_STATE_SCHEMA')
    for name, expected in initial(auth, plan_hash, artifact_id, tag_oid).items():
        if name not in ('sequence', 'state', 'intent', 'release_id', 'asset_id', 'downloads'):
            require(value[name] == expected, 'PUBLICATION_STATE_BINDING')
    hex_value(value['checksum'])
    for name in ('plan_sha256', 'artifact_id', 'authorization_sha256', 'trust_sha256'):
        hex_value(value[name])
    hex_value(value['tag_oid'], SHA)
    require(value == with_checksum(value), 'PUBLICATION_STATE_CHECKSUM')
    for name in ('release_id', 'asset_id'):
        require(value[name] is None or type(value[name]) is int and value[name] > 0,
                'PUBLICATION_STATE_SCHEMA')
    require(value['asset_id'] is None or value['release_id'] is not None, 'PUBLICATION_STATE_SCHEMA')
    require((value['release_id'] is not None) == (value['state'] not in ('NEW', 'TAGGED')) and
            (value['asset_id'] is not None) == (value['state'] in ('UPLOADED', 'VERIFIED', 'PUBLISHED', 'COMPLETE')),
            'PUBLICATION_STATE_SCHEMA')
    require(type(value['downloads']) is list and len(value['downloads']) <= 100, 'PUBLICATION_STATE_SCHEMA')
    for item in value['downloads']:
        fields(item, ('phase', 'file', 'bytes', 'sha256'))
        require(item['phase'] in ('draft', 'public') and type(item['file']) is str and
                len(item['file']) == 45 and item['file'].startswith('download-') and
                item['file'].endswith('.zip') and
                all(c in '0123456789abcdef' for c in item['file'][9:-4]) and
                type(item['bytes']) is int and item['bytes'] > 0, 'PUBLICATION_STATE_SCHEMA')
        hex_value(item['sha256'])
    phases = {item['phase'] for item in value['downloads']}
    require(value['state'] != 'VERIFIED' or 'draft' in phases,
            'PUBLICATION_STATE_SCHEMA')
    require(value['state'] != 'COMPLETE' or 'public' in phases, 'PUBLICATION_STATE_SCHEMA')
    return value


class PublicationStore:
    def __init__(self, auth, plan_hash, artifact_id, tag_oid):
        from release_approval import absolute
        self.auth = auth
        self.plan_hash, self.artifact_id, self.tag_oid = plan_hash, artifact_id, tag_oid
        self.root = absolute(auth.payload['workflow']) / 'publication'
        self.path = self.root / 'state.json'

    def validate(self, value):
        return validate(value, self.auth, self.plan_hash, self.artifact_id, self.tag_oid)

    def inspect(self):
        if not inspect_path(self.root, owner=os.getuid(), mode=0o700, directory=True, missing=True):
            return None
        require(sorted(p.name for p in self.root.iterdir()) == ['downloads', 'state.json'],
                'PUBLICATION_PERSISTENCE_INCOMPLETE')
        inspect_path(self.root / 'downloads', owner=os.getuid(), mode=0o700, directory=True)
        raw = read_file(self.path, owner=os.getuid(), mode=0o600)
        value = self.validate(decode(raw))
        require(raw == canonical(value), 'PUBLICATION_STATE_SCHEMA')
        return value

    def create(self):
        require(not os.path.lexists(self.root), 'PUBLICATION_PERSISTENCE_EXISTS')
        inspect_path(self.root.parent, owner=os.getuid(), mode=0o700, directory=True)
        self.root.mkdir(mode=0o700)
        fsync_directory(self.root.parent)
        (self.root / 'downloads').mkdir(mode=0o700)
        fsync_directory(self.root)
        return self.write(initial(self.auth, self.plan_hash, self.artifact_id, self.tag_oid), creating=True)

    def write(self, value, *, creating=False):
        inspect_path(self.root, owner=os.getuid(), mode=0o700, directory=True)
        if not creating:
            self.inspect()
        else:
            require(not os.path.lexists(self.path), 'PUBLICATION_PERSISTENCE_EXISTS')
        value = self.validate(with_checksum({**value, 'sequence': value['sequence'] + 1}))
        temporary = self.root / ('.state-' + uuid.uuid4().hex)
        replaced = False
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as handle:
                handle.write(canonical(value))
                handle.flush()
                os.fsync(handle.fileno())
            if not creating:
                inspect_path(self.path, owner=os.getuid(), mode=0o600)
            os.replace(temporary, self.path)
            replaced = True
            fsync_directory(self.root)
        except OSError as exc:
            raise Stop('PUBLICATION_PERSISTENCE_UNCERTAIN' if replaced else
                       'PUBLICATION_PERSISTENCE_FAILED') from exc
        return value

    def change(self, value, **updates):
        return self.write({**value, **updates})
