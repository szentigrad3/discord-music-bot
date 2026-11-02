"""Dashboard security and malformed-input regression checks."""
import unittest
from unittest.mock import patch

from bot.dashboard.app import app, _can_manage, _has_access


class DashboardSecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_cookie_settings(self):
        self.assertTrue(app.config['SESSION_COOKIE_HTTPONLY'])
        self.assertEqual(app.config['SESSION_COOKIE_SAMESITE'], 'Lax')

    def test_permission_validation(self):
        self.assertFalse(_can_manage({'permissions': 'invalid'}))
        self.assertFalse(_can_manage({'permissions': '0'}))
        self.assertTrue(_can_manage({'permissions': '32'}))
        self.assertTrue(_can_manage({'permissions': '0', 'owner': True}))
        self.assertFalse(_has_access({'guilds': [{'id': '12', 'permissions': '0'}]}, '12'))
        self.assertTrue(_has_access({'guilds': [{'id': '12', 'permissions': '32'}]}, '12'))

    def test_invalid_volume_does_not_throw_500(self):
        with self.client.session_transaction() as sess:
            sess['user'] = {'guilds': [{'id': '12', 'permissions': '32'}]}
            sess['_csrf'] = 'csrf-test'
        response = self.client.post('/dashboard/12/settings', data={
            '_csrf': 'csrf-test', 'defaultVolume': 'abc',
        })
        self.assertEqual(response.status_code, 400)

    def test_invalid_role_id_does_not_reach_database(self):
        with self.client.session_transaction() as sess:
            sess['user'] = {'guilds': [{'id': '12', 'permissions': '32'}]}
            sess['_csrf'] = 'csrf-test'
        with patch('bot.dashboard.app._update_settings') as save:
            response = self.client.post('/dashboard/12/settings', data={
                '_csrf': 'csrf-test', 'defaultVolume': '80',
                'djRoleId': 'not-a-snowflake',
            })
        self.assertEqual(response.status_code, 400)
        save.assert_not_called()

    def test_callback_requires_matching_state(self):
        response = self.client.get('/auth/discord/callback?state=forged&code=abc')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers['Location'].endswith('/'))


if __name__ == '__main__':
    unittest.main()
