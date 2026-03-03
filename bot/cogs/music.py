from __future__ import annotations

import os

import discord
from discord import app_commands
from discord.ext import commands

from bot.db import get_guild_settings, update_guild_settings
from bot.i18n import t
from bot.music.player import FILTERS, MusicPlayer, RepeatMode
from bot.music.queue import get_or_create_player, resolve_tracks
from bot.views import SearchView, build_now_playing_embed

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
        await player.skip()
        msg = t('skip.skipped', lang, {'title': title})
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # =================================================================== /back ==

    @app_commands.command(name='back', description='Go back to the previous track')
    async def back_slash(self, interaction: discord.Interaction) -> None:
        await self._back(interaction)

    @commands.command(name='back', aliases=['previous', 'prev'])
    async def back_prefix(self, ctx: commands.Context) -> None:
        await self._back(ctx)

    async def _back(self, ctx) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player:
            msg = t('errors.nothingPlaying', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        if not player.history:
            msg = '❌ No previous tracks in history.'
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        await player.back()
        msg = '⏮️ Going back to the previous track.'
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

        await player.stop()
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

        await player.pause()
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

        await player.resume()
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

        await player.set_volume(level)
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

        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player:
            msg = t('errors.notConnected', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        await player.stop()
        if player._vl_player.is_connected:
            await player._vl_player.disconnect()
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

        await player.set_filter(name)
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

        embed = build_now_playing_embed(player)

        if is_inter:
            return await ctx.response.send_message(embeds=[embed])
        return await ctx.reply(embeds=[embed])


    # ================================================================= /search ==

    @app_commands.command(name='search', description='Search for tracks and pick one from a list')
    @app_commands.describe(query='Search query')
    async def search_slash(self, interaction: discord.Interaction, query: str) -> None:
        await self._search(interaction, query)

    @commands.command(name='search')
    async def search_prefix(self, ctx: commands.Context, *, query: str = '') -> None:
        await self._search(ctx, query)

    async def _search(self, ctx, query: str) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        member = ctx.user if is_inter else ctx.author
        lang = await self._get_lang(guild)

        async def reply(content=None, *, ephemeral=False, **kwargs):
            if is_inter:
                if ctx.response.is_done():
                    return await ctx.followup.send(content, ephemeral=ephemeral, **kwargs)
                return await ctx.response.send_message(content, ephemeral=ephemeral, **kwargs)
            return await ctx.reply(content, **kwargs)

        async def edit_reply(content=None, **kwargs):
            if is_inter:
                return await ctx.edit_original_response(content=content, **kwargs)
            return await ctx.reply(content, **kwargs)

        if not query:
            return await reply('Please provide a search query.', ephemeral=True)

        voice_channel = getattr(member.voice, 'channel', None) if hasattr(member, 'voice') else None
        if not voice_channel:
            return await reply(t('errors.notInVoice', lang), ephemeral=True)

        if is_inter:
            await ctx.response.defer()

        # Search for results
        try:
            from bot.voicelink import NodePool, Playlist as VoicelinkPlaylist
            from bot.voicelink.enums import SearchType
            node = NodePool.get_node()
            results = await node.get_tracks(f'ytsearch:{query}', requester=None, search_type=SearchType.YOUTUBE)
        except Exception as err:
            return await edit_reply(f'❌ {err}')

        if not results:
            return await edit_reply(t('errors.noResults', lang))

        from bot.music.track import Track
        from bot.views.search import MAX_SEARCH_RESULTS

        vl_tracks = results.tracks if isinstance(results, VoicelinkPlaylist) else results
        tracks = [Track.from_voicelink(r, str(member)) for r in vl_tracks[:MAX_SEARCH_RESULTS]]
        player = await get_or_create_player(guild, voice_channel, ctx.channel, self.bot)
        settings = await get_guild_settings(str(guild.id))
        player.volume = settings.get('defaultVolume', 80)

        embed = discord.Embed(
            title=f'🔍 Search results for: {query}',
            color=0x5865F2,
        )
        lines = [
            f'`{i + 1}.` [{t_.title}]({t_.url}) — {t_.duration}'
            for i, t_ in enumerate(tracks)
        ]
        embed.description = '\n'.join(lines)
        view = SearchView(tracks, player)

        await edit_reply(embeds=[embed], view=view)

    # ================================================================ /skipto ==

    @app_commands.command(name='skipto', description='Jump to a specific position in the queue')
    @app_commands.describe(position='Queue position (1-based)')
    async def skipto_slash(self, interaction: discord.Interaction, position: app_commands.Range[int, 1]) -> None:
        await self._skipto(interaction, position)

    @commands.command(name='skipto', aliases=['st'])
    async def skipto_prefix(self, ctx: commands.Context, position: int = 0) -> None:
        await self._skipto(ctx, position)

    async def _skipto(self, ctx, position: int) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player or (not player.current and not player.tracks):
            msg = t('errors.nothingPlaying', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        if position < 1 or position > len(player.tracks):
            msg = f'❌ Position must be between 1 and {len(player.tracks)}.'
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        # Remove all tracks before the target position
        player.tracks = player.tracks[position - 1:]
        await player.skip()

        msg = f'⏭️ Skipping to position **{position}**.'
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)

    # ================================================================ /remove ==

    @app_commands.command(name='remove', description='Remove a track from the queue')
    @app_commands.describe(position='Queue position to remove (1-based)')
    async def remove_slash(self, interaction: discord.Interaction, position: app_commands.Range[int, 1]) -> None:
        await self._remove(interaction, position)

    @commands.command(name='remove', aliases=['rm'])
    async def remove_prefix(self, ctx: commands.Context, position: int = 0) -> None:
        await self._remove(ctx, position)

    async def _remove(self, ctx, position: int) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        lang = await self._get_lang(guild)
        player: MusicPlayer | None = self.bot.queues.get(str(guild.id))

        if not player or not player.tracks:
            msg = t('errors.queueEmpty', lang)
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        if position < 1 or position > len(player.tracks):
            msg = f'❌ Position must be between 1 and {len(player.tracks)}.'
            if is_inter:
                return await ctx.response.send_message(msg, ephemeral=True)
            return await ctx.reply(msg)

        removed = player.tracks.pop(position - 1)
        msg = f'🗑️ Removed **{removed.title}** from position {position}.'
        if is_inter:
            return await ctx.response.send_message(msg)
        return await ctx.reply(msg)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
