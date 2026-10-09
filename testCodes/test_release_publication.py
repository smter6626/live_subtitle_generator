"""Actual fake-gh process, binary bytes and signed decisions; no network API."""
from __future__ import annotations

import base64
import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from testCodes.test_release_workflow import Fixture as BaseFixture, retained_root, snapshot
import release_approval as approval
import release_publication as publication
import release_publication_state as state
import release_integration as integration

FAKE_GH = r'''#!PYTHON -B
import base64, json, os, pathlib, sys
root = pathlib.Path(__file__).parent
argv = sys.argv[1:]
endpoint = argv[1]
method = argv[argv.index('--method') + 1]
binary = 'Accept: application/octet-stream' in argv
stdin = sys.stdin.buffer.read() if '--input' in argv and argv[argv.index('--input')+1] == '-' else b''
uploaded = pathlib.Path(argv[argv.index('--input')+1]).read_bytes() if '--input' in argv and not stdin else None
record = {'argv': argv, 'stdin': base64.b64encode(stdin).decode(),
          'upload': None if uploaded is None else base64.b64encode(uploaded).decode(),
          'env_keys': sorted(os.environ), 'dont_write_bytecode': sys.dont_write_bytecode}
with (root/'fake-gh-calls.jsonl').open('a') as log: log.write(json.dumps(record)+'\n')
path = root/'fake-remote.json'
remote = json.loads(path.read_text())
mode = remote.get('fault')
status = 200
base = 'repos/smter6626/live_subtitle_generator'
release_url = 'https://api.github.com/'+base+'/releases/101'
if mode in ('403','500','bad-json','empty'):
    status = int(mode) if mode.isdigit() else 200
    body = b'not-json' if mode == 'bad-json' else b''
elif binary:
    body = (root/'fake-upload.zip').read_bytes()
    if mode == 'corrupt-download': body += b'x'
elif method == 'POST' and endpoint == base+'/releases':
    value = json.loads(stdin)
    remote['release'] = {'id':101, **value, 'url':release_url,
        'html_url':'https://github.com/smter6626/live_subtitle_generator/releases/tag/1.1.0', 'published_at':None}
    remote['assets'] = []
    body = json.dumps(remote['release']).encode()
    status = 201
elif method == 'POST' and endpoint.startswith('https://uploads.github.com/'+base+'/releases/101/assets?name='):
    (root/'fake-upload.zip').write_bytes(uploaded)
    value = {'id':201,'name':'ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip',
        'state':'uploaded','size':len(uploaded),'content_type':'application/zip',
        'url':'https://api.github.com/'+base+'/releases/assets/201',
        'browser_download_url':'https://github.com/smter6626/live_subtitle_generator/releases/download/1.1.0/ClassroomTranscriber-1.1.0-macOS-AppleSilicon.zip'}
    remote['assets'] = [value]
    if mode == 'starter': remote['assets'][0]['state']='starter'
    body = json.dumps(remote['assets'][0]).encode()
    status = 201
elif method == 'PATCH':
    remote['release'].update(json.loads(stdin))
    remote['release']['published_at']='2026-10-03T12:00:00Z'
    body = json.dumps(remote['release']).encode()
elif '/assets?' in endpoint:
    body = json.dumps(remote['assets']).encode()
elif endpoint == base+'/releases/latest':
    body = json.dumps(remote['release']).encode()
elif endpoint.startswith(base+'/releases?'):
    values = [] if remote['release'] is None else [remote['release']]
    page = int(endpoint.rsplit('page=',1)[1])
    if mode == 'paginate':
        values = [{'id':i+1000,'tag_name':'historical-'+str(i),'name':'history'} for i in range(100)] if page == 1 else values
    body = json.dumps(values).encode()
else:
    body = json.dumps(remote['release']).encode()
path.write_text(json.dumps(remote))
if mode == 'create-200' and method == 'POST' and endpoint == base+'/releases': status=200
# Real gh 2.96.0 emits LF for its status line and CRLF for headers.
sys.stdout.buffer.write(('HTTP/2.0 '+str(status)+' OK\nContent-Type: application/octet-stream\r\n\r\n').encode()+body)
sys.exit(0 if status < 400 else 1)
'''


