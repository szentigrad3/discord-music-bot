"""Private, guild-scoped saved playlists with prefix and slash commands.

Track URLs are saved rather than Lavalink encoded IDs so playlists can be
re-resolved after restarting the node or updating its source plugins.
"""
from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

from bot.db import (
    MAX_SAVED_TRACKS,
    delete_saved_playlist,
    get_saved_playlist,
    list_saved_playlists,
    save_playlist,
)
from bot.logger import get_logger
from bot.music.player import QueueFullError
from bot.music.queue import get_or_create_player, resolve_tracks

logger = get_logger(__name__)


async def resolve_saved_tracks(urls: list[str], requester: str) -> list:
    """Resolve a saved URL snapshot in order, with at most 3 active requests."""
    limit = asyncio.Semaphore(3)

    async def resolve_one(url: str) -> list:
        async with limit:
            try:
                tracks = await resolve_tracks(url, requester)
                # One saved entry represents exactly one original track.
                return tracks[:1]
            except Exception as exc:
                logger.warning('Cannot resolve saved playlist entry: %s',
                               type(exc).__name__)
                return []

    groups = await asyncio.gather(*(resolve_one(url) for url in urls))
    return [track for group in groups for track in group]


class Playlists(commands.Cog):
    """Save and replay playlists that belong to a user in one server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @staticmethod
    async def _send(ctx: commands.Context, message: str) -> None:
        await ctx.send(message, ephemeral=ctx.interaction is not None)

    @commands.hybrid_group(
        name='playlist', description='Manage your saved music playlists',
        invoke_without_command=True,
    )
    async def playlist(self, ctx: commands.Context) -> None:
        await self._send(ctx, 'Commands: playlist save, list, load, delete.')

    @playlist.command(name='save', description='Save currently playing and queued tracks')
    async def save(self, ctx: commands.Context, *, name: str) -> None:
        if ctx.guild is None:
            return await self._send(ctx, '❌ Saved playlists require a server.')
        player = self.bot.queues.get(str(ctx.guild.id))
        if player is None or (not player.current and not player.tracks):
            return await self._send(ctx, '❌ There is no music to save.')
        snapshot = await player.snapshot_tracks()
        urls = [track.url for track in snapshot if track.url][:MAX_SAVED_TRACKS]
        try:
            await save_playlist(str(ctx.guild.id), str(ctx.author.id), name, urls)
        except ValueError as exc:
            return await self._send(ctx, f'❌ {exc}')
        await self._send(
            ctx, f'✅ Saved **{name}** ({len(urls)} tracks, max {MAX_SAVED_TRACKS}).'
        )

    @playlist.command(name='list', description='List your saved playlists in this server')
    async def list_(self, ctx: commands.Context) -> None:
        if ctx.guild is None:
            return await self._send(ctx, '❌ Saved playlists require a server.')
        items = await list_saved_playlists(str(ctx.guild.id), str(ctx.author.id))
        if not items:
            return await self._send(ctx, 'You have no saved playlists in this server.')
        lines = [f'• **{name}** — {count} tracks' for name, count in items]
        await self._send(ctx, '🎶 Your saved playlists:\n' + '\n'.join(lines))

    @playlist.command(name='load', description='Queue a previously saved playlist')
    async def load(self, ctx: commands.Context, *, name: str) -> None:
        if ctx.guild is None:
            return await self._send(ctx, '❌ Saved playlists require a server.')
        try:
            urls = await get_saved_playlist(str(ctx.guild.id), str(ctx.author.id), name)
        except ValueError as exc:
            return await self._send(ctx, f'❌ {exc}')
        if urls is None:
            return await self._send(ctx, '❌ No saved playlist with that name.')

        member = ctx.author
        voice_channel = getattr(getattr(member, 'voice', None), 'channel', None)
        if voice_channel is None:
            return await self._send(ctx, '❌ Join a voice channel before loading music.')
        bot_member = ctx.guild.me
        permission = voice_channel.permissions_for(bot_member)
        if not permission.connect or not permission.speak:
            return await self._send(ctx, '❌ I need Connect and Speak permissions.')
        if ctx.interaction is not None:
            await ctx.defer(ephemeral=True)

        tracks = await resolve_saved_tracks(urls, str(member))
        if not tracks:
            return await self._send(ctx, '❌ No playable entries remain in this playlist.')
        try:
            player = await get_or_create_player(
                ctx.guild, voice_channel, ctx.channel, self.bot
            )
            await player.enqueue_many(tracks)
        except QueueFullError as exc:
            return await self._send(ctx, f'❌ {exc}')
        except Exception:
            logger.exception('Failed to load saved playlist')
            return await self._send(ctx, '❌ Unable to start the playlist right now.')
        skipped = len(urls) - len(tracks)
        suffix = f' ({skipped} unavailable)' if skipped else ''
        await self._send(ctx, f'✅ Queued **{len(tracks)}** tracks from **{name}**{suffix}.')

    @playlist.command(name='delete', description='Delete one of your saved playlists')
    async def delete(self, ctx: commands.Context, *, name: str) -> None:
        if ctx.guild is None:
            return await self._send(ctx, '❌ Saved playlists require a server.')
        try:
            deleted = await delete_saved_playlist(
                str(ctx.guild.id), str(ctx.author.id), name
            )
        except ValueError as exc:
            return await self._send(ctx, f'❌ {exc}')
        await self._send(ctx, f'🗑️ Deleted **{name}**.' if deleted
                         else '❌ No saved playlist with that name.')


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Playlists(bot))
