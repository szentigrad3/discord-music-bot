from __future__ import annotations

import asyncio
import os

import discord
import wavelink
from discord.ext import commands
from dotenv import load_dotenv

from bot.db import get_guild_settings, init_db

load_dotenv()


async def _get_prefix(bot: commands.Bot, message: discord.Message) -> str:
    if not message.guild:
        return '!'
    try:
        settings = await get_guild_settings(str(message.guild.id))
        return settings.get('prefix', '!')
    except Exception:
        return '!'


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.voice_states = True

    bot = commands.Bot(
        command_prefix=_get_prefix,
        intents=intents,
        help_command=None,
    )
    bot.queues: dict = {}
    return bot


bot = create_bot()


@bot.event
async def on_ready() -> None:
    print(f'✅ Logged in as {bot.user}')
    print(f'   Serving {len(bot.guilds)} guild(s)')
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name='🎵 Music | /play',
        )
    )
    try:
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} application (/) commands.')
    except Exception as e:
        print(f'Failed to sync commands: {e}')


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload) -> None:
    print(f'✅ Lavalink node connected: {payload.node.identifier} (resumed={payload.resumed})')


@bot.event
async def on_wavelink_track_end(payload: wavelink.TrackEndEventPayload) -> None:
    wl_player = payload.player
    music_player = getattr(wl_player, '_music_player', None)
    if music_player is None:
        return
    # Only advance the queue for "normal" end reasons (finished, loadFailed, etc.)
    # Reason 'replaced' means a new track was explicitly started, so skip
    if payload.reason == 'replaced':
        return
    await music_player._on_track_end()


@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
) -> None:
    guild = member.guild
    music_player = bot.queues.get(str(guild.id))
    if not music_player:
        return

    wl_player = music_player._wl_player
    if not wl_player or not wl_player.connected:
        return

    bot_channel = wl_player.channel
    if not bot_channel:
        return

    non_bots = [m for m in bot_channel.members if not m.bot]
    if non_bots:
        return

    await asyncio.sleep(5)

    # Re-check after the delay
    if not wl_player.connected:
        return
    bot_channel = wl_player.channel
    if not bot_channel:
        return
    non_bots = [m for m in bot_channel.members if not m.bot]
    if non_bots:
        return

    await music_player.stop()
    await wl_player.disconnect()
    bot.queues.pop(str(guild.id), None)
    print(f'[voiceStateUpdate] Auto-left empty channel in guild {guild.id}')


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    print(f'[on_command_error] {error}')
    try:
        await ctx.reply('❌ An error occurred while executing that command.')
    except Exception:
        pass


async def main() -> None:
    await init_db()

    async with bot:
        await bot.load_extension('bot.cogs.music')
        await bot.load_extension('bot.cogs.utility')

        token = os.getenv('DISCORD_TOKEN')
        if not token:
            raise RuntimeError('DISCORD_TOKEN environment variable is not set.')

        lavalink_host = os.getenv('LAVALINK_HOST', 'lavalink')
        lavalink_port = os.getenv('LAVALINK_PORT', '2333')
        lavalink_password = os.getenv('LAVALINK_PASSWORD', 'youshallnotpass')

        node = wavelink.Node(
            uri=f'http://{lavalink_host}:{lavalink_port}',
            password=lavalink_password,
        )
        await wavelink.Pool.connect(nodes=[node], client=bot, cache_capacity=100)

        await bot.start(token)


if __name__ == '__main__':
    asyncio.run(main())
