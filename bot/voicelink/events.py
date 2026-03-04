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

from .pool import NodePool
from discord.ext.commands import Bot
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .player import Player


class VoicelinkEvent:
    """The base class for all events dispatched by a node."""
    name = "event"
    handler_args = ()

    def dispatch(self, bot: Bot):
        bot.dispatch(f"voicelink_{self.name}", *self.handler_args)


class TrackStartEvent(VoicelinkEvent):
    name = "track_start"

    def __init__(self, data: dict, player: Player):
        self.player: Player = player
        self.track = self.player._current
        self.handler_args = self.player, self.track


class TrackEndEvent(VoicelinkEvent):
    name = "track_end"

    def __init__(self, data: dict, player: Player):
        self.player: Player = player
        self.track = self.player._ending_track
        self.reason: str = data["reason"]
        self.handler_args = self.player, self.track, self.reason


class TrackStuckEvent(VoicelinkEvent):
    name = "track_stuck"

    def __init__(self, data: dict, player: Player):
        self.player: Player = player
        self.track = self.player._ending_track
        self.threshold: float = data["thresholdMs"]
        self.handler_args = self.player, self.track, self.threshold


class TrackExceptionEvent(VoicelinkEvent):
    name = "track_exception"

    def __init__(self, data: dict, player: Player):
        self.player: Player = player
        self.track = self.player._ending_track
        self.exception: dict = data.get("exception", {
            "severity": "",
            "message": "",
            "cause": ""
        })
        self.handler_args = self.player, self.track, self.exception


class WebSocketClosedPayload:
    def __init__(self, data: dict):
        self.guild = NodePool.get_node().bot.get_guild(int(data["guildId"]))
        self.code: int = data["code"]
        self.reason: str = data["reason"]
        self.by_remote: bool = data["byRemote"]


class WebSocketClosedEvent(VoicelinkEvent):
    name = "websocket_closed"

    def __init__(self, data: dict, _):
        self.payload = WebSocketClosedPayload(data)
        self.handler_args = self.payload,


class WebSocketOpenEvent(VoicelinkEvent):
    name = "websocket_open"

    def __init__(self, data: dict, _):
        self.target: str = data["target"]
        self.ssrc: int = data["ssrc"]
        self.handler_args = self.target, self.ssrc
