import json, os, secrets, subprocess, urllib.request, urllib.error
from pathlib import Path

env = os.environ.copy()
env['PROMPT_TOKEN'] = secrets.token_urlsafe(32)
env['PORT'] = '18787'
cmd = ['docker', 'compose', '-p', 'promptobs-smoke-' + secrets.token_hex(4)]
def compose(*args):
    return subprocess.run(cmd + list(args), env=env, cwd=Path(__file__).resolve().parents[1], check=True)
def request(path, payload=None, auth=True):
    headers = {'Content-Type':'application/json'}
    if auth: headers['Authorization'] = 'Bearer ' + env['PROMPT_TOKEN']
    req = urllib.request.Request('http://127.0.0.1:18787'+path,
        data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)
try:
    compose('--profile', 'tunnel', 'config', '-q')
    compose('up', '-d', '--no-build', '--wait', '--wait-timeout', '60', 'observatory')
    assert request('/health', auth=False) == {'status':'ok'}
    try:
        request('/api/events', auth=False)
        raise AssertionError('Missing authentication')
    except urllib.error.HTTPError as error:
        assert error.code == 401
    rule = request('/api/rules', {'name':'docker rule','contains':'test','severity':'warning'})
    event = {'id':'docker-smoke','provider':'chatgpt','prompt':'Docker test'}
    assert request('/api/events', event)['matches'][0]['id'] == rule['id']
    request('/api/events', event)
    assert len(request('/api/events?severity=warning')) == 1
    compose('down')
    compose('up', '-d', '--no-build', '--wait', '--wait-timeout', '60', 'observatory')
    assert request('/api/events')[0]['prompt'] == event['prompt']
    compose('exec', '-T', 'observatory', 'python', '-c',
        "import os; assert os.getuid()==10001; print('Non-root user: OK')")
    print('Docker smoke: health, auth, ingestion, rules, deduplication and persistence after recreation: OK')
finally:
    compose('down', '-v')
