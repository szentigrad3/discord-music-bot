"""Regression tests for application-command syncing on reconnect."""
import asyncio
import logging
import unittest
from unittest.mock import AsyncMock

from bot.command_sync import CommandTreeSync


class CommandSyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_reconnect_does_not_sync_twice(self):
        tree = AsyncMock()
        tree.sync.return_value = ['play', 'skip']
        gate = CommandTreeSync()
        log = logging.getLogger(__name__)
        self.assertTrue(await gate.sync(tree, log))
        self.assertTrue(await gate.sync(tree, log))
        tree.sync.assert_awaited_once()

    async def test_failed_sync_retries_on_next_ready(self):
        tree = AsyncMock()
        tree.sync.side_effect = [RuntimeError('temporary outage'), ['play']]
        gate = CommandTreeSync()
        log = logging.getLogger(__name__)
        self.assertFalse(await gate.sync(tree, log))
        self.assertTrue(await gate.sync(tree, log))
        self.assertEqual(tree.sync.await_count, 2)

    async def test_simultaneous_events_sync_once(self):
        tree = AsyncMock()
        tree.sync.return_value = []
        gate = CommandTreeSync()
        results = await asyncio.gather(*(
            gate.sync(tree, logging.getLogger(__name__)) for _ in range(5)
        ))
        self.assertEqual(results, [True] * 5)
        tree.sync.assert_awaited_once()
