from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from bot.voicelink import Track as VoicelinkTrack


class Track:
    """Represents a single music track."""

    def __init__(
        self,
        title: str,
        url: str,
        duration: str,
        thumbnail: str | None = None,
        requested_by: str | None = None,
        author: str | None = None,
        source: str | None = None,
        _vl_track: Optional[VoicelinkTrack] = None,
    ):
        self.title = title
        self.url = url
        self.duration = duration or 'Unknown'
        self.thumbnail = thumbnail
        self.requested_by = requested_by
        self.author = author
        self.source = source
        # Reference to the original voicelink Track (holds the encoded track_id for Lavalink)
        self._vl_track: Optional[VoicelinkTrack] = _vl_track

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
    def from_voicelink(cls, track: VoicelinkTrack, requested_by: str | None = None) -> 'Track':
        """Create a Track from a voicelink Track object."""
        return cls(
            title=track.title or 'Unknown Title',
            url=track.uri or '',
            duration=cls.format_duration(track.length),
            thumbnail=track.thumbnail,
            requested_by=requested_by,
            author=getattr(track, 'author', None),
            source=getattr(track, 'source', None),
            _vl_track=track,
        )
