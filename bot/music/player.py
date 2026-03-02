from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

import discord

from .track import Track

if TYPE_CHECKING:
    from discord.ext import commands

FILTERS: dict[str, str | None] = {
    'none': None,
    'nightcore': 'atempo=1.3,asetrate=44100*1.25',
    'bassboost': 'bass=g=20,dynaudnorm=f=200',
}


class RepeatMode:
    OFF = 0
    ONE = 1
    ALL = 2


class MusicPlayer:
    def __init__(
        self,
        guild: discord.Guild,
        voice_client: discord.VoiceClient,
        text_channel: discord.abc.Messageable,
        bot: commands.Bot,
    ):
        self.guild = guild
        self.voice_client = voice_client
        self.text_channel = text_channel
        self.bot = bot

        self.tracks: list[Track] = []
        self.current: Track | None = None
        self.volume: int = 80
        self.filter: str = 'none'
        self.repeat_mode: int = RepeatMode.OFF
        self.paused: bool = False
        self._restart_requested: bool = False

    def _ffmpeg_options(self) -> dict:
        filter_str = FILTERS[self.filter]
        volume_filter = f'volume={self.volume / 100}'
        filter_chain = f'{filter_str},{volume_filter}' if filter_str else volume_filter
        return {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': f'-af {filter_chain} -vn',
        }

    async def _get_stream_url(self, url: str) -> str:
        import yt_dlp

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
        }

        loop = asyncio.get_event_loop()

        def _extract():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    info = info['entries'][0]
                # Prefer a format with only audio
                formats = info.get('formats', [info])
                audio_formats = [
                    f for f in formats
                    if f.get('acodec') != 'none' and f.get('vcodec') in ('none', None)
                ]
                if audio_formats:
                    return audio_formats[-1]['url']
                return info.get('url', url)

        return await loop.run_in_executor(None, _extract)

    async def _play(self, track: Track) -> None:
        self.current = track
        try:
            stream_url = await self._get_stream_url(track.url)
            ffmpeg_opts = self._ffmpeg_options()
            source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_opts)

            def after_playing(error: Exception | None) -> None:
                if error:
                    print(f'[Player:{self.guild.id}] Audio error: {error}')
                asyncio.run_coroutine_threadsafe(self._on_track_end(), self.bot.loop)

            if self.voice_client and self.voice_client.is_connected():
                self.voice_client.play(source, after=after_playing)

            if self.text_channel:
                try:
                    from bot.db import get_guild_settings
                    settings = await get_guild_settings(str(self.guild.id))
                    if settings and settings.get('announceNowPlaying'):
                        embed = discord.Embed(
                            title='🎵 Now Playing',
                            description=f'**[{track.title}]({track.url})**',
                            color=0x5865F2,
                        )
                        embed.add_field(name='Duration', value=track.duration, inline=True)
                        embed.add_field(
                            name='Requested by',
                            value=track.requested_by or 'Unknown',
                            inline=True,
                        )
                        if track.thumbnail:
                            embed.set_thumbnail(url=track.thumbnail)
                        await self.text_channel.send(embed=embed)
                except Exception:
                    pass
        except Exception as e:
            print(f'[Player:{self.guild.id}] Failed to play "{track.title}": {e}')
            asyncio.run_coroutine_threadsafe(self._on_track_end(), self.bot.loop)

    async def _on_track_end(self) -> None:
        if self._restart_requested:
            self._restart_requested = False
            await self._play(self.current)
            return

        if self.repeat_mode == RepeatMode.ONE and self.current:
            await self._play(self.current)
            return

        if self.repeat_mode == RepeatMode.ALL and self.current:
            self.tracks.append(self.current)

        self.current = None

        if self.tracks:
            next_track = self.tracks.pop(0)
            await self._play(next_track)
        else:
            await self._cleanup()

    async def enqueue(self, track: Track) -> None:
        if (
            not self.voice_client.is_playing()
            and not self.voice_client.is_paused()
            and not self.current
        ):
            await self._play(track)
        else:
            self.tracks.append(track)

    async def enqueue_many(self, tracks: list[Track]) -> None:
        if not tracks:
            return
        if (
            not self.voice_client.is_playing()
            and not self.voice_client.is_paused()
            and not self.current
        ):
            first, *rest = tracks
            self.tracks.extend(rest)
            await self._play(first)
        else:
            self.tracks.extend(tracks)

    def skip(self) -> None:
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()

    def pause(self) -> None:
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            self.paused = True

    def resume(self) -> None:
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            self.paused = False

    def stop(self) -> None:
        self.tracks = []
        self.repeat_mode = RepeatMode.OFF
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()

    def set_volume(self, vol: int) -> None:
        self.volume = max(1, min(100, vol))
        if self.current:
            self._restart_current()

    def set_filter(self, filter_name: str) -> bool:
        if filter_name not in FILTERS:
            return False
        self.filter = filter_name
        if self.current:
            self._restart_current()
        return True

    def _restart_current(self) -> None:
        if self.current and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self._restart_requested = True
            self.voice_client.stop()

    def shuffle(self) -> None:
        random.shuffle(self.tracks)

    def set_repeat(self, mode: int) -> None:
        self.repeat_mode = mode

    async def _cleanup(self) -> None:
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
        guild_id = str(self.guild.id)
        self.bot.queues.pop(guild_id, None)
