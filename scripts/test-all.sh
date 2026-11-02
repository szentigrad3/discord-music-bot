#!/usr/bin/env bash
# One-command offline validation. Never starts Discord or requires credentials.
set -euo pipefail
cd "$(dirname "$0")/.."

# Always prefer the project's virtual environment when present, regardless of
# whether the caller is using Bash or fish. PYTHON_BIN may override explicitly.
if [[ -z "${PYTHON_BIN:-}" ]]; then
    if [[ -x .venv/bin/python ]]; then
        PYTHON_BIN="$PWD/.venv/bin/python"
    else
        PYTHON_BIN=python3
    fi
fi

echo "== Selected Python =="
"$PYTHON_BIN" --version

# A missing virtual environment / failed pip installation previously resulted
# in dozens of misleading unittest import errors and wrote a template
# settings.json via settings.py's module import. Fail before loading the bot.
if ! "$PYTHON_BIN" -c '
import importlib.util, sys
requirements = ("discord", "aiosqlite", "aiohttp", "flask", "requests", "yaml")
missing = [name for name in requirements if importlib.util.find_spec(name) is None]
if missing:
    print("ERROR: Missing test dependencies: " + ", ".join(missing), file=sys.stderr)
    print("Create a venv: python3 -m venv .venv", file=sys.stderr)
    print("Install without activation: .venv/bin/python -m pip install -r requirements.txt pyyaml", file=sys.stderr)
    sys.exit(2)
'; then
    exit 2
fi

if [[ ! -f settings.json ]]; then
    echo "ERROR: settings.json is missing; run the v1.2.1 importer before testing." >&2
    echo "See docs/UPGRADE_FROM_1_2_1.md. The test runner will not create a placeholder." >&2
    exit 2
fi

echo "== Syntax and import compilation =="
"$PYTHON_BIN" -m compileall -q bot tests scripts install.py update.py update_lavalink.py
echo "== Complete unit suite =="
"$PYTHON_BIN" -m unittest discover -s tests -p 'test_*.py' -v

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "== Docker Compose validation =="
    docker compose config --quiet
else
    echo "SKIP: Docker Compose validation (Docker Compose v2 not installed)"
fi

echo "PASS: available local checks completed."
