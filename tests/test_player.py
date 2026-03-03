"""Tests for voicelink player voice update dispatch and play() data format."""

import asyncio
import logging
import sys
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call

# Ensure the bot package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.voicelink.player import Player
from bot.voicelink.objects import Track
from bot.voicelink.enums import RequestMethod
from bot.voicelink.exceptions import NodeException


def _make_track(track_id: str = "encoded_track_id", length: int = 300000) -> Track:
    info = {
        "identifier": "test_id",
        "title": "Test Track",
        "author": "Test Author",
        "uri": "https://www.youtube.com/watch?v=test_id",
        "sourceName": "youtube",
        "length": length,
        "isStream": False,
        "isSeekable": True,
        "position": 0,
    }
    return Track(track_id=track_id, info=info)


def _make_player() -> Player:
    """Create a Player instance with mocked node, guild, and channel."""
    node = MagicMock()
    node._session_id = "test_session_id"
    node._players = {}
    node._logger = logging.getLogger("voicelink")
    node.yt_ratelimit = None
    node.send = AsyncMock(return_value={})

    guild = MagicMock()
    guild.id = 123456789

    channel = MagicMock()
    channel.guild = guild

    with patch("bot.voicelink.player.NodePool") as MockPool:
        MockPool.get_node.return_value = node
        player = Player(client=MagicMock(), channel=channel)

    player._node = node
    player._guild = guild
    player._logger = logging.getLogger("voicelink")
    return player


class TestDispatchVoiceUpdate(unittest.TestCase):
    """Tests for Player._dispatch_voice_update."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_returns_early_when_session_id_is_none(self):
        """Guard: returns immediately when Lavalink session ID is not yet set."""
        player = _make_player()
        player._node._session_id = None
        player._voice_state = {"sessionId": "ds1", "event": {"token": "tok", "endpoint": "us-east1.discord.media:443"}}

        self._run(player._dispatch_voice_update())

        player._node.send.assert_not_called()

    def test_returns_early_when_voice_state_incomplete_missing_event(self):
        """Guard: returns immediately when voice state only has sessionId (no event yet)."""
        player = _make_player()
        player._voice_state = {"sessionId": "ds1"}

        self._run(player._dispatch_voice_update())

        player._node.send.assert_not_called()

    def test_returns_early_when_voice_state_incomplete_missing_session_id(self):
        """Guard: returns immediately when voice state only has event (no sessionId yet)."""
        player = _make_player()
        player._voice_state = {"event": {"token": "tok", "endpoint": "us-east1.discord.media:443"}}

        self._run(player._dispatch_voice_update())

        player._node.send.assert_not_called()

    def test_returns_early_when_voice_state_empty(self):
        """Guard: returns immediately when voice state is empty."""
        player = _make_player()
        player._voice_state = {}

        self._run(player._dispatch_voice_update())

        player._node.send.assert_not_called()

    def test_returns_early_when_endpoint_is_none(self):
        """Guard: returns immediately when voice server endpoint is null."""
        player = _make_player()
        player._voice_state = {
            "sessionId": "ds1",
            "event": {"token": "tok", "endpoint": None},
        }

        self._run(player._dispatch_voice_update())

        player._node.send.assert_not_called()

    def test_returns_early_when_token_is_missing(self):
        """Guard: returns immediately when voice token is missing."""
        player = _make_player()
        player._voice_state = {
            "sessionId": "ds1",
            "event": {"endpoint": "us-east1.discord.media:443"},
        }

        self._run(player._dispatch_voice_update())

        player._node.send.assert_not_called()

    def test_returns_early_when_session_id_value_is_none(self):
        """Guard: returns immediately when Discord voice sessionId value is None."""
        player = _make_player()
        player._voice_state = {
            "sessionId": None,
            "event": {"token": "tok", "endpoint": "us-east1.discord.media:443"},
        }

        self._run(player._dispatch_voice_update())

        player._node.send.assert_not_called()

    def test_sends_correct_voice_data_to_lavalink(self):
        """Happy path: correct JSON body is sent when all voice state fields are valid."""
        player = _make_player()
        player._voice_state = {
            "sessionId": "discord_session_abc",
            "event": {
                "token": "voice_token_xyz",
                "endpoint": "us-east1.discord.media:443",
                "guild_id": "123456789",
            },
        }

        self._run(player._dispatch_voice_update())

        player._node.send.assert_called_once()
        call_args = player._node.send.call_args
        # The node.send receives (method, query=uri, data=payload)
        sent_data = call_args.kwargs.get("data") or call_args.args[2] if len(call_args.args) > 2 else call_args.kwargs.get("data")
        self.assertIsNotNone(sent_data)
        self.assertIn("voice", sent_data)
        voice = sent_data["voice"]
        self.assertEqual(voice["token"], "voice_token_xyz")
        self.assertEqual(voice["endpoint"], "us-east1.discord.media:443")
        self.assertEqual(voice["sessionId"], "discord_session_abc")

    def test_strips_protocol_prefix_from_endpoint(self):
        """Endpoint with wss:// prefix is stripped before being sent to Lavalink."""
        player = _make_player()
        player._voice_state = {
            "sessionId": "discord_session_abc",
            "event": {
                "token": "voice_token_xyz",
                "endpoint": "wss://us-east1.discord.media:443",
            },
        }

        self._run(player._dispatch_voice_update())

        call_args = player._node.send.call_args
        sent_data = call_args.kwargs.get("data") or call_args.args[2]
        self.assertEqual(sent_data["voice"]["endpoint"], "us-east1.discord.media:443")

    def test_logs_warning_on_node_exception(self):
        """A NodeException from Lavalink is caught and logged as a WARNING."""
        player = _make_player()
        player._node.send = AsyncMock(
            side_effect=NodeException("Lavalink REST api returned 400: Bad Request")
        )
        player._voice_state = {
            "sessionId": "discord_session_abc",
            "event": {"token": "tok", "endpoint": "us-east1.discord.media:443"},
        }

        with self.assertLogs("voicelink", level="WARNING") as cm:
            self._run(player._dispatch_voice_update())

        self.assertTrue(any("Failed to dispatch voice update" in msg for msg in cm.output))

    def test_voice_data_values_are_strings(self):
        """All three voice state values sent to Lavalink are strings (Lavalink v4 requirement)."""
        player = _make_player()
        player._voice_state = {
            "sessionId": "discord_session_123",
            "event": {
                "token": "some_token",
                "endpoint": "us-east1.discord.media:443",
            },
        }

        self._run(player._dispatch_voice_update())

        call_args = player._node.send.call_args
        sent_data = call_args.kwargs.get("data") or call_args.args[2]
        voice = sent_data["voice"]
        self.assertIsInstance(voice["token"], str)
        self.assertIsInstance(voice["endpoint"], str)
        self.assertIsInstance(voice["sessionId"], str)


