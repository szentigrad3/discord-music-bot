"""Regression tests for keeping queue/audio intact across a Lavalink restart."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.voicelink.pool import Node
from bot.voicelink.player import Player
from bot.voicelink.enums import RequestMethod
from bot.voicelink.exceptions import NodeException


def make_recovering_node(*, valid_voice=True, paused=False, with_track=True):
    node = object.__new__(Node)
    node._identifier = 'MAIN'
    node._session_id = 'fresh-session-123'
    node._logger = MagicMock()
    node._resumed = False
    player = MagicMock()
    player.channel = MagicMock()
    player.guild.id = 42
    player._guild.change_voice_state = AsyncMock()
    player._voice_state = ({
        'sessionId': 'discord-voice-session',
        'channelId': '24',
        'event': {'token': 'private-test-token', 'endpoint': 'voice.discord.example'},
    } if valid_voice else {})
    player._voice_ready_event = asyncio.Event()
    player._voice_ready_event.set()
    player._dispatch_voice_update = AsyncMock(return_value=True if valid_voice else False)
    player._last_position = 3200
    player.is_paused = paused
    player.play = AsyncMock()
    player.set_pause = AsyncMock()
    if with_track:
        player.current = MagicMock()
        player.current.length = 10000
    else:
        player.current = None
    player.teardown = AsyncMock()
    node._players = {42: player}
    return node, player


class RestartRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_reuses_cached_discord_voice_and_replays_current_track(self):
        node, player = make_recovering_node()
        await node.reconnect()
        player._dispatch_voice_update.assert_awaited_once_with()
        player._guild.change_voice_state.assert_not_awaited()
        player.play.assert_awaited_once_with(track=player.current, start=3200)
        player.teardown.assert_not_awaited()
        self.assertEqual(len(node.players), 1)

    async def test_no_track_does_not_start_phantom_playback(self):
        node, player = make_recovering_node(with_track=False)
        await node.reconnect()
        player._dispatch_voice_update.assert_awaited_once()
        player.play.assert_not_awaited()
        player.teardown.assert_not_awaited()

    async def test_paused_track_stays_paused_after_replay(self):
        node, player = make_recovering_node(paused=True)
        await node.reconnect()
        player.play.assert_awaited_once()
        player.set_pause.assert_awaited_once_with(True)

    async def test_position_never_exceeds_track_length(self):
        node, player = make_recovering_node()
        player._last_position = 999999
        await node.reconnect()
        self.assertEqual(player.play.await_args.kwargs['start'], 10000)

    async def test_recovery_failure_keeps_voice_and_queue(self):
        node, player = make_recovering_node()
        player.play.side_effect = RuntimeError('temporary Lavalink failure')
        await node.reconnect()
        player.teardown.assert_not_awaited()
        self.assertIs(node.players[42], player)

    async def test_missing_cached_voice_requests_fresh_handshake(self):
        node, player = make_recovering_node(valid_voice=False)
        async def new_discord_events(**kwargs):
            player._voice_ready_event.set()
        player._guild.change_voice_state.side_effect = new_discord_events
        await node.reconnect()
        player._dispatch_voice_update.assert_not_awaited()
        self.assertEqual(player._guild.change_voice_state.await_count, 2)
        self.assertIsNone(player._guild.change_voice_state.await_args_list[0].kwargs['channel'])
        self.assertIs(player._guild.change_voice_state.await_args_list[1].kwargs['channel'],
                      player.channel)
        player.play.assert_awaited_once()
        self.assertFalse(player._recovering_voice)
        player.teardown.assert_not_awaited()

    async def test_fresh_handshake_timeout_preserves_player(self):
        node, player = make_recovering_node(valid_voice=False)
        with patch('bot.voicelink.pool.asyncio.wait_for', side_effect=asyncio.TimeoutError):
            await node.reconnect()
        player.play.assert_not_awaited()
        player.teardown.assert_not_awaited()
        self.assertIs(node.players[42], player)

    async def test_new_node_session_is_required_before_recovery(self):
        node, player = make_recovering_node()
        node._session_id = None
        from bot.voicelink.exceptions import NodeNotAvailable
        with self.assertRaises(NodeNotAvailable):
            await node.reconnect()
        player._dispatch_voice_update.assert_not_awaited()

    async def test_low_level_player_confirms_successful_voice_handshake(self):
        player = object.__new__(Player)
        player._node = MagicMock()
        player._node._session_id = 'new-lavalink-session'
        player._guild = MagicMock()
        player._guild.id = 42
        player._logger = MagicMock()
        player._voice_ready_event = asyncio.Event()
        player._voice_state = {
            'sessionId': 'discord-session',
            'channelId': '42',
            'event': {'token': 'test-token', 'endpoint': 'wss://voice.discord.example'},
        }
        player.send = AsyncMock(return_value={})
        ok = await player._dispatch_voice_update()
        self.assertTrue(ok)
        self.assertTrue(player._voice_ready_event.is_set())
        payload = player.send.await_args.kwargs
        self.assertEqual(payload['data']['voice']['endpoint'], 'voice.discord.example')
        self.assertEqual(payload['method'], RequestMethod.PATCH)

    async def test_failed_voice_handshake_does_not_report_success(self):
        player = object.__new__(Player)
        player._node = MagicMock()
        player._node._session_id = 'new-lavalink-session'
        player._guild = MagicMock()
        player._guild.id = 42
        player._logger = MagicMock()
        player._voice_ready_event = asyncio.Event()
        player._voice_state = {
            'sessionId': 'discord-session',
            'channelId': '42',
            'event': {'token': 'test-token', 'endpoint': 'voice.discord.example'},
        }
        player.send = AsyncMock(side_effect=NodeException('rejected'))
        self.assertFalse(await player._dispatch_voice_update())
        self.assertFalse(player._voice_ready_event.is_set())

    async def test_incomplete_voice_cache_never_sends(self):
        player = object.__new__(Player)
        player._node = MagicMock()
        player._node._session_id = 'new-lavalink-session'
        player._voice_state = {'channelId': '42'}
        player.send = AsyncMock()
        self.assertFalse(await player._dispatch_voice_update())
        player.send.assert_not_awaited()

    async def test_connect_waits_for_new_ready_session_before_recovery(self):
        node, player = make_recovering_node()
        node._available = False
        node._session_id = 'obsolete'
        node._session = MagicMock()
        node._session.ws_connect = AsyncMock(return_value=MagicMock())
        node._bot = MagicMock()
        node._info = None
        node._websocket_uri = 'ws://lavalink:2333/v4/websocket'
        node._headers = {}
        node._heartbeat = 30
        node.send = AsyncMock(return_value={})
        node.reconnect = AsyncMock()

        def on_listener_created(coro):
            coro.close()
            self.assertIsNone(node._session_id)
            node._session_id = 'new-session'
            node._ready_event.set()
            return MagicMock()

        node._bot.loop.create_task = MagicMock(side_effect=on_listener_created)
        with patch('bot.voicelink.pool.NodeInfo', return_value=MagicMock()):
            await node.connect()
        self.assertEqual(node._session_id, 'new-session')
        node.reconnect.assert_awaited_once()

    async def test_no_new_ready_session_never_restores_audio(self):
        node, player = make_recovering_node()
        node._available = False
        node._session = MagicMock()
        node._session.ws_connect = AsyncMock(return_value=MagicMock())
        node._session.ws_connect.return_value.close = AsyncMock()
        node._bot = MagicMock()
        node._bot.loop.create_task = MagicMock()
        node._websocket_uri = 'ws://lavalink:2333/v4/websocket'
        node._headers = {}
        node._heartbeat = 30
        node.send = AsyncMock(return_value={})
        node.reconnect = AsyncMock()
        with patch('bot.voicelink.pool.NodeInfo', return_value=MagicMock()):
            with patch('bot.voicelink.pool.asyncio.wait_for', side_effect=asyncio.TimeoutError):
                from bot.voicelink.exceptions import NodeConnectionFailure
                with self.assertRaises(NodeConnectionFailure):
                    await node.connect()
        node.reconnect.assert_not_awaited()
        self.assertFalse(node._available)
        node._session.ws_connect.return_value.close.assert_awaited_once()

    async def test_intentional_voice_refresh_does_not_destroy_music_queue(self):
        player = object.__new__(Player)
        player._recovering_voice = True
        player._voice_state = {'event': {'token': 'old-token'}}
        player.teardown = AsyncMock()
        await player.on_voice_state_update({'channel_id': None, 'session_id': None})
        player.teardown.assert_not_awaited()
        self.assertEqual(player._voice_state, {})

    async def test_real_voice_disconnect_still_cleans_up(self):
        player = object.__new__(Player)
        player._recovering_voice = False
        player._voice_state = {}
        player.teardown = AsyncMock()
        await player.on_voice_state_update({'channel_id': None, 'session_id': None})
        player.teardown.assert_awaited_once()
