"""Search result controls should not allow users outside the bot's voice room."""
import unittest
from unittest.mock import AsyncMock, MagicMock

import discord

from bot.views.search import SearchSelect


class SearchVoiceAccessTests(unittest.IsolatedAsyncioTestCase):
    def make_select(self):
        track = MagicMock()
        track.title = 'Sample'
        track.duration = '2:30'
        track.url = 'https://example.com/'
        track.thumbnail = None
        player = MagicMock()
        player._vl_player.channel.id = 100
        player.enqueue = AsyncMock()
        select = SearchSelect([track], player)
        return select, player

    async def test_rejects_user_outside_voice_channel(self):
        select, player = self.make_select()
        interaction = MagicMock()
        interaction.user = MagicMock()
        interaction.response.send_message = AsyncMock()
        await select.callback(interaction)
        player.enqueue.assert_not_awaited()
        interaction.response.send_message.assert_awaited_once()

    async def test_rejects_member_in_different_channel(self):
        select, player = self.make_select()
        member = MagicMock(spec=discord.Member)
        member.voice.channel.id = 200
        interaction = MagicMock(user=member)
        interaction.user = member
        interaction.response.send_message = AsyncMock()
        await select.callback(interaction)
        player.enqueue.assert_not_awaited()

    async def test_same_voice_channel_queues_result(self):
        select, player = self.make_select()
        member = MagicMock(spec=discord.Member)
        member.voice.channel.id = 100
        interaction = MagicMock()
        interaction.user = member
        interaction.response.edit_message = AsyncMock()
        select._values = ['0']
        await select.callback(interaction)
        player.enqueue.assert_awaited_once()
        interaction.response.edit_message.assert_awaited_once()
