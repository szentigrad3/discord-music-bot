"""Tests for MusicPlayer new features: seek, move_track, clear_queue, and new filters."""

import asyncio
import logging
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.music.player import MusicPlayer, FILTERS, _build_voicelink_filters, RepeatMode
from bot.music.track import Track as MusicTrack


def _make_vl_track(title="Test Track", length=300000, is_seekable=True) -> MagicMock:
    """Create a minimal mock voicelink track."""
    t = MagicMock()
    t.title = title
    t.uri = "https://www.youtube.com/watch?v=test"
    t.length = length
    t.thumbnail = None
    t.author = "Test Artist"
    t.source = "youtube"
    t.is_seekable = is_seekable
    t.is_stream = False
    t.track_id = "encoded_track_id"
    return t


def _make_music_track(title="Track", **kwargs) -> MusicTrack:
    vl = _make_vl_track(title=title)
    return MusicTrack(
        title=title,
        url="https://example.com",
        duration="3:00",
        _vl_track=vl,
    )


def _make_music_player() -> MusicPlayer:
    """Create a MusicPlayer with all external dependencies mocked."""
    vl_player = MagicMock()
    vl_player.is_playing = False
    vl_player.is_paused = False
    vl_player.is_connected = True
    vl_player.position = 0
    vl_player.stop = AsyncMock()
    vl_player.set_volume = AsyncMock()
    vl_player.play = AsyncMock()
    vl_player.seek = AsyncMock()
    vl_player.set_pause = AsyncMock()
    vl_player.reset_filters = AsyncMock()
    vl_player.add_filter = AsyncMock()
    vl_player.disconnect = AsyncMock()

    guild = MagicMock()
    guild.id = 123456789

    bot = MagicMock()
    bot.queues = {}

    text_channel = MagicMock()

    player = MusicPlayer(guild=guild, vl_player=vl_player, text_channel=text_channel, bot=bot)
    return player


class TestFilters(unittest.TestCase):
    """Tests for the expanded FILTERS dictionary and _build_voicelink_filters."""

    def test_filters_dict_contains_all_expected_filters(self):
        """FILTERS should include all standard and extended filter names."""
        expected = {'none', 'nightcore', 'bassboost', 'vaporwave', '8d', 'karaoke', 'slowed'}
        self.assertEqual(set(FILTERS.keys()), expected)

    def test_build_voicelink_filters_nightcore(self):
        filters = _build_voicelink_filters('nightcore')
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0].tag, 'nightcore')

    def test_build_voicelink_filters_bassboost(self):
        filters = _build_voicelink_filters('bassboost')
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0].tag, 'boost')

    def test_build_voicelink_filters_vaporwave(self):
        filters = _build_voicelink_filters('vaporwave')
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0].tag, 'vaporwave')

    def test_build_voicelink_filters_8d(self):
        filters = _build_voicelink_filters('8d')
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0].tag, '8d')

    def test_build_voicelink_filters_karaoke(self):
        filters = _build_voicelink_filters('karaoke')
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0].tag, 'karaoke')

    def test_build_voicelink_filters_slowed(self):
        filters = _build_voicelink_filters('slowed')
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0].tag, 'slowed')

    def test_build_voicelink_filters_none_returns_empty(self):
        filters = _build_voicelink_filters('none')
        self.assertEqual(filters, [])

    def test_build_voicelink_filters_unknown_returns_empty(self):
        filters = _build_voicelink_filters('unknown_filter')
        self.assertEqual(filters, [])


class TestMusicPlayerSeek(unittest.TestCase):
    """Tests for MusicPlayer.seek()."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_seek_calls_vl_player_seek_with_milliseconds(self):
        """seek(seconds) should call the underlying player's seek() with seconds * 1000."""
        player = _make_music_player()
        self._run(player.seek(30))
        player._vl_player.seek.assert_called_once_with(30000)

    def test_seek_zero_seconds(self):
        """seek(0) should call seek with 0 milliseconds."""
        player = _make_music_player()
        self._run(player.seek(0))
        player._vl_player.seek.assert_called_once_with(0)

    def test_seek_large_value(self):
        """seek with a large seconds value should pass it correctly converted."""
        player = _make_music_player()
        self._run(player.seek(3600))  # 1 hour
        player._vl_player.seek.assert_called_once_with(3600000)


