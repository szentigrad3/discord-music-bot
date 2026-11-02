#!/usr/bin/env bash
# One-command offline validation; never starts Discord or requires credentials.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON_BIN="${PYTHON_BIN:-python3}"
echo "== Python version =="
"$PYTHON_BIN" --version
echo "== Syntax and import compilation =="
"$PYTHON_BIN" -m compileall -q bot tests install.py update.py update_lavalink.py
echo "== Complete unit suite =="
"$PYTHON_BIN" -m unittest discover -s tests -p 'test_*.py' -v
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "== Docker Compose validation =="
    docker compose config --quiet
else
    echo "SKIP: Docker Compose validation (Docker Compose v2 not installed)"
fi
echo "PASS: available local checks completed."
