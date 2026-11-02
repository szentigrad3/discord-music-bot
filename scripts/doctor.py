#!/usr/bin/env python3
"""Offline Discord Music Bot configuration preflight.

Reads configuration but prints only issue codes and descriptions. It never
connects to Discord, Spotify or Lavalink and never displays credentials.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit


def inspect_config(data: object) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return ['settings.json must contain a JSON object.'], warnings

    token = data.get('token')
    if not isinstance(token, str) or len(token.strip()) < 20 or 'YOUR_' in token.upper():
        errors.append('Discord bot token is missing or is a placeholder.')

    lavalink = data.get('lavalink', {})
    if not isinstance(lavalink, dict):
        errors.append('Lavalink settings must be an object.')
        lavalink = {}
    host = lavalink.get('host', 'localhost')
    if not isinstance(host, str) or not host.strip():
        errors.append('Lavalink host is missing.')
    try:
        port = int(lavalink.get('port', 2333))
        if not 1 <= port <= 65535:
            raise ValueError()
    except (ValueError, TypeError):
        errors.append('Lavalink port must be between 1 and 65535.')
    password = lavalink.get('password')
    if not isinstance(password, str) or not password:
        errors.append('Lavalink password is missing.')
    elif password == 'youshallnotpass':
        warnings.append('Replace the example Lavalink password before public deployment.')

    dashboard_secret = data.get('session_secret')
    if dashboard_secret:
        if not isinstance(dashboard_secret, str) or len(dashboard_secret) < 32:
            warnings.append('Dashboard session secret should have at least 32 characters.')
        if not data.get('client_id') or not data.get('client_secret'):
            errors.append('Dashboard requires Discord OAuth client_id and client_secret.')
        url = data.get('callback_url', 'http://localhost:3000/auth/discord/callback')
        try:
            callback = urlsplit(url)
            valid = callback.scheme in ('http', 'https') and bool(callback.hostname)
            if not valid:
                errors.append('Dashboard callback URL must be an absolute http(s) URL.')
            elif callback.scheme != 'https' and callback.hostname not in ('localhost', '127.0.0.1', '::1'):
                warnings.append('Public dashboard OAuth callback should use HTTPS.')
        except (ValueError, TypeError):
            errors.append('Dashboard callback URL is invalid.')

    spotify_id, spotify_secret = data.get('spotify_client_id'), data.get('spotify_client_secret')
    if bool(spotify_id) != bool(spotify_secret):
        warnings.append('Spotify API support needs both client_id and client_secret.')
    return errors, warnings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='settings.json')
    parser.add_argument('--strict', action='store_true',
                        help='Treat configuration warnings as a failure.')
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.config).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        print('FAIL: Configuration cannot be read as JSON. No secrets were displayed.')
        return 2
    errors, warnings = inspect_config(data)
    for error in errors:
        print('ERROR:', error)
    for warning in warnings:
        print('WARN:', warning)
    if errors or (warnings and args.strict):
        print(f'FAIL: {len(errors)} error(s), {len(warnings)} warning(s).')
        return 1
    print(f'PASS: Offline configuration preflight ({len(warnings)} warning(s)).')
    print('Live audio, Discord permissions and provider availability remain unverified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
