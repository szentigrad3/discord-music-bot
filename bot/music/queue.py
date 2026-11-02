from __future__ import annotations

import asyncio
import re
from weakref import WeakValueDictionary
from urllib.parse import urlsplit
from typing import TYPE_CHECKING

import discord

from bot.logger import get_logger
from bot.voicelink import NodePool, Player as VoicelinkPlayer, Playlist as VoicelinkPlaylist
from bot.voicelink.enums import SearchType
from .player import MusicPlayer
from .track import Track

if TYPE_CHECKING:
    from discord.ext import commands

logger = get_logger(__name__)


# A weak mapping avoids retaining idle guild locks indefinitely. Each active
# caller holds a strong reference to its lock for the duration of the request.
_connect_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()


def _get_connect_lock(guild_id: str) -> asyncio.Lock:
    lock = _connect_locks.get(guild_id)
    if lock is None:
        lock = asyncio.Lock()
        _connect_locks[guild_id] = lock
    return lock


async def get_or_create_player(
    guild: discord.Guild,
    voice_channel: discord.VoiceChannel,
    text_channel: discord.abc.Messageable,
    bot: commands.Bot,
) -> MusicPlayer:
    guild_id = str(guild.id)
    async with _get_connect_lock(guild_id):
        if guild_id in bot.queues:
            existing: MusicPlayer = bot.queues[guild_id]
            if existing._vl_player.channel and existing._vl_player.channel.id != voice_channel.id:
                await existing._vl_player.move_to(voice_channel)
            return existing

        vl_player: VoicelinkPlayer = await voice_channel.connect(
            cls=VoicelinkPlayer(bot, voice_channel), self_deaf=True
        )
        player = MusicPlayer(guild, vl_player, text_channel, bot)
        bot.queues[guild_id] = player
        return player


def _spotify_link(query: str) -> tuple[str, str] | None:
    """Accept only genuine Spotify album, playlist and track URLs."""
    try:
        url = urlsplit(query.strip())
        if url.scheme not in ('http', 'https') or url.hostname != 'open.spotify.com':
            return None
    except ValueError:
        return None
    match = re.fullmatch(r'/(track|album|playlist)/([A-Za-z0-9]+)/?', url.path)
    return (match.group(1), match.group(2)) if match else None


async def resolve_tracks(query: str, requested_by: str | None = None) -> list[Track]:
    if _spotify_link(query):
        return await _resolve_spotify(query, requested_by)

    return await _resolve_via_voicelink(query, requested_by)


async def _resolve_via_voicelink(query: str, requested_by: str | None) -> list[Track]:
    is_url = query.startswith('http://') or query.startswith('https://')
    search_query = query if is_url else f'ytsearch:{query}'

    try:
        node = NodePool.get_node()
        results = await node.get_tracks(search_query, requester=None, search_type=SearchType.YOUTUBE)
    except Exception as e:
        raise RuntimeError(f'Could not find: {query} — {e}') from e

    if not results:
        raise RuntimeError(f'No results found for: {query}')

    if isinstance(results, VoicelinkPlaylist):
        return [Track.from_voicelink(t, requested_by) for t in results.tracks[:50]]

    # Single track or search result — return only the first match
    return [Track.from_voicelink(results[0], requested_by)]


_spotify_access_token: str | None = None
_spotify_token_expiry: float = 0.0
_spotify_token_lock = asyncio.Lock()


async def _ensure_spotify_token() -> bool:
    """Refresh Spotify credentials once when many requests arrive together."""
    import base64
    import time
    import aiohttp

    from bot.settings import settings

    global _spotify_access_token, _spotify_token_expiry

    client_id = settings.spotify_client_id
    client_secret = settings.spotify_client_secret
    if not client_id or not client_secret:
        return False

    async with _spotify_token_lock:
        if _spotify_access_token and time.monotonic() < _spotify_token_expiry:
            return True

        credentials = base64.b64encode(
            f'{client_id}:{client_secret}'.encode()
        ).decode()
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=15)
            ) as session:
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
            token = data.get('access_token')
            expires = int(data.get('expires_in', 0))
            if not isinstance(token, str) or not token or expires <= 0:
                raise ValueError('Spotify token response was invalid.')
            _spotify_access_token = token
            # Refresh before expiry, using a monotonic clock.
            _spotify_token_expiry = time.monotonic() + max(1, expires - 60)
            return True
        except Exception as exc:
            logger.warning('[Spotify] Cannot refresh client token: %s',
                           type(exc).__name__)
            return False


async def _spotify_get(path: str) -> dict:
    import aiohttp

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
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

    link = _spotify_link(url)
    if link is None:
        raise RuntimeError('Unsupported Spotify URL.')
    kind, identifier = link
    track_names: list[str] = []

    if kind == 'track':
        t = await _spotify_get(f'/tracks/{identifier}')
        track_names.append(f'{t["artists"][0]["name"]} {t["name"]}')
    elif kind == 'album':
        data = await _spotify_get(f'/albums/{identifier}/tracks?limit=50')
        for t in data['items'][:50]:
            if t.get('artists') and t.get('name'):
                track_names.append(f'{t["artists"][0]["name"]} {t["name"]}')
    elif kind == 'playlist':
        data = await _spotify_get(f'/playlists/{identifier}/tracks?limit=50')
        for item in data['items'][:50]:
            t = item.get('track') if isinstance(item, dict) else None
            if isinstance(t, dict) and t.get('artists') and t.get('name'):
                track_names.append(f'{t["artists"][0]["name"]} {t["name"]}')

    if not track_names:
        raise RuntimeError('The Spotify link contains no playable tracks.')

    # Keep the API load bounded; preserve playlist order even when calls finish
    # in a different order. Unavailable entries can be skipped individually.
    limit = asyncio.Semaphore(3)

    async def resolve_one(name: str) -> list[Track]:
        async with limit:
            try:
                return await _resolve_via_voicelink(name, requested_by)
            except Exception as exc:
                logger.warning('[Spotify] Cannot resolve %r: %s', name, exc)
                return []

    resolved_groups = await asyncio.gather(*(resolve_one(name) for name in track_names))
    tracks = [track for group in resolved_groups for track in group]
    if not tracks:
        raise RuntimeError('No playable matches were found for this Spotify link.')
    return tracks[:50]
