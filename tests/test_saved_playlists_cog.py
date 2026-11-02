"""Saved playlist URL resolution and command registration tests."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from bot.cogs.playlists import Playlists, resolve_saved_tracks


class SavedPlaylistResolutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_order_and_parallelism(self):
        active = 0
        peak = 0

        async def resolve(url, requester):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep((10 - int(url[-1])) * 0.002)
                return [url]
            finally:
                active -= 1

        urls = [f'https://example.com/t/{n}' for n in range(8)]
        with patch('bot.cogs.playlists.resolve_tracks', side_effect=resolve):
            results = await resolve_saved_tracks(urls, 'requester')
        self.assertEqual(results, urls)
        self.assertGreater(peak, 1)
        self.assertLessEqual(peak, 3)

    async def test_failed_entry_does_not_abort_playlist(self):
        async def resolve(url, requester):
            if 'missing' in url:
                raise RuntimeError('not found')
            return [url]
        urls = ['https://example.com/one', 'https://example.com/missing',
                'https://example.com/three']
        with patch('bot.cogs.playlists.resolve_tracks', side_effect=resolve):
            result = await resolve_saved_tracks(urls, 'someone')
        self.assertEqual(result, [urls[0], urls[2]])

    async def test_one_saved_entry_never_expands_to_multiple_tracks(self):
        with patch('bot.cogs.playlists.resolve_tracks',
                   new=AsyncMock(return_value=['first', 'second'])):
            self.assertEqual(await resolve_saved_tracks(['https://example.com/a'], 'x'),
                             ['first'])


class SavedPlaylistCogTests(unittest.IsolatedAsyncioTestCase):
    async def test_hybrid_subcommands_register(self):
        intents = discord.Intents.default()
        bot = commands.Bot(command_prefix='!', intents=intents)
        async with bot:
            await bot.add_cog(Playlists(bot))
            group = bot.get_command('playlist')
            self.assertIsNotNone(group)
            self.assertEqual({c.name for c in group.commands},
                             {'save', 'list', 'show', 'load', 'add', 'remove', 'rename', 'delete'})
            self.assertIn('playlist', {cmd.name for cmd in bot.tree.get_commands()})
