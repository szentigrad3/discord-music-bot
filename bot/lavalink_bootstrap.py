"""Supervise the initial Lavalink connection without blocking Discord ready events.

Once a node has joined NodePool, Voicelink owns websocket reconnection.
This supervisor only retries the *initial* create_node() operation.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable


class LavalinkBootstrap:
    def __init__(self, initial_delay: float = 2.0,
                 max_delay: float = 30.0) -> None:
        if initial_delay <= 0 or max_delay < initial_delay:
            raise ValueError('Invalid Lavalink retry settings.')
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self._task: asyncio.Task | None = None
        self._closed = False

    def ensure(self, connect: Callable[[], Awaitable[object]],
               exists: Callable[[], bool], logger: logging.Logger) -> None:
        """Schedule at most one initial connection job across ready events."""
        if self._closed or exists():
            return
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(
            self._run(connect, exists, logger), name='lavalink-initial-connect',
        )

    async def _run(self, connect: Callable[[], Awaitable[object]],
                   exists: Callable[[], bool], logger: logging.Logger) -> None:
        delay = self.initial_delay
        while not self._closed and not exists():
            try:
                await connect()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Exception messages can include hosts or upstream responses.
                # Avoid logging authentication values or response bodies.
                logger.warning('Initial Lavalink connection failed (%s); '
                               'retrying in %.1fs.', type(exc).__name__, delay)
            else:
                logger.info('Initial Lavalink node connected.')
                return
            await asyncio.sleep(delay)
            delay = min(delay * 2, self.max_delay)

    async def close(self) -> None:
        """Cancel a pending retry when the Discord bot shuts down."""
        self._closed = True
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
