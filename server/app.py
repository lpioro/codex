import hashlib
import hmac
import json
import os
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

DB = os.environ.get('PROMPT_DB', 'data/prompts.sqlite3')
TOKEN = os.environ.get('PROMPT_TOKEN', '')
STATIC = Path(__file__).parent / 'static'
PROVIDERS = {'chatgpt', 'claude', 'gemini'}


def connect():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    return db


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
        ''')


def ingest(payload):
    event_id, provider, prompt = (payload.get(k) for k in ('id', 'provider', 'prompt'))
    if not isinstance(event_id, str) or not 1 <= len(event_id) <= 100:
        raise ValueError('Invalid event id')
    if not isinstance(provider, str) or provider not in PROVIDERS:
        raise ValueError('Unsupported provider')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 100000:
        raise ValueError('Prompt must contain 1–100000 characters')
    with connect() as db:
        matches = [dict(r) for r in db.execute('SELECT * FROM rules')
                   if r['contains'].casefold() in prompt.casefold()]
        db.execute('INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?)',
                   (event_id, datetime.now(timezone.utc).isoformat(), provider,
                    prompt, json.dumps(matches)))
    return {'id': event_id, 'matches': matches}


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

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == '/health':
            return self.send(200, {'status': 'ok'})
        if url.path.startswith('/api/'):
            if not self.authorized():
                return self.send(401, {'error': 'Unauthorized'})
            with connect() as db:
                if url.path == '/api/rules':
                    return self.send(200, [dict(r) for r in db.execute('SELECT * FROM rules ORDER BY id DESC')])
                if url.path == '/api/events':
                    q = parse_qs(url.query)
                    rows = db.execute('SELECT * FROM events ORDER BY received_at DESC LIMIT 1000').fetchall()
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
        files = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}
        if url.path not in files:
            return self.send(404, {'error': 'Not found'})
        filename = files[url.path]
        body = (STATIC / filename).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', {'html': 'text/html; charset=utf-8', 'js': 'text/javascript', 'css': 'text/css'}[filename.split('.')[-1]])
        self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self.authorized():
            return self.send(401, {'error': 'Unauthorized'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 650000:
                return self.send(413, {'error': 'Request too large'})
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Expected object')
            if self.path == '/api/events':
                return self.send(201, ingest(data))
            if self.path == '/api/rules':
                name, contains, severity = (data.get(k) for k in ('name', 'contains', 'severity'))
                if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
                    raise ValueError('Invalid rule name')
                if not isinstance(contains, str) or not 1 <= len(contains.strip()) <= 500:
                    raise ValueError('Invalid rule text')
                if severity not in ('info', 'warning', 'critical'):
                    raise ValueError('Invalid severity')
                with connect() as db:
                    cursor = db.execute('INSERT INTO rules(name, contains, severity) VALUES (?, ?, ?)', (name.strip(), contains.strip(), severity))
                return self.send(201, {'id': cursor.lastrowid})
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
    ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('PORT', '8787'))), Handler).serve_forever()
