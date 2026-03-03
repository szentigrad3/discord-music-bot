"""Settings loader — reads settings.json and exposes a typed Settings object.

Follows the same pattern as Vocard (ChocoMeow/Vocard): a single
open_json() helper and a Settings class whose attributes replace
all previous os.getenv() calls throughout the project.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict

ROOT_DIR: Path = Path(__file__).parent.parent


def open_json(path: str) -> Dict[str, Any]:
    """Load a JSON file relative to the project root. Returns {} on failure."""
    try:
        with open(ROOT_DIR / path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


class Settings:
    """Typed wrapper around settings.json — mirrors Vocard's Settings class."""

    def __init__(self, data: Dict[str, Any]) -> None:
        # Discord
        self.token: str = data.get('token', '')
        self.client_id: str = data.get('client_id', '')
        self.client_secret: str = data.get('client_secret', '')
        self.callback_url: str = data.get(
            'callback_url',
            'http://localhost:3000/auth/discord/callback',
        )

        # Spotify (optional)
        self.spotify_client_id: str = data.get('spotify_client_id', '')
        self.spotify_client_secret: str = data.get('spotify_client_secret', '')

        # Dashboard
        self.session_secret: str = data.get('session_secret', '')
        self.dashboard_port: int = int(data.get('dashboard_port', 3000))

        # Database
        self.database_url: str = data.get('database_url', 'file:./data/bot.db')

        # Lavalink (nested, like Vocard's "nodes" dict)
        lavalink: Dict[str, Any] = data.get('lavalink', {})
        self.lavalink_host: str = lavalink.get('host', 'lavalink')
        self.lavalink_port: int = int(lavalink.get('port', 2333))
        self.lavalink_password: str = lavalink.get('password', 'youshallnotpass')

        # Logging — LOG_LEVEL env var takes precedence over settings.json
        _level_str: str = (
            os.environ.get('LOG_LEVEL') or data.get('log_level', 'INFO')
        ).upper()
        _valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if _level_str not in _valid_levels:
            raise ValueError(
                f'Invalid log_level: "{_level_str}". '
                f'Must be one of: {", ".join(sorted(_valid_levels))}'
            )
        self.log_level: int = getattr(logging, _level_str)


_settings_file = ROOT_DIR / 'settings.json'
if not _settings_file.exists():
    _example_file = ROOT_DIR / 'settings Example.json'
    if _example_file.exists():
        shutil.copy2(_example_file, _settings_file)
        print(
            "settings.json created from 'settings Example.json'. "
            "Please update it with your actual values before running the bot."
        )
    else:
        raise Exception(
            "Settings file not found! "
            "Please create 'settings.json' and fill in your values."
        )

settings = Settings(open_json('settings.json'))
