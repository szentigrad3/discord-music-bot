"""SQLite regression tests for editing private user playlists."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.db import (
    MAX_SAVED_TRACKS, init_db, get_saved_playlist, list_saved_playlists,
    save_playlist, rename_saved_playlist, append_saved_track,
    remove_saved_track,
)


class PlaylistEditingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = str(Path(self.temp.name) / 'db.sqlite3')
        self.database_patch = patch('bot.db._DATABASE_URL', path)
        self.database_patch.start()
        await init_db()

    async def asyncTearDown(self):
        self.database_patch.stop()
        self.temp.cleanup()

    async def test_rename_add_remove_and_order(self):
        await save_playlist('g', 'u', 'One', [
            'https://example.com/a', 'https://example.com/b',
        ])
        self.assertTrue(await rename_saved_playlist('g', 'u', 'One', 'Two'))
        self.assertIsNone(await get_saved_playlist('g', 'u', 'One'))
        self.assertEqual(
            await append_saved_track('g', 'u', 'Two', 'https://example.com/c'), 3
        )
        self.assertEqual(await remove_saved_track('g', 'u', 'Two', 2), 2)
        self.assertEqual(await get_saved_playlist('g', 'u', 'Two'), [
            'https://example.com/a', 'https://example.com/c',
        ])

    async def test_rename_refuses_overwrite(self):
        await save_playlist('g', 'u', 'First', ['https://example.com/a'])
        await save_playlist('g', 'u', 'Second', ['https://example.com/b'])
        with self.assertRaisesRegex(ValueError, 'already have'):
            await rename_saved_playlist('g', 'u', 'First', 'Second')
        self.assertEqual(await get_saved_playlist('g', 'u', 'First'),
                         ['https://example.com/a'])
        self.assertEqual(await get_saved_playlist('g', 'u', 'Second'),
                         ['https://example.com/b'])

    async def test_case_only_rename_and_missing(self):
        await save_playlist('g', 'u', 'Mix', ['https://example.com/a'])
        self.assertTrue(await rename_saved_playlist('g', 'u', 'MIX', 'mix'))
        self.assertEqual(await list_saved_playlists('g', 'u'), [('mix', 1)])
        self.assertFalse(await rename_saved_playlist('g', 'u', 'missing', 'new'))
        self.assertIsNone(await append_saved_track('g', 'u', 'missing',
                                                  'https://example.com/'))
        self.assertIsNone(await remove_saved_track('g', 'u', 'missing', 1))

    async def test_invalid_removals_do_not_alter_single_track(self):
        await save_playlist('g', 'u', 'Solo', ['https://example.com/a'])
        for position in (0, -1, 2, True):
            with self.subTest(position=position), self.assertRaises(ValueError):
                await remove_saved_track('g', 'u', 'Solo', position)
        with self.assertRaisesRegex(ValueError, 'last track'):
            await remove_saved_track('g', 'u', 'Solo', 1)
        self.assertEqual(await get_saved_playlist('g', 'u', 'Solo'),
                         ['https://example.com/a'])

    async def test_limit_and_ownership_enforced(self):
        await save_playlist('g', 'u', 'Full', [
            f'https://example.com/{i}' for i in range(MAX_SAVED_TRACKS)
        ])
        with self.assertRaisesRegex(ValueError, 'Maximum'):
            await append_saved_track('g', 'u', 'Full', 'https://example.com/extra')
        self.assertIsNone(await append_saved_track('g', 'other', 'Full',
                                                   'https://example.com/extra'))
        self.assertFalse(await rename_saved_playlist('g', 'other', 'Full', 'Copy'))
        self.assertIsNone(await remove_saved_track('other', 'u', 'Full', 1))
        self.assertEqual(len(await get_saved_playlist('g', 'u', 'Full')),
                         MAX_SAVED_TRACKS)

    async def test_concurrent_appends_are_not_lost(self):
        await save_playlist('g', 'u', 'Duo', ['https://example.com/seed'])
        await asyncio.gather(*(
            append_saved_track('g', 'u', 'Duo', f'https://example.com/{i}')
            for i in range(10)
        ))
        urls = await get_saved_playlist('g', 'u', 'Duo')
        self.assertEqual(len(urls), 11)
        self.assertEqual(set(urls), {'https://example.com/seed'} | {
            f'https://example.com/{i}' for i in range(10)
        })
