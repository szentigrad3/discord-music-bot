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

__version__ = "1.4"
__author__ = 'Vocard Development, ChocoMeow'
__license__ = "MIT"
__copyright__ = "Copyright 2023 - present (c) Vocard Development, ChocoMeow"

from .enums import SearchType, LoopType, RequestMethod, NodeAlgorithm
from .events import (
    VoicelinkEvent,
    TrackStartEvent,
    TrackEndEvent,
    TrackStuckEvent,
    TrackExceptionEvent,
    WebSocketClosedEvent,
    WebSocketOpenEvent,
)
from .exceptions import (
    VoicelinkException,
    NodeException,
    NodeCreationError,
    NodeConnectionFailure,
    NodeConnectionClosed,
    NodeNotAvailable,
    NoNodesAvailable,
    TrackInvalidPosition,
    TrackLoadError,
    FilterInvalidArgument,
    FilterTagAlreadyInUse,
    FilterTagInvalid,
    QueueFull,
    OutofList,
    DuplicateTrack,
)
from .filters import (
    Filter,
    Filters,
    Equalizer,
    Timescale,
    Karaoke,
    Tremolo,
    Vibrato,
    Rotation,
    LowPass,
)
from .objects import Track, Playlist
from .player import Player
from .pool import Node, NodePool
from .transformer import encode, decode