class Fixture(BaseFixture):
    def __init__(self, root, **kwargs):
        super().__init__(root, **kwargs)
        self.make_artifact()
        self.fake = self.root / 'fake-gh'
        self.fake.write_text(FAKE_GH.replace('PYTHON', str(Path(sys.executable).resolve())))
        self.fake.chmod(0o700)
        (self.root / 'gh-config').mkdir(mode=0o700)
        self.remote_api = self.root / 'fake-remote.json'
        self.remote_api.write_text(json.dumps({'release': None, 'assets': []}))
        self.plan = {**self.common('publication-plan'), 'artifact_id': self.artifact['artifact_id'],
            'human_receipt_sha256': approval.digest(self.policy.trust_file('artifact-human.json')),
            'source_commit': self.final, 'source_tree': self.tree, 'notes_sha256': publication.NOTES_HASH,
            'tag_timestamp': 1791028800, 'tag_oid': publication.tag_identity(self.final, 1791028800),
            'transport': {'executable': str(self.fake), 'sha256': approval.digest(self.fake.read_bytes()),
                          'config_dir': str(self.root / 'gh-config'), 'config_gid': os.getgid()}}
        self.sign('publication-plan', self.plan)

    def publisher(self, checkpoint=None):
        return publication.Publisher(self.policy, checkpoint=checkpoint)

    def api(self, **updates):
        value = json.loads(self.remote_api.read_text())
        value.update(updates)
        self.remote_api.write_text(json.dumps(value))
        return value

    def call_records(self):
        path = self.root / 'fake-gh-calls.jsonl'
        return [] if not path.exists() else [json.loads(line) for line in path.read_text().splitlines()]

    def writes(self):
        return [v for v in self.call_records() if v['argv'][v['argv'].index('--method')+1] != 'GET']

    def reconcile(self, phase):
        value = self.api()
        self.sign('publication-reconciliation', {**self.common('publication-reconciliation'),
            'plan_sha256': approval.digest(self.policy.trust_file('publication-plan.json')),
            'artifact_id': self.artifact['artifact_id'], 'human_receipt_sha256': self.plan['human_receipt_sha256'],
            'source_commit': self.final, 'tag_oid': self.plan['tag_oid'], 'release_id': value['release']['id'],
            'asset_id': value['assets'][0]['id'] if value['assets'] else None, 'phase': phase})


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = retained_root()

    def test_real_argv_binary_upload_download_draft_publish_and_latest(self):
        f = Fixture(self.root)
        self.assertEqual(f.publisher().execute(), 'PUBLICATION_VERIFIED_SAME_ARTIFACT')
        self.assertEqual(integration.git(f.remote, 'rev-parse', 'refs/tags/1.1.0'), f.plan['tag_oid'])
        self.assertEqual(integration.git(f.remote, 'rev-parse', 'refs/tags/1.1.0^{}'), f.final)
        self.assertEqual((f.root / 'fake-upload.zip').read_bytes(), Path(f.artifact['zip_path']).read_bytes())
        writes = f.writes()
        self.assertEqual([v['argv'][v['argv'].index('--method')+1] for v in writes], ['POST', 'POST', 'PATCH'])
        self.assertEqual(json.loads(base64.b64decode(writes[0]['stdin']))['body'], publication.Publisher(f.policy).notes_text)
        self.assertEqual(json.loads(base64.b64decode(writes[-1]['stdin']))['make_latest'], 'true')
        self.assertTrue(all('--repo' not in v['argv'] and '--clobber' not in v['argv'] for v in f.call_records()))
        self.assertTrue(all(v['dont_write_bytecode'] is True for v in f.call_records()))
        store = f.publisher().store
        value = store.inspect()
        self.assertEqual(value['state'], 'COMPLETE')
        self.assertEqual([v['phase'] for v in value['downloads']], ['draft', 'public'])
        for proof in value['downloads']:
            self.assertEqual((store.root / 'downloads' / proof['file']).read_bytes(), Path(f.artifact['zip_path']).read_bytes())

    def test_unicode_multiline_magic_arguments_use_exact_utf8_json_stdin(self):
        f = Fixture(self.root)
        transport = f.publisher().transport
        payload = {'body': '@filename\n中文 "quotes" `backticks`\r\n\x1b[31m forged\u2028line', 'draft': True}
        # Direct transport fixture exercises encoding, not publication acceptance.
        transport.request('POST', publication.BASE+'/releases', payload=payload)
        call = f.call_records()[-1]
        self.assertEqual(json.loads(base64.b64decode(call['stdin'])), payload)
        self.assertNotIn('中文', ' '.join(call['argv']))
        self.assertNotIn('-F', call['argv'])
        self.assertTrue(all(key not in call['env_keys'] for key in
            ('GH_TOKEN','GITHUB_TOKEN','CODEX_ACCESS_TOKEN','OPENAI_API_KEY','HOME','PYTHONPATH')))

    def test_missing_or_revoked_human_plan_or_changed_zip_has_zero_api_writes(self):
        for kind in ('human', 'plan', 'revoke', 'zip', 'tools', 'false-plan'):
            f = Fixture(self.root)
            if kind in ('human', 'plan'):
                (f.policy.root / ('artifact-human.json' if kind == 'human' else 'publication-plan.json')).unlink()
            elif kind == 'revoke':
                f.write('revoked.json', approval.canonical({'schema_version':1,'ids':[f.human_receipt['id']]}))
            elif kind == 'zip':
                Path(f.artifact['zip_path']).write_bytes(b'changed')
            elif kind == 'tools':
                (f.source / 'scripts/release_publication.py').write_bytes(b'changed')
            else:
                f.sign('publication-plan', {**f.plan, 'tag_oid': 'a'*40})
            with self.subTest(kind=kind), self.assertRaises((approval.Stop, OSError)):
                f.publisher().execute()
            self.assertEqual(f.writes(), [])
            self.assertEqual(integration.run_git(f.remote, 'rev-parse', '--verify', 'refs/tags/1.1.0', allow_failure=True).returncode, 128)

    def test_http_errors_empty_nonjson_and_post200_do_not_gain_ownership(self):
        for kind in ('403', '500', 'bad-json', 'empty', 'create-200'):
            f = Fixture(self.root)
            f.api(fault=kind)
            with self.subTest(kind=kind), self.assertRaises(approval.Stop):
                f.publisher().execute()
            self.assertFalse(any(v['argv'][v['argv'].index('--method')+1] == 'PATCH' for v in f.call_records()))

    def test_complete_pagination_and_starter_no_delete_or_clobber(self):
        f = Fixture(self.root)
        f.api(fault='paginate')
        self.assertEqual(f.publisher().execute(), 'PUBLICATION_VERIFIED_SAME_ARTIFACT')
        self.assertTrue(any('page=2' in v['argv'][1] for v in f.call_records()))
        g = Fixture(self.root)
        g.api(fault='starter')
        with self.assertRaises(approval.Stop):
            g.publisher().execute()
        self.assertEqual(g.api()['assets'][0]['state'], 'starter')
        self.assertEqual(len(g.writes()), 2)

    def test_crash_recovery_requires_signed_remote_ids_not_rehashed_hint(self):
        for point, phase in (('after_create', 'DRAFT'), ('after_upload', 'UPLOADED'), ('after_publish', 'PUBLISHED')):
            f = Fixture(self.root)
            def crash(name):
                if name == point:
                    raise KeyboardInterrupt()
            with self.subTest(point=point), self.assertRaises(KeyboardInterrupt):
                f.publisher(crash).execute()
            before = len(f.writes())
            with self.assertRaises(approval.Stop) as caught:
                f.publisher().execute()
            self.assertEqual(caught.exception.code, 'PUBLICATION_RECONCILIATION_REQUIRED')
            self.assertEqual(len(f.writes()), before)
            f.reconcile(phase)
            from release_pipeline import resume
            self.assertEqual(resume(f.policy), 'PUBLICATION_VERIFIED_SAME_ARTIFACT')
            self.assertEqual(len(f.writes()), 3)

    def test_same_name_foreign_object_never_adopted_even_with_rehashed_state(self):
        f = Fixture(self.root)
        p = f.publisher()
        def stop(name):
            if name == 'after_create': raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): f.publisher(stop).execute()
        value = p.store.inspect()
        value.update(state='DRAFT', intent=None, release_id=101)
        p.store.path.write_bytes(approval.canonical(state.with_checksum(value)))
        with self.assertRaises(approval.Stop) as caught: f.publisher().execute()
        self.assertEqual(caught.exception.code, 'PUBLICATION_RECONCILIATION_REQUIRED')
        self.assertEqual(len(f.writes()), 1)

    def test_publish_intent_boundary_remote_notes_assets_or_bytes_drift_stops_before_patch(self):
        for kind in ('notes', 'assets', 'bytes'):
            f = Fixture(self.root)
            def corrupt(name):
                if name == 'before_publish':
                    remote = f.api()
                    if kind == 'notes': remote['release']['body']='changed'
                    elif kind == 'assets': remote['assets']=[]
                    else: (f.root/'fake-upload.zip').write_bytes(b'changed')
                    f.api(**remote)
            with self.subTest(kind=kind), self.assertRaises(approval.Stop): f.publisher(corrupt).execute()
            self.assertEqual(len(f.writes()), 2)
            self.assertTrue(f.api()['release']['draft'])

    def test_completed_cross_invocation_still_checks_signed_receipt_and_exact_public_bytes(self):
        f = Fixture(self.root)
        f.publisher().execute()
        with self.assertRaises(approval.Stop): f.publisher().execute()
        f.reconcile('PUBLISHED')
        before = len(f.writes())
        self.assertEqual(f.publisher().execute(), 'PUBLICATION_VERIFIED_SAME_ARTIFACT')
        self.assertEqual(len(f.writes()), before)
        f.api(fault='corrupt-download')
        with self.assertRaises(approval.Stop): f.publisher().execute()
        self.assertEqual(len(f.writes()), before)

    def test_remote_schema_type_identity_and_pagination_conflicts_never_write(self):
        # Each adversarial object has an otherwise valid response envelope. A
        # foreign same-version object is never accepted as an idempotent hint.
        f = Fixture(self.root)
        def crash(name):
            if name == 'after_create': raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): f.publisher(crash).execute()
        original = f.api()
        for key, value in (('id',True),('draft',1),('prerelease',0),('tag_name','1.0.0'),
                           ('name','wrong'),('body','changed'),('target_commitish','main'),
                           ('url','https://foreign.invalid/release'),('published_at','unexpected')):
            remote = copy.deepcopy(original)
            remote['release'][key] = value
            f.api(**remote)
            with self.subTest(key=key), self.assertRaises(approval.Stop): f.publisher().execute()
            self.assertEqual(len(f.writes()),1)
        f.api(**original)
        f.reconcile('DRAFT')
        changed = approval.decode(f.policy.trust_file('publication-reconciliation.json'))
        for key, value in (('release_id',True),('phase','PUBLISHED'),('plan_sha256','a'*64),
                           ('human_receipt_sha256','a'*64),('source_commit',f.accepted)):
            f.sign('publication-reconciliation',{**changed,key:value})
            with self.subTest(key=key), self.assertRaises(approval.Stop):f.publisher().execute()
            self.assertEqual(len(f.writes()),1)

    def test_human_purpose_signature_exact_artifact_and_revocation_remain_write_boundary(self):
        f=Fixture(self.root)
        original=copy.deepcopy(f.human_receipt)
        for key,value in (('purpose',approval.RECEIPT_PURPOSES['integration']),('decision',True),
                          ('decision','FAIL'),('integration_receipt_sha256','a'*64),
                          ('artifact',{**f.artifact,'zip_sha256':'a'*64})):
            f.sign('artifact-human',{**original,key:value})
            with self.subTest(key=key),self.assertRaises(approval.Stop):f.publisher().execute()
            self.assertEqual(f.writes(),[])


if __name__ == '__main__':
    unittest.main()
