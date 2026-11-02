"""Regression tests for Lavalink node-owned HTTP session cleanup."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.voicelink.pool import NodePool


def fake_node(*, owned=True, fail=False):
    node = MagicMock()
    node._owns_session = owned
    node._session.closed = False
    node._session.close = AsyncMock()
    node.disconnect = AsyncMock(side_effect=RuntimeError('disconnect failed') if fail else None)
    return node


class NodePoolShutdownTests(unittest.IsolatedAsyncioTestCase):
    async def test_closes_owned_session_after_disconnect(self):
        node = fake_node()
        with patch.object(NodePool, '_nodes', {'MAIN': node}):
            await NodePool.close_all()
            self.assertEqual(NodePool._nodes, {})
        node.disconnect.assert_awaited_once_with(remove_from_pool=True)
        node._session.close.assert_awaited_once()

    async def test_does_not_close_caller_owned_session(self):
        node = fake_node(owned=False)
        with patch.object(NodePool, '_nodes', {'EXTERNAL': node}):
            await NodePool.close_all()
            self.assertEqual(NodePool._nodes, {})
        node._session.close.assert_not_awaited()

    async def test_session_closes_even_if_disconnect_fails(self):
        good = fake_node()
        bad = fake_node(fail=True)
        with patch.object(NodePool, '_nodes', {'BAD': bad, 'GOOD': good}), \
             patch('bot.voicelink.pool.logging.getLogger'):
            await NodePool.close_all()
            self.assertEqual(NodePool._nodes, {})
        bad._session.close.assert_awaited_once()
        good._session.close.assert_awaited_once()

    async def test_no_nodes_is_safe(self):
        with patch.object(NodePool, '_nodes', {}):
            await NodePool.close_all()
            self.assertEqual(NodePool._nodes, {})

    async def test_closed_session_is_not_closed_again(self):
        node = fake_node()
        node._session.closed = True
        with patch.object(NodePool, '_nodes', {'MAIN': node}):
            await NodePool.close_all()
        node._session.close.assert_not_awaited()
