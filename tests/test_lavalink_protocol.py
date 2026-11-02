"""Offline Lavalink websocket-recovery and REST protocol checks."""
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from bot.voicelink.enums import RequestMethod
from bot.voicelink.exceptions import NodeNotAvailable, NodeException
from bot.voicelink.pool import Node


def make_node():
    node = object.__new__(Node)
    node._available = True
    node._identifier = 'MAIN'
    node._rest_uri = 'http://lavalink:2333'
    node._password = 'local-test-password'
    node._logger = MagicMock()
    node._session = MagicMock()
    return node


class LavalinkProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_websocket_error_triggers_reconnect(self):
        node = make_node()
        message = MagicMock()
        message.type = aiohttp.WSMsgType.ERROR
        node._websocket = MagicMock()
        node._websocket.receive = AsyncMock(return_value=message)

        async def reconnect():
            node._available = True
            return node

        node.connect = AsyncMock(side_effect=reconnect)
        with patch('bot.voicelink.pool.asyncio.sleep', new=AsyncMock()):
            await node._listen()

        node.connect.assert_awaited_once()
        node._logger.error.assert_called_once()

    async def test_rest_requests_have_timeout_and_correct_auth(self):
        node = make_node()
        response = MagicMock()
        response.status = 200
        response.json = AsyncMock(return_value={'status': 'ok'})
        node._session.request.return_value.__aenter__.return_value = response

        result = await node.send(
            RequestMethod.PATCH, 'sessions/session/players/42',
            {'encodedTrack': 'abc'}
        )
        self.assertEqual(result, {'status': 'ok'})
        kwargs = node._session.request.call_args.kwargs
        self.assertEqual(kwargs['url'], 'http://lavalink:2333/v4/sessions/session/players/42')
        self.assertEqual(kwargs['headers']['Authorization'], 'local-test-password')
        self.assertEqual(kwargs['json'], {'encodedTrack': 'abc'})
        self.assertEqual(kwargs['timeout'].total, 20)

    async def test_unavailable_node_refuses_requests(self):
        node = make_node()
        node._available = False
        with self.assertRaises(NodeNotAvailable):
            await node.send(RequestMethod.GET, 'info')
        node._session.request.assert_not_called()

    async def test_rest_failure_is_not_reported_as_success(self):
        node = make_node()
        response = MagicMock()
        response.status = 500
        response.text = AsyncMock(return_value='backend failed')
        node._session.request.return_value.__aenter__.return_value = response
        with self.assertRaises(NodeException):
            await node.send(RequestMethod.PATCH, 'sessions/s/players/g', {})
