"""Saved playlist listings must not expose private URLs to public channels."""
import unittest
from unittest.mock import AsyncMock, MagicMock

import discord

from bot.cogs.playlists import Playlists


class PlaylistPrivacyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ctx = MagicMock()
        self.ctx.interaction = None
        self.ctx.author.send = AsyncMock()
        self.ctx.send = AsyncMock()

    async def test_private_prefix_reply_uses_dm_not_channel(self):
        await Playlists._send(self.ctx, 'Private playlist URLs', private=True)
        self.ctx.author.send.assert_awaited_once()
        self.ctx.send.assert_not_awaited()

    async def test_nonprivate_prefix_reply_stays_in_channel(self):
        await Playlists._send(self.ctx, 'Music queued')
        self.ctx.send.assert_awaited_once()
        self.ctx.author.send.assert_not_awaited()

    async def test_denied_dm_only_reports_generic_error(self):
        response = MagicMock()
        response.status = 403
        response.reason = 'Forbidden'
        self.ctx.author.send.side_effect = discord.Forbidden(
            response, 'Cannot message user',
        )
        await Playlists._send(self.ctx, 'Secret playlist URLs', private=True)
        self.ctx.send.assert_awaited_once()
        msg = self.ctx.send.call_args.args[0]
        self.assertIn('Could not send', msg)
        self.assertNotIn('Secret playlist URLs', msg)

    async def test_slash_private_reply_is_ephemeral(self):
        self.ctx.interaction = MagicMock()
        await Playlists._send(self.ctx, 'Private list', private=True)
        self.ctx.send.assert_awaited_once()
        self.assertTrue(self.ctx.send.call_args.kwargs['ephemeral'])
        self.ctx.author.send.assert_not_awaited()
