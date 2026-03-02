"""Deploy slash commands to Discord via REST API."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

load_dotenv()

DISCORD_API = 'https://discord.com/api/v10'


async def main() -> None:
    token = os.getenv('DISCORD_TOKEN')
    client_id = os.getenv('DISCORD_CLIENT_ID')

    if not token or not client_id:
        raise RuntimeError('DISCORD_TOKEN and DISCORD_CLIENT_ID must be set.')

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
        'Authorization': f'Bot {token}',
        'Content-Type': 'application/json',
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.put(
            f'{DISCORD_API}/applications/{client_id}/commands',
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
