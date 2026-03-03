from __future__ import annotations

import asyncio
import socket
import threading
from pathlib import Path

import discord
import wavelink
from discord.ext import commands

from bot.db import get_guild_settings, init_db
from bot.logger import get_logger, setup_logging
from bot.settings import settings

logger = get_logger(__name__)


async def _get_prefix(bot: commands.Bot, message: discord.Message) -> str:
    if not message.guild:
        return '!'
    try:
        guild_settings = await get_guild_settings(str(message.guild.id))
        return guild_settings.get('prefix', '!')
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
    logger.info('Logged in as %s', bot.user)
    logger.info('Serving %d guild(s)', len(bot.guilds))
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name='🎵 Music | /play',
        )
    )
    try:
        synced = await bot.tree.sync()
        logger.info('Synced %d application (/) commands.', len(synced))
    except Exception as e:
        logger.error('Failed to sync commands: %s', e)


@bot.event
async def on_wavelink_node_ready(payload: wavelink.NodeReadyEventPayload) -> None:
    logger.info('Lavalink node connected: %s (resumed=%s)', payload.node.identifier, payload.resumed)


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
    logger.info('[voiceStateUpdate] Auto-left empty channel in guild %s', guild.id)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error('[on_command_error] %s', error)
    try:
        await ctx.reply('❌ An error occurred while executing that command.')
    except Exception:
        pass


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


async def _launch_lavalink() -> asyncio.subprocess.Process | None:
    jar_path = Path(__file__).parent.parent / 'lavalink' / 'Lavalink.jar'
    if not jar_path.exists():
        logger.warning('lavalink/Lavalink.jar not found, skipping Lavalink auto-start')
        return None
    logger.info('Starting Lavalink…')
    log_path = jar_path.parent / 'lavalink.log'
    log_file = open(log_path, 'a', encoding='utf-8')  # noqa: WPS515
    try:
        proc = await asyncio.create_subprocess_exec(
            'java', '-jar', str(jar_path),
            cwd=str(jar_path.parent),
            stdout=log_file,
            stderr=log_file,
        )
    except FileNotFoundError:
        logger.warning('java not found, skipping Lavalink auto-start')
        return None
    finally:
        log_file.close()
    return proc


async def _wait_for_lavalink(timeout: int = 60) -> bool:
    host = settings.lavalink_host
    port = settings.lavalink_port
    logger.info('Waiting for Lavalink at %s:%d…', host, port)
    for _ in range(timeout):
        if _is_port_open(host, port):
            logger.info('Lavalink is ready')
            return True
        await asyncio.sleep(1)
    logger.warning('Lavalink at %s:%d did not become ready within %d seconds', host, port, timeout)
    return False


def _start_dashboard() -> None:
    if not settings.session_secret:
        logger.warning('Dashboard not started: session_secret is not set in settings.json')
        return
    from bot.dashboard.app import app as flask_app
    port = settings.dashboard_port
    logger.info('Dashboard running at http://localhost:%d', port)
    try:
        flask_app.run(host='0.0.0.0', port=port)
    except Exception as exc:
        logger.error('[dashboard] Failed to start: %s', exc)


async def main() -> None:
    setup_logging(level=settings.log_level)
    await init_db()

    lavalink_proc = await _launch_lavalink()
    if not await _wait_for_lavalink():
        if lavalink_proc is not None:
            lavalink_proc.terminate()
            try:
                await asyncio.wait_for(lavalink_proc.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                lavalink_proc.kill()
            raise RuntimeError(
                f'Lavalink did not become ready at '
                f'{settings.lavalink_host}:{settings.lavalink_port}'
            )
        logger.warning(
            'Lavalink is not yet reachable at %s:%d — proceeding anyway; '
            'wavelink will retry the connection automatically.',
            settings.lavalink_host,
            settings.lavalink_port,
        )

    dashboard_thread = threading.Thread(target=_start_dashboard, daemon=True)
    dashboard_thread.start()

    try:
        async with bot:
            cogs_dir = Path(__file__).parent / 'cogs'
            for cog_file in sorted(cogs_dir.glob('*.py')):
                if cog_file.stem == '__init__':
                    continue
                try:
                    await bot.load_extension(f'bot.cogs.{cog_file.stem}')
                except Exception as e:
                    logger.warning('Failed to load cog %s: %s', cog_file.stem, e)

            if not settings.token:
                raise RuntimeError('token is not set in settings.json')

            node = wavelink.Node(
                uri=f'http://{settings.lavalink_host}:{settings.lavalink_port}',
                password=settings.lavalink_password,
            )
            await wavelink.Pool.connect(nodes=[node], client=bot, cache_capacity=100)

            await bot.start(settings.token)
    finally:
        if lavalink_proc is not None:
            lavalink_proc.terminate()
            try:
                await asyncio.wait_for(lavalink_proc.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                lavalink_proc.kill()


if __name__ == '__main__':
    asyncio.run(main())
