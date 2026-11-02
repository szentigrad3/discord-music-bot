from __future__ import annotations

import asyncio
import json
import os
import re
from urllib.parse import urlsplit

import aiosqlite

from bot.settings import settings

_DATABASE_URL: str = ''


def _get_db_path() -> str:
    global _DATABASE_URL
    if not _DATABASE_URL:
        _DATABASE_URL = settings.database_url.replace('file:', '', 1)
    return _DATABASE_URL


async def init_db() -> None:
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS GuildSettings (
                guildId            TEXT    NOT NULL PRIMARY KEY,
                prefix             TEXT    NOT NULL DEFAULT '!',
                language           TEXT    NOT NULL DEFAULT 'en',
                defaultVolume      INTEGER NOT NULL DEFAULT 80,
                djRoleId           TEXT,
                announceNowPlaying BOOLEAN NOT NULL DEFAULT 1
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS SavedPlaylists (
                guildId TEXT NOT NULL,
                userId TEXT NOT NULL,
                nameKey TEXT NOT NULL,
                displayName TEXT NOT NULL,
                tracksJson TEXT NOT NULL,
                updatedAt TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guildId, userId, nameKey)
            )
            """
        )
        await db.commit()


async def get_guild_settings(guild_id: str) -> dict:
    db_path = _get_db_path()
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            'SELECT * FROM GuildSettings WHERE guildId = ?', (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            return dict(row)

        # Create default settings
        # Two slash commands can initialize a new guild simultaneously.
        await db.execute(
            'INSERT OR IGNORE INTO GuildSettings (guildId) VALUES (?)', (guild_id,)
        )
        await db.commit()
        async with db.execute(
            'SELECT * FROM GuildSettings WHERE guildId = ?', (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row)


_ALLOWED_COLUMNS = frozenset({
    'prefix', 'language', 'defaultVolume', 'djRoleId', 'announceNowPlaying'
})


async def update_guild_settings(guild_id: str, data: dict) -> dict:
    db_path = _get_db_path()
    # Validate column names to prevent SQL injection
    invalid = set(data) - _ALLOWED_COLUMNS
    if invalid:
        raise ValueError(f'Invalid column name(s): {invalid}')
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        # Ensure the row exists
        await db.execute(
            'INSERT OR IGNORE INTO GuildSettings (guildId) VALUES (?)', (guild_id,)
        )
        if data:
            set_clause = ', '.join(f'{k} = ?' for k in data)
            values = list(data.values()) + [guild_id]
            await db.execute(
                f'UPDATE GuildSettings SET {set_clause} WHERE guildId = ?',
                values,
            )
        await db.commit()
        async with db.execute(
            'SELECT * FROM GuildSettings WHERE guildId = ?', (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
        return dict(row)



# Saved playlists are private to the requesting user within a guild.
MAX_SAVED_PLAYLISTS = 20
MAX_SAVED_TRACKS = 50
_PLAYLIST_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9 _-]{0,39}\Z')


def _validated_name(name: str) -> tuple[str, str]:
    if not isinstance(name, str):
        raise ValueError('Playlist name must be text.')
    if any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise ValueError('Playlist names cannot contain control characters.')
    name = ' '.join(name.strip().split())
    if not _PLAYLIST_NAME.fullmatch(name):
        raise ValueError('Playlist name must be 1–40 letters, digits, spaces, _ or -.')
    return name, name.casefold()


def _validated_urls(urls: list[str]) -> list[str]:
    if not urls or len(urls) > MAX_SAVED_TRACKS:
        raise ValueError(f'Playlist must have 1–{MAX_SAVED_TRACKS} tracks.')
    cleaned = []
    for url in urls:
        if not isinstance(url, str) or len(url) > 2048:
            raise ValueError('Invalid track URL in playlist.')
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            raise ValueError('Playlist tracks require absolute http(s) URLs.')
        cleaned.append(url)
    return cleaned


async def save_playlist(guild_id: str, user_id: str, name: str,
                        urls: list[str]) -> None:
    """Atomically save/replace a user's private, guild-scoped playlist."""
    display, key = _validated_name(name)
    checked = _validated_urls(urls)
    async with aiosqlite.connect(_get_db_path(), timeout=15) as db:
        await db.execute('BEGIN IMMEDIATE')
        async with db.execute(
            'SELECT COUNT(*) FROM SavedPlaylists WHERE guildId=? AND userId=?',
            (guild_id, user_id),
        ) as cur:
            count = (await cur.fetchone())[0]
        async with db.execute(
            'SELECT 1 FROM SavedPlaylists WHERE guildId=? AND userId=? AND nameKey=?',
            (guild_id, user_id, key),
        ) as cur:
            existing = await cur.fetchone()
        if not existing and count >= MAX_SAVED_PLAYLISTS:
            raise ValueError(f'Maximum {MAX_SAVED_PLAYLISTS} saved playlists per user.')
        await db.execute(
            """
            INSERT INTO SavedPlaylists (guildId, userId, nameKey, displayName, tracksJson)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guildId, userId, nameKey) DO UPDATE SET
                displayName=excluded.displayName,
                tracksJson=excluded.tracksJson,
                updatedAt=CURRENT_TIMESTAMP
            """,
            (guild_id, user_id, key, display, json.dumps(checked)),
        )
        await db.commit()


async def get_saved_playlist(guild_id: str, user_id: str,
                             name: str) -> list[str] | None:
    _, key = _validated_name(name)
    async with aiosqlite.connect(_get_db_path()) as db:
        async with db.execute(
            'SELECT tracksJson FROM SavedPlaylists '
            'WHERE guildId=? AND userId=? AND nameKey=?',
            (guild_id, user_id, key),
        ) as cur:
            row = await cur.fetchone()
    if row is None:
        return None
    return _validated_urls(json.loads(row[0]))


async def list_saved_playlists(guild_id: str, user_id: str) -> list[tuple[str, int]]:
    async with aiosqlite.connect(_get_db_path()) as db:
        async with db.execute(
            'SELECT displayName, tracksJson FROM SavedPlaylists '
            'WHERE guildId=? AND userId=? ORDER BY displayName COLLATE NOCASE',
            (guild_id, user_id),
        ) as cur:
            rows = await cur.fetchall()
    return [(name, len(json.loads(raw))) for name, raw in rows]


async def delete_saved_playlist(guild_id: str, user_id: str,
                                name: str) -> bool:
    _, key = _validated_name(name)
    async with aiosqlite.connect(_get_db_path()) as db:
        result = await db.execute(
            'DELETE FROM SavedPlaylists WHERE guildId=? AND userId=? AND nameKey=?',
            (guild_id, user_id, key),
        )
        await db.commit()
        return result.rowcount > 0
