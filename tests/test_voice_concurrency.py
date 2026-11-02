"""Concurrency tests for voice joins and idle-channel auto-leave."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.music.queue import VoiceChannelMismatchError, get_or_create_player
from bot.voice_idle import EmptyVoiceManager


def create_voice_fixture():
    guild = MagicMock()
    guild.id = 42
    channel = MagicMock()
    channel.id = 91
    channel.members = [MagicMock(bot=True)]
    voice = MagicMock()
    voice.is_connected = True
    voice.channel = channel
    voice.stop = AsyncMock()
    voice.disconnect = AsyncMock()
    bot = MagicMock()
    bot.queues = {}
    player = MagicMock()
    player.bot = bot
    player._vl_player = voice
    player.stop = AsyncMock()
    return guild, channel, voice, bot, player


class ConcurrentJoinTests(unittest.IsolatedAsyncioTestCase):
    async def test_simultaneous_joins_share_one_player(self):
        guild, channel, voice, bot, unused = create_voice_fixture()
        ready = asyncio.Event()
        release = asyncio.Event()

        async def connect(**kwargs):
            ready.set()
            await release.wait()
            return voice

        channel.connect = AsyncMock(side_effect=connect)
        with patch('bot.music.queue.VoicelinkPlayer'):
            first = asyncio.create_task(
                get_or_create_player(guild, channel, None, bot))
            await asyncio.wait_for(ready.wait(), timeout=2)
            second = asyncio.create_task(
                get_or_create_player(guild, channel, None, bot))
            release.set()
            p1, p2 = await asyncio.gather(first, second)
        self.assertIs(p1, p2)
        self.assertEqual(channel.connect.await_count, 1)
        self.assertIs(bot.queues['42'], p1)

    async def test_another_channel_cannot_hijack_existing_player(self):
        guild, channel, voice, bot, player = create_voice_fixture()
        original_channel = channel
        other_channel = MagicMock()
        other_channel.id = channel.id + 1
        bot.queues[str(guild.id)] = player
        with self.assertRaisesRegex(VoiceChannelMismatchError, 'another voice channel'):
            await get_or_create_player(guild, other_channel, None, bot)
        voice.move_to.assert_not_called()
        other_channel.connect.assert_not_called()
        self.assertIs(bot.queues[str(guild.id)], player)
        self.assertIs(voice.channel, original_channel)

    async def test_existing_player_same_channel_can_enqueue(self):
        guild, channel, voice, bot, player = create_voice_fixture()
        bot.queues[str(guild.id)] = player
        existing = await get_or_create_player(guild, channel, None, bot)
        self.assertIs(existing, player)
        channel.connect.assert_not_called()
        voice.move_to.assert_not_called()

    async def test_failed_connect_does_not_lock_future_joins(self):
        guild, channel, voice, bot, unused = create_voice_fixture()
        channel.connect = AsyncMock(side_effect=[RuntimeError('refused'), voice])
        with patch('bot.music.queue.VoicelinkPlayer'):
            with self.assertRaises(RuntimeError):
                await get_or_create_player(guild, channel, None, bot)
            player = await get_or_create_player(guild, channel, None, bot)
        self.assertIs(bot.queues['42'], player)
        self.assertEqual(channel.connect.await_count, 2)


class EmptyVoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_empty_channel_leaves_once(self):
        _, channel, voice, bot, player = create_voice_fixture()
        bot.queues['42'] = player
        manager = EmptyVoiceManager(delay=0.01)
        manager.update('42', player, bot.queues.get)
        manager.update('42', player, bot.queues.get)
        await asyncio.sleep(0.04)
        player.stop.assert_awaited_once()
        voice.disconnect.assert_awaited_once()
        self.assertNotIn('42', bot.queues)

    async def test_user_return_cancels_pending_leave(self):
        _, channel, voice, bot, player = create_voice_fixture()
        bot.queues['42'] = player
        manager = EmptyVoiceManager(delay=0.03)
        manager.update('42', player, bot.queues.get)
        channel.members.append(MagicMock(bot=False))
        manager.update('42', player, bot.queues.get)
        await asyncio.sleep(0.06)
        player.stop.assert_not_awaited()
        voice.disconnect.assert_not_awaited()

    async def test_replaced_player_is_not_disconnected(self):
        _, channel, voice, bot, player = create_voice_fixture()
        bot.queues['42'] = player
        manager = EmptyVoiceManager(delay=0.01)
        manager.update('42', player, bot.queues.get)
        bot.queues['42'] = MagicMock()
        await asyncio.sleep(0.04)
        player.stop.assert_not_awaited()
        voice.disconnect.assert_not_awaited()

    async def test_new_listener_at_timeout_prevents_leave(self):
        _, channel, voice, bot, player = create_voice_fixture()
        bot.queues['42'] = player
        manager = EmptyVoiceManager(delay=0.01)
        manager.update('42', player, bot.queues.get)
        channel.members.append(MagicMock(bot=False))
        await asyncio.sleep(0.04)
        player.stop.assert_not_awaited()
        voice.disconnect.assert_not_awaited()
