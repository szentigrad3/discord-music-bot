#!/usr/bin/env bash
# install.sh — Bootstrap the Discord Music Bot installer.
#
# This script verifies that Python 3.12+ is available, then delegates to
# install.py which drives the full interactive, Docker-based installation
# (including optional Lavalink and Dashboard services).
set -euo pipefail

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { echo "[INFO]  $*"; }
error() { echo "[ERROR] $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 1. Locate Python 3.12+
# ---------------------------------------------------------------------------
info "Checking Python version..."

PYTHON_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        _ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        _major=$(echo "$_ver" | cut -d. -f1)
        _minor=$(echo "$_ver" | cut -d. -f2)
        if [ "${_major:-0}" -ge 3 ] && [ "${_minor:-0}" -ge 12 ]; then
            PYTHON_BIN="$candidate"
            info "Using $candidate $_ver"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    error "Python 3.12 or newer is required but was not found.
  On Debian/Ubuntu:  sudo apt install python3.12
  On macOS:          brew install python@3.12
  Or download from:  https://www.python.org/downloads/"
fi

# ---------------------------------------------------------------------------
# 2. Run the Python installer
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$PYTHON_BIN" "$SCRIPT_DIR/install.py" "$@"
