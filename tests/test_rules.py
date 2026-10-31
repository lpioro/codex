import sqlite3
import tempfile
import unittest
from pathlib import Path
from server import app
from server.rules import matches, valid_pesel, validate_rule


class Detectors(unittest.TestCase):
    def test_email(self):
        rule = {'type':'email'}
        for text in ['Kontakt: anna+tag@example.com.', 'a.b@sub.example.pl', '<a@example.com>']:
            self.assertTrue(matches(rule, text), text)
        for text in ['a@localhost', 'a..b@example.com', 'a@-example.com', '@example.com', 'bez emaila']:
            self.assertFalse(matches(rule, text), text)

    def test_pesel(self):
        self.assertTrue(valid_pesel('44051401458'))
        self.assertTrue(matches({'type':'pesel'}, 'PESEL: 44051401458.'))
        for value in ['44051401459', '00000000000', '123', 'abcdefghijk']:
            self.assertFalse(valid_pesel(value), value)
        for text in ['144051401458', '440514014580', 'x44051401458']:
            self.assertFalse(matches({'type':'pesel'}, text))
        # Every encoded century and an impossible date with a correct checksum.
        def number(prefix):
            weights = [1,3,7,9,1,3,7,9,1,3]
            return prefix + str((-sum(int(c)*w for c,w in zip(prefix,weights))) % 10)
        for month in ['01','21','41','61','81']:
            self.assertTrue(valid_pesel(number('00'+month+'01000'+'1')))
        self.assertFalse(valid_pesel(number('0099010001')))
        self.assertFalse(valid_pesel(number('0002310001')))

    def test_disabled_and_legacy(self):
        self.assertTrue(matches({'contains':'Sekret'}, 'SEKRET'))
        self.assertFalse(matches({'type':'email','enabled':0}, 'a@example.com'))
        with self.assertRaises(ValueError):
            validate_rule({'name':'bad','type':'regex','severity':'critical'})

    def test_legacy_migration_preserves_rules_and_history(self):
        previous = app.DB
        with tempfile.TemporaryDirectory() as tmp:
            app.DB = str(Path(tmp) / 'legacy.sqlite3')
            try:
                with sqlite3.connect(app.DB) as db:
                    db.execute('CREATE TABLE rules (id INTEGER PRIMARY KEY,name TEXT NOT NULL,contains TEXT NOT NULL,severity TEXT NOT NULL)')
                    db.execute("INSERT INTO rules VALUES (1,'Legacy','secret','warning')")
                app.init_db()
                app.init_db()
                with app.connect() as db:
                    rule = dict(db.execute('SELECT * FROM rules').fetchone())
                    self.assertEqual(rule['type'], 'contains')
                    self.assertEqual(rule['enabled'], 1)
                    self.assertEqual(rule['contains'], 'secret')
                    self.assertEqual(db.execute('SELECT count(*) FROM rules').fetchone()[0], 1)
            finally:
                app.DB = previous
