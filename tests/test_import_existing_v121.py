"""v1.2.1 private configuration and SQLite migration regression tests."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.import_existing_v121 import import_setup, _dotenv_literal


class LegacyMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.old = self.root / 'old'
        self.new = self.root / 'checkout'
        (self.old / 'lavalink').mkdir(parents=True)
        (self.old / 'data/sfx').mkdir(parents=True)
        (self.new / 'lavalink').mkdir(parents=True)
        (self.new / 'data/sfx').mkdir(parents=True)
        (self.old / 'settings.json').write_text(json.dumps({
            'token': 'private-test-bot-token',
            'lavalink': {'host': 'localhost', 'port': 2333,
                         'password': 'test-custom-password'},
        }), encoding='utf8')
        (self.old / 'lavalink/application.yml').write_text(
            'lavalink:\n  server:\n    password: test-custom-password\n', encoding='utf8'
        )
        (self.old / 'lavalink/application.docker.yml').write_text(
            'lavalink:\n  server:\n    password: test-custom-password\n', encoding='utf8'
        )
        (self.new / 'lavalink/application.yml').write_text('tracked default', encoding='utf8')
        (self.new / 'lavalink/application.docker.yml').write_text(
            'tracked docker default', encoding='utf8'
        )
        (self.new / 'docker-compose.yml').write_text(
            'services:\n  lavalink:\n    environment:\n'
            '      - LAVALINK_SERVER_PASSWORD=${LAVALINK_PASSWORD:-youshallnotpass}\n',
            encoding='utf8',
        )
        (self.old / 'data/sfx/.gitkeep').write_text('', encoding='utf8')
        (self.new / 'data/sfx/.gitkeep').write_text('', encoding='utf8')
        (self.old / 'data/sfx/custom.mp3').write_bytes(b'fake music')
        db = self.old / 'data/bot.db'
        with sqlite3.connect(db) as conn:
            conn.execute('CREATE TABLE GuildSettings (guildId TEXT)')
            conn.execute('INSERT INTO GuildSettings (guildId) VALUES (?)', ('guild-test',))

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_never_copies_secrets(self):
        old_contents = (self.old / 'settings.json').read_bytes()
        planned = import_setup(self.old, self.new)
        self.assertTrue(any('settings.json' in x for x in planned))
        self.assertTrue(any('data/bot.db' in x for x in planned))
        self.assertFalse((self.new / 'settings.json').exists())
        self.assertFalse((self.new / '.env').exists())
        self.assertEqual((self.old / 'settings.json').read_bytes(), old_contents)

    def test_import_keeps_git_tracked_lavalink_defaults(self):
        old_content = (self.old / 'settings.json').read_bytes()
        imported = import_setup(self.old, self.new, apply=True)
        self.assertTrue(imported)
        self.assertEqual((self.new / 'settings.json').read_bytes(), old_content)
        self.assertEqual((self.old / 'settings.json').read_bytes(), old_content)
        self.assertEqual((self.new / 'lavalink/application.yml').read_text(),
                         'tracked default')
        self.assertEqual((self.new / 'lavalink/application.docker.yml').read_text(),
                         'tracked docker default')
        self.assertEqual((self.new / 'lavalink/application.local.yml').read_text(),
                         (self.old / 'lavalink/application.yml').read_text())
        self.assertEqual((self.new / 'lavalink/application.docker.local.yml').read_text(),
                         (self.old / 'lavalink/application.docker.yml').read_text())
        self.assertEqual((self.new / 'data/sfx/custom.mp3').read_bytes(), b'fake music')
        self.assertTrue((self.new / 'data/sfx/.gitkeep').exists())

    def test_sqlite_data_survives_and_file_is_private(self):
        import_setup(self.old, self.new, apply=True)
        db = self.new / 'data/bot.db'
        with sqlite3.connect(db) as conn:
            self.assertEqual(conn.execute('SELECT guildId FROM GuildSettings').fetchone(),
                             ('guild-test',))
        self.assertEqual(db.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.new / 'settings.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.new / '.env').stat().st_mode & 0o777, 0o600)

    def test_env_uses_real_local_password_without_printing_or_committing(self):
        import_setup(self.old, self.new, apply=True)
        env = (self.new / '.env').read_text(encoding='utf8')
        self.assertIn("LAVALINK_PASSWORD='test-custom-password'", env)
        self.assertIn('LAVALINK_CONFIG_FILE=application.docker.local.yml', env)

    def test_refuses_existing_private_config_in_destination(self):
        (self.new / 'settings.json').write_text('already configured')
        with self.assertRaises(FileExistsError):
            import_setup(self.old, self.new, apply=True)
        self.assertEqual((self.new / 'settings.json').read_text(), 'already configured')
        self.assertFalse((self.new / '.env').exists())

    def test_refuses_repeat_import(self):
        import_setup(self.old, self.new, apply=True)
        with self.assertRaises(FileExistsError):
            import_setup(self.old, self.new, apply=True)

    def test_refuses_same_directory(self):
        with self.assertRaises(ValueError):
            import_setup(self.old, self.old, apply=True)

    def test_requires_compose_env_password_support(self):
        (self.new / 'docker-compose.yml').write_text('services: {}')
        with self.assertRaises(ValueError):
            import_setup(self.old, self.new, apply=True)

    def test_refuses_empty_lavalink_password(self):
        cfg = json.loads((self.old / 'settings.json').read_text())
        cfg['lavalink']['password'] = ''
        (self.old / 'settings.json').write_text(json.dumps(cfg))
        with self.assertRaises(ValueError):
            import_setup(self.old, self.new, apply=True)

    def test_password_escaping_is_literal_and_no_linebreaks(self):
        self.assertEqual(_dotenv_literal('abc$def'), "'abc$def'")
        with self.assertRaises(ValueError):
            _dotenv_literal('abc\ninvalid')

    def test_generated_example_settings_are_safely_backed_up(self):
        generated = '{"token":"example-token","lavalink":{"password":"example"}}'
        (self.new / 'settings Example.json').write_text(generated, encoding='utf-8')
        (self.new / 'settings.json').write_text(generated, encoding='utf-8')
        plan = import_setup(self.old, self.new)
        self.assertTrue(any('generated-template.backup' in item for item in plan))
        self.assertEqual((self.new / 'settings.json').read_text(), generated)
        import_setup(self.old, self.new, apply=True)
        self.assertEqual((self.new / 'settings.json.generated-template.backup').read_text(), generated)
        self.assertEqual((self.new / 'settings.json').read_bytes(),
                         (self.old / 'settings.json').read_bytes())

    def test_modified_settings_not_mistaken_for_generated_example(self):
        (self.new / 'settings Example.json').write_text('{"token":""}')
        (self.new / 'settings.json').write_text('{"token":"my real token"}')
        with self.assertRaises(FileExistsError):
            import_setup(self.old, self.new, apply=True)
        self.assertEqual((self.new / 'settings.json').read_text(), '{"token":"my real token"}')
        self.assertFalse((self.new / 'settings.json.generated-template.backup').exists())

    def test_existing_template_backup_cannot_be_overwritten(self):
        generated = '{"token":""}'
        (self.new / 'settings Example.json').write_text(generated)
        (self.new / 'settings.json').write_text(generated)
        (self.new / 'settings.json.generated-template.backup').write_text('keep')
        with self.assertRaises(FileExistsError):
            import_setup(self.old, self.new, apply=True)
        self.assertEqual((self.new / 'settings.json.generated-template.backup').read_text(),
                         'keep')
