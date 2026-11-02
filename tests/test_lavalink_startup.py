"""Lavalink initial connection failures and node-pool availability tests."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.voicelink.pool import Node, NodePool


class NodeStartupTests(unittest.IsolatedAsyncioTestCase):
    def make_node(self):
        node = object.__new__(Node)
        node._available = False
        node._identifier = 'MAIN'
        node._logger = MagicMock()
        node._players = {}
        node._websocket_uri = 'ws://localhost:2333/v4/websocket'
        node._headers = {'Authorization': 'secret'}
        node._heartbeat = 30
        node._bot = MagicMock()

        def capture_task(coroutine):
            # No real event loop task is started in this test. Close the
            # coroutine to avoid unawaited-coroutine warnings on Python 3.14.
            coroutine.close()
            return MagicMock()

        node._bot.loop.create_task = MagicMock(side_effect=capture_task)
        node._session = MagicMock()
        node._session.ws_connect = AsyncMock()
        node._session.ws_connect.return_value.close = AsyncMock()
        node._info = None
        node._task = None
        node.send = AsyncMock()
        return node

    async def test_failed_rest_handshake_closes_socket_without_listener(self):
        node = self.make_node()
        node.send.side_effect = RuntimeError('Lavalink REST unavailable')
        with self.assertRaisesRegex(RuntimeError, 'REST unavailable'):
            await node.connect()
        self.assertFalse(node._available)
        self.assertIsNone(node._websocket)
        node._session.ws_connect.return_value.close.assert_awaited_once()
        node._bot.loop.create_task.assert_not_called()

    async def test_successful_startup_starts_listener_after_handshake(self):
        node = self.make_node()
        node.send.return_value = {}
        with patch('bot.voicelink.pool.NodeInfo', return_value=MagicMock()):
            await node.connect()
        self.assertTrue(node._available)
        self.assertIsNotNone(node._info)
        node._bot.loop.create_task.assert_called_once()

    async def test_create_node_closes_own_session_on_failed_connect(self):
        node = MagicMock()
        node.connect = AsyncMock(side_effect=RuntimeError('bad handshake'))
        node._session.close = AsyncMock()
        with patch.object(NodePool, '_nodes', {}), \
             patch('bot.voicelink.pool.Node', return_value=node):
            with self.assertRaises(RuntimeError):
                await NodePool.create_node(
                    bot=MagicMock(), host='localhost', port=2333,
                    password='test', identifier='MAIN'
                )
            self.assertEqual(NodePool._nodes, {})
        node._session.close.assert_awaited_once()

    async def test_external_session_is_not_closed(self):
        node = MagicMock()
        node.connect = AsyncMock(side_effect=RuntimeError('bad handshake'))
        node._session.close = AsyncMock()
        session = MagicMock()
        with patch.object(NodePool, '_nodes', {}), \
             patch('bot.voicelink.pool.Node', return_value=node):
            with self.assertRaises(RuntimeError):
                await NodePool.create_node(
                    bot=MagicMock(), host='localhost', port=2333,
                    password='test', identifier='MAIN', session=session
                )
        node._session.close.assert_not_awaited()


class NodeSelectionTests(unittest.TestCase):
    def test_disconnected_node_not_selected(self):
        stale = MagicMock()
        stale.is_connected = True
        stale._available = False
        live = MagicMock()
        live.is_connected = True
        live._available = True
        live.players = {}
        with patch.object(NodePool, '_nodes', {'old': stale, 'new': live}):
            self.assertIs(NodePool.get_node(), live)
