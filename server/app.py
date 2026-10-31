import hashlib
import hmac
import json
import os
import secrets
import uuid
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from server.rules import matches as rule_matches, validate_rule

DB = os.environ.get('PROMPT_DB', 'data/prompts.sqlite3')
TOKEN = os.environ.get('PROMPT_TOKEN', '')
STATIC = Path(__file__).parent / 'static'
PROVIDERS = {'chatgpt', 'claude', 'gemini'}


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def init_db():
    Path(DB).parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS events (
          id TEXT PRIMARY KEY, received_at TEXT NOT NULL, provider TEXT NOT NULL,
          prompt TEXT NOT NULL, matches TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS rules (
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, contains TEXT NOT NULL,
          severity TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS endpoints (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, group_name TEXT NOT NULL DEFAULT '',
          token_hash TEXT NOT NULL UNIQUE, revoked INTEGER NOT NULL DEFAULT 0,
          instance_id TEXT, version TEXT, created_at TEXT NOT NULL, last_seen TEXT);
        ''')
        columns = {r['name'] for r in db.execute('PRAGMA table_info(rules)')}
        if 'type' not in columns:
            db.execute("ALTER TABLE rules ADD COLUMN type TEXT NOT NULL DEFAULT 'contains'")
        if 'enabled' not in columns:
            db.execute('ALTER TABLE rules ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1')
        event_columns = {r['name'] for r in db.execute('PRAGMA table_info(events)')}
        if 'endpoint_id' not in event_columns:
            db.execute('ALTER TABLE events ADD COLUMN endpoint_id TEXT')
        db.execute('CREATE INDEX IF NOT EXISTS events_endpoint ON events(endpoint_id, received_at)')



def ingest(payload, endpoint_id=None):
    event_id, provider, prompt = (payload.get(k) for k in ('id', 'provider', 'prompt'))
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 100:
        raise ValueError('Invalid event id')
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError('Unsupported provider')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 100000:
        raise ValueError('Prompt must contain 1–100000 characters')
    with connect() as db:
        storage_id = f'{endpoint_id}:{event_id}' if endpoint_id else event_id
        existing = db.execute('SELECT matches FROM events WHERE id=?', (storage_id,)).fetchone()
        if existing:
            return {'id': event_id, 'matches': json.loads(existing['matches'])}
        matches = [dict(r) for r in db.execute('SELECT * FROM rules')
                   if rule_matches(dict(r), prompt)]
        db.execute('INSERT INTO events(id,received_at,provider,prompt,matches,endpoint_id) VALUES (?, ?, ?, ?, ?, ?)',
                   (storage_id, datetime.now(timezone.utc).isoformat(), provider,
                    prompt, json.dumps(matches), endpoint_id))
        if endpoint_id:
            db.execute("UPDATE endpoints SET last_seen=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), endpoint_id))
    return {'id': event_id, 'matches': matches}


def endpoint_fields(data):
    name, group = data.get('name'), data.get('group_name', '')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError('Invalid endpoint name')
    if not isinstance(group, str) or len(group.strip()) > 100:
        raise ValueError('Invalid group')
    return name.strip(), group.strip()


def create_endpoint(data):
    name, group = endpoint_fields(data)
    endpoint_id, token = str(uuid.uuid4()), secrets.token_urlsafe(32)
    with connect() as db:
        db.execute('INSERT INTO endpoints(id,name,group_name,token_hash,created_at) VALUES (?,?,?,?,?)',
                   (endpoint_id, name, group, hashlib.sha256(token.encode()).hexdigest(),
                    datetime.now(timezone.utc).isoformat()))
    return {'id': endpoint_id, 'name': name, 'group_name': group, 'token': token}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Never log URLs, tokens or prompt contents.
        pass

    def send(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        actual = self.headers.get('Authorization', '')
        return hmac.compare_digest(hashlib.sha256(actual.encode()).digest(),
                                   hashlib.sha256(('Bearer ' + TOKEN).encode()).digest())

    def endpoint_identity(self):
        authorization = self.headers.get('Authorization', '')
        if not authorization.startswith('Bearer '):
            return None
        digest = hashlib.sha256(authorization[7:].encode()).hexdigest()
        with connect() as db:
            row = db.execute('SELECT * FROM endpoints WHERE token_hash=? AND revoked=0', (digest,)).fetchone()
            return dict(row) if row else None

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/health':
            return self.send(200, {'status': 'ok'})
        if url.path.startswith('/api/'):
            if not self.authorized():
                return self.send(401, {'error': 'Unauthorized'})
            with connect() as db:
                if url.path == '/api/endpoints':
                    rows = db.execute('SELECT e.id,e.name,e.group_name,e.revoked,e.instance_id,e.version,e.created_at,e.last_seen,'
                                      '(SELECT count(*) FROM events v WHERE v.endpoint_id=e.id) AS event_count '
                                      'FROM endpoints e ORDER BY e.created_at DESC').fetchall()
                    return self.send(200, [dict(row) for row in rows])
                if url.path == '/api/rules':
                    return self.send(200, [dict(r) for r in db.execute('SELECT * FROM rules ORDER BY id DESC')])
                if url.path == '/api/events':
                    q = parse_qs(url.query)
                    endpoint_filter = q.get('endpoint_id', [''])[0]
                    where = 'WHERE v.endpoint_id IS NULL' if endpoint_filter == 'legacy' else 'WHERE v.endpoint_id=?' if endpoint_filter else ''
                    rows = db.execute('SELECT v.*,e.name AS endpoint_name,e.group_name AS endpoint_group FROM events v '
                                      'LEFT JOIN endpoints e ON e.id=v.endpoint_id ' + where +
                                      ' ORDER BY v.received_at DESC LIMIT 1000',
                                      (endpoint_filter,) if endpoint_filter and endpoint_filter != 'legacy' else ()).fetchall()
                    items = []
                    for row in rows:
                        item = dict(row)
                        item['matches'] = json.loads(item['matches'])
                        if q.get('q', [''])[0].casefold() not in item['prompt'].casefold():
                            continue
                        if q.get('provider', [''])[0] not in ('', item['provider']):
                            continue
                        if q.get('severity', [''])[0] and not any(m['severity'] == q['severity'][0] for m in item['matches']):
                            continue
                        items.append(item)
                    return self.send(200, items)
            return self.send(404, {'error': 'Not found'})
        files = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css', '/logo.svg': 'logo.svg', '/vendor/bootstrap.min.css': 'vendor/bootstrap.min.css'}
        if url.path not in files:
            return self.send(404, {'error': 'Not found'})
        filename = files[url.path]
        body = (STATIC / filename).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html; charset=utf-8', 'js': 'text/javascript', 'css': 'text/css', 'svg': 'image/svg+xml'}[filename.split('.')[-1]])
        self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        admin = self.authorized()
        identity = None if admin else self.endpoint_identity()
        if not admin and identity is None:
            return self.send(401, {'error': 'Unauthorized'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 650000:
                return self.send(413, {'error': 'Request too large'})
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Expected object')
            if not admin and self.path not in ('/api/events', '/api/heartbeat'):
                return self.send(403, {'error': 'Endpoint token can only send events and heartbeats'})
            if self.path in ('/api/events', '/api/heartbeat') and identity:
                instance_id = data.get('instance_id')
                version = data.get('version', '')
                if not isinstance(instance_id, str) or not 1 <= len(instance_id) <= 100 or not isinstance(version, str) or len(version) > 40:
                    raise ValueError('Invalid installation metadata')
                if data.get('endpoint_id', identity['id']) != identity['id']:
                    return self.send(403, {'error': 'Endpoint identity mismatch'})
                with connect() as db:
                    # One token belongs to one browser profile; conditional update is atomic.
                    cursor = db.execute('UPDATE endpoints SET instance_id=?,version=?,last_seen=? WHERE id=? AND revoked=0 '
                                        'AND (instance_id IS NULL OR instance_id=?)',
                                        (instance_id, version, datetime.now(timezone.utc).isoformat(), identity['id'], instance_id))
                    if not cursor.rowcount:
                        return self.send(409, {'error': 'Token already paired with another installation; create a separate endpoint'})
            if self.path == '/api/heartbeat':
                if admin:
                    return self.send(403, {'error': 'Use a dedicated endpoint token'})
                return self.send(200, {'id': identity['id'], 'name': identity['name'], 'group_name': identity['group_name']})
            if self.path == '/api/events':
                if admin and data.get('endpoint_id'):
                    return self.send(403, {'error': 'Admin ingestion cannot impersonate endpoints'})
                return self.send(201, ingest(data, identity['id'] if identity else None))
            if self.path == '/api/endpoints':
                return self.send(201, create_endpoint(data))
            if self.path.startswith('/api/endpoints/'):
                parts = self.path.strip('/').split('/')
                if len(parts) not in (3, 4):
                    raise ValueError('Invalid endpoint operation')
                endpoint_id = parts[2]
                with connect() as db:
                    if not db.execute('SELECT id FROM endpoints WHERE id=?', (endpoint_id,)).fetchone():
                        return self.send(404, {'error':'Endpoint not found'})
                    if len(parts) == 3:
                        name, group = endpoint_fields(data)
                        db.execute('UPDATE endpoints SET name=?,group_name=? WHERE id=?', (name,group,endpoint_id))
                    elif parts[3] == 'revoke':
                        db.execute('UPDATE endpoints SET revoked=1 WHERE id=?', (endpoint_id,))
                    elif parts[3] == 'rotate':
                        token = secrets.token_urlsafe(32)
                        db.execute('UPDATE endpoints SET token_hash=?,revoked=0,instance_id=NULL,last_seen=NULL WHERE id=?',
                                   (hashlib.sha256(token.encode()).hexdigest(),endpoint_id))
                        return self.send(200, {'id':endpoint_id,'token':token})
                    else:
                        raise ValueError('Unknown endpoint operation')
                return self.send(200, {'id':endpoint_id})

            if self.path == '/api/rules/test':
                rule = validate_rule(data)
                text = data.get('text')
                if not isinstance(text, str) or len(text) > 100000:
                    raise ValueError('Invalid test text')
                return self.send(200, {'matched': rule_matches(rule, text)})
            if self.path == '/api/rules' or self.path.startswith('/api/rules/'):
                rule = validate_rule(data)
                values = (rule['name'], rule['contains'], rule['severity'], rule['type'], rule['enabled'])
                with connect() as db:
                    if self.path == '/api/rules':
                        cursor = db.execute('INSERT INTO rules(name, contains, severity, type, enabled) VALUES (?, ?, ?, ?, ?)', values)
                        rule_id = cursor.lastrowid
                    else:
                        rule_id = int(self.path.rsplit('/', 1)[1])
                        cursor = db.execute('UPDATE rules SET name=?, contains=?, severity=?, type=?, enabled=? WHERE id=?', (*values, rule_id))
                        if not cursor.rowcount:
                            return self.send(404, {'error': 'Rule not found'})
                return self.send(201 if self.path == '/api/rules' else 200, {'id': rule_id})
            return self.send(404, {'error': 'Not found'})
        except (ValueError, TypeError):
            return self.send(400, {'error': 'Invalid request'})

    def do_DELETE(self):
        if not self.authorized():
            return self.send(401, {'error': 'Unauthorized'})
        try:
            prefix, rule_id = self.path.rsplit('/', 1)
            if prefix != '/api/rules':
                return self.send(404, {'error': 'Not found'})
            with connect() as db:
                db.execute('DELETE FROM rules WHERE id = ?', (int(rule_id),))
            return self.send(200, {'ok': True})
        except ValueError:
            return self.send(400, {'error': 'Invalid rule id'})


if __name__ == '__main__':
    if len(TOKEN) < 32:
        raise SystemExit('Set PROMPT_TOKEN to a random token of at least 32 characters')
    init_db()
    ThreadingHTTPServer((os.environ.get('HOST', '127.0.0.1'), int(os.environ.get('PORT', '8787'))), Handler).serve_forever()
