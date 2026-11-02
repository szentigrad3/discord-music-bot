"""Read-only Lavalink smoke probe contract tests (no external requests)."""
import json
import unittest
from unittest.mock import MagicMock

from scripts.lavalink_smoke import check_lavalink


def response(data, status=200):
    res = MagicMock()
    res.status = status
    res.read.return_value = data
    res.__enter__.return_value = res
    return res


class LavalinkSmokeTests(unittest.TestCase):
    def test_version_info_and_auth_are_checked(self):
        info = {
            'plugins': [{'name': 'youtube-plugin'}, {'name': 'lavasrc-plugin'}],
            'sourceManagers': ['soundcloud', 'twitch'],
        }
        opened = MagicMock(side_effect=[
            response(b'4.0.8'),
            response(json.dumps(info).encode()),
        ])
        result = check_lavalink('localhost', 2333, 'secret', opener=opened)
        self.assertEqual(result['version'], '4.0.8')
        self.assertEqual(result['plugins'], ['youtube-plugin', 'lavasrc-plugin'])
        self.assertEqual(opened.call_count, 2)
        for args, kwargs in opened.call_args_list:
            request = args[0]
            self.assertEqual(request.get_header('Authorization'), 'secret')
            self.assertEqual(kwargs['timeout'], 5)

    def test_empty_version_is_failure(self):
        with self.assertRaises(ValueError):
            check_lavalink('localhost', 2333, 'secret',
                           opener=MagicMock(return_value=response(b'')))

    def test_no_password_fails_before_network(self):
        opener = MagicMock()
        with self.assertRaises(ValueError):
            check_lavalink('localhost', 2333, '', opener=opener)
        opener.assert_not_called()

    def test_malformed_plugin_list_is_not_fatal(self):
        opened = MagicMock(side_effect=[
            response(b'4.0.8'), response(b'{"plugins": null}')
        ])
        data = check_lavalink('localhost', 2333, 'secret', opener=opened)
        self.assertEqual(data['plugins'], [])
