"""Coordinate Discord application-command synchronization across ready events."""
from __future__ import annotations

import asyncio
import logging
from typing import Any


class CommandTreeSync:
    """Synchronize commands at most once successfully per process.

    A failed attempt is intentionally retryable on the next ready event.
    The lock also prevents overlapping ready handlers from syncing twice.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._synced = False

    async def sync(self, tree: Any, logger: logging.Logger) -> bool:
        """Return True when sync completed, False when it failed."""
        async with self._lock:
            if self._synced:
                return True
            try:
                commands = await tree.sync()
            except Exception:
                logger.exception('Failed to sync application (/) commands')
                return False
            self._synced = True
            logger.info('Synced %d application (/) commands.', len(commands))
            return True
