from __future__ import annotations

import asyncio
import os
import threading
import zipfile
from pathlib import Path

import aiohttp
import discord
from bot.voicelink import NodePool
from discord.ext import commands

from bot.command_sync import CommandTreeSync
from bot.lavalink_bootstrap import LavalinkBootstrap
from bot.db import get_guild_settings, init_db
from bot.logger import get_logger, setup_logging
from bot.settings import settings
from bot.voice_idle import EmptyVoiceManager

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
_command_sync = CommandTreeSync()
_node_bootstrap = LavalinkBootstrap()
_empty_voice = EmptyVoiceManager()


async def _connect_main_node() -> None:
    await NodePool.create_node(
        bot=bot,
        host=settings.lavalink_host,
        port=settings.lavalink_port,
        password=settings.lavalink_password,
        identifier='MAIN',
    )


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
    # Discord can dispatch on_ready again after reconnecting. Sync only once
    # per process, retrying on a later ready event if the first sync fails.
    await _command_sync.sync(bot.tree, logger)

    # Do not block on_ready during a transient Lavalink outage. The
    # bootstrapper retries initial creation; Voicelink owns reconnects after
    # a node has been registered successfully.
    _node_bootstrap.ensure(
        _connect_main_node, lambda: 'MAIN' in NodePool._nodes, logger,
    )


@bot.event
async def on_voicelink_track_end(player, track, reason: str) -> None:
    music_player = getattr(player, '_music_player', None)
    if music_player is None:
        return
    # Manual STOPPED transitions are performed by skip/back/skipto under
    # the queue lock. Acting on the subsequent node event would advance twice.
    if str(reason).lower() in ('replaced', 'stopped'):
        return
    await music_player._on_track_end(reason=reason, ended_track=track)


@bot.event
async def on_voicelink_track_stuck(player, track, threshold: float) -> None:
    music_player = getattr(player, '_music_player', None)
    if music_player is not None:
        logger.warning('Lavalink track stuck after %s ms', threshold)
        await music_player._on_track_end(reason='loadFailed', ended_track=track)


@bot.event
async def on_voicelink_track_exception(player, track, exception: dict) -> None:
    music_player = getattr(player, '_music_player', None)
    if music_player is not None:
        logger.warning('Lavalink track exception: %s',
                       exception.get('severity', 'unknown') if isinstance(exception, dict) else 'unknown')
        await music_player._on_track_end(reason='loadFailed', ended_track=track)


@bot.event
async def on_voice_state_update(
    member: discord.Member,
    before: discord.VoiceState,
    after: discord.VoiceState,
) -> None:
    guild_id = str(member.guild.id)
    music_player = bot.queues.get(guild_id)
    if music_player is None:
        _empty_voice.cancel(guild_id)
        return
    _empty_voice.update(guild_id, music_player, bot.queues.get)


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception) -> None:
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error('[on_command_error] %s', error)
    try:
        await ctx.reply('❌ An error occurred while executing that command.')
    except Exception:
        pass


def _clean_corrupted_plugins(plugins_dir: Path) -> None:
    """Remove corrupted plugin JAR files so Lavalink can re-download them on startup.

    A corrupted JAR (e.g. from an interrupted download) causes a
    ``ZipException: zip END header not found`` that prevents Lavalink from
    starting.  Removing the bad file lets Lavalink fetch a fresh copy.
    """
    for jar in plugins_dir.glob('*.jar'):
        try:
            with zipfile.ZipFile(jar) as zf:
                if zf.testzip() is not None:
                    raise zipfile.BadZipFile('CRC check failed')
        except (zipfile.BadZipFile, OSError):
            logger.warning('Removing corrupted plugin JAR: %s', jar.name)
            try:
                jar.unlink()
            except OSError as exc:
                logger.warning('Could not remove %s: %s', jar.name, exc)


def _run_lavalink_updater() -> None:
    """Run the Lavalink JAR and plugin updater for non-Docker installations.

    Errors are caught and logged so a transient network failure does not
    prevent the bot from starting.
    """
    try:
        import update_lavalink
        update_lavalink.update_lavalink_jar()
        update_lavalink.update_lavalink_plugins()
    except Exception as exc:
        logger.warning('Lavalink auto-update failed (will use existing version): %s', exc)


async def _launch_lavalink() -> asyncio.subprocess.Process | None:
    jar_path = Path(__file__).parent.parent / 'lavalink' / 'Lavalink.jar'
    if not jar_path.exists():
        logger.warning('lavalink/Lavalink.jar not found, skipping Lavalink auto-start')
        return None
    plugins_dir = jar_path.parent / 'plugins'
    if plugins_dir.exists():
        _clean_corrupted_plugins(plugins_dir)
    logger.info('Starting Lavalink…')
    log_path = jar_path.parent / 'lavalink.log'
    log_file = open(log_path, 'a', encoding='utf-8')  # noqa: WPS515
    # A private local Lavalink config avoids embedding real passwords in
    # tracked application.yml while preserving existing source/plugin tuning.
    env = os.environ.copy()
    local_config = jar_path.parent / 'application.local.yml'
    if local_config.is_file():
        env['SPRING_CONFIG_LOCATION'] = f'file:{local_config}'
    try:
        proc = await asyncio.create_subprocess_exec(
            'java', '--enable-native-access=ALL-UNNAMED', '-jar', str(jar_path),
            cwd=str(jar_path.parent),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=log_file,
            stderr=log_file,
            env=env,
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
    url = f'http://{host}:{port}/version'
    headers = {'Authorization': settings.lavalink_password}
    logger.info('Waiting for Lavalink at %s:%d…', host, port)
    async with aiohttp.ClientSession() as session:
        for _ in range(timeout):
            try:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        logger.info('Lavalink is ready')
                        return True
            except Exception as exc:
                logger.debug('Lavalink not ready yet at %s:%d: %s', host, port, exc)
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

    lavalink_proc = None
    if os.environ.get('BOT_IN_DOCKER', '').lower() != 'true':
        _run_lavalink_updater()
        lavalink_proc = await _launch_lavalink()
    if not await _wait_for_lavalink():
        if lavalink_proc is not None:
            lavalink_proc.terminate()
            raise RuntimeError(
                f'Lavalink did not become ready at '
                f'{settings.lavalink_host}:{settings.lavalink_port}'
            )
        logger.warning(
            'Lavalink is not yet reachable at %s:%d — proceeding anyway; '
            'voicelink will retry the connection automatically.',
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

            await bot.start(settings.token)
    finally:
        await _node_bootstrap.close()
        await NodePool.close_all()
        if lavalink_proc is not None:
            lavalink_proc.terminate()


if __name__ == '__main__':
    asyncio.run(main())
