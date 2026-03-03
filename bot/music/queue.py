from __future__ import annotations

import re
from typing import TYPE_CHECKING

import discord
import wavelink

from bot.logger import get_logger
from .player import MusicPlayer
from .track import Track

if TYPE_CHECKING:
    from discord.ext import commands

logger = get_logger(__name__)


async def get_or_create_player(
    guild: discord.Guild,
    voice_channel: discord.VoiceChannel,
    text_channel: discord.abc.Messageable,
    bot: commands.Bot,
) -> MusicPlayer:
    guild_id = str(guild.id)
    if guild_id in bot.queues:
        existing: MusicPlayer = bot.queues[guild_id]
        # Move to new channel if needed
        if existing._wl_player.channel and existing._wl_player.channel.id != voice_channel.id:
            await existing._wl_player.move_to(voice_channel)
        return existing

    wl_player: wavelink.Player = await voice_channel.connect(cls=wavelink.Player, self_deaf=True)
    player = MusicPlayer(guild, wl_player, text_channel, bot)
    bot.queues[guild_id] = player
    return player


async def resolve_tracks(query: str, requested_by: str | None = None) -> list[Track]:
    if re.search(r'open\.spotify\.com/(track|album|playlist)/', query):
        return await _resolve_spotify(query, requested_by)

    return await _resolve_via_wavelink(query, requested_by)


async def _resolve_via_wavelink(query: str, requested_by: str | None) -> list[Track]:
    is_url = query.startswith('http://') or query.startswith('https://')
    search_query = query if is_url else f'ytsearch:{query}'

    try:
        results: wavelink.Search = await wavelink.Playable.search(search_query)
    except Exception as e:
        raise RuntimeError(f'Could not find: {query} — {e}') from e

    if not results:
        raise RuntimeError(f'No results found for: {query}')

    if isinstance(results, wavelink.Playlist):
        return [Track.from_wavelink(t, requested_by) for t in results.tracks[:50]]

    # Single track or search result — return only the first match
    return [Track.from_wavelink(results[0], requested_by)]


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
        logger.error('[Spotify] Failed to get token: %s', e)
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
            resolved = await _resolve_via_wavelink(name, requested_by)
            tracks.extend(resolved)
        except Exception:
            pass
    return tracks
