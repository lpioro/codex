import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from server import app


class Endpoints(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = app.DB, app.TOKEN
        app.DB = str(Path(self.tmp.name) / 'endpoints.sqlite3')
        app.TOKEN = 'admin-' + 'x' * 40
        app.init_db()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        app.DB, app.TOKEN = self.previous
        self.tmp.cleanup()

    def request(self, path, data=None, token=None, status=200):
        headers = {'Authorization':'Bearer '+(token or app.TOKEN), 'Content-Type':'application/json'}
        request = Request(self.url+path, data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            response = urlopen(request)
        except HTTPError as error:
            response = error
        with response:
            self.assertEqual(response.status, status)
            return json.load(response)

    def create(self, name):
        return self.request('/api/endpoints', {'name':name,'group_name':'QA'}, status=201)

    def test_identity_scoping_and_permissions(self):
        a, b = self.create('Laptop A'), self.create('Laptop B')
        heartbeat = {'instance_id':'profile-a','version':'0.3.0'}
        self.assertEqual(self.request('/api/heartbeat', heartbeat, a['token'])['id'], a['id'])
        self.request('/api/heartbeat', {}, a['token'], 400)
        self.request('/api/heartbeat', {**heartbeat,'instance_id':'copy'}, a['token'], 409)
        self.request('/api/heartbeat', heartbeat, status=403)
        for path in ['/api/events','/api/rules','/api/endpoints']:
            self.request(path, token=a['token'], status=401)
        self.request('/api/rules', {'name':'hack','contains':'x','severity':'info'}, a['token'],403)
        self.request('/api/endpoints', {'name':'hack'}, a['token'],403)
        self.request('/api/endpoints/'+b['id']+'/revoke', {}, a['token'],403)
        event = {**heartbeat,'id':'same-client-id','provider':'chatgpt','prompt':'first'}
        self.request('/api/events', {**event,'endpoint_id':b['id']}, a['token'],403)
        self.request('/api/events', {**event,'endpoint_id':a['id']}, status=403)
        self.request('/api/events', event, a['token'],201)
        self.request('/api/events', event, a['token'],201)
        self.request('/api/events', {**event,'instance_id':'profile-b','prompt':'second'},b['token'],201)
        self.request('/api/events', {'id':'legacy','provider':'gemini','prompt':'legacy'},status=201)
        self.assertEqual(len(self.request('/api/events')),3)
        events_a = self.request('/api/events?endpoint_id='+a['id'])
        self.assertEqual(len(events_a),1)
        self.assertEqual(events_a[0]['endpoint_name'],'Laptop A')
        self.assertEqual(events_a[0]['endpoint_group'],'QA')
        self.assertEqual(events_a[0]['prompt'],'first')
        self.assertEqual(self.request('/api/events?endpoint_id='+b['id'])[0]['prompt'],'second')
        self.assertEqual(self.request('/api/events?endpoint_id=legacy')[0]['prompt'],'legacy')
        listing = self.request('/api/endpoints')
        self.assertEqual(len(listing),2)
        for row in listing:
            self.assertNotIn('token',row)
            self.assertNotIn('token_hash',row)
            self.assertEqual(row['event_count'],1)
            self.assertIsNotNone(row['last_seen'])
        with app.connect() as db:
            stored=db.execute('SELECT token_hash FROM endpoints WHERE id=?',(a['id'],)).fetchone()[0]
        self.assertEqual(stored,hashlib.sha256(a['token'].encode()).hexdigest())

    def test_revoke_rotate_and_rename_preserve_events(self):
        endpoint=self.create('Old name')
        event={'id':'retained','provider':'claude','prompt':'history','instance_id':'old-profile'}
        self.request('/api/events',event,endpoint['token'],201)
        self.request('/api/endpoints/'+endpoint['id'],{'name':'New name','group_name':'Finance'})
        self.assertEqual(self.request('/api/events')[0]['endpoint_name'],'New name')
        self.request('/api/endpoints/'+endpoint['id']+'/revoke',{})
        self.request('/api/heartbeat',{'instance_id':'old-profile'},endpoint['token'],401)
        self.request('/api/events',event,endpoint['token'],401)
        rotated=self.request('/api/endpoints/'+endpoint['id']+'/rotate',{})
        self.request('/api/heartbeat',{'instance_id':'old-profile'},endpoint['token'],401)
        self.request('/api/heartbeat',{'instance_id':'replacement-profile'},rotated['token'])
        self.assertEqual(self.request('/api/endpoints')[0]['revoked'],0)
        self.assertEqual(len(self.request('/api/events')),1)

    def test_old_database_migration(self):
        legacy=Path(self.tmp.name)/'legacy.sqlite3'
        with sqlite3.connect(legacy) as db:
            db.execute('CREATE TABLE events(id TEXT PRIMARY KEY,received_at TEXT NOT NULL,provider TEXT NOT NULL,prompt TEXT NOT NULL,matches TEXT NOT NULL)')
            db.execute("INSERT INTO events VALUES ('old','2026-01-01','claude','old prompt','[]')")
        current=app.DB
        app.DB=str(legacy)
        try:
            app.init_db()
            app.init_db()
            with app.connect() as db:
                row=dict(db.execute('SELECT * FROM events').fetchone())
                self.assertIsNone(row['endpoint_id'])
                self.assertEqual(row['prompt'],'old prompt')
        finally:
            app.DB=current
