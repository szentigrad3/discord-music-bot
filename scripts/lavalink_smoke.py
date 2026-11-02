#!/usr/bin/env python3
"""Read-only Lavalink API smoke test (does not need a Discord token).

Run on the host for standalone setups, or inside the bot container:
    docker compose exec -T bot python scripts/lavalink_smoke.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def check_lavalink(host: str, port: int, password: str,
                   opener=urlopen) -> dict:
    if not host or not password or not 1 <= port <= 65535:
        raise ValueError('Lavalink host, password or port is invalid.')
    host_for_url = f'[{host}]' if ':' in host and not host.startswith('[') else host
    base = f'http://{host_for_url}:{port}'
    results = {}
    for endpoint in ('version', 'v4/info'):
        request = Request(base + '/' + endpoint,
                          headers={'Authorization': password})
        with opener(request, timeout=5) as response:
            if getattr(response, 'status', 200) != 200:
                raise RuntimeError(f'Lavalink {endpoint} returned non-200 status.')
            payload = response.read(131072)
            if endpoint == 'version':
                version = payload.decode('utf-8', errors='replace').strip()
                if not version:
                    raise ValueError('Lavalink /version returned an empty response.')
                results['version'] = version[:100]
            else:
                info = json.loads(payload)
                if not isinstance(info, dict):
                    raise ValueError('Lavalink /v4/info response must be a JSON object.')
                plugins = info.get('plugins', [])
                results['plugins'] = [
                    p.get('name', 'unknown') for p in plugins
                    if isinstance(p, dict)
                ] if isinstance(plugins, list) else []
                results['sources'] = info.get('sourceManagers', [])
    return results


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default='settings.json',
                        help='Bot settings JSON (default: settings.json)')
    args = parser.parse_args(argv)
    config_path = Path(args.config)
    if not config_path.is_file():
        print('FAIL: settings.json not found; configure the bot first.', file=sys.stderr)
        return 2
    try:
        data = json.loads(config_path.read_text(encoding='utf-8'))
        lavalink = data.get('lavalink', {})
        host = lavalink.get('host') or 'localhost'
        if os.getenv('BOT_IN_DOCKER', '').lower() == 'true' and host == 'localhost':
            host = 'lavalink'
        result = check_lavalink(host, int(lavalink.get('port', 2333)),
                                lavalink.get('password', ''))
    except (ValueError, TypeError, KeyError, OSError, HTTPError, URLError,
            RuntimeError, json.JSONDecodeError) as exc:
        # Do not log an authorization header, URL query, token, or response body.
        print(f'FAIL: Lavalink probe ({type(exc).__name__}).', file=sys.stderr)
        return 1
    print('PASS: Lavalink /version and /v4/info API endpoints respond.')
    print('Lavalink version:', result['version'])
    print('Loaded plugins:', ', '.join(result['plugins']) or '(none)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
