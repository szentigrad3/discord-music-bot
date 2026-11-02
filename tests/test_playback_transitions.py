"""Playback queue transitions without a live Discord/Lavalink connection."""
import asyncio
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.music.player import MusicPlayer, RepeatMode
from bot.music.track import Track


def make_player():
    guild = MagicMock()
    guild.id = 42
    vl = MagicMock()
    vl.is_playing = False
    vl.is_paused = False
    vl.is_connected = True
    vl.stop = AsyncMock()
    vl.play = AsyncMock()
    vl.set_volume = AsyncMock()
    vl.disconnect = AsyncMock()
    bot = MagicMock()
    bot.queues = {}
    player = MusicPlayer(guild, vl, None, bot)
    bot.queues['42'] = player
    return player


def track(name, encoded=True):
    return Track(title=name, url='https://example.com',
                 duration='3:00', _vl_track=(MagicMock(track_id=name) if encoded else None))


class PlaybackTransitionTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeat_one_replays_successful_finish(self):
        p = make_player()
        first = track('first')
        await p.enqueue(first)
        p.set_repeat(RepeatMode.ONE)
        await p._on_track_end(reason='finished', ended_track=first._vl_track)
        self.assertIs(p.current, first)
        self.assertEqual(p._vl_player.play.await_count, 2)
        self.assertEqual(p.history, [])

    async def test_skip_ignores_repeat_one(self):
        p = make_player()
        first, second = track('first'), track('second')
        await p.enqueue_many([first, second])
        p.set_repeat(RepeatMode.ONE)
        await p._on_track_end(reason='stopped', ended_track=first._vl_track)
        self.assertIs(p.current, second)
        self.assertEqual(p._vl_player.play.await_count, 2)

    async def test_late_end_event_cannot_skip_next_track(self):
        p = make_player()
        first, second = track('first'), track('second')
        await p.enqueue_many([first, second])
        await p._on_track_end(reason='finished', ended_track=first._vl_track)
        await p._on_track_end(reason='finished', ended_track=first._vl_track)
        self.assertIs(p.current, second)
        self.assertEqual(p._vl_player.play.await_count, 2)

    async def test_stop_blocks_late_end_event(self):
        p = make_player()
        first, second = track('first'), track('second')
        await p.enqueue_many([first, second])
        await p.stop()
        await p._on_track_end(reason='stopped', ended_track=first._vl_track)
        self.assertIsNone(p.current)
        self.assertEqual(p.tracks, [])
        self.assertEqual(p._vl_player.play.await_count, 1)

    async def test_unplayable_track_falls_forward(self):
        p = make_player()
        missing, good = track('missing', encoded=False), track('good')
        await p.enqueue_many([missing, good])
        self.assertIs(p.current, good)
        self.assertEqual(p._vl_player.play.await_count, 1)

    async def test_repeat_one_does_not_retry_failed_track_indefinitely(self):
        p = make_player()
        bad, good = track('bad'), track('good')
        await p.enqueue_many([bad, good])
        p.set_repeat(RepeatMode.ONE)
        p._vl_player.play.side_effect = [RuntimeError('source unavailable'), None]
        with patch('bot.music.player.logger'):
            await p._on_track_end(reason='finished', ended_track=bad._vl_track)
        self.assertIs(p.current, good)
        self.assertEqual(p._vl_player.play.await_count, 3)

    async def test_many_unplayable_tracks_do_not_recurse(self):
        p = make_player()
        items = [track(str(n), encoded=False) for n in range(1100)]
        with patch('bot.music.player.logger'):
            await p.enqueue_many(items)
        self.assertIsNone(p.current)
        self.assertEqual(p.tracks, [])
        p._vl_player.disconnect.assert_awaited_once()

    async def test_concurrent_enqueues_start_only_one_track(self):
        p = make_player()
        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_start(_):
            started.set()
            await release.wait()

        p._vl_player.play.side_effect = slow_start
        first, second = track('first'), track('second')
        task_a = asyncio.create_task(p.enqueue(first))
        await asyncio.wait_for(started.wait(), 2)
        task_b = asyncio.create_task(p.enqueue(second))
        release.set()
        await asyncio.gather(task_a, task_b)
        self.assertIs(p.current, first)
        self.assertEqual(p.tracks, [second])
        self.assertEqual(p._vl_player.play.await_count, 1)
