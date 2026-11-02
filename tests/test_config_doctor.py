"""Offline preflight checks intentionally never expose provided secrets."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts.doctor import inspect_config, main


def sample():
    return {
        'token': 'private-discord-test-token-value-123',
        'lavalink': {
            'host': 'localhost', 'port': 2333, 'password': 'different-test-secret',
        },
    }


class ConfigDoctorTests(unittest.TestCase):
    def test_valid_minimal_bot_config(self):
        errors, warnings = inspect_config(sample())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_bad_token_and_password(self):
        conf = sample()
        conf['token'] = 'YOUR_TOKEN_HERE'
        conf['lavalink']['password'] = ''
        errors, warnings = inspect_config(conf)
        self.assertEqual(len(errors), 2)

    def test_invalid_port_does_not_raise(self):
        conf = sample()
        for port in ('invalid', 0, 99999, None):
            with self.subTest(port=port):
                conf['lavalink']['port'] = port
                self.assertTrue(inspect_config(conf)[0])

    def test_dashboard_requires_oauth_client_credentials(self):
        conf = sample()
        conf['session_secret'] = 'a' * 32
        errors, _ = inspect_config(conf)
        self.assertTrue(any('OAuth' in error for error in errors))

    def test_http_public_oauth_callback_warning(self):
        conf = sample()
        conf.update({
            'session_secret': 'a' * 32,
            'client_id': '123',
            'client_secret': 'secret',
            'callback_url': 'http://public.example.com/auth/discord/callback',
        })
        self.assertFalse(inspect_config(conf)[0])
        self.assertTrue(any('HTTPS' in w for w in inspect_config(conf)[1]))

    def test_no_sensitive_values_in_command_output(self):
        conf = sample()
        conf['lavalink']['password'] = 'youshallnotpass'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'settings.json'
            path.write_text(json.dumps(conf), encoding='utf-8')
            out = io.StringIO()
            with redirect_stdout(out):
                status = main(['--config', str(path)])
            self.assertEqual(status, 0)
            self.assertIn('WARN', out.getvalue())
            self.assertNotIn(conf['token'], out.getvalue())
            self.assertNotIn('youshallnotpass', out.getvalue())

    def test_strict_warnings_fail_without_disclosing_secrets(self):
        conf = sample()
        conf['lavalink']['password'] = 'youshallnotpass'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'settings.json'
            path.write_text(json.dumps(conf), encoding='utf-8')
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--config', str(path), '--strict']), 1)

    def test_malformed_config_or_missing_file(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'settings.json'
            path.write_text('{not json', encoding='utf-8')
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--config', str(path)]), 2)
                self.assertEqual(main(['--config', str(path) + 'missing']), 2)