class TestMusicPlayerMoveTrack(unittest.TestCase):
    """Tests for MusicPlayer.move_track()."""

    def _make_player_with_tracks(self, count=5) -> MusicPlayer:
        player = _make_music_player()
        player.tracks = [_make_music_track(title=f'Track {i}') for i in range(1, count + 1)]
        return player

    def test_move_track_from_first_to_last(self):
        """Moving the first track to the last position."""
        player = self._make_player_with_tracks(5)
        player.move_track(1, 5)
        titles = [t.title for t in player.tracks]
        self.assertEqual(titles, ['Track 2', 'Track 3', 'Track 4', 'Track 5', 'Track 1'])

    def test_move_track_from_last_to_first(self):
        """Moving the last track to the first position."""
        player = self._make_player_with_tracks(5)
        player.move_track(5, 1)
        titles = [t.title for t in player.tracks]
        self.assertEqual(titles, ['Track 5', 'Track 1', 'Track 2', 'Track 3', 'Track 4'])

    def test_move_track_middle(self):
        """Moving track 2 to position 4."""
        player = self._make_player_with_tracks(5)
        player.move_track(2, 4)
        titles = [t.title for t in player.tracks]
        self.assertEqual(titles, ['Track 1', 'Track 3', 'Track 4', 'Track 2', 'Track 5'])

    def test_move_track_queue_length_unchanged(self):
        """Queue length should remain the same after a move."""
        player = self._make_player_with_tracks(5)
        player.move_track(2, 4)
        self.assertEqual(len(player.tracks), 5)


class TestMusicPlayerClearQueue(unittest.TestCase):
    """Tests for MusicPlayer.clear_queue()."""

    def test_clear_queue_removes_all_tracks(self):
        """clear_queue() should empty the tracks list."""
        player = _make_music_player()
        player.tracks = [_make_music_track() for _ in range(5)]
        player.clear_queue()
        self.assertEqual(player.tracks, [])

    def test_clear_queue_returns_correct_count(self):
        """clear_queue() should return the number of tracks removed."""
        player = _make_music_player()
        player.tracks = [_make_music_track() for _ in range(7)]
        count = player.clear_queue()
        self.assertEqual(count, 7)

    def test_clear_queue_empty_queue_returns_zero(self):
        """clear_queue() on an empty queue should return 0."""
        player = _make_music_player()
        count = player.clear_queue()
        self.assertEqual(count, 0)

    def test_clear_queue_does_not_affect_current_track(self):
        """clear_queue() should not touch the currently playing track."""
        player = _make_music_player()
        current = _make_music_track(title='Now Playing')
        player.current = current
        player.tracks = [_make_music_track() for _ in range(3)]
        player.clear_queue()
        self.assertEqual(player.current, current)


class TestMusicTrackFields(unittest.TestCase):
    """Tests for the updated Track model with author and source fields."""

    def test_from_voicelink_populates_author(self):
        """Track.from_voicelink should populate the author field."""
        vl = _make_vl_track(title="Song")
        track = MusicTrack.from_voicelink(vl, requested_by="user#1234")
        self.assertEqual(track.author, "Test Artist")

    def test_from_voicelink_populates_source(self):
        """Track.from_voicelink should populate the source field."""
        vl = _make_vl_track()
        track = MusicTrack.from_voicelink(vl)
        self.assertEqual(track.source, "youtube")

    def test_from_voicelink_author_none_when_missing(self):
        """Track.from_voicelink should handle missing author gracefully."""
        vl = MagicMock()
        vl.title = "Track"
        vl.uri = "https://example.com"
        vl.length = 180000
        vl.thumbnail = None
        vl.is_stream = False
        vl.author = None
        vl.source = None
        track = MusicTrack.from_voicelink(vl)
        self.assertIsNone(track.author)


if __name__ == "__main__":
    unittest.main()
