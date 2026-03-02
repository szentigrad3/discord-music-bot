from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

import discord

from .player import MusicPlayer
from .track import Track

if TYPE_CHECKING:
    from discord.ext import commands


async def get_or_create_player(
    guild: discord.Guild,
    voice_channel: discord.VoiceChannel,
    text_channel: discord.abc.Messageable,
    bot: commands.Bot,
) -> MusicPlayer:
    guild_id = str(guild.id)
    if guild_id in bot.queues:
        return bot.queues[guild_id]

    voice_client = guild.voice_client
    if voice_client and voice_client.is_connected():
        if voice_client.channel.id != voice_channel.id:
            await voice_client.move_to(voice_channel)
    else:
        voice_client = await voice_channel.connect(self_deaf=True)

    player = MusicPlayer(guild, voice_client, text_channel, bot)
    bot.queues[guild_id] = player
    return player


async def resolve_tracks(query: str, requested_by: str | None = None) -> list[Track]:
    if re.search(r'open\.spotify\.com/(track|album|playlist)/', query):
        return await _resolve_spotify(query, requested_by)

    if re.search(r'youtube\.com/playlist\?list=|[?&]list=', query):
        return await _resolve_youtube_playlist(query, requested_by)

    return await _resolve_youtube(query, requested_by)


async def _resolve_youtube(query: str, requested_by: str | None) -> list[Track]:
    import yt_dlp

    is_url = query.startswith('http://') or query.startswith('https://')
    target = query if is_url else f'ytsearch:{query}'

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'add_header': ['referer:youtube.com', 'user-agent:googlebot'],
    }

    loop = asyncio.get_event_loop()

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(target, download=False)

    try:
        info = await loop.run_in_executor(None, _extract)
    except Exception as e:
        raise RuntimeError(f'Could not find: {query} — {e}') from e

    if 'entries' in info:
        entry = info['entries'][0] if info['entries'] else None
        if not entry:
            raise RuntimeError(f'No results found for: {query}')
        return [Track.from_ytdlp_info(entry, requested_by)]

    return [Track.from_ytdlp_info(info, requested_by)]


async def _resolve_youtube_playlist(url: str, requested_by: str | None) -> list[Track]:
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'playlistend': 50,
    }

    loop = asyncio.get_event_loop()

    def _extract():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        info = await loop.run_in_executor(None, _extract)
    except Exception as e:
        raise RuntimeError(f'Failed to load playlist: {e}') from e

    entries = info.get('entries') or [info]
    tracks = []
    for e in entries[:50]:
        video_id = e.get('id')
        video_url = (
            e.get('url')
            or e.get('webpage_url')
            or (f'https://www.youtube.com/watch?v={video_id}' if video_id else None)
        )
        if not video_url:
            continue
        thumbnails = e.get('thumbnails') or []
        thumbnail = e.get('thumbnail') or (thumbnails[0].get('url') if thumbnails else None)
        tracks.append(Track(
            title=e.get('title') or 'Unknown',
            url=video_url,
            duration=Track.format_duration(e.get('duration')),
            thumbnail=thumbnail,
            requested_by=requested_by,
        ))
    return tracks


_spotify_access_token: str | None = None
_spotify_token_expiry: float = 0.0


async def _ensure_spotify_token() -> bool:
    import os
    import time
    import aiohttp

    global _spotify_access_token, _spotify_token_expiry

    client_id = os.getenv('SPOTIFY_CLIENT_ID')
    client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    if not client_id or not client_secret:
        return False

    if time.time() < _spotify_token_expiry:
        return True

    import base64
    credentials = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                'https://accounts.spotify.com/api/token',
                headers={
                    'Authorization': f'Basic {credentials}',
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                data='grant_type=client_credentials',
            ) as resp:
                if not resp.ok:
                    raise RuntimeError(f'Spotify token request failed: {resp.status}')
                data = await resp.json()
                _spotify_access_token = data['access_token']
                _spotify_token_expiry = time.time() + data['expires_in'] - 60
                return True
    except Exception as e:
        print(f'[Spotify] Failed to get token: {e}')
        return False


async def _spotify_get(path: str) -> dict:
    import aiohttp

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f'https://api.spotify.com/v1{path}',
            headers={'Authorization': f'Bearer {_spotify_access_token}'},
        ) as resp:
            if not resp.ok:
                raise RuntimeError(f'Spotify API error: {resp.status} {resp.reason} ({path})')
            return await resp.json()


async def _resolve_spotify(url: str, requested_by: str | None) -> list[Track]:
    ok = await _ensure_spotify_token()
    if not ok:
        raise RuntimeError('Spotify support is not configured.')

    track_match = re.search(r'open\.spotify\.com/track/([A-Za-z0-9]+)', url)
    album_match = re.search(r'open\.spotify\.com/album/([A-Za-z0-9]+)', url)
    playlist_match = re.search(r'open\.spotify\.com/playlist/([A-Za-z0-9]+)', url)

    track_names: list[str] = []

    if track_match:
        t = await _spotify_get(f'/tracks/{track_match.group(1)}')
        track_names.append(f'{t["artists"][0]["name"]} {t["name"]}')
    elif album_match:
        data = await _spotify_get(f'/albums/{album_match.group(1)}/tracks?limit=50')
        for t in data['items'][:50]:
            track_names.append(f'{t["artists"][0]["name"]} {t["name"]}')
    elif playlist_match:
        data = await _spotify_get(f'/playlists/{playlist_match.group(1)}/tracks?limit=50')
        for item in data['items'][:50]:
            if item.get('track'):
                t = item['track']
                track_names.append(f'{t["artists"][0]["name"]} {t["name"]}')
    else:
        raise RuntimeError('Unsupported Spotify URL.')

    tracks: list[Track] = []
    for name in track_names:
        try:
            resolved = await _resolve_youtube(name, requested_by)
            tracks.extend(resolved)
        except Exception:
            pass
    return tracks
