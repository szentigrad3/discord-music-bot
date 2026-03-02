from __future__ import annotations

import asyncio
import os

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
        await db.execute(
            'INSERT INTO GuildSettings (guildId) VALUES (?)', (guild_id,)
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
