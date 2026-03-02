from __future__ import annotations

import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from bot.db import get_guild_settings, update_guild_settings
from bot.i18n import t

SFX_DIR = Path(__file__).parent.parent.parent / 'data' / 'sfx'


class Utility(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ================================================================= /ping ==

    @app_commands.command(name='ping', description='Check the bot latency')
    async def ping_slash(self, interaction: discord.Interaction) -> None:
        await self._ping(interaction)

    @commands.command(name='ping')
    async def ping_prefix(self, ctx: commands.Context) -> None:
        await self._ping(ctx)

    async def _ping(self, ctx) -> None:
        is_inter = isinstance(ctx, discord.Interaction)

        if is_inter:
            await ctx.response.send_message('Pinging…')
            msg = await ctx.original_response()
            roundtrip = (msg.created_at - ctx.created_at).total_seconds() * 1000
            ws_latency = round(self.bot.latency * 1000)
            embed = discord.Embed(title='🏓 Pong!', color=0x5865F2)
            embed.add_field(name='Roundtrip', value=f'{roundtrip:.0f}ms', inline=True)
            embed.add_field(name='WebSocket', value=f'{ws_latency}ms', inline=True)
            await ctx.edit_original_response(content=None, embeds=[embed])
        else:
            sent = await ctx.reply('Pinging…')
            roundtrip = (sent.created_at - ctx.message.created_at).total_seconds() * 1000
            ws_latency = round(self.bot.latency * 1000)
            embed = discord.Embed(title='🏓 Pong!', color=0x5865F2)
            embed.add_field(name='Roundtrip', value=f'{roundtrip:.0f}ms', inline=True)
            embed.add_field(name='WebSocket', value=f'{ws_latency}ms', inline=True)
            await sent.edit(content=None, embeds=[embed])

    # =============================================================== /lyrics ==

    @app_commands.command(name='lyrics', description='Fetch lyrics for a song')
    @app_commands.describe(song='Song name (defaults to current track)')
    async def lyrics_slash(self, interaction: discord.Interaction, song: str = '') -> None:
        await self._lyrics(interaction, song or None)

    @commands.command(name='lyrics', aliases=['ly'])
    async def lyrics_prefix(self, ctx: commands.Context, *, song: str = '') -> None:
        await self._lyrics(ctx, song or None)

    async def _lyrics(self, ctx, song: str | None) -> None:
        import aiohttp

        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild

        query = song
        if not query:
            player = self.bot.queues.get(str(guild.id))
            if player and player.current:
                query = player.current.title
            else:
                msg = 'Please provide a song name or have a track playing.'
                if is_inter:
                    return await ctx.response.send_message(msg, ephemeral=True)
                return await ctx.reply(msg)

        if is_inter:
            await ctx.response.defer()

        async def edit(content=None, **kwargs):
            if is_inter:
                return await ctx.edit_original_response(content=content, **kwargs)
            return await ctx.reply(content, **kwargs)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'https://lrclib.net/api/search',
                    params={'q': query},
                ) as resp:
                    if not resp.ok:
                        raise RuntimeError(f'LRCLIB responded with {resp.status}')
                    results = await resp.json()

            if not results:
                return await edit(f'❌ No lyrics found for **{query}**.')

            best = results[0]
            lyrics = best.get('plainLyrics') or best.get('syncedLyrics', '')
            if lyrics:
                import re
                lyrics = re.sub(r'\[\d+:\d+\.\d+\]', '', lyrics).strip()

            if not lyrics:
                return await edit(f'❌ Lyrics are unavailable for **{best.get("trackName", query)}**.')

            MAX = 4000
            chunks: list[str] = []
            current = ''
            for line in lyrics.split('\n'):
                candidate = current + ('\n' if current else '') + line
                if len(candidate) > MAX:
                    chunks.append(current)
                    current = line
                else:
                    current = candidate
            if current:
                chunks.append(current)

            embed = discord.Embed(
                title=f'🎤 {best.get("trackName", query)} — {best.get("artistName", "")}',
                description=chunks[0],
                color=0x5865F2,
            )
            embed.set_footer(text=f'Page 1/{len(chunks)} • Powered by LRCLIB')
            await edit(embeds=[embed])

            for i, chunk in enumerate(chunks[1:], start=2):
                page_embed = discord.Embed(description=chunk, color=0x5865F2)
                page_embed.set_footer(text=f'Page {i}/{len(chunks)} • Powered by LRCLIB')
                if is_inter:
                    await ctx.followup.send(embeds=[page_embed])
                else:
                    await ctx.channel.send(embeds=[page_embed])

        except Exception as err:
            print(f'[lyrics] {err}')
            await edit(f'❌ Failed to fetch lyrics: {err}')

    # ================================================================== /sfx ==

    @app_commands.command(name='sfx', description='Play a sound effect')
    @app_commands.describe(name='Name of the sound effect')
    async def sfx_slash(self, interaction: discord.Interaction, name: str) -> None:
        await self._sfx(interaction, name)

    @commands.command(name='sfx')
    async def sfx_prefix(self, ctx: commands.Context, name: str = '') -> None:
        await self._sfx(ctx, name)

    async def _sfx(self, ctx, name: str) -> None:
        from discord import FFmpegPCMAudio
        from discord.ext.commands import BotMissingPermissions

        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        member = ctx.user if is_inter else ctx.author
        voice_channel = getattr(member.voice, 'channel', None) if hasattr(member, 'voice') else None

        async def reply(content, *, ephemeral=False):
            if is_inter:
                if ctx.response.is_done():
                    return await ctx.followup.send(content, ephemeral=ephemeral)
                return await ctx.response.send_message(content, ephemeral=ephemeral)
            return await ctx.reply(content)

        if not voice_channel:
            return await reply('❌ You must be in a voice channel to use SFX.', ephemeral=True)

        if not name:
            return await reply('Please provide an SFX name.', ephemeral=True)

        sfx_path = SFX_DIR / f'{name}.mp3'
        if not sfx_path.exists():
            if SFX_DIR.exists():
                available = ', '.join(
                    p.stem for p in SFX_DIR.iterdir() if p.suffix == '.mp3'
                ) or 'None'
            else:
                available = 'None'
            return await reply(f'❌ SFX `{name}` not found. Available: {available}', ephemeral=True)

        voice_client = guild.voice_client
        if voice_client and voice_client.is_connected():
            if voice_client.channel.id != voice_channel.id:
                await voice_client.move_to(voice_channel)
        else:
            voice_client = await voice_channel.connect(self_deaf=True)

        source = FFmpegPCMAudio(str(sfx_path))
        guild_id = str(guild.id)

        def after_sfx(error):
            if not self.bot.queues.get(guild_id):
                import asyncio
                asyncio.run_coroutine_threadsafe(
                    voice_client.disconnect(), self.bot.loop
                )

        voice_client.play(source, after=after_sfx)
        await reply(f'🔊 Playing SFX: `{name}`')

    # ============================================================== /settings ==

    settings_group = app_commands.Group(
        name='settings',
        description='View or change bot settings for this server',
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @settings_group.command(name='show', description='Show current settings')
    async def settings_show_slash(self, interaction: discord.Interaction) -> None:
        await self._settings_show(interaction)

    @settings_group.command(name='prefix', description='Set the command prefix')
    @app_commands.describe(value='New prefix')
    async def settings_prefix_slash(self, interaction: discord.Interaction, value: str) -> None:
        guild = interaction.guild
        if len(value) > 5:
            return await interaction.response.send_message(
                'Prefix must be 5 characters or fewer.', ephemeral=True
            )
        await update_guild_settings(str(guild.id), {'prefix': value})
        await interaction.response.send_message(f'✅ Prefix set to `{value}`')

    @settings_group.command(name='language', description='Set the bot language')
    @app_commands.describe(value='Language code')
    @app_commands.choices(value=[
        app_commands.Choice(name='English', value='en'),
        app_commands.Choice(name='Español', value='es'),
    ])
    async def settings_language_slash(self, interaction: discord.Interaction, value: str) -> None:
        await update_guild_settings(str(interaction.guild.id), {'language': value})
        await interaction.response.send_message(f'✅ Language set to `{value}`')

    @settings_group.command(name='volume', description='Set the default volume')
    @app_commands.describe(value='1–100')
    async def settings_volume_slash(
        self,
        interaction: discord.Interaction,
        value: app_commands.Range[int, 1, 100],
    ) -> None:
        await update_guild_settings(str(interaction.guild.id), {'defaultVolume': value})
        await interaction.response.send_message(f'✅ Default volume set to {value}%')

    @settings_group.command(name='djrole', description='Set the DJ role (leave blank to clear)')
    @app_commands.describe(role='DJ role')
    async def settings_djrole_slash(
        self,
        interaction: discord.Interaction,
        role: discord.Role | None = None,
    ) -> None:
        await update_guild_settings(str(interaction.guild.id), {'djRoleId': str(role.id) if role else None})
        msg = f'✅ DJ role set to {role.mention}' if role else '✅ DJ role cleared.'
        await interaction.response.send_message(msg)

    @settings_group.command(name='announce', description='Toggle now-playing announcements')
    @app_commands.describe(value='Enabled?')
    async def settings_announce_slash(
        self,
        interaction: discord.Interaction,
        value: bool,
    ) -> None:
        await update_guild_settings(str(interaction.guild.id), {'announceNowPlaying': int(value)})
        state = 'enabled' if value else 'disabled'
        await interaction.response.send_message(f'✅ Now-playing announcements {state}.')

    async def _settings_show(self, ctx) -> None:
        is_inter = isinstance(ctx, discord.Interaction)
        guild = ctx.guild
        settings = await get_guild_settings(str(guild.id))

        embed = discord.Embed(
            title=f'⚙️ Settings — {guild.name}',
            color=0x5865F2,
        )
        embed.add_field(name='Prefix', value=f'`{settings.get("prefix", "!")}`', inline=True)
        embed.add_field(name='Language', value=settings.get('language', 'en'), inline=True)
        embed.add_field(name='Default Volume', value=f'{settings.get("defaultVolume", 80)}%', inline=True)
        dj_role_id = settings.get('djRoleId')
        embed.add_field(name='DJ Role', value=f'<@&{dj_role_id}>' if dj_role_id else 'None', inline=True)
        embed.add_field(
            name='Announce Now Playing',
            value='Yes' if settings.get('announceNowPlaying') else 'No',
            inline=True,
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        if is_inter:
            await ctx.response.send_message(embeds=[embed])
        else:
            await ctx.reply(embeds=[embed])

    @commands.command(name='settings')
    async def settings_prefix(self, ctx: commands.Context) -> None:
        await self._settings_show(ctx)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utility(bot))
