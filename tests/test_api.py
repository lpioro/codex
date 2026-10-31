import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from server import app


class API(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        app.DB = cls.tmp.name + '/test.sqlite3'
        app.TOKEN = 'test-token-' + 'x' * 32
        app.init_db()
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def request(self, path, data=None, token=True, method=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + app.TOKEN
        req = Request(self.url + path, data=json.dumps(data).encode() if data is not None else None,
                      headers=headers, method=method)
        with urlopen(req) as response:
            return json.load(response)

    def test_workflow(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/api/events', token=False)
        self.assertEqual(error.exception.code, 401)
        rule = self.request('/api/rules', {'name': 'Credentials', 'contains': 'SECRET', 'severity': 'critical'})
        event = {'id': 'unique-event', 'provider': 'chatgpt', 'prompt': 'This is a secret'}
        self.assertEqual(self.request('/api/events', event)['matches'][0]['severity'], 'critical')
        self.request('/api/events', event)
        events = self.request('/api/events?severity=critical&q=secret')
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['prompt'], event['prompt'])
        self.assertEqual(self.request('/api/events?provider=claude'), [])
        self.request('/api/rules/' + str(rule['id']), method='DELETE')
        self.assertEqual(self.request('/api/rules'), [])
        self.assertEqual(len(self.request('/api/events')[0]['matches']), 1)

    def test_bad_payload(self):
        for payload in [[], {'id':'bad','provider':'unknown','prompt':'hello'}, {'id':'bad','provider':'chatgpt','prompt':''}]:
            with self.assertRaises(HTTPError) as error:
                self.request('/api/events', payload)
            self.assertEqual(error.exception.code, 400)

    def test_dashboard(self):
        with urlopen(self.url + '/') as response:
            self.assertIn(b'Wallee', response.read())
            self.assertIn("frame-ancestors 'none'", response.headers['Content-Security-Policy'])
        self.assertEqual(self.request('/health', token=False), {'status':'ok'})
        for path, content_type, marker in [
            ('/vendor/bootstrap.min.css', 'text/css', b'v5.3.3'),
            ('/logo.svg', 'image/svg+xml', b'<svg'),
        ]:
            with urlopen(self.url + path) as response:
                self.assertEqual(response.headers.get_content_type(), content_type)
                self.assertTrue(marker in response.read(), path)


if __name__ == '__main__':
    unittest.main()
