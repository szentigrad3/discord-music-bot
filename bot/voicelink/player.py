"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import time
import logging

from typing import Any, Dict, List, Optional, Union

from discord import (
    Client,
    Guild,
    VoiceChannel,
    VoiceProtocol,
)

from . import events
from .enums import RequestMethod
from .events import TrackEndEvent, TrackStartEvent, TrackExceptionEvent
from .filters import Filter, Filters
from .objects import Track
from .exceptions import NodeException
from .pool import Node, NodePool


class Player(VoiceProtocol):
    """The base player class for Voicelink.

    In order to initiate a player, you must pass it in as a cls when you connect to a channel::

        await channel.connect(cls=voicelink.Player(bot, channel))
    """

    def __call__(self, client: Client, channel: VoiceChannel):
        self.client: Client = client
        self.channel: VoiceChannel = channel
        return self

    def __init__(
        self,
        client: Optional[Client] = None,
        channel: Optional[VoiceChannel] = None,
    ):
        self.client: Client = client
        self._bot: Client = client
        self.channel: VoiceChannel = channel
        self._guild: Optional[Guild] = channel.guild if channel else None

        self._node: Node = NodePool.get_node()
        self._current: Optional[Track] = None
        self._filters: Filters = Filters()
        self._paused: bool = False
        self._is_connected: bool = False
        self._volume: int = 100

        self._position: int = 0
        self._last_position: int = 0
        self._last_update: int = 0
        self._ending_track: Optional[Track] = None
        self._voice_state: dict = {}

        self._logger: Optional[logging.Logger] = self._node._logger

    def __repr__(self):
        return (
            f"<Voicelink.player bot={self.bot} guildId={self.guild.id} "
            f"is_connected={self.is_connected} is_playing={self.is_playing}>"
        )

    # ------------------------------------------------------------------ properties

    @property
    def position(self) -> float:
        """Returns the player's position in the current track in milliseconds."""
        if not self.is_playing or not self._current:
            return 0
        if self.is_paused:
            return min(self._last_position, self._current.length)
        difference = (time.time() * 1000) - self._last_update
        position = self._last_position + difference
        if position > self._current.length:
            return 0
        return min(position, self._current.length)

    @property
    def is_playing(self) -> bool:
        return self._is_connected and self._current is not None

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def is_paused(self) -> bool:
        return self._is_connected and self._paused

    @property
    def current(self) -> Optional[Track]:
        return self._current

    @property
    def node(self) -> Node:
        return self._node

    @property
    def guild(self) -> Optional[Guild]:
        return self._guild

    @property
    def volume(self) -> int:
        return self._volume

    @property
    def filters(self) -> Filters:
        return self._filters

    @property
    def bot(self) -> Client:
        return self._bot

    @property
    def is_dead(self) -> bool:
        return self._guild is not None and self._guild.id not in self._node._players

    # ------------------------------------------------------------------ internal

    async def send(self, method: RequestMethod, query: str = None, data: Union[Dict, str] = {}) -> Dict:
        uri: str = f"sessions/{self._node._session_id}/players/{self._guild.id}" + (f"?{query}" if query else "")
        return await self._node.send(method, query=uri, data=data)

    async def _update_state(self, data: dict) -> None:
        state: dict = data.get("state")
        self._last_update = time.time() * 1000
        self._is_connected = state.get("connected")
        self._last_position = state.get("position")

    async def _dispatch_voice_update(self, voice_data: Dict[str, Any] = None) -> None:
        if not self._node._session_id:
            return
        if not all(k in self._voice_state for k in ("sessionId", "channelId", "event")):
            return
        state = voice_data or self._voice_state
        endpoint = state['event'].get('endpoint')
        if not endpoint:
            return
        if "://" in endpoint:
            endpoint = endpoint.split("://", 1)[1]
        token = state['event'].get('token')
        session_id = state.get('sessionId')
        channel_id = state.get('channelId')
        if not token or not session_id or not channel_id:
            return
        data = {
            "token": str(token),
            "endpoint": str(endpoint),
            "sessionId": str(session_id),
            "channelId": str(channel_id),
        }
        try:
            await self.send(method=RequestMethod.PATCH, data={"voice": data})
        except NodeException as e:
            self._logger.warning(f"Failed to dispatch voice update for guild {self._guild.id}: {e}")

    async def on_voice_server_update(self, data: dict) -> None:
        self._voice_state.update({"event": data})
        await self._dispatch_voice_update(self._voice_state)

    async def on_voice_state_update(self, data: dict) -> None:
        self._voice_state.update({
            "sessionId": data.get("session_id"),
            "channelId": data.get("channel_id"),
        })
        if not (channel_id := data.get("channel_id")):
            await self.teardown()
            self._voice_state.clear()
            return
        self.channel = self.guild.get_channel(int(channel_id))
        if not data.get("token"):
            # If VOICE_SERVER_UPDATE already arrived (event is present), dispatch
            # now that we have the fresh Discord session ID.
            if "event" in self._voice_state:
                await self._dispatch_voice_update(self._voice_state)
            return
        await self._dispatch_voice_update({**self._voice_state, "event": data})

    async def _dispatch_event(self, data: dict) -> None:
        event_type = data.get("type")
        event = getattr(events, event_type)(data, self)

        if isinstance(event, TrackEndEvent) and event.reason != "replaced":
            self._current = None

        if isinstance(event, TrackExceptionEvent):
            if self._node.yt_ratelimit:
                msg = event.exception.get("message", "")
                if msg == "This content isn't available.":
                    await self._node.yt_ratelimit.flag_active_token()

        event.dispatch(self._bot)

        if isinstance(event, TrackStartEvent):
            self._ending_track = self._current

    # ------------------------------------------------------------------ playback

    async def connect(
        self,
        *,
        timeout: float = 0.0,
        reconnect: bool = True,
        self_deaf: bool = True,
        self_mute: bool = False,
    ) -> None:
        self._voice_state.clear()
        await self.guild.change_voice_state(channel=self.channel, self_deaf=self_deaf, self_mute=self_mute)
        self._node._players[self.guild.id] = self
        self._is_connected = True

    async def stop(self) -> None:
        """Stops the currently playing track."""
        self._current = None
        await self.send(method=RequestMethod.PATCH, data={'encodedTrack': None})

    async def disconnect(self, *, force: bool = False) -> None:
        """Disconnects the player from voice."""
        try:
            await self.guild.change_voice_state(channel=None)
        finally:
            self.cleanup()
            self._is_connected = False
            self.channel = None

    async def destroy(self) -> None:
        """Disconnects and destroys the player."""
        try:
            await self.disconnect()
        except Exception:
            assert self.channel is None and not self.is_connected

        self._node._players.pop(self.guild.id, None)
        await self.send(method=RequestMethod.DELETE)

    async def teardown(self) -> None:
        """Cleans up and destroys the player."""
        try:
            await self.destroy()
        except Exception:
            pass

    async def play(
        self,
        track: Track,
        *,
        start: int = 0,
        end: int = 0,
        ignore_if_playing: bool = False,
    ) -> Track:
        """Plays a track."""
        data: Dict[str, Any] = {
            "encodedTrack": track.track_id,
            "position": start or 0,
            "volume": self._volume,
        }
        if end or getattr(track, 'end_time', None):
            data["endTime"] = end or track.end_time

        await self.send(
            method=RequestMethod.PATCH,
            query=f"noReplace={'true' if ignore_if_playing else 'false'}",
            data=data,
        )
        if self._node.yt_ratelimit:
            await self._node.yt_ratelimit.handle_request()

        self._current = track
        return self._current

    async def seek(self, position: float) -> float:
        """Seeks to a position in the currently playing track (milliseconds)."""
        await self.send(method=RequestMethod.PATCH, data={"position": position})
        return position

    async def set_pause(self, pause: bool) -> bool:
        """Sets the pause state of the currently playing track."""
        self._paused = pause
        await self.send(method=RequestMethod.PATCH, data={"paused": pause})
        return self._paused

    async def set_volume(self, volume: int) -> int:
        """Sets the volume of the player (0-1000, Lavalink accepts 0-500)."""
        self._volume = volume
        await self.send(method=RequestMethod.PATCH, data={"volume": volume})
        return self._volume

    async def move_to(self, channel: VoiceChannel) -> None:
        """Moves the player to a different voice channel."""
        self.channel = channel
        await self.guild.change_voice_state(channel=channel, self_deaf=True)

    async def add_filter(self, filter: Filter, fast_apply: bool = False) -> Filters:
        """Adds a filter to the player's audio stream."""
        self._filters.add_filter(filter=filter)
        payload = self._filters.get_all_payloads()
        await self.send(method=RequestMethod.PATCH, data={"filters": payload})
        if fast_apply:
            await self.seek(self.position)
        return self._filters

    async def remove_filter(self, filter_tag: str, fast_apply: bool = False) -> Filters:
        """Removes a filter from the player's audio stream."""
        self._filters.remove_filter(filter_tag=filter_tag)
        payload = self._filters.get_all_payloads()
        await self.send(method=RequestMethod.PATCH, data={"filters": payload})
        if fast_apply:
            await self.seek(self.position)
        return self._filters

    async def reset_filters(self, fast_apply: bool = False) -> Filters:
        """Clears all active filters."""
        self._filters.reset_filters()
        await self.send(method=RequestMethod.PATCH, data={"filters": {}})
        if fast_apply:
            await self.seek(self.position)
        return self._filters
