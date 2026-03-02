from __future__ import annotations

import random
from typing import TYPE_CHECKING

import discord
import wavelink

from .track import Track

if TYPE_CHECKING:
    from discord.ext import commands

FILTERS: dict[str, str | None] = {
    'none': None,
    'nightcore': 'nightcore',
    'bassboost': 'bassboost',
}


class RepeatMode:
    OFF = 0
    ONE = 1
    ALL = 2


def _build_wavelink_filters(filter_name: str) -> wavelink.Filters:
    filters = wavelink.Filters()
    if filter_name == 'nightcore':
        filters.timescale.set(pitch=1.3, speed=1.3, rate=1.0)
    elif filter_name == 'bassboost':
        filters.equalizer.set(bands=[
            {'band': 0, 'gain': 0.25},
            {'band': 1, 'gain': 0.25},
            {'band': 2, 'gain': 0.15},
        ])
    return filters


class MusicPlayer:
    def __init__(
        self,
        guild: discord.Guild,
        wl_player: wavelink.Player,
        text_channel: discord.abc.Messageable,
        bot: commands.Bot,
    ):
        self.guild = guild
        self._wl_player = wl_player
        self.text_channel = text_channel
        self.bot = bot

        # Store back-reference so the track-end event can locate this wrapper
        wl_player._music_player = self  # type: ignore[attr-defined]

        self.tracks: list[Track] = []
        self.current: Track | None = None
        self._volume: int = 80
        self.filter: str = 'none'
        self.repeat_mode: int = RepeatMode.OFF
        self.paused: bool = False

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, val: int) -> None:
        self._volume = max(1, min(100, val))

    # ------------------------------------------------------------------ playback

    async def _resolve_wl_track(self, track: Track) -> wavelink.Playable | None:
        """Resolve a Track URL to a wavelink.Playable for playback."""
        try:
            results: wavelink.Search = await wavelink.Playable.search(track.url)
            if isinstance(results, wavelink.Playlist):
                return results.tracks[0] if results.tracks else None
            return results[0] if results else None
        except Exception as e:
            print(f'[Player:{self.guild.id}] Failed to resolve "{track.title}": {e}')
            return None

    async def _play(self, track: Track) -> None:
        self.current = track
        wl_track = await self._resolve_wl_track(track)
        if not wl_track:
            print(f'[Player:{self.guild.id}] Could not resolve "{track.title}", skipping.')
            await self._on_track_end()
            return

        try:
            await self._wl_player.play(wl_track, volume=self._volume)
            # Apply active filter
            if self.filter != 'none':
                await self._wl_player.set_filters(_build_wavelink_filters(self.filter))
        except Exception as e:
            print(f'[Player:{self.guild.id}] Failed to play "{track.title}": {e}')
            await self._on_track_end()
            return

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

    async def _on_track_end(self) -> None:
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

    # ------------------------------------------------------------------ queue ops

    async def enqueue(self, track: Track) -> None:
        if not self._wl_player.playing and not self._wl_player.paused and not self.current:
            await self._play(track)
        else:
            self.tracks.append(track)

    async def enqueue_many(self, tracks: list[Track]) -> None:
        if not tracks:
            return
        if not self._wl_player.playing and not self._wl_player.paused and not self.current:
            first, *rest = tracks
            self.tracks.extend(rest)
            await self._play(first)
        else:
            self.tracks.extend(tracks)

    # ------------------------------------------------------------------ controls

    async def skip(self) -> None:
        await self._wl_player.stop()

    async def pause(self) -> None:
        await self._wl_player.pause(True)
        self.paused = True

    async def resume(self) -> None:
        await self._wl_player.pause(False)
        self.paused = False

    async def stop(self) -> None:
        self.tracks = []
        self.repeat_mode = RepeatMode.OFF
        self.current = None
        await self._wl_player.stop()

    async def set_volume(self, vol: int) -> None:
        self.volume = vol
        await self._wl_player.set_volume(self._volume)

    async def set_filter(self, filter_name: str) -> bool:
        if filter_name not in FILTERS:
            return False
        self.filter = filter_name
        await self._wl_player.set_filters(_build_wavelink_filters(filter_name))
        return True

    def shuffle(self) -> None:
        random.shuffle(self.tracks)

    def set_repeat(self, mode: int) -> None:
        self.repeat_mode = mode

    # ------------------------------------------------------------------ cleanup

    async def _cleanup(self) -> None:
        if self._wl_player and self._wl_player.connected:
            await self._wl_player.disconnect()
        guild_id = str(self.guild.id)
        self.bot.queues.pop(guild_id, None)
