from __future__ import annotations


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
    def format_duration(seconds) -> str:
        if not seconds:
            return 'Live'
        try:
            seconds = float(seconds)
        except (TypeError, ValueError):
            return 'Live'
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f'{h}:{m:02d}:{s:02d}'
        return f'{m}:{s:02d}'

    @classmethod
    def from_ytdlp_info(cls, info: dict, requested_by: str | None = None) -> 'Track':
        thumbnails = info.get('thumbnails') or []
        thumbnail = info.get('thumbnail') or (thumbnails[0].get('url') if thumbnails else None)
        return cls(
            title=info.get('title') or 'Unknown Title',
            url=info.get('webpage_url') or info.get('url') or '',
            duration=cls.format_duration(info.get('duration')),
            thumbnail=thumbnail,
            requested_by=requested_by,
        )
