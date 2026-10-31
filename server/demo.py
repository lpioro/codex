"""Create a separate demo database. Existing paths are never overwritten."""
import argparse
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from server import app
from server.rules import validate_rule

FIXTURE = Path(__file__).with_name('demo_data.json')


def create_demo(output):
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
        now = datetime.now(timezone.utc).replace(microsecond=0)
        for index, event in enumerate(fixture['events']):
            result = app.ingest(event)
            if sorted(m['name'] for m in result['matches']) != sorted(event['expected']):
                raise ValueError(f"Unexpected detector result: {event['id']}")
            with app.connect() as db:
                stamp = now - timedelta(minutes=30 * (len(fixture['events']) - 1 - index))
                db.execute('UPDATE events SET received_at=? WHERE id=?', (stamp.isoformat(), event['id']))
        # SQLite backup includes committed WAL data in a portable standalone file.
        source = sqlite3.connect(app.DB)
        destination = sqlite3.connect(output)
        try:
            source.backup(destination)
            destination.execute('PRAGMA journal_mode=DELETE')
        finally:
            source.close()
            destination.close()
        return {'rules':len(fixture['rules']), 'events':len(fixture['events']), 'database':str(output)}
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    finally:
        app.DB = previous
        temporary.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('data/walleeguard-demo.sqlite3'))
    args = parser.parse_args()
    try:
        result = create_demo(args.output)
    except FileExistsError:
        parser.exit(1, f'Plik już istnieje — nie nadpisuję: {args.output}\n')
    print(json.dumps(result, ensure_ascii=False))
