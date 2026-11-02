from __future__ import annotations

import asyncio
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


MAX_PENDING_TRACKS = 500


class QueueFullError(ValueError):
    """Adding these tracks would exceed the per-guild queue limit."""


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
        # Serialize track-end transitions and stop/enqueue operations.
        self._advance_lock = asyncio.Lock()

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
        """Start a track, skipping unplayable queued tracks without recursion.

        A playlist with many broken entries must not exhaust the call stack.
        Repeat-one applies only to successfully completed tracks.
        """
        while True:
            self.current = track
            self.paused = False
            vl_track = track._vl_track
            if vl_track is None:
                logger.warning('[Player:%s] Missing Lavalink track for "%s".',
                               self.guild.id, track.title)
            else:
                try:
                    await self._vl_player.set_volume(self._volume)
                    await self._vl_player.play(vl_track)
                except Exception:
                    logger.exception('[Player:%s] Failed to play "%s"',
                                     self.guild.id, track.title)
                else:
                    # Filter setup is optional: a rejected Lavalink filter
                    # must not skip an otherwise successfully started song.
                    if self.filter != 'none':
                        try:
                            await self._apply_filters(self.filter)
                        except Exception:
                            logger.warning('[Player:%s] Cannot apply audio filter; '
                                           'continuing without it.', self.guild.id)
                            self.filter = 'none'
                            try:
                                await self._vl_player.reset_filters()
                            except Exception:
                                pass
                    if self.text_channel:
                        try:
                            await self._send_or_update_controller()
                        except Exception:
                            logger.exception('[Player:%s] Controller update failed',
                                             self.guild.id)
                    return

            # Failed tracks do not enter the history or repeat loop.
            self.current = None
            if not self.tracks:
                await self._cleanup()
                return
            track = self.tracks.pop(0)

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

    async def _on_track_end(self, *, reason: str = 'finished',
                            ended_track=None) -> None:
        """Handle node events, serialized with user actions and enqueue requests."""
        async with self._advance_lock:
            await self._advance_locked(reason=reason, ended_track=ended_track)

    async def _advance_locked(self, *, reason: str,
                              ended_track=None) -> None:
        """Advance the queue while the caller holds _advance_lock."""
        if self.current is None:
            return
        current_vl = self.current._vl_track
        if ended_track is not None and current_vl is not ended_track:
            # Late end event for a track already replaced locally.
            return
        reason = reason.lower()
        if reason == 'replaced':
            return
        if reason == 'finished' and self.repeat_mode == RepeatMode.ONE:
            await self._play(self.current)
            return

        previous = self.current
        if reason not in ('loadfailed', 'cleanup'):
            self.history.append(previous)
            if len(self.history) > 20:
                del self.history[:-20]

        if (self.repeat_mode == RepeatMode.ALL
                and reason not in ('loadfailed', 'cleanup')
                and len(self.tracks) < MAX_PENDING_TRACKS):
            self.tracks.append(previous)
        self.current = None
        if self.tracks:
            await self._play(self.tracks.pop(0))
        else:
            await self._cleanup()

    # ------------------------------------------------------------------ queue ops

    async def enqueue(self, track: Track) -> None:
        await self.enqueue_many([track])

    async def enqueue_many(self, tracks: list[Track]) -> None:
        if not tracks:
            return
        async with self._advance_lock:
            idle = not self._vl_player.is_playing and not self._vl_player.is_paused and not self.current
            incoming_pending = len(tracks) - int(idle)
            if len(self.tracks) + incoming_pending > MAX_PENDING_TRACKS:
                raise QueueFullError(f'Queue is full (maximum {MAX_PENDING_TRACKS} waiting tracks).')
            if idle:
                first, *rest = tracks
                self.tracks.extend(rest)
                await self._play(first)
            else:
                self.tracks.extend(tracks)

    async def snapshot_tracks(self) -> list[Track]:
        """Take a consistent current+queue snapshot for saved playlists."""
        async with self._advance_lock:
            return ([self.current] if self.current else []) + list(self.tracks)

    # ------------------------------------------------------------------ controls

    async def skip(self) -> None:
        """Skip immediately; do not rely on a STOPPED event from Lavalink."""
        async with self._advance_lock:
            if self.current is None:
                return
            ended_track = self.current._vl_track
            await self._vl_player.stop()
            await self._advance_locked(reason='stopped', ended_track=ended_track)

    async def skip_to(self, position: int) -> None:
        """Jump to a 1-based waiting track, atomically with the stop request."""
        async with self._advance_lock:
            if not 1 <= position <= len(self.tracks):
                raise IndexError('Queue position out of range')
            if self.current is not None:
                ended_track = self.current._vl_track
                await self._vl_player.stop()
                self.tracks = self.tracks[position - 1:]
                await self._advance_locked(reason='stopped', ended_track=ended_track)
            else:
                self.tracks = self.tracks[position - 1:]
                await self._play(self.tracks.pop(0))

    async def back(self) -> None:
        """Play previous history entry without waiting for a node end event."""
        async with self._advance_lock:
            if not self.history:
                return
            if self.current is not None:
                ended_track = self.current._vl_track
                await self._vl_player.stop()
                self.tracks.insert(0, self.history.pop())
                await self._advance_locked(reason='stopped', ended_track=ended_track)
            else:
                await self._play(self.history.pop())

    async def pause(self) -> None:
        await self._vl_player.set_pause(True)
        self.paused = True

    async def resume(self) -> None:
        await self._vl_player.set_pause(False)
        self.paused = False

    async def stop(self) -> None:
        async with self._advance_lock:
            # Preserve the queue if Lavalink refuses the stop request.
            # A subsequent retry should not lose every waiting track.
            await self._vl_player.stop()
            self.tracks = []
            self.repeat_mode = RepeatMode.OFF
            self.current = None
            self.paused = False
            await self._disable_controller()

    async def set_volume(self, vol: int) -> None:
        target = max(1, min(100, vol))
        await self._vl_player.set_volume(target)
        self._volume = target

    async def set_filter(self, filter_name: str) -> bool:
        if filter_name not in FILTERS:
            return False
        if filter_name == 'none':
            await self._vl_player.reset_filters()
        else:
            await self._apply_filters(filter_name)
        self.filter = filter_name
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
        if not 1 <= from_pos <= len(self.tracks):
            raise IndexError('Source queue position is out of range')
        if not 1 <= to_pos <= len(self.tracks):
            raise IndexError('Destination queue position is out of range')
        if from_pos == to_pos:
            return
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
