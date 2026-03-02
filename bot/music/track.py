from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import wavelink


class Track:
    """Represents a single music track."""

    def __init__(
        self,
        title: str,
        url: str,
        duration: str,
        thumbnail: str | None = None,
        requested_by: str | None = None,
    ):
        self.title = title
        self.url = url
        self.duration = duration or 'Unknown'
        self.thumbnail = thumbnail
        self.requested_by = requested_by

    @staticmethod
    def format_duration(milliseconds) -> str:
        if not milliseconds:
            return 'Live'
        try:
            seconds = float(milliseconds) / 1000
        except (TypeError, ValueError):
            return 'Live'
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f'{h}:{m:02d}:{s:02d}'
        return f'{m}:{s:02d}'

    @classmethod
    def from_wavelink(cls, track: wavelink.Playable, requested_by: str | None = None) -> 'Track':
        return cls(
            title=track.title or 'Unknown Title',
            url=track.uri or '',
            duration=cls.format_duration(track.length),
            thumbnail=track.artwork,
            requested_by=requested_by,
        )
