#!/usr/bin/env python3
"""
Lavalink and plugin updater for non-Docker installations.

For Docker installations Watchtower handles Lavalink updates automatically.
Run this script manually (or via cron / Task Scheduler) to keep a bare-metal
Lavalink JAR and its plugins up-to-date:

    python update_lavalink.py           # update JAR + plugins
    python update_lavalink.py --jar     # update JAR only
    python update_lavalink.py --plugins # update plugins only
    python update_lavalink.py --check   # print current vs. latest versions
"""

import argparse
import os
import re
import sys

import requests

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
LAVALINK_DIR = os.path.join(ROOT_DIR, "lavalink")

# Path to the Lavalink JAR managed by install.py.
LAVALINK_JAR_PATH = os.path.join(LAVALINK_DIR, "Lavalink.jar")

# Stores the version tag of the currently installed JAR so we can skip
# unnecessary re-downloads when the JAR is already up-to-date.
LAVALINK_VERSION_FILE = os.path.join(LAVALINK_DIR, ".lavalink-version")

LAVALINK_RELEASES_API_URL = (
    "https://api.github.com/repos/lavalink-devs/Lavalink/releases/latest"
)
LAVALINK_JAR_URL = (
    "https://github.com/lavalink-devs/Lavalink/releases/latest/download/Lavalink.jar"
)

# Maps each plugin's Maven group:artifact coordinate to its GitHub releases API URL.
# Update this dict when new first-party plugins are added to the default config.
PLUGIN_RELEASES: dict[str, str] = {
    "dev.lavalink.youtube:youtube-plugin": (
        "https://api.github.com/repos/lavalink-devs/youtube-source/releases/latest"
    ),
    "com.github.topi314.lavasrc:lavasrc-plugin": (
        "https://api.github.com/repos/topi314/LavaSrc/releases/latest"
    ),
}

# Lavalink config files that contain plugin dependency declarations.
# Both the generic and Docker-specific configs are updated together so they
# stay in sync.
LAVALINK_CONFIG_FILES: list[str] = [
    os.path.join(LAVALINK_DIR, "application.yml"),
    os.path.join(LAVALINK_DIR, "application.docker.yml"),
]


