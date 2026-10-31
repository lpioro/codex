"""Create a separate demo database. Existing paths are never overwritten."""
import argparse
import json
import sqlite3
import tempfile
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from server import app
from server.rules import validate_rule

FIXTURE = Path(__file__).with_name('demo_data.json')


ENDPOINTS = [
    ('Laptop Anny · Chrome','Finanse'), ('MacBook Piotra · Praca','Inżynieria'),
    ('Stanowisko QA · Profil testowy','QA'), ('Laptop Marka · Finanse','Finanse'),
    ('Desktop Oli · Dev','Inżynieria'), ('Obsługa klienta · Warszawa','Obsługa klienta'),
    ('Laptop Ewy · Rekrutacja','HR'), ('Stacja buildów · Dev','Inżynieria'),
    ('Obsługa klienta · Kraków','Obsługa klienta'), ('Desktop kadr · HR','HR'),
    ('Audyt finansowy · Chrome','Finanse'), ('Laboratorium QA · Chromium','QA'),
]


def demo_events(count=720):
    fixture = json.loads(FIXTURE.read_text())
    if not isinstance(count, int) or not len(fixture['events']) <= count <= 10000:
        raise ValueError('Event count must be between fixture size and 10000')
    for index in range(count):
        template = fixture['events'][index % len(fixture['events'])]
        yield {**template, 'id': template['id'] if index < len(fixture['events']) else f'demo-generated-{index:05d}'}


def create_demo(output, event_count=720):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also refuses symlinks and existing empty files.
    with output.open('xb'):
        pass
    previous = app.DB
    temporary = tempfile.TemporaryDirectory()
    app.DB = str(Path(temporary.name) / 'working.sqlite3')
    try:
        fixture = json.loads(FIXTURE.read_text())
        app.init_db()
        with app.connect() as db:
            for data in fixture['rules']:
                rule = validate_rule(data)
                db.execute('INSERT INTO rules(name,contains,severity,type,enabled) VALUES (?,?,?,?,?)',
                           tuple(rule[k] for k in ('name','contains','severity','type','enabled')))
        endpoints = []
        now = datetime.now(timezone.utc).replace(microsecond=0)
        rng = random.Random(42)
        for index, (name, group) in enumerate(ENDPOINTS):
            created = app.create_endpoint({'name':'DEMO · '+name,'group_name':group})
            endpoints.append(created['id'])
            with app.connect() as db:
                db.execute('UPDATE endpoints SET instance_id=?,version=?,created_at=? WHERE id=?',
                           ('demo-profile-'+str(index),'0.3.0-demo',(now-timedelta(days=8)).isoformat(),created['id']))
        latest = {}
        for index, event in enumerate(demo_events(event_count)):
            endpoint_id = endpoints[index % len(endpoints)]
            result = app.ingest(event, endpoint_id)
            if sorted(m['name'] for m in result['matches']) != sorted(event['expected']):
                raise ValueError(f"Unexpected detector result: {event['id']}")
            day = rng.choices(range(7), weights=[30,20,14,11,10,8,7])[0]
            stamp = now - timedelta(days=day, minutes=rng.randrange(1440))
            latest[endpoint_id] = max(latest.get(endpoint_id, stamp), stamp)
            with app.connect() as db:
                db.execute('UPDATE events SET received_at=? WHERE id=?', (stamp.isoformat(),endpoint_id+':'+event['id']))
        with app.connect() as db:
            for index, endpoint_id in enumerate(endpoints):
                db.execute('UPDATE endpoints SET last_seen=?,revoked=? WHERE id=?',
                           (latest[endpoint_id].isoformat(),int(index==10),endpoint_id))
        # SQLite backup includes committed WAL data in a portable standalone file.
        source = sqlite3.connect(app.DB)
        destination = sqlite3.connect(output)
        try:
            source.backup(destination)
            destination.execute('PRAGMA journal_mode=DELETE')
        finally:
            source.close()
            destination.close()
        return {'rules':len(fixture['rules']), 'events':event_count, 'endpoints':len(endpoints), 'groups':len({g for _,g in ENDPOINTS}), 'database':str(output)}
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    finally:
        app.DB = previous
        temporary.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/walleeguard-demo.sqlite3'))
    parser.add_argument('--events',type=int,default=720,help='Number of demo prompts (up to 10000)')
    args = parser.parse_args()
    try:
        result = create_demo(args.output,args.events)
    except FileExistsError:
        parser.exit(1, f'Plik już istnieje — nie nadpisuję: {args.output}\n')
    print(json.dumps(result, ensure_ascii=False))
