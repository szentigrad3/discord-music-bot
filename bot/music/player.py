from __future__ import annotations

import random
from typing import TYPE_CHECKING

import discord

from bot.logger import get_logger
from bot.voicelink import Equalizer, Filters, Player as VoicelinkPlayer, Timescale
from bot.voicelink.filters import Rotation
from .track import Track

if TYPE_CHECKING:
    from discord.ext import commands

logger = get_logger(__name__)

FILTERS: dict[str, str | None] = {
    'none': None,
    'nightcore': 'nightcore',
    'bassboost': 'bassboost',
    'vaporwave': 'vaporwave',
    '8d': '8d',
    'karaoke': 'karaoke',
    'slowed': 'slowed',
}


class RepeatMode:
    OFF = 0
    ONE = 1
    ALL = 2


def _build_voicelink_filters(filter_name: str) -> list:
    """Return a list of voicelink Filter objects for the given filter name."""
    if filter_name == 'nightcore':
        return [Timescale.nightcore()]
    elif filter_name == 'bassboost':
        return [Equalizer.boost()]
    elif filter_name == 'vaporwave':
        return [Timescale.vaporwave()]
    elif filter_name == '8d':
        return [Rotation.nightD()]
    elif filter_name == 'karaoke':
        from bot.voicelink.filters import Karaoke
        return [Karaoke()]
    elif filter_name == 'slowed':
        return [Timescale(tag='slowed', speed=0.75, pitch=0.9)]
    return []


class MusicPlayer:
    def __init__(
        self,
        guild: discord.Guild,
        vl_player: VoicelinkPlayer,
        text_channel: discord.abc.Messageable,
        bot: commands.Bot,
    ):
        self.guild = guild
        self._vl_player = vl_player
        self.text_channel = text_channel
        self.bot = bot

        # Store back-reference so the track-end event can locate this wrapper
        vl_player._music_player = self  # type: ignore[attr-defined]

        self.tracks: list[Track] = []
        self.history: list[Track] = []
        self.current: Track | None = None
        self._volume: int = 80
        self.filter: str = 'none'
        self.repeat_mode: int = RepeatMode.OFF
        self.paused: bool = False

        # Interactive controller message (Vocard-style)
        self._controller_message: discord.Message | None = None

    @property
    def volume(self) -> int:
        return self._volume

    @volume.setter
    def volume(self, val: int) -> None:
        self._volume = max(1, min(100, val))

    # ------------------------------------------------------------------ playback

    async def _play(self, track: Track) -> None:
        self.current = track
        self.paused = False

        vl_track = track._vl_track
        if not vl_track:
            logger.warning('[Player:%s] No voicelink track for "%s", skipping.', self.guild.id, track.title)
            await self._on_track_end()
            return

        try:
            await self._vl_player.set_volume(self._volume)
            await self._vl_player.play(vl_track)
            # Apply active filter
            if self.filter != 'none':
                await self._apply_filters(self.filter)
        except Exception as e:
            logger.error('[Player:%s] Failed to play "%s": %s', self.guild.id, track.title, e)
            await self._on_track_end()
            return

        if self.text_channel:
            try:
                await self._send_or_update_controller()
            except Exception:
                pass

    async def _apply_filters(self, filter_name: str) -> None:
        """Reset filters then apply the named filter set (fast-apply for instant effect)."""
        await self._vl_player.reset_filters()
        for f in _build_voicelink_filters(filter_name):
            await self._vl_player.add_filter(f, fast_apply=True)

    async def _send_or_update_controller(self) -> None:
        """Send a new controller message or update the existing one."""
        from bot.views.controller import PlayerController, build_now_playing_embed

        embed = build_now_playing_embed(self)
        view = PlayerController(self)

        if self._controller_message:
            try:
                await self._controller_message.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.HTTPException):
                self._controller_message = None

        try:
            self._controller_message = await self.text_channel.send(embed=embed, view=view)
        except Exception as e:
            logger.error('[Player:%s] Failed to send controller: %s', self.guild.id, e)

    async def _on_track_end(self) -> None:
        if self.repeat_mode == RepeatMode.ONE and self.current:
            await self._play(self.current)
            return

        if self.current:
            self.history.append(self.current)
            # Keep history bounded to last 20 tracks
            if len(self.history) > 20:
                self.history.pop(0)

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
        if not self._vl_player.is_playing and not self._vl_player.is_paused and not self.current:
            await self._play(track)
        else:
            self.tracks.append(track)

    async def enqueue_many(self, tracks: list[Track]) -> None:
        if not tracks:
            return
        if not self._vl_player.is_playing and not self._vl_player.is_paused and not self.current:
            first, *rest = tracks
            self.tracks.extend(rest)
            await self._play(first)
        else:
            self.tracks.extend(tracks)

    # ------------------------------------------------------------------ controls

    async def skip(self) -> None:
        await self._vl_player.stop()

    async def back(self) -> None:
        """Go back to the previous track in history."""
        if not self.history:
            return
        prev = self.history.pop()
        # Insert the previous track at the front of the queue so _on_track_end
        # picks it up naturally after stop() fires the track-end event.
        self.tracks.insert(0, prev)
        await self._vl_player.stop()

    async def pause(self) -> None:
        await self._vl_player.set_pause(True)
        self.paused = True

    async def resume(self) -> None:
        await self._vl_player.set_pause(False)
        self.paused = False

    async def stop(self) -> None:
        self.tracks = []
        self.repeat_mode = RepeatMode.OFF
        self.current = None
        await self._vl_player.stop()
        await self._disable_controller()

    async def set_volume(self, vol: int) -> None:
        self.volume = vol
        await self._vl_player.set_volume(self._volume)

    async def set_filter(self, filter_name: str) -> bool:
        if filter_name not in FILTERS:
            return False
        self.filter = filter_name
        if filter_name == 'none':
            await self._vl_player.reset_filters()
        else:
            await self._apply_filters(filter_name)
        return True

    def shuffle(self) -> None:
        random.shuffle(self.tracks)

    def set_repeat(self, mode: int) -> None:
        self.repeat_mode = mode

    async def seek(self, seconds: int) -> None:
        """Seek to a position in the current track (seconds)."""
        await self._vl_player.seek(seconds * 1000)

    def move_track(self, from_pos: int, to_pos: int) -> None:
        """Move a track from one queue position to another (1-based indices)."""
        track = self.tracks.pop(from_pos - 1)
        self.tracks.insert(to_pos - 1, track)

    def clear_queue(self) -> int:
        """Clear all queued tracks without stopping the current track. Returns number cleared."""
        count = len(self.tracks)
        self.tracks = []
        return count

    # ------------------------------------------------------------------ cleanup

    async def _disable_controller(self) -> None:
        """Disable all controller buttons when playback ends."""
        if not self._controller_message:
            return
        try:
            from bot.views.controller import PlayerController, build_now_playing_embed
            view = PlayerController(self)
            for child in view.children:
                child.disabled = True
            embed = discord.Embed(
                title='⏹️ Playback stopped',
                description='Queue cleared.',
                color=0x5865F2,
            )
            await self._controller_message.edit(embed=embed, view=view)
        except Exception:
            pass
        finally:
            self._controller_message = None

    async def _cleanup(self) -> None:
        await self._disable_controller()
        if self._vl_player and self._vl_player.is_connected:
            await self._vl_player.disconnect()
        guild_id = str(self.guild.id)
        self.bot.queues.pop(guild_id, None)
