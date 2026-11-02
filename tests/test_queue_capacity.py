"""Queue capacity tests, including atomic rejection of whole playlists."""
import unittest
from unittest.mock import AsyncMock, MagicMock

from bot.music.player import MAX_PENDING_TRACKS, MusicPlayer, QueueFullError, RepeatMode
from bot.music.track import Track


def make_player():
    voice = MagicMock()
    voice.is_playing = False
    voice.is_paused = False
    voice.is_connected = False
    voice.play = AsyncMock()
    voice.set_volume = AsyncMock()
    guild = MagicMock(id=42)
    bot = MagicMock()
    bot.queues = {}
    return MusicPlayer(guild, voice, None, bot)


def make_track(name):
    return Track(name, 'https://example.com', '3:00', _vl_track=MagicMock())


class QueueCapacityTests(unittest.IsolatedAsyncioTestCase):
    async def test_idle_player_reserves_first_track_for_immediate_play(self):
        player = make_player()
        items = [make_track(str(i)) for i in range(MAX_PENDING_TRACKS + 1)]
        await player.enqueue_many(items)
        self.assertIs(player.current, items[0])
        self.assertEqual(len(player.tracks), MAX_PENDING_TRACKS)

    async def test_overlimit_enqueue_is_atomic(self):
        player = make_player()
        items = [make_track(str(i)) for i in range(MAX_PENDING_TRACKS + 2)]
        with self.assertRaises(QueueFullError):
            await player.enqueue_many(items)
        self.assertEqual(player.tracks, [])
        self.assertIsNone(player.current)
        player._vl_player.play.assert_not_awaited()

    async def test_active_queue_rejects_extra_track(self):
        player = make_player()
        player.current = make_track('current')
        player.tracks = [make_track(str(i)) for i in range(MAX_PENDING_TRACKS)]
        with self.assertRaises(QueueFullError):
            await player.enqueue(make_track('extra'))
        self.assertEqual(len(player.tracks), MAX_PENDING_TRACKS)

    async def test_failed_repeat_all_does_not_requeue_unplayable(self):
        player = make_player()
        now = make_track('now')
        next_track = make_track('next')
        player.current = now
        player.tracks = [next_track]
        player.set_repeat(RepeatMode.ALL)
        await player._on_track_end(reason='loadFailed', ended_track=now._vl_track)
        self.assertIs(player.current, next_track)
        self.assertEqual(player.tracks, [])
