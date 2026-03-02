"""Deploy slash commands to Discord via REST API."""
from __future__ import annotations

import asyncio

import aiohttp

from bot.settings import settings

DISCORD_API = 'https://discord.com/api/v10'


async def main() -> None:
    if not settings.token or not settings.client_id:
        raise RuntimeError('token and client_id must be set in settings.json')

    # Import the bot and collect all app commands
    import discord
    from discord.ext import commands

    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix='!', intents=intents)
    bot.queues = {}

    await bot.load_extension('bot.cogs.music')
    await bot.load_extension('bot.cogs.utility')

    # Collect commands as JSON payloads
    commands_payload = [cmd.to_dict() for cmd in bot.tree.get_commands()]
    print(f'Deploying {len(commands_payload)} application (/) commands...')

    headers = {
        'Authorization': f'Bot {settings.token}',
        'Content-Type': 'application/json',
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.put(
            f'{DISCORD_API}/applications/{settings.client_id}/commands',
            json=commands_payload,
        ) as resp:
            if not resp.ok:
                body = await resp.text()
                raise RuntimeError(f'Failed to deploy commands: {resp.status} {body}')
            data = await resp.json()
            print(f'Successfully deployed {len(data)} application (/) commands.')

    await bot.close()


if __name__ == '__main__':
    asyncio.run(main())
