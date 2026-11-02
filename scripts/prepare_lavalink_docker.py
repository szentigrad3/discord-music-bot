#!/usr/bin/env python3
"""Prepare private bind mounts for Lavalink's non-root Docker UID.

The official standard Lavalink image uses UID 322. Grant named-user POSIX ACLs
instead of making configuration files world-readable. This script never reads,
prints, or modifies any secret values. Run from any directory:

    python3 scripts/prepare_lavalink_docker.py          # dry run
    python3 scripts/prepare_lavalink_docker.py --apply  # apply ACLs

Requires the Arch/CachyOS 'acl' package (setfacl). For a custom image with a
different user, pass --uid with the image's numeric UID.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_UID = 322
DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def _safe_path(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f'Refusing symlink: {path}')


def prepare(root: Path, *, uid: int = DEFAULT_UID,
            apply: bool = False) -> list[tuple[str, str]]:
    """Return intended ACL operations, or apply them safely.

    The Lavalink root gets execute-only traversal, its private Docker YAML
    gets read-only access, and its plugin tree gets only the rights needed for
    plugin installation and updates. settings.json, .env, DB and standalone
    Lavalink YAML are deliberately left untouched.
    """
    if isinstance(uid, bool) or not isinstance(uid, int) or uid < 1:
        raise ValueError('Container UID must be a positive integer.')
    root = root.expanduser().resolve()
    lavalink = root / 'lavalink'
    config = lavalink / 'application.docker.local.yml'
    plugins = lavalink / 'plugins'

    _safe_path(lavalink)
    _safe_path(config)
    _safe_path(plugins)

    if not lavalink.is_dir():
        raise FileNotFoundError('The lavalink/ directory does not exist.')
    if not config.is_file():
        raise FileNotFoundError('Private Lavalink Docker configuration is missing.')

    # Only apply if all preconditions have been checked; fail before changing
    # permissions when setfacl is not installed.
    if apply and shutil.which('setfacl') is None:
        raise RuntimeError("setfacl is missing; install the 'acl' package first.")

    paths: list[tuple[Path, str]] = [
        (lavalink, 'x'),       # traverse config/plugin paths, not list secrets
        (config, 'r'),         # Lavalink reads its private YAML
        (plugins, 'rwx'),     # new plugins need to be written
    ]

    if plugins.exists() and not plugins.is_dir():
        raise ValueError('lavalink/plugins exists but is not a directory.')
    if plugins.is_dir():
        for child in sorted(plugins.rglob('*')):
            _safe_path(child)
            if child.is_dir():
                paths.append((child, 'rwx'))
            elif child.is_file():
                paths.append((child, 'rw'))

    if apply:
        plugins.mkdir(parents=False, exist_ok=True)
        for path, rights in paths:
            subprocess.run(
                ['setfacl', '-m', f'u:{uid}:{rights}', str(path)],
                check=True,
                capture_output=True,
                text=True,
            )

    return [(str(path.relative_to(root)), rights) for path, rights in paths]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--uid', type=int, default=DEFAULT_UID)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args(argv)
    try:
        changes = prepare(args.root, uid=args.uid, apply=args.apply)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        # Never expose stdout/stderr of external tools; they may carry paths or
        # diagnostic details not intended for a public log.
        print(f'FAIL: Lavalink ACL preparation ({type(exc).__name__}).', file=sys.stderr)
        return 1
    print('Applied ACLs:' if args.apply else 'Dry run — proposed ACLs:')
    for path, rights in changes:
        print(f'  {path}: Lavalink user access={rights}')
    print('No secret contents or database files were changed.')
    if not args.apply:
        print('Run again with --apply to set ACLs.')
    else:
        print('Next: docker compose restart lavalink && docker compose ps')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
