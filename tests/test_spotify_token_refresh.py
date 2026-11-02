"""Spotify credential refresh concurrency regression tests."""
import asyncio
import unittest
from unittest.mock import patch

from bot.music import queue


class FakeResponse:
    ok = True
    status = 200

    def __init__(self, token):
        self.token = token

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        await asyncio.sleep(0.01)
        return {'access_token': self.token, 'expires_in': 3600}


class FakeSession:
    def __init__(self, tracker):
        self.tracker = tracker

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    def post(self, *args, **kwargs):
        self.tracker['count'] += 1
        assert kwargs['data'] == 'grant_type=client_credentials'
        return FakeResponse('example-test-token')


class SpotifyTokenRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_requests_share_one_refresh(self):
        calls = {'count': 0}
        settings = type('Settings', (), {
            'spotify_client_id': 'id', 'spotify_client_secret': 'secret',
        })()
        with patch('bot.settings.settings', settings), \
             patch('aiohttp.ClientSession', side_effect=lambda **kw: FakeSession(calls)), \
             patch.object(queue, '_spotify_access_token', None), \
             patch.object(queue, '_spotify_token_expiry', 0.0):
            results = await asyncio.gather(*[
                queue._ensure_spotify_token() for _ in range(20)
            ])
            self.assertEqual(results, [True] * 20)
            self.assertEqual(calls['count'], 1)
            self.assertEqual(queue._spotify_access_token, 'example-test-token')

    async def test_expired_token_is_refreshed(self):
        calls = {'count': 0}
        settings = type('Settings', (), {
            'spotify_client_id': 'id', 'spotify_client_secret': 'secret',
        })()
        with patch('bot.settings.settings', settings), \
             patch('aiohttp.ClientSession', side_effect=lambda **kw: FakeSession(calls)), \
             patch.object(queue, '_spotify_access_token', None), \
             patch.object(queue, '_spotify_token_expiry', 0.0):
            self.assertTrue(await queue._ensure_spotify_token())
            queue._spotify_token_expiry = 0.0
            self.assertTrue(await queue._ensure_spotify_token())
            self.assertEqual(calls['count'], 2)

    async def test_missing_credentials_do_not_contact_provider(self):
        settings = type('Settings', (), {
            'spotify_client_id': '', 'spotify_client_secret': '',
        })()
        with patch('bot.settings.settings', settings), \
             patch('aiohttp.ClientSession') as client:
            self.assertFalse(await queue._ensure_spotify_token())
            client.assert_not_called()