class bcolors:
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL    = "\033[91m"
    ENDC    = "\033[0m"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_local_lavalink_version() -> str:
    """Return the version tag recorded in .lavalink-version, or 'unknown'."""
    if os.path.exists(LAVALINK_VERSION_FILE):
        with open(LAVALINK_VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip()
    return "unknown"


def fetch_latest_github_tag(api_url: str) -> str:
    """Query the GitHub releases API and return the latest release tag name.

    Any leading ``v`` is stripped so the result can be used directly as a
    Maven version string (e.g. ``4.8.1`` rather than ``v4.8.1``).
    """
    response = requests.get(api_url, timeout=10)
    response.raise_for_status()
    tag: str = response.json()["tag_name"]
    return tag.lstrip("v")


# ---------------------------------------------------------------------------
# JAR updater
# ---------------------------------------------------------------------------

def update_lavalink_jar() -> bool:
    """Check for a newer Lavalink JAR and download it if one is available.

    Skips silently when ``Lavalink.jar`` is not present (Docker installs or
    setups where Lavalink is managed externally).

    Returns:
        ``True`` if the JAR was updated, ``False`` if already up-to-date or
        not applicable.
    """
    if not os.path.exists(LAVALINK_JAR_PATH):
        return False

    latest = fetch_latest_github_tag(LAVALINK_RELEASES_API_URL)
    current = _read_local_lavalink_version()

    if latest == current:
        print(f"{bcolors.OKGREEN}Lavalink JAR is already up-to-date! ({current}){bcolors.ENDC}")
        return False

    print(f"Updating Lavalink JAR: {current} → {latest} …")
    response = requests.get(LAVALINK_JAR_URL, timeout=120)
    response.raise_for_status()

    with open(LAVALINK_JAR_PATH, "wb") as f:
        f.write(response.content)
    with open(LAVALINK_VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(latest)

    print(f"{bcolors.OKGREEN}Lavalink JAR updated to {latest}.{bcolors.ENDC}")
    return True


# ---------------------------------------------------------------------------
# Plugin updater
# ---------------------------------------------------------------------------

def update_lavalink_plugins() -> bool:
    """Update Lavalink plugin version pins in application config files.

    Queries the GitHub releases API for each plugin listed in
    :data:`PLUGIN_RELEASES` and replaces the pinned version string in every
    config file that exists on disk.  Both ``application.yml`` and
    ``application.docker.yml`` are updated so they stay in sync.

    Lavalink re-downloads plugins whose version has changed on the next
    startup, so no manual intervention is required after running this.

    Returns:
        ``True`` if at least one plugin version was updated, ``False``
        otherwise.
    """
    updated = False

    for group_artifact, api_url in PLUGIN_RELEASES.items():
        latest = fetch_latest_github_tag(api_url)
        # Matches: dependency: "group:artifact:OLD_VERSION"
        pattern = re.compile(
            r'(dependency:\s*"' + re.escape(group_artifact) + r':)([^"]+)(")'
        )

        for config_path in LAVALINK_CONFIG_FILES:
            if not os.path.exists(config_path):
                continue

            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()

            new_content, count = pattern.subn(r"\g<1>" + latest + r"\g<3>", content)
            if count and new_content != content:
                with open(config_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(
                    f"{bcolors.OKGREEN}Updated {group_artifact} to {latest} "
                    f"in {os.path.basename(config_path)}.{bcolors.ENDC}"
                )
                updated = True

    if not updated:
        print(f"{bcolors.OKGREEN}All Lavalink plugins are already up-to-date!{bcolors.ENDC}")

    return updated


# ---------------------------------------------------------------------------
# Version check (read-only)
# ---------------------------------------------------------------------------

def check_versions() -> None:
    """Print the currently installed and latest available versions."""
    current_lavalink = _read_local_lavalink_version()

    if os.path.exists(LAVALINK_JAR_PATH):
        latest_lavalink = fetch_latest_github_tag(LAVALINK_RELEASES_API_URL)
        status = (
            f"{bcolors.OKGREEN}up-to-date{bcolors.ENDC}"
            if latest_lavalink == current_lavalink
            else f"{bcolors.WARNING}update available: {latest_lavalink}{bcolors.ENDC}"
        )
        print(f"Lavalink JAR  : {current_lavalink}  ({status})")
    else:
        print("Lavalink JAR  : not found (Docker or externally managed)")

    for group_artifact, api_url in PLUGIN_RELEASES.items():
        latest_plugin = fetch_latest_github_tag(api_url)
        # Find the current version from the first existing config file.
        current_plugin = "unknown"
        pattern = re.compile(
            r'dependency:\s*"' + re.escape(group_artifact) + r':([^"]+)"'
        )
        for config_path in LAVALINK_CONFIG_FILES:
            if not os.path.exists(config_path):
                continue
            with open(config_path, "r", encoding="utf-8") as f:
                m = pattern.search(f.read())
            if m:
                current_plugin = m.group(1)
                break
        status = (
            f"{bcolors.OKGREEN}up-to-date{bcolors.ENDC}"
            if latest_plugin == current_plugin
            else f"{bcolors.WARNING}update available: {latest_plugin}{bcolors.ENDC}"
        )
        print(f"{group_artifact}: {current_plugin}  ({status})")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Update the Lavalink JAR and/or plugin versions for non-Docker installations.\n"
            "With no flags, both the JAR and all plugins are updated."
        ),
    )
    parser.add_argument(
        "--jar",
        action="store_true",
        help="Update the Lavalink JAR only.",
    )
    parser.add_argument(
        "--plugins",
        action="store_true",
        help="Update Lavalink plugin versions in application config files only.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Print current and latest versions without making any changes.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.check:
        check_versions()
        return

    if args.jar:
        update_lavalink_jar()
    elif args.plugins:
        update_lavalink_plugins()
    else:
        # Default: update both JAR and plugins.
        update_lavalink_jar()
        update_lavalink_plugins()


if __name__ == "__main__":
    main()