class TestPlayDataFormat(unittest.TestCase):
    """Tests for Player.play() to verify correct Lavalink v4 data types."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_position_is_integer_not_string(self):
        """play() must send 'position' as an integer, not a string.

        Lavalink v4 expects position as Long; sending a string causes a
        Jackson deserialization failure and a 400 Bad Request response.
        """
        player = _make_player()
        track = _make_track()

        self._run(player.play(track=track, start=12345))

        call_args = player._node.send.call_args
        sent_data = call_args.kwargs.get("data") or call_args.args[2]
        self.assertIn("position", sent_data)
        self.assertIsInstance(
            sent_data["position"],
            int,
            "position must be an integer (not string) for Lavalink v4",
        )
        self.assertEqual(sent_data["position"], 12345)

    def test_position_zero_is_integer(self):
        """play() with default start=0 must send integer 0, not string '0'."""
        player = _make_player()
        track = _make_track()

        self._run(player.play(track=track))

        call_args = player._node.send.call_args
        sent_data = call_args.kwargs.get("data") or call_args.args[2]
        self.assertIsInstance(sent_data["position"], int)
        self.assertEqual(sent_data["position"], 0)

    def test_end_time_is_integer_not_string(self):
        """play() must send 'endTime' as an integer, not a string."""
        player = _make_player()
        track = _make_track()

        self._run(player.play(track=track, end=60000))

        call_args = player._node.send.call_args
        sent_data = call_args.kwargs.get("data") or call_args.args[2]
        self.assertIn("endTime", sent_data)
        self.assertIsInstance(
            sent_data["endTime"],
            int,
            "endTime must be an integer (not string) for Lavalink v4",
        )
        self.assertEqual(sent_data["endTime"], 60000)

    def test_no_replace_false_is_lowercase(self):
        """noReplace query param must be lowercase 'false', not Python 'False'."""
        player = _make_player()
        track = _make_track()

        self._run(player.play(track=track, ignore_if_playing=False))

        call_args = player._node.send.call_args
        # The query param is passed through player.send as the `query` argument to node.send
        # player.send builds the uri using the query argument
        # We inspect the `query` keyword argument passed to player.send via the URI
        uri_arg = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("query", "")
        self.assertIn("noReplace=false", uri_arg,
                      "noReplace=false (lowercase) is required by Lavalink v4")
        self.assertNotIn("noReplace=False", uri_arg,
                         "Python's capitalized 'False' must not be sent")

    def test_no_replace_true_is_lowercase(self):
        """noReplace query param must be lowercase 'true', not Python 'True'."""
        player = _make_player()
        track = _make_track()

        self._run(player.play(track=track, ignore_if_playing=True))

        call_args = player._node.send.call_args
        uri_arg = call_args.args[1] if len(call_args.args) > 1 else call_args.kwargs.get("query", "")
        self.assertIn("noReplace=true", uri_arg,
                      "noReplace=true (lowercase) is required by Lavalink v4")
        self.assertNotIn("noReplace=True", uri_arg,
                         "Python's capitalized 'True' must not be sent")

    def test_encoded_track_is_included(self):
        """play() must include encodedTrack in the request body."""
        player = _make_player()
        track = _make_track(track_id="my_encoded_track")

        self._run(player.play(track=track))

        call_args = player._node.send.call_args
        sent_data = call_args.kwargs.get("data") or call_args.args[2]
        self.assertEqual(sent_data["encodedTrack"], "my_encoded_track")

    def test_end_time_from_track_is_integer(self):
        """When end_time comes from the track object, it must also be sent as integer."""
        player = _make_player()
        track = _make_track()
        track.end_time = 90000  # set end_time on the track

        self._run(player.play(track=track))

        call_args = player._node.send.call_args
        sent_data = call_args.kwargs.get("data") or call_args.args[2]
        self.assertIn("endTime", sent_data)
        self.assertIsInstance(sent_data["endTime"], int)
        self.assertEqual(sent_data["endTime"], 90000)


class TestOnVoiceServerUpdate(unittest.TestCase):
    """Tests for Player.on_voice_server_update / on_voice_state_update interaction."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_on_voice_server_update_dispatches_when_state_complete(self):
        """on_voice_server_update should trigger _dispatch_voice_update when sessionId is set."""
        player = _make_player()
        player._voice_state = {"sessionId": "discord_session_1"}

        voice_server_data = {
            "token": "fresh_token",
            "endpoint": "us-east1.discord.media:443",
            "guild_id": str(player._guild.id),
        }

        self._run(player.on_voice_server_update(voice_server_data))

        player._node.send.assert_called_once()
        call_args = player._node.send.call_args
        sent_data = call_args.kwargs.get("data") or call_args.args[2]
        self.assertEqual(sent_data["voice"]["token"], "fresh_token")

    def test_on_voice_server_update_no_dispatch_when_session_id_missing(self):
        """on_voice_server_update should NOT dispatch if sessionId not yet set."""
        player = _make_player()
        player._voice_state = {}  # no sessionId yet

        voice_server_data = {
            "token": "fresh_token",
            "endpoint": "us-east1.discord.media:443",
            "guild_id": str(player._guild.id),
        }

        self._run(player.on_voice_server_update(voice_server_data))

        player._node.send.assert_not_called()

    def test_on_voice_state_update_updates_session_id(self):
        """on_voice_state_update should update _voice_state with the new Discord session ID."""
        player = _make_player()
        player._voice_state = {}
        player._guild.get_channel = MagicMock(return_value=MagicMock())

        voice_state_data = {
            "session_id": "new_discord_session",
            "channel_id": "987654321",
            "user_id": "111",
            "guild_id": str(player._guild.id),
        }

        self._run(player.on_voice_state_update(voice_state_data))

        self.assertEqual(player._voice_state.get("sessionId"), "new_discord_session")

    def test_on_voice_state_update_dispatches_when_event_already_present(self):
        """When VOICE_SERVER_UPDATE arrived first (event set), VOICE_STATE_UPDATE triggers dispatch."""
        player = _make_player()
        # Simulate VOICE_SERVER_UPDATE already received before VOICE_STATE_UPDATE
        player._voice_state = {
            "event": {"token": "fresh_token", "endpoint": "us-east1.discord.media:443"}
        }
        player._guild.get_channel = MagicMock(return_value=MagicMock())

        voice_state_data = {
            "session_id": "new_discord_session",
            "channel_id": "987654321",
            "user_id": "111",
        }

        self._run(player.on_voice_state_update(voice_state_data))

        player._node.send.assert_called_once()
        call_args = player._node.send.call_args
        sent_data = call_args.kwargs.get("data") or call_args.args[2]
        self.assertEqual(sent_data["voice"]["token"], "fresh_token")
        self.assertEqual(sent_data["voice"]["sessionId"], "new_discord_session")

    def test_on_voice_state_update_no_dispatch_when_event_absent(self):
        """VOICE_STATE_UPDATE does NOT dispatch when event is not yet in _voice_state."""
        player = _make_player()
        player._voice_state = {}
        player._guild.get_channel = MagicMock(return_value=MagicMock())

        voice_state_data = {
            "session_id": "new_discord_session",
            "channel_id": "987654321",
            "user_id": "111",
        }

        self._run(player.on_voice_state_update(voice_state_data))

        player._node.send.assert_not_called()

    def test_on_voice_state_update_teardown_on_channel_leave(self):
        player = _make_player()
        player._voice_state = {"sessionId": "old_session", "event": {"token": "t", "endpoint": "e"}}
        player.teardown = AsyncMock()

        voice_state_data = {
            "session_id": "old_session",
            "channel_id": None,
            "user_id": "111",
            "guild_id": str(player._guild.id),
        }

        self._run(player.on_voice_state_update(voice_state_data))

        player.teardown.assert_called_once()
        self.assertEqual(player._voice_state, {})


if __name__ == "__main__":
    unittest.main()
