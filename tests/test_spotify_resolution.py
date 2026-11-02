"""Spotify URL parsing and bounded playlist resolution regression tests."""
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from bot.music.queue import _resolve_spotify, _spotify_link, resolve_tracks


class SpotifyUrlTests(unittest.TestCase):
    def test_accepts_real_links(self):
        self.assertEqual(_spotify_link('https://open.spotify.com/track/abc123?si=xx'), ('track', 'abc123'))
        self.assertEqual(_spotify_link('https://open.spotify.com/album/abc123'), ('album', 'abc123'))
        self.assertEqual(_spotify_link('https://open.spotify.com/playlist/abc123/'), ('playlist', 'abc123'))

    def test_rejects_spoofing_and_malformed_urls(self):
        for value in ('https://open.spotify.com.evil.test/track/abc',
                      'https://evil.test/open.spotify.com/track/abc',
                      'file://open.spotify.com/track/abc',
                      'https://open.spotify.com/other/abc',
                      'https://open.spotify.com/track/abc/extra'):
            with self.subTest(value=value):
                self.assertIsNone(_spotify_link(value))


class SpotifyResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_playlist_preserves_order_with_bounded_parallelism(self):
        active = 0
        peak = 0
        async def resolve(name, requester):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep((6 - int(name[-1])) * 0.002)
                return [name]
            finally:
                active -= 1

        items = [{'track': {'name': f'Song{i}', 'artists': [{'name': 'Band'}]}}
                 for i in range(6)]
        with patch('bot.music.queue._ensure_spotify_token', new=AsyncMock(return_value=True)), \
             patch('bot.music.queue._spotify_get', new=AsyncMock(return_value={'items': items})), \
             patch('bot.music.queue._resolve_via_voicelink', side_effect=resolve):
            result = await _resolve_spotify('https://open.spotify.com/playlist/test123', 'tester')
        self.assertEqual(result, [f'Band Song{i}' for i in range(6)])
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 3)

    async def test_no_playable_results_is_error(self):
        with patch('bot.music.queue._ensure_spotify_token', new=AsyncMock(return_value=True)), \
             patch('bot.music.queue._spotify_get', new=AsyncMock(return_value={'items': []})):
            with self.assertRaisesRegex(RuntimeError, 'no playable tracks'):
                await _resolve_spotify('https://open.spotify.com/playlist/test123', 'tester')

    async def test_failed_individual_track_does_not_abort_other_results(self):
        async def resolve(name, requester):
            if name.endswith('Broken'):
                raise RuntimeError('Unavailable')
            return [name]

        items = [{'track': {'name': n, 'artists': [{'name': 'Band'}]}}
                 for n in ('Good', 'Broken', 'Other')]
        with patch('bot.music.queue._ensure_spotify_token', new=AsyncMock(return_value=True)), \
             patch('bot.music.queue._spotify_get', new=AsyncMock(return_value={'items': items})), \
             patch('bot.music.queue._resolve_via_voicelink', side_effect=resolve):
            result = await _resolve_spotify('https://open.spotify.com/playlist/test123', None)
        self.assertEqual(result, ['Band Good', 'Band Other'])

    async def test_spoofed_domain_goes_to_generic_search(self):
        with patch('bot.music.queue._resolve_via_voicelink', new=AsyncMock(return_value=['fallback'])) as mock:
            result = await resolve_tracks('https://open.spotify.com.evil.test/track/abc')
        self.assertEqual(result, ['fallback'])
        mock.assert_awaited_once()
