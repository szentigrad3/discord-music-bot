"""SQLite saved-playlist persistence, privacy, and input-boundary tests."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bot.db import (
    MAX_SAVED_PLAYLISTS,
    MAX_SAVED_TRACKS,
    delete_saved_playlist,
    get_saved_playlist,
    init_db,
    list_saved_playlists,
    save_playlist,
)


class SavedPlaylistsDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = str(Path(self.temp.name) / 'data' / 'bot.db')
        self.patch_path = patch('bot.db._DATABASE_URL', path)
        self.patch_path.start()
        await init_db()

    async def asyncTearDown(self):
        self.patch_path.stop()
        self.temp.cleanup()

    async def test_save_list_load_delete(self):
        urls = ['https://example.com/a', 'https://example.com/b']
        await save_playlist('guild1', 'user1', 'Favourites', urls)
        self.assertEqual(await list_saved_playlists('guild1', 'user1'), [('Favourites', 2)])
        self.assertEqual(await get_saved_playlist('guild1', 'user1', 'favourites'), urls)
        self.assertTrue(await delete_saved_playlist('guild1', 'user1', 'FAVOURITES'))
        self.assertIsNone(await get_saved_playlist('guild1', 'user1', 'Favourites'))
        self.assertFalse(await delete_saved_playlist('guild1', 'user1', 'Favourites'))

    async def test_guild_and_user_isolation(self):
        await save_playlist('g1', 'u1', 'My tracks', ['https://example.com/a'])
        self.assertIsNone(await get_saved_playlist('g1', 'u2', 'My tracks'))
        self.assertIsNone(await get_saved_playlist('g2', 'u1', 'My tracks'))
        self.assertEqual(await list_saved_playlists('g2', 'u1'), [])

    async def test_case_insensitive_overwrite(self):
        await save_playlist('g', 'u', 'Chill', ['https://example.com/one'])
        await save_playlist('g', 'u', 'CHILL', ['https://example.com/two'])
        self.assertEqual(await list_saved_playlists('g', 'u'), [('CHILL', 1)])
        self.assertEqual(await get_saved_playlist('g', 'u', 'chill'),
                         ['https://example.com/two'])

    async def test_rejects_invalid_names_before_database_change(self):
        for name in ('', ' ', '../a', 'a' * 41, '@everyone', 'x\nnew'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                await save_playlist('g', 'u', name, ['https://example.com/a'])
        self.assertEqual(await list_saved_playlists('g', 'u'), [])

    async def test_rejects_unsafe_or_oversize_urls(self):
        for value in ('file:///etc/passwd', 'ftp://example.com/a',
                      'javascript:alert(1)', 'http://', '/relative', 'https://'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                await save_playlist('g', 'u', 'Safe', [value])
        with self.assertRaises(ValueError):
            await save_playlist('g', 'u', 'Safe', [])
        with self.assertRaises(ValueError):
            await save_playlist('g', 'u', 'Safe', ['https://example.com/'] * (MAX_SAVED_TRACKS + 1))

    async def test_per_user_limit_preserves_existing_playlists(self):
        for i in range(MAX_SAVED_PLAYLISTS):
            await save_playlist('g', 'u', f'Mix{i}', ['https://example.com/a'])
        with self.assertRaisesRegex(ValueError, 'Maximum'):
            await save_playlist('g', 'u', 'TooMany', ['https://example.com/b'])
        await save_playlist('g', 'u', 'Mix0', ['https://example.com/replaced'])
        self.assertEqual(len(await list_saved_playlists('g', 'u')), MAX_SAVED_PLAYLISTS)
        self.assertEqual(await get_saved_playlist('g', 'u', 'Mix0'),
                         ['https://example.com/replaced'])

    async def test_database_persists_between_connections(self):
        await save_playlist('g', 'u', 'Persistent', ['https://example.com/a'])
        await init_db()  # Startup/migration on a subsequent launch.
        self.assertEqual(await get_saved_playlist('g', 'u', 'Persistent'),
                         ['https://example.com/a'])
