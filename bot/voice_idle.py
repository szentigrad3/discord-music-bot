"""Debounced empty-voice-channel cleanup.

Discord emits bursts of voice-state events. Schedule at most one empty-channel
check per guild and cancel it if a listener returns before the grace period.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)


class EmptyVoiceManager:
    def __init__(self, delay: float = 5.0) -> None:
        self.delay = delay
        self._tasks: dict[str, asyncio.Task] = {}

    def cancel(self, guild_id: str) -> None:
        task = self._tasks.pop(guild_id, None)
        if task is not None and task is not asyncio.current_task() and not task.done():
            task.cancel()

    def update(self, guild_id: str, player: Any,
               lookup: Callable[[str], Any]) -> None:
        """Update a guild's pending leave check after a voice-state change."""
        voice = player._vl_player
        channel = voice.channel if voice and voice.is_connected else None
        if channel is None or any(not m.bot for m in channel.members):
            self.cancel(guild_id)
            return
        task = self._tasks.get(guild_id)
        if task is not None and not task.done():
            return
        task = asyncio.create_task(self._leave_if_empty(guild_id, player, lookup))
        self._tasks[guild_id] = task

        def discard(done: asyncio.Task) -> None:
            if self._tasks.get(guild_id) is done:
                self._tasks.pop(guild_id, None)

        task.add_done_callback(discard)

    async def _leave_if_empty(self, guild_id: str, player: Any,
                              lookup: Callable[[str], Any]) -> None:
        try:
            await asyncio.sleep(self.delay)
            if lookup(guild_id) is not player:
                return
            voice = player._vl_player
            channel = voice.channel if voice and voice.is_connected else None
            if channel is None or any(not m.bot for m in channel.members):
                return
            await player.stop()
            await voice.disconnect()
            if lookup(guild_id) is player:
                player.bot.queues.pop(guild_id, None)
            logger.info('Auto-left empty voice channel in guild %s', guild_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Failed empty-channel cleanup in guild %s', guild_id)
