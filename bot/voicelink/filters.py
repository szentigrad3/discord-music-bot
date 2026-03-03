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

import collections
from .exceptions import FilterInvalidArgument, FilterTagAlreadyInUse, FilterTagInvalid

from typing import (
    Dict,
    List
)

class Filter:
    def __init__(self):
        self.payload: Dict = None
        self.scope: Dict = None
        self.tag: str = None

    def _init_with_scope(self, scope: Dict, **kwargs):
        self.scope = scope
        for prop, (min_val, max_val) in scope.items():
            setattr(self, prop, kwargs.get(prop, scope[prop][0]))
            if not min_val <= getattr(self, prop) <= max_val:
                raise FilterInvalidArgument(f"{self.__class__.__name__} {prop} must be between {min_val} and {max_val}.")
        self.tag = kwargs.get("tag")
        self.payload = {self.__class__.__name__.lower(): {prop: getattr(self, prop) for prop in scope}}

class Filters:
    def __init__(self) -> None:
        self._filters: List[Filter] = []

    def add_filter(self, *, filter: Filter) -> None:
        if self.has_filter(filter_tag=filter.tag):
            raise FilterTagAlreadyInUse("A filter with that tag is already in use")
        self._filters.append(filter)

    def remove_filter(self, *, filter_tag: str) -> None:
        if not self.has_filter(filter_tag=filter_tag):
            raise FilterTagInvalid("A filter with that tag was not found.")
        for index, f in enumerate(self._filters):
            if f.tag == filter_tag:
                del self._filters[index]
                return

    def has_filter(self, *, filter_tag: str) -> bool:
        return any(f for f in self._filters if f.tag == filter_tag)

    def reset_filters(self) -> None:
        self._filters = []

    def get_all_payloads(self) -> dict:
        payload = {}
        for f in self._filters:
            payload.update(f.payload)
        return payload

    def get_filters(self) -> List[Filter]:
        return self._filters


class Equalizer(Filter):
    def __init__(self, *, tag: str = "equalizer", levels: list):
        super().__init__()
        self.eq = self._factory(levels)
        self.raw = levels
        self.payload = {"equalizer": self.eq}
        self.tag = tag

    def _factory(self, levels: list):
        _dict = collections.defaultdict(int)
        _dict.update(levels)
        _dict = [{"band": i, "gain": _dict[i]} for i in range(15)]
        return _dict

    @classmethod
    def boost(cls):
        levels = [
            (0, -0.075), (1, 0.125), (2, 0.125), (3, 0.1), (4, 0.1),
            (5, .05), (6, 0.075), (7, 0.0), (8, 0.0), (9, 0.0),
            (10, 0.0), (11, 0.0), (12, 0.125), (13, 0.15), (14, 0.05)
        ]
        return cls(tag="boost", levels=levels)


class Timescale(Filter):
    def __init__(
        self,
        *,
        tag: str = "timescale",
        speed: float = 1.0,
        pitch: float = 1.0,
        rate: float = 1.0
    ):
        super().__init__()
        self._init_with_scope({
            "speed": [0, 5],
            "pitch": [0, 5],
            "rate": [0, 5]
        }, tag=tag, speed=speed, pitch=pitch, rate=rate)

    @classmethod
    def nightcore(cls):
        return cls(tag="nightcore", speed=1.25, pitch=1.3)

    @classmethod
    def vaporwave(cls):
        return cls(tag="vaporwave", speed=0.8, pitch=0.8)


class Karaoke(Filter):
    def __init__(
        self,
        *,
        tag: str = "karaoke",
        level: float = 1.0,
        mono_level: float = 1.0,
        filter_band: float = 220.0,
        filter_width: float = 100.0
    ):
        super().__init__()
        self._init_with_scope({
            "level": [0, 5],
            "monoLevel": [0, 5],
            "filterBand": [0, 500],
            "filterWidth": [0, 300]
        }, tag=tag, level=level, mono_level=mono_level, filter_band=filter_band, filter_width=filter_width)


class Tremolo(Filter):
    def __init__(self, *, tag: str = "tremolo", frequency: float = 2.0, depth: float = 0.5):
        super().__init__()
        self._init_with_scope({
            "frequency": [0, 5],
            "depth": [0, 1]
        }, tag=tag, frequency=frequency, depth=depth)


class Vibrato(Filter):
    def __init__(self, *, tag: str = "vibrato", frequency: float = 2.0, depth: float = 0.5):
        super().__init__()
        self._init_with_scope({
            "frequency": [0, 14],
            "depth": [0, 1]
        }, tag=tag, frequency=frequency, depth=depth)


class Rotation(Filter):
    def __init__(self, *, tag: str = "rotation", rotation_hertz: float = 5):
        super().__init__()
        self._init_with_scope({
            "rotationHz": [0, 10]
        }, tag=tag, rotationHz=rotation_hertz)

    @classmethod
    def nightD(cls):
        return cls(tag="8d", rotation_hertz=0.2)


class LowPass(Filter):
    def __init__(self, *, tag: str = "lowpass", smoothing: float = 20):
        super().__init__()
        self._init_with_scope({
            "smoothing": [0, 100]
        }, tag=tag, smoothing=smoothing)
