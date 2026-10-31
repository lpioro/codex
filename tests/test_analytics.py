import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from server import app
from server.analytics import filtered_events, summarize


class Analytics(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.previous=app.DB
        app.DB=str(Path(self.tmp.name)/'analytics.sqlite3');app.init_db()
        self.endpoint=app.create_endpoint({'name':'Laptop','group_name':'Finanse'})['id']

    def tearDown(self):
        app.DB=self.previous;self.tmp.cleanup()

    def test_filtering_precedes_list_limit_and_summary_is_complete(self):
        now=datetime.now(timezone.utc).isoformat()
        matches=json.dumps([{'name':'E-mail','severity':'warning'},{'name':'PESEL','severity':'critical'}])
        with app.connect() as db:
            db.executemany('INSERT INTO events(id,received_at,provider,prompt,matches,endpoint_id) VALUES(?,?,?,?,?,?)',
                [(f'a-{i}',now,'chatgpt','DANE ŻÓŁĆ',matches,self.endpoint) for i in range(1200)])
            db.executemany('INSERT INTO events(id,received_at,provider,prompt,matches,endpoint_id) VALUES(?,?,?,?,?,?)',
                [(f'b-{i}',now,'claude','no matches','[]',None) for i in range(50)])
            query={'group':['Finanse'],'q':['żółć'],'range':['24h']}
            events=filtered_events(db,query)
            self.assertEqual(len(filtered_events(db,query,1000)),1000)
            self.assertEqual(len(events),1200)
            stats=summarize(events)
            self.assertEqual(stats['total'],1200)
            self.assertEqual(stats['alerts'],1200)
            self.assertEqual(stats['critical'],1200)
            self.assertEqual(stats['severity'],{'info':0,'warning':0,'critical':1200})
            self.assertEqual(sum(b['events'] for b in stats['buckets']),1200)
            self.assertEqual(sum(b['alerts'] for b in stats['buckets']),1200)
            self.assertEqual(stats['providers'],{'chatgpt':1200})
            self.assertEqual(len(filtered_events(db,{'group':['__none__']})),50)
            self.assertEqual(filtered_events(db,{'provider':['claude'],'alerts':['1']}),[])

    def test_time_range_and_empty_chart(self):
        app.ingest({'id':'old','provider':'gemini','prompt':'old'})
        with app.connect() as db:
            db.execute('UPDATE events SET received_at=?',( (datetime.now(timezone.utc)-timedelta(days=8)).isoformat(),))
            self.assertEqual(filtered_events(db,{'range':['7d']}),[])
            self.assertEqual(len(filtered_events(db,{'range':['30d']})),1)
            with self.assertRaises(ValueError):filtered_events(db,{'range':['bad']})
        stats=summarize([])
        self.assertEqual(stats['total'],0)
        self.assertEqual(len(stats['buckets']),24)
        self.assertEqual(sum(b['alerts'] for b in stats['buckets']),0)
