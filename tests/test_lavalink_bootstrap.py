"""Initial Lavalink startup retry tests, independent of a live Discord login."""
import asyncio
import logging
import unittest
from unittest.mock import AsyncMock

from bot.lavalink_bootstrap import LavalinkBootstrap


class LavalinkBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_ready_bursts_create_one_connect_attempt(self):
        bootstrap = LavalinkBootstrap(initial_delay=0.01, max_delay=0.02)
        ready = asyncio.Event()
        release = asyncio.Event()
        connected = False

        async def connect():
            nonlocal connected
            ready.set()
            await release.wait()
            connected = True

        task = AsyncMock(side_effect=connect)
        exists = lambda: connected
        for _ in range(15):
            bootstrap.ensure(task, exists, logging.getLogger(__name__))
        await asyncio.wait_for(ready.wait(), timeout=1)
        self.assertEqual(task.await_count, 1)
        release.set()
        await asyncio.sleep(0.02)
        bootstrap.ensure(task, exists, logging.getLogger(__name__))
        self.assertEqual(task.await_count, 1)
        await bootstrap.close()

    async def test_transient_failure_retries_without_another_ready(self):
        connected = False
        bootstrap = LavalinkBootstrap(initial_delay=0.005, max_delay=0.01)

        async def connect():
            nonlocal connected
            if not connected:
                connected = True
                raise RuntimeError('first connection failed')

        task = AsyncMock(side_effect=connect)
        # Simulate an initial failure followed by a successful connection;
        # the exists predicate tracks pool registration, not the attempt.
        bootstrap.ensure(task, lambda: False, logging.getLogger(__name__))
        await asyncio.sleep(0.03)
        self.assertEqual(task.await_count, 2)
        await bootstrap.close()

    async def test_shutdown_cancels_retry(self):
        bootstrap = LavalinkBootstrap(initial_delay=0.2, max_delay=0.4)
        attempt = AsyncMock(side_effect=RuntimeError('offline'))
        bootstrap.ensure(attempt, lambda: False, logging.getLogger(__name__))
        await asyncio.sleep(0.01)
        self.assertEqual(attempt.await_count, 1)
        await bootstrap.close()
        await asyncio.sleep(0.03)
        self.assertEqual(attempt.await_count, 1)
        bootstrap.ensure(attempt, lambda: False, logging.getLogger(__name__))
        self.assertEqual(attempt.await_count, 1)

    async def test_registered_node_never_recreated(self):
        bootstrap = LavalinkBootstrap()
        connect = AsyncMock()
        bootstrap.ensure(connect, lambda: True, logging.getLogger(__name__))
        await asyncio.sleep(0)
        connect.assert_not_awaited()
        await bootstrap.close()

    def test_invalid_retry_configuration_is_rejected(self):
        with self.assertRaises(ValueError):
            LavalinkBootstrap(initial_delay=0)
        with self.assertRaises(ValueError):
            LavalinkBootstrap(initial_delay=10, max_delay=5)
