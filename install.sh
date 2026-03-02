#!/usr/bin/env bash
# install.sh — Set up the Discord Music Bot using the Vocard Installer.
set -euo pipefail

INSTALLER_URL="https://raw.githubusercontent.com/ChocoMeow/Vocard-Installer/refs/heads/main/installer.py"
INSTALLER_TMP=$(mktemp /tmp/vocard_installer.XXXXXX.py)
trap 'rm -f "$INSTALLER_TMP"' EXIT

if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found. Please install Python 3 or newer." >&2
    exit 1
fi

echo "[INFO] Downloading Vocard Installer..."
if command -v curl &>/dev/null; then
    curl -fsSL "$INSTALLER_URL" -o "$INSTALLER_TMP"
elif command -v wget &>/dev/null; then
    wget -q "$INSTALLER_URL" -O "$INSTALLER_TMP"
else
    echo "[ERROR] Neither curl nor wget found. Please install one of them." >&2
    exit 1
fi

echo "[INFO] Running Vocard Installer..."
python3 "$INSTALLER_TMP"
