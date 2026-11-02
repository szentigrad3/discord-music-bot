"""Deterministic control transitions under delayed or missing node events."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.music.player import MusicPlayer, RepeatMode
from bot.music.track import Track


def make_track(name):
    return Track(title=name, url='https://example.invalid/' + name,
                 duration='3:00', _vl_track=MagicMock(track_id=name))


def player():
    guild = MagicMock()
    guild.id = 123
    vl = MagicMock()
    vl.is_playing = False
    vl.is_paused = False
    vl.is_connected = False
    vl.play = AsyncMock()
    vl.set_volume = AsyncMock()
    vl.stop = AsyncMock()
    bot = MagicMock()
    bot.queues = {}
    return MusicPlayer(guild, vl, None, bot)


class DeterministicPlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def test_skip_advances_without_a_node_event(self):
        p = player()
        first, second = make_track('first'), make_track('second')
        await p.enqueue_many([first, second])
        await p.skip()
        self.assertIs(p.current, second)
        self.assertEqual(p.history, [first])
        self.assertEqual(p._vl_player.play.await_count, 2)
        p._vl_player.stop.assert_awaited_once()
        await p._on_track_end(reason='stopped', ended_track=first._vl_track)
        self.assertIs(p.current, second)

    async def test_skip_bypasses_repeat_one(self):
        p = player()
        first, second = make_track('first'), make_track('second')
        await p.enqueue_many([first, second])
        p.set_repeat(RepeatMode.ONE)
        await p.skip()
        self.assertIs(p.current, second)

    async def test_back_revisits_history_without_event(self):
        p = player()
        old, now, later = [make_track(name) for name in ('old', 'now', 'later')]
        p.current = now
        p.history = [old]
        p.tracks = [later]
        await p.back()
        self.assertIs(p.current, old)
        self.assertEqual(p.tracks, [later])
        self.assertEqual(p.history, [now])

    async def test_skipto_changes_queue_atomically(self):
        p = player()
        now, a, b, c = [make_track(name) for name in ('now', 'a', 'b', 'c')]
        p.current = now
        p.tracks = [a, b, c]
        await p.skip_to(2)
        self.assertIs(p.current, b)
        self.assertEqual(p.tracks, [c])

    async def test_invalid_skipto_does_not_stop(self):
        p = player()
        p.current = make_track('now')
        p.tracks = [make_track('a')]
        with self.assertRaises(IndexError):
            await p.skip_to(3)
        self.assertEqual(len(p.tracks), 1)
        p._vl_player.stop.assert_not_awaited()

    async def test_skip_rolls_back_if_node_refuses_stop(self):
        p = player()
        now, next_track = make_track('now'), make_track('next')
        p.current = now
        p.tracks = [next_track]
        p._vl_player.stop.side_effect = RuntimeError('unavailable')
        with self.assertRaises(RuntimeError):
            await p.skip()
        self.assertIs(p.current, now)
        self.assertEqual(p.tracks, [next_track])

    async def test_concurrent_skip_requests_do_not_skip_two_songs(self):
        p = player()
        first, second, third = [make_track(x) for x in ('first', 'second', 'third')]
        await p.enqueue_many([first, second, third])
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow_stop():
            entered.set()
            await release.wait()

        p._vl_player.stop.side_effect = slow_stop
        t = asyncio.create_task(p.skip())
        await asyncio.wait_for(entered.wait(), timeout=2)
        # Natural track end is serialized behind the in-flight user action.
        event_task = asyncio.create_task(p._on_track_end(
            reason='stopped', ended_track=first._vl_track))
        release.set()
        await asyncio.gather(t, event_task)
        self.assertIs(p.current, second)
        self.assertEqual(p.tracks, [third])

    async def test_repeat_all_does_not_overfill_waiting_queue(self):
        p = player()
        old = make_track('old')
        p.current = old
        p.repeat_mode = RepeatMode.ALL
        from bot.music.player import MAX_PENDING_TRACKS
        p.tracks = [make_track(str(i)) for i in range(MAX_PENDING_TRACKS)]
        await p._on_track_end(reason='finished', ended_track=old._vl_track)
        self.assertEqual(len(p.tracks), MAX_PENDING_TRACKS - 1)
        self.assertIsNot(p.current, old)
