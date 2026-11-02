"""Local Lavalink REST integration: actual sockets, HTTP, auth and JSON.

The server binds only to 127.0.0.1 and is created per test. No Discord
credentials, Lavalink process or public network are required.
"""
import aiohttp
import unittest
from aiohttp import web

from bot.voicelink.pool import Node
from bot.voicelink.enums import RequestMethod
from bot.voicelink.exceptions import NodeException


class LavalinkHTTPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []

        async def info(request):
            self.requests.append(('info', request.headers.get('Authorization')))
            if request.headers.get('Authorization') != 'local-test-secret':
                raise web.HTTPUnauthorized()
            return web.json_response({'version': {'semver': '4.0.0'},
                                      'sourceManagers': ['youtube']})

        async def player(request):
            self.requests.append(('player', request.headers.get('Authorization')))
            if request.headers.get('Authorization') != 'local-test-secret':
                raise web.HTTPUnauthorized()
            body = await request.json()
            if body.get('encodedTrack') == 'invalid':
                raise web.HTTPBadRequest(text='track unavailable')
            return web.json_response({'encodedTrack': body.get('encodedTrack')})

        app = web.Application()
        app.add_routes([
            web.get('/v4/info', info),
            web.patch('/v4/sessions/s1/players/42', player),
        ])
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await self.site.start()
        port = self.site._server.sockets[0].getsockname()[1]
        self.session = aiohttp.ClientSession()
        self.node = object.__new__(Node)
        self.node._available = True
        self.node._identifier = 'TEST'
        self.node._rest_uri = f'http://127.0.0.1:{port}'
        self.node._password = 'local-test-secret'
        self.node._session = self.session

    async def asyncTearDown(self):
        await self.session.close()
        await self.runner.cleanup()

    async def test_info_endpoint_roundtrip(self):
        result = await self.node.send(RequestMethod.GET, 'info')
        self.assertIn('youtube', result['sourceManagers'])
        self.assertEqual(self.requests, [('info', 'local-test-secret')])

    async def test_player_update_roundtrip(self):
        data = await self.node.send(
            RequestMethod.PATCH, 'sessions/s1/players/42',
            {'encodedTrack': 'abc123'},
        )
        self.assertEqual(data['encodedTrack'], 'abc123')
        self.assertEqual(self.requests, [('player', 'local-test-secret')])

    async def test_http_error_is_reported(self):
        with self.assertRaises(NodeException):
            await self.node.send(
                RequestMethod.PATCH, 'sessions/s1/players/42',
                {'encodedTrack': 'invalid'},
            )

    async def test_bad_authorization_is_rejected(self):
        self.node._password = 'wrong'
        with self.assertRaises(NodeException):
            await self.node.send(RequestMethod.GET, 'info')
        self.assertEqual(self.requests, [('info', 'wrong')])
