"""Playback remains usable when Lavalink rejects optional player settings."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.music.player import MusicPlayer
from bot.music.track import Track


def music_player():
    voice = MagicMock()
    voice.is_playing = False
    voice.is_paused = False
    voice.is_connected = False
    voice.play = AsyncMock()
    voice.set_volume = AsyncMock()
    voice.reset_filters = AsyncMock()
    voice.add_filter = AsyncMock()
    guild = MagicMock(id=777)
    bot = MagicMock()
    bot.queues = {}
    player = MusicPlayer(guild, voice, None, bot)
    return player


class OptionalSettingFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_filter_failure_does_not_skip_playing_track(self):
        player = music_player()
        first = Track('song', 'https://example.com/one', '2:30',
                      _vl_track=MagicMock())
        second = Track('next', 'https://example.com/two', '2:30',
                       _vl_track=MagicMock())
        player.filter = 'nightcore'
        player._vl_player.add_filter.side_effect = RuntimeError('not supported')
        with patch('bot.music.player.logger'):
            await player.enqueue_many([first, second])
        self.assertIs(player.current, first)
        self.assertEqual(player.tracks, [second])
        self.assertEqual(player.filter, 'none')
        player._vl_player.play.assert_awaited_once()
        self.assertGreaterEqual(player._vl_player.reset_filters.await_count, 2)

    async def test_volume_failure_keeps_previous_volume(self):
        player = music_player()
        previous = player.volume
        player._vl_player.set_volume.side_effect = RuntimeError('node down')
        with self.assertRaises(RuntimeError):
            await player.set_volume(40)
        self.assertEqual(player.volume, previous)

    async def test_volume_success_clamps_and_commits(self):
        player = music_player()
        await player.set_volume(200)
        self.assertEqual(player.volume, 100)
        player._vl_player.set_volume.assert_awaited_once_with(100)

    async def test_filter_failure_does_not_change_requested_setting(self):
        player = music_player()
        player._vl_player.add_filter.side_effect = RuntimeError('unsupported')
        with self.assertRaises(RuntimeError):
            await player.set_filter('nightcore')
        self.assertEqual(player.filter, 'none')

    async def test_filter_reset_failure_does_not_change_local_setting(self):
        player = music_player()
        player.filter = 'nightcore'
        player._vl_player.reset_filters.side_effect = RuntimeError('offline')
        with self.assertRaises(RuntimeError):
            await player.set_filter('none')
        self.assertEqual(player.filter, 'nightcore')
