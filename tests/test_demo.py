import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from server import app
from server.demo import create_demo, FIXTURE, demo_events


class DemoDatabase(unittest.TestCase):
    def test_fixture_results_and_portable_database(self):
        previous = app.DB
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'demo.sqlite3'
            result = create_demo(path)
            self.assertEqual(app.DB, previous)
            self.assertEqual(result['rules'], 14)
            self.assertEqual(result['events'], 720)
            self.assertEqual(result['endpoints'], 12)
            self.assertEqual(result['groups'], 5)
            fixture = json.loads(FIXTURE.read_text())
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                rows = db.execute('SELECT id,matches FROM events').fetchall()
                expected = {e['id']:sorted(e['expected']) for e in demo_events()}
                for event_id, matches in rows:
                    self.assertEqual(sorted(m['name'] for m in json.loads(matches)), expected[event_id.rsplit(':',1)[-1]])
                self.assertEqual(db.execute('SELECT count(*) FROM rules WHERE enabled=1').fetchone()[0], 13)
            self.assertFalse(Path(str(path) + '-wal').exists())

    def test_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'existing.sqlite3'
            path.write_bytes(b'existing-user-data')
            with self.assertRaises(FileExistsError):
                create_demo(path)
            self.assertEqual(path.read_bytes(), b'existing-user-data')
