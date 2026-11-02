"""Docker SIGTERM and SIGINT must leave Discord voice before process exit."""
import asyncio
import signal
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.main import _install_shutdown_handlers, _stop_bot_gracefully


class GracefulStopTests(unittest.IsolatedAsyncioTestCase):
    async def test_voice_disconnect_precedes_discord_gateway_close(self):
        order = []
        bootstrap = MagicMock()
        nodes = MagicMock()
        discord_bot = MagicMock()

        async def bootstrap_close():
            order.append('stop bootstrap')
        async def nodes_close():
            order.append('leave voice')
        async def bot_close():
            order.append('close gateway')

        bootstrap.close = AsyncMock(side_effect=bootstrap_close)
        nodes.close_all = AsyncMock(side_effect=nodes_close)
        discord_bot.close = AsyncMock(side_effect=bot_close)

        await _stop_bot_gracefully(discord_bot, bootstrap, nodes)
        self.assertEqual(order, ['stop bootstrap', 'leave voice', 'close gateway'])

    async def test_cleanup_error_still_closes_discord(self):
        bootstrap = MagicMock()
        bootstrap.close = AsyncMock()
        nodes = MagicMock()
        nodes.close_all = AsyncMock(side_effect=RuntimeError('backend unavailable'))
        bot = MagicMock()
        bot.close = AsyncMock()
        with patch('bot.main.logger'):
            await _stop_bot_gracefully(bot, bootstrap, nodes)
        bot.close.assert_awaited_once()

    async def test_timeout_still_closes_gateway(self):
        bootstrap = MagicMock()
        bootstrap.close = AsyncMock()
        nodes = MagicMock()
        nodes.close_all = AsyncMock()
        bot = MagicMock()
        bot.close = AsyncMock()
        with patch('bot.main.asyncio.wait_for', side_effect=asyncio.TimeoutError), \
             patch('bot.main.logger'):
            await _stop_bot_gracefully(bot, bootstrap, nodes, timeout=0.01)
        bot.close.assert_awaited_once()

    async def test_signal_handlers_register_both_stop_signals(self):
        loop = MagicMock()
        handler = MagicMock()
        registered = _install_shutdown_handlers(loop, handler)
        self.assertEqual(registered, [signal.SIGTERM, signal.SIGINT])
        loop.add_signal_handler.assert_any_call(signal.SIGTERM, handler)
        loop.add_signal_handler.assert_any_call(signal.SIGINT, handler)

    async def test_signal_handlers_fallback_on_unsupported_loop(self):
        loop = MagicMock()
        loop.add_signal_handler.side_effect = NotImplementedError()
        self.assertEqual(_install_shutdown_handlers(loop, lambda: None), [])
