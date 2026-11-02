#!/usr/bin/env python3
"""Safely bring a v1.2.1 installation into a fresh development checkout.

Example:
  python scripts/import_existing_v121.py --old ../discord-music-bot-old --apply

Stop the old bot and Lavalink before using --apply. The old installation is
never modified. Secrets and databases are never printed or committed.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
import shutil
import sqlite3
from pathlib import Path

# Keep local Lavalink configs separate from Git-tracked defaults.
# This avoids merge conflicts and accidental git commits of embedded secrets.
PRIVATE_FILES = {
    'settings.json': 'settings.json',
    'lavalink/application.yml': 'lavalink/application.local.yml',
    'lavalink/application.docker.yml': 'lavalink/application.docker.local.yml',
}


def _private_copy(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError('Source is not a regular file.')
    if target.exists() or target.is_symlink():
        raise FileExistsError('Destination already contains a private file.')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(0o600)


def _dotenv_literal(value: str) -> str:
    """Docker Compose .env supports single-quoted, noninterpolated values."""
    if not isinstance(value, str) or not value or any(c in value for c in '\r\n\x00'):
        raise ValueError('Lavalink password must be non-empty and single-line.')
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


_TEMPLATE_BACKUP = 'settings.json.generated-template.backup'


def _is_generated_template(dest: Path) -> bool:
    """Only recognise the exact installer-generated template, never real settings."""
    current = dest / 'settings.json'
    example = dest / 'settings Example.json'
    return (current.is_file() and not current.is_symlink()
            and example.is_file() and not example.is_symlink()
            and current.read_bytes() == example.read_bytes())


def _plan(source: Path, dest: Path) -> list[str]:
    if source.resolve() == dest.resolve() or source.resolve() in dest.resolve().parents:
        raise ValueError('Old and new installations must be separate directories.')
    if not (source / 'settings.json').is_file():
        raise FileNotFoundError('Old installation is missing settings.json.')
    if not (dest / 'docker-compose.yml').is_file():
        raise FileNotFoundError('New checkout must contain docker-compose.yml.')
    if 'LAVALINK_PASSWORD' not in (dest / 'docker-compose.yml').read_text(encoding='utf-8'):
        raise ValueError('New checkout does not support a local Lavalink password.')
    generated_placeholder = _is_generated_template(dest)
    if generated_placeholder and (dest / _TEMPLATE_BACKUP).exists():
        raise FileExistsError('An old generated-template backup already exists.')
    for source_rel, dest_rel in PRIVATE_FILES.items():
        if (source / source_rel).is_file() and (dest / dest_rel).exists():
            if dest_rel == 'settings.json' and generated_placeholder:
                continue
            raise FileExistsError(f'{dest_rel} already exists in the destination.')
    if (dest / '.env').exists():
        raise FileExistsError('The destination already has an .env file.')
    if (source / 'data/bot.db').is_file() and (dest / 'data/bot.db').exists():
        raise FileExistsError('The destination database already exists.')
    if (source / 'data').is_symlink() or (source / 'lavalink').is_symlink():
        raise ValueError('Symlinked source directories are not supported.')
    # Settings must be parsed before the first write.
    settings = json.loads((source / 'settings.json').read_text(encoding='utf-8'))
    password = settings.get('lavalink', {}).get('password')
    _dotenv_literal(password)
    names = [
        f'{source_rel} → {dest_rel}'
        for source_rel, dest_rel in PRIVATE_FILES.items()
        if (source / source_rel).is_file()
    ]
    if (source / 'data/bot.db').is_file():
        names.append('data/bot.db (SQLite backup)')
    if (source / 'data').is_dir():
        for file in sorted((source / 'data').rglob('*')):
            if file.is_file() and not file.is_symlink() and file.name not in ('bot.db', '.gitkeep') and not file.name.startswith('bot.db-'):
                rel = file.relative_to(source).as_posix()
                if (dest / rel).exists():
                    raise FileExistsError(f'{rel} already exists in destination.')
                names.append(rel)
    if generated_placeholder:
        names.insert(0, f'generated settings.json → {_TEMPLATE_BACKUP} (kept as backup)')
    return names + ['.env (generated locally)']


def import_setup(source: Path, dest: Path, *, apply: bool = False) -> list[str]:
    """Return a safe migration plan; copy only when apply=True."""
    source = source.expanduser().resolve()
    dest = dest.expanduser().resolve()
    items = _plan(source, dest)
    if not apply:
        return items

    settings = json.loads((source / 'settings.json').read_text(encoding='utf-8'))
    password = settings['lavalink']['password']
    # The older AIO runner could copy settings Example.json into the new
    # checkout during an import-only test. Preserve it, and replace it only if
    # byte-for-byte identical to the tracked example.
    if _is_generated_template(dest):
        (dest / 'settings.json').rename(dest / _TEMPLATE_BACKUP)
    for source_rel, dest_rel in PRIVATE_FILES.items():
        src = source / source_rel
        if src.is_file():
            _private_copy(src, dest / dest_rel)

    data = source / 'data'
    db = data / 'bot.db'
    if db.is_file():
        if db.is_symlink():
            raise ValueError('Symlinked databases are not supported.')
        dest_db = dest / 'data/bot.db'
        dest_db.parent.mkdir(parents=True, exist_ok=True)
        # SQLite backup API safely preserves the database including WAL state.
        # sqlite3.Connection context managers manage transactions but do
        # not close connections. Explicitly close both on Python 3.14+.
        with closing(sqlite3.connect(f'file:{db}?mode=ro', uri=True)) as old:
            with closing(sqlite3.connect(dest_db)) as new:
                old.backup(new)
        dest_db.chmod(0o600)

    if data.is_dir():
        for src in sorted(data.rglob('*')):
            if not src.is_file() or src.is_symlink() or src.name in ('bot.db', '.gitkeep') or src.name.startswith('bot.db-'):
                continue
            target = dest / src.relative_to(source)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, target)

    envfile = dest / '.env'
    docker_config = ('application.docker.local.yml'
                     if (source / 'lavalink/application.docker.yml').is_file()
                     else 'application.docker.yml')
    envfile.write_text(
        'LAVALINK_PASSWORD=' + _dotenv_literal(password) + '\n'
        + 'LAVALINK_CONFIG_FILE=' + docker_config + '\n',
        encoding='utf-8',
    )
    envfile.chmod(0o600)
    return items


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', required=True, type=Path, help='Existing v1.2.1 directory')
    parser.add_argument('--new', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--apply', action='store_true', help='Actually copy files; default is dry-run')
    args = parser.parse_args(argv)
    try:
        items = import_setup(args.old, args.new, apply=args.apply)
    except (OSError, ValueError, sqlite3.Error, TypeError) as exc:
        print(f'FAIL: Migration was not completed ({type(exc).__name__}: {exc}).')
        return 1
    print('Imported:' if args.apply else 'Dry run — would import:')
    for item in items:
        print('  -', item)
    if args.apply:
        print('PASS: Original installation unchanged. No credentials printed.')
        print('Next: python3 scripts/prepare_lavalink_docker.py --apply')
        print('Then: .venv/bin/python scripts/doctor.py && bash scripts/test-all.sh')
    else:
        print('Re-run with --apply after stopping the old bot.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
