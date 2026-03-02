from __future__ import annotations

import os

import discord
from discord import app_commands
from discord.ext import commands

from bot.db import get_guild_settings, update_guild_settings
from bot.i18n import t
from bot.music.player import FILTERS, MusicPlayer, RepeatMode
from bot.music.queue import get_or_create_player, resolve_tracks

PAGE_SIZE = 10


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ------------------------------------------------------------------ helpers

    async def _get_lang(self, guild: discord.Guild) -> str:
        try:
            s = await get_guild_settings(str(guild.id))
            return s.get('language', 'en')
        except Exception:
            return 'en'

    # ================================================================== /play ==

    @app_commands.command(name='play', description='Play a song or playlist from YouTube, SoundCloud, or Spotify')
    @app_commands.describe(query='Song name, URL, or Spotify/YouTube playlist link')
    async def play_slash(self, interaction: discord.Interaction, query: str) -> None:
        await self._play(interaction, query)

    @commands.command(name='play', aliases=['p'])
    async def play_prefix(self, ctx: commands.Context, *, query: str = '') -> None:
        await self._play(ctx, query)

    async def _play(self, ctx, query: str) -> None:
        is_inter = isinstance(ctx, discord.Interaction)

        async def reply(content=None, *, ephemeral=False, **kwargs):
            if is_inter:
                if ctx.response.is_done():
                    return await ctx.followup.send(content, ephemeral=ephemeral, **kwargs)
                return await ctx.response.send_message(content, ephemeral=ephemeral, **kwargs)
            return await ctx.reply(content, **kwargs)

        async def edit_reply(content=None, **kwargs):
            if is_inter:
                return await ctx.edit_original_response(content=content, **kwargs)
            # For prefix commands we just send a follow-up
            return await ctx.reply(content, **kwargs)

        guild = ctx.guild if is_inter else ctx.guild
        member = ctx.user if is_inter else ctx.author
        lang = await self._get_lang(guild)

        if not query:
            return await reply('Please provide a song name or URL.', ephemeral=True)

        voice_channel = getattr(member.voice, 'channel', None) if hasattr(member, 'voice') else None
        if not voice_channel:
            return await reply(t('errors.notInVoice', lang), ephemeral=True)

        bot_member = guild.me
        if not voice_channel.permissions_for(bot_member).connect or \
                not voice_channel.permissions_for(bot_member).speak:
            return await reply(
                'I need **Connect** and **Speak** permissions in your voice channel.',
                ephemeral=True,
            )

        if is_inter:
            await ctx.response.defer()

        settings = await get_guild_settings(str(guild.id))
        text_channel = ctx.channel

        try:
            tracks = await resolve_tracks(query, str(member))
        except Exception as err:
            return await edit_reply(f'❌ {err}')

        if not tracks:
            return await edit_reply(t('errors.noResults', lang))

        player = await get_or_create_player(guild, voice_channel, text_channel, self.bot)
        player.volume = settings.get('defaultVolume', 80)

        if len(tracks) == 1:
            await player.enqueue(tracks[0])
            track = tracks[0]
            embed = discord.Embed(
                title=t('play.added', lang),
                description=f'**[{track.title}]({track.url})**',
                color=0x5865F2,
            )
            embed.add_field(name='Duration', value=track.duration, inline=True)
            if track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)
            return await edit_reply(embeds=[embed])
        else:
            await player.enqueue_many(tracks)
            embed = discord.Embed(
                title=t('play.addedPlaylist', lang),
                description=t('play.addedPlaylistDesc', lang, {'count': len(tracks)}),
                color=0x5865F2,
            )
            return await edit_reply(embeds=[embed])

    # ================================================================== /skip ==

    @app_commands.command(name='skip', description='Skip the current track')
    async def skip_slash(self, interaction: discord.Interaction) -> None:
        await self._skip(interaction)

    @commands.command(name='skip', aliases=['s'])
    async def skip_prefix(self, ctx: commands.Context) -> None:
        await self._skip(ctx)

    async def _skip(self, ctx) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player or not player.current:
            msg = t('errors.nothingPlaying', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        title = player.current.title
        player.skip()
        msg = t('skip.skipped', lang, {'title': title})
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # ================================================================== /stop ==

    @app_commands.command(name='stop', description='Stop playback and clear the queue')
    async def stop_slash(self, interaction: discord.Interaction) -> None:
        await self._stop(interaction)

    @commands.command(name='stop')
    async def stop_prefix(self, ctx: commands.Context) -> None:
        await self._stop(ctx)

    async def _stop(self, ctx) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player:
            msg = t('errors.nothingPlaying', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        player.stop()
        msg = t('stop.stopped', lang)
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # ================================================================= /pause ==

    @app_commands.command(name='pause', description='Pause the current track')
    async def pause_slash(self, interaction: discord.Interaction) -> None:
        await self._pause(interaction)

    @commands.command(name='pause')
    async def pause_prefix(self, ctx: commands.Context) -> None:
        await self._pause(ctx)

    async def _pause(self, ctx) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player or not player.current:
            msg = t('errors.nothingPlaying', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        if player.paused:
            msg = t('pause.alreadyPaused', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        player.pause()
        msg = t('pause.paused', lang)
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # ================================================================ /resume ==

    @app_commands.command(name='resume', description='Resume the paused track')
    async def resume_slash(self, interaction: discord.Interaction) -> None:
        await self._resume(interaction)

    @commands.command(name='resume', aliases=['unpause'])
    async def resume_prefix(self, ctx: commands.Context) -> None:
        await self._resume(ctx)

    async def _resume(self, ctx) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player or not player.current:
            msg = t('errors.nothingPlaying', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        if not player.paused:
            msg = t('resume.notPaused', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        player.resume()
        msg = t('resume.resumed', lang)
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # ================================================================= /queue ==

    @app_commands.command(name='queue', description='Show the current queue')
    @app_commands.describe(page='Page number')
    async def queue_slash(self, interaction: discord.Interaction, page: int = 1) -> None:
        await self._queue(interaction, page)

    @commands.command(name='queue', aliases=['q'])
    async def queue_prefix(self, ctx: commands.Context, page: int = 1) -> None:
        await self._queue(ctx, page)

    async def _queue(self, ctx, page: int = 1) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player or (not player.current and not player.tracks):
            msg = t('errors.queueEmpty', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        total_pages = max(1, -(-len(player.tracks) // PAGE_SIZE))  # ceiling division
        clamped = min(max(page, 1), total_pages)
        start = (clamped - 1) * PAGE_SIZE
        entries = player.tracks[start:start + PAGE_SIZE]

        repeat_labels = {RepeatMode.OFF: 'Off', RepeatMode.ONE: 'One', RepeatMode.ALL: 'All'}

        embed = discord.Embed(
            title=f'🎶 Queue — Page {clamped}/{total_pages}',
            color=0x5865F2,
        )
        embed.add_field(
            name='Now Playing',
            value=(
                f'**[{player.current.title}]({player.current.url})** ({player.current.duration})'
                if player.current
                else 'Nothing'
            ),
            inline=False,
        )

        if entries:
            lines = [
                f'`{start + i + 1}.` [{tr.title}]({tr.url}) — {tr.duration}'
                for i, tr in enumerate(entries)
            ]
            embed.add_field(name='Up Next', value='\n'.join(lines), inline=False)

        embed.set_footer(
            text=(
                f'{len(player.tracks)} track(s) in queue • '
                f'Repeat: {repeat_labels[player.repeat_mode]} • '
                f'Volume: {player.volume}%'
            )
        )

        if is_inter:
            return await ctx.response.send_message(embeds=[embed])
        return await ctx.reply(embeds=[embed])

    # ================================================================ /volume ==

    @app_commands.command(name='volume', description='Set the playback volume (1–100)')
    @app_commands.describe(level='Volume level 1–100')
    async def volume_slash(self, interaction: discord.Interaction, level: app_commands.Range[int, 1, 100]) -> None:
        await self._volume(interaction, level)

    @commands.command(name='volume', aliases=['vol'])
    async def volume_prefix(self, ctx: commands.Context, level: int = 0) -> None:
        await self._volume(ctx, level)

    async def _volume(self, ctx, level: int) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)

        if not level or level < 1 or level > 100:
            msg = 'Please provide a volume between 1 and 100.'
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))
        if not player:
            msg = t('errors.nothingPlaying', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        player.set_volume(level)
        msg = t('volume.set', lang, {'level': level})
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # ================================================================ /shuffle ==

    @app_commands.command(name='shuffle', description='Shuffle the queue')
    async def shuffle_slash(self, interaction: discord.Interaction) -> None:
        await self._shuffle(interaction)

    @commands.command(name='shuffle')
    async def shuffle_prefix(self, ctx: commands.Context) -> None:
        await self._shuffle(ctx)

    async def _shuffle(self, ctx) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player or len(player.tracks) < 2:
            msg = t('errors.notEnoughTracks', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        player.shuffle()
        msg = t('shuffle.shuffled', lang, {'count': len(player.tracks)})
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # ================================================================= /repeat ==

    @app_commands.command(name='repeat', description='Set the repeat mode')
    @app_commands.describe(mode='off, one, or all')
    @app_commands.choices(mode=[
        app_commands.Choice(name='Off', value='off'),
        app_commands.Choice(name='One', value='one'),
        app_commands.Choice(name='All', value='all'),
    ])
    async def repeat_slash(self, interaction: discord.Interaction, mode: str) -> None:
        await self._repeat(interaction, mode)

    @commands.command(name='repeat', aliases=['loop'])
    async def repeat_prefix(self, ctx: commands.Context, mode: str = '') -> None:
        await self._repeat(ctx, mode.lower())

    async def _repeat(self, ctx, mode: str) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)

        mode_map = {'off': RepeatMode.OFF, 'one': RepeatMode.ONE, 'all': RepeatMode.ALL}

        if mode not in mode_map:
            msg = 'Valid modes: `off`, `one`, `all`'
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))
        if not player:
            msg = t('errors.nothingPlaying', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        player.set_repeat(mode_map[mode])
        msg = t('repeat.set', lang, {'mode': mode})
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # ================================================================= /leave ==

    @app_commands.command(name='leave', description='Disconnect the bot from the voice channel')
    async def leave_slash(self, interaction: discord.Interaction) -> None:
        await self._leave(interaction)

    @commands.command(name='leave', aliases=['disconnect', 'dc'])
    async def leave_prefix(self, ctx: commands.Context) -> None:
        await self._leave(ctx)

    async def _leave(self, ctx) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)

        voice_client = guild.voice_client
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not voice_client and not player:
            msg = t('errors.notConnected', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        if player:
            player.stop()
        if voice_client and voice_client.is_connected():
            await voice_client.disconnect()
        self.bot.queues.pop(str(guild.id), None)

        msg = t('leave.left', lang)
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # =============================================================== /filter ==

    @app_commands.command(name='filter', description='Apply an audio filter')
    @app_commands.describe(name='Filter name')
    @app_commands.choices(name=[
        app_commands.Choice(name='None', value='none'),
        app_commands.Choice(name='Nightcore', value='nightcore'),
        app_commands.Choice(name='Bass Boost', value='bassboost'),
    ])
    async def filter_slash(self, interaction: discord.Interaction, name: str) -> None:
        await self._filter(interaction, name)

    @commands.command(name='filter')
    async def filter_prefix(self, ctx: commands.Context, name: str = '') -> None:
        await self._filter(ctx, name.lower())

    async def _filter(self, ctx, name: str) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)

        if not name or name not in FILTERS:
            msg = f'Valid filters: {", ".join(FILTERS.keys())}'
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))
        if not player or not player.current:
            msg = t('errors.nothingPlaying', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        player.set_filter(name)
        msg = t('filter.set', lang, {'name': name})
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # =========================================================== /nowplaying ==

    @app_commands.command(name='nowplaying', description='Show the currently playing track')
    async def nowplaying_slash(self, interaction: discord.Interaction) -> None:
        await self._nowplaying(interaction)

    @commands.command(name='nowplaying', aliases=['np', 'current'])
    async def nowplaying_prefix(self, ctx: commands.Context) -> None:
        await self._nowplaying(ctx)

    async def _nowplaying(self, ctx) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player or not player.current:
            msg = t('errors.nothingPlaying', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        track = player.current
        repeat_labels = {RepeatMode.OFF: 'Off', RepeatMode.ONE: 'One', RepeatMode.ALL: 'All'}

        embed = discord.Embed(
            title='🎵 Now Playing',
            description=f'**[{track.title}]({track.url})**',
            color=0x5865F2,
        )
        embed.add_field(name='Duration', value=track.duration, inline=True)
        embed.add_field(name='Requested by', value=track.requested_by or 'Unknown', inline=True)
        embed.add_field(name='Volume', value=f'{player.volume}%', inline=True)
        embed.add_field(name='Filter', value=player.filter, inline=True)
        embed.add_field(name='Repeat', value=repeat_labels[player.repeat_mode], inline=True)
        embed.add_field(name='Queue', value=f'{len(player.tracks)} track(s)', inline=True)

        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)

        if is_inter:
            return await ctx.response.send_message(embeds=[embed])
        return await ctx.reply(embeds=[embed])


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
