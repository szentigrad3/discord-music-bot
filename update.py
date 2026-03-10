"""MIT License

Copyright (c) 2025 - present szentigrad3

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from io import BytesIO

import requests

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

PYTHON_CMD_NAME = os.path.basename(sys.executable)
VERSION_FILE = os.path.join(ROOT_DIR, "version.txt")
VERSION_URL = "https://raw.githubusercontent.com/szentigrad3/discord-music-bot/main/version.txt"
DOWNLOAD_URL = "https://github.com/szentigrad3/discord-music-bot/archive/refs/heads/main.zip"


def _read_local_version() -> str:
    """Read the installed version from version.txt."""
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE) as f:
            return f.read().strip()
    return "unknown"


__version__ = _read_local_version()

# Files and directories to preserve across updates.
IGNORE_FILES = ["settings.json", "data", "logs"]


class bcolors:
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    OKGREEN = "\033[92m"
    ENDC = "\033[0m"


def check_version(with_msg: bool = False) -> str:
    """Check for the latest version on the main branch.

    Args:
        with_msg: When True, print whether the bot is up-to-date.

    Returns:
        The latest version string read from main's ``version.txt``.
    """
    response = requests.get(VERSION_URL, timeout=10)
    response.raise_for_status()
    latest_version = response.text.strip()
    if with_msg:
        if latest_version == __version__:
            print(
                f"{bcolors.OKGREEN}Your bot is up-to-date! - {latest_version}{bcolors.ENDC}"
            )
        else:
            print(
                f"{bcolors.WARNING}Your bot is not up-to-date! "
                f"The latest version is {latest_version} and you are currently "
                f"running version {__version__}\n"
                f"Run `{PYTHON_CMD_NAME} update.py -l` to update your bot!{bcolors.ENDC}"
            )
    return latest_version


def download_file(version: str | None = None) -> requests.Response:
    """Download the main branch zip from GitHub.

    Args:
        version: Used only for the progress message.  The main branch is
            only downloaded when the version increases.

    Returns:
        The HTTP response whose content is the downloaded zip archive.
    """
    if version is None:
        version = check_version()
    print(f"Downloading discord-music-bot version: {version}")
    response = requests.get(DOWNLOAD_URL, timeout=60)
    if response.status_code == 404:
        print(f"{bcolors.FAIL}Error: Version not found!{bcolors.ENDC}")
        sys.exit(1)
    print("Download completed.")
    return response


def _run_pip_install() -> None:
    """Install Python dependencies from requirements.txt into the active environment."""
    req_file = os.path.join(ROOT_DIR, "requirements.txt")
    if not os.path.exists(req_file):
        return
    print("Installing Python dependencies...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_file],
        check=True,
    )
    print(f"{bcolors.OKGREEN}Dependencies installed.{bcolors.ENDC}")


def _is_docker_setup() -> bool:
    """Return True when a docker-compose.yml is present and Docker is running.

    This is used to decide whether ``install()`` should rebuild the Docker
    Compose stack instead of running ``pip install`` directly.
    """
    compose_file = os.path.join(ROOT_DIR, "docker-compose.yml")
    if not os.path.exists(compose_file):
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _run_docker_compose_build() -> None:
    """Rebuild and restart the Docker Compose stack after an update."""
    print("Rebuilding and restarting Docker containers...")
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", "--build"],
            check=True,
            cwd=ROOT_DIR,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        print(
            f"{bcolors.FAIL}docker compose up timed out. "
            f"Run `docker compose up -d --build` manually to start your bot.{bcolors.ENDC}"
        )
        return
    except (OSError, subprocess.CalledProcessError) as exc:
        print(
            f"{bcolors.FAIL}Failed to rebuild Docker containers: {exc}\n"
            f"Run `docker compose up -d --build` manually to start your bot.{bcolors.ENDC}"
        )
        return
    print(f"{bcolors.OKGREEN}Docker containers updated and restarted.{bcolors.ENDC}")


def _read_docker_secrets() -> dict[str, str | None]:
    """Read persisted credentials from existing config files before an update.

    Reads from ``settings.json`` (which is preserved across updates via
    :data:`IGNORE_FILES`): Lavalink password, Lavalink port, and Spotify
    credentials.  Reads the YouTube OAuth refresh token from
    ``lavalink/application.docker.yml`` or ``lavalink/application.yml``
    (both are overwritten during updates and must be captured beforehand).

    Returns:
        Dict with the following keys (values are ``None`` when absent):

        - ``lavalink_password``
        - ``lavalink_port``
        - ``spotify_client_id``
        - ``spotify_client_secret``
        - ``youtube_refresh_token``
    """
    secrets: dict[str, str | None] = {
        "lavalink_password": None,
        "lavalink_port": None,
        "spotify_client_id": None,
        "spotify_client_secret": None,
        "youtube_refresh_token": None,
    }

    settings_path = os.path.join(ROOT_DIR, "settings.json")
    if os.path.exists(settings_path):
        try:
            with open(settings_path) as f:
                data = json.load(f)
            password = data.get("lavalink", {}).get("password")
            if password:
                secrets["lavalink_password"] = password
            port = data.get("lavalink", {}).get("port")
            if port is not None:
                try:
                    secrets["lavalink_port"] = str(int(port))
                except (TypeError, ValueError):
                    pass
            spotify_id = data.get("spotify_client_id", "")
            if spotify_id:
                secrets["spotify_client_id"] = spotify_id
            spotify_secret = data.get("spotify_client_secret", "")
            if spotify_secret:
                secrets["spotify_client_secret"] = spotify_secret
        except (OSError, ValueError):
            pass

    if secrets["lavalink_password"] is None:
        docker_compose = os.path.join(ROOT_DIR, "docker-compose.yml")
        if os.path.exists(docker_compose):
            try:
                with open(docker_compose) as f:
                    content = f.read()
                m = re.search(r"LAVALINK_SERVER_PASSWORD=(\S+)", content)
                if m:
                    secrets["lavalink_password"] = m.group(1).strip()
            except OSError:
                pass

    # Try both lavalink config files for the refresh token; the docker variant
    # is checked first, then the non-docker variant as a fallback.
    _refresh_token_pattern = re.compile(
        r'^ +refreshToken:\s*"([^"]+)"', re.MULTILINE
    )
    for config_name in ("lavalink/application.docker.yml", "lavalink/application.yml"):
        if secrets["youtube_refresh_token"] is not None:
            break
        config_path = os.path.join(ROOT_DIR, config_name)
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    content = f.read()
                m = _refresh_token_pattern.search(content)
                if m:
                    secrets["youtube_refresh_token"] = m.group(1)
            except OSError:
                pass

    return secrets


def _patch_docker_files(secrets: dict[str, str | None]) -> None:
    """Apply preserved credentials to freshly extracted docker config files.

    Updates ``docker-compose.yml`` with the saved Lavalink password and port,
    and updates both ``lavalink/application.docker.yml`` and
    ``lavalink/application.yml`` with the same set of values so that the
    Docker and non-Docker configurations remain in sync:

    - Lavalink server password
    - Lavalink server port
    - Spotify client ID and client secret
    - YouTube OAuth refresh token

    Args:
        secrets: Dict returned by :func:`_read_docker_secrets`.
    """
    password = secrets.get("lavalink_password")
    port = secrets.get("lavalink_port")
    spotify_id = secrets.get("spotify_client_id")
    spotify_secret = secrets.get("spotify_client_secret")
    yt_token = secrets.get("youtube_refresh_token")

    docker_compose = os.path.join(ROOT_DIR, "docker-compose.yml")
    if os.path.exists(docker_compose) and (password or port):
        try:
            with open(docker_compose) as f:
                content = f.read()
            new_content = content
            if password:
                new_content = re.sub(
                    r"(LAVALINK_SERVER_PASSWORD=)\S+",
                    lambda m: m.group(1) + password,
                    new_content,
                )
            if port:
                new_content = re.sub(
                    r"(SERVER_PORT=)\S+",
                    lambda m: m.group(1) + port,
                    new_content,
                )
            if new_content != content:
                with open(docker_compose, "w") as f:
                    f.write(new_content)
                print(
                    f"{bcolors.OKGREEN}Preserved Lavalink credentials in docker-compose.yml{bcolors.ENDC}"
                )
        except OSError:
            pass

    for config_name in (
        "lavalink/application.docker.yml",
        "lavalink/application.yml",
    ):
        config_path = os.path.join(ROOT_DIR, config_name)
        if not os.path.exists(config_path):
            continue
        try:
            with open(config_path) as f:
                content = f.read()
            changed = False

            if port:
                new_content = re.sub(
                    r"^(  port:\s*)\d+",
                    lambda m: m.group(1) + port,
                    content,
                    flags=re.MULTILINE,
                )
                if new_content != content:
                    content = new_content
                    changed = True

            if password:
                new_content = re.sub(
                    r'^(    password:\s*)"[^"]*"',
                    lambda m: m.group(1) + f'"{password}"',
                    content,
                    flags=re.MULTILINE,
                )
                if new_content != content:
                    content = new_content
                    changed = True

            if spotify_id:
                new_content = re.sub(
                    r'^(      clientId:\s*)"[^"]*"',
                    lambda m: m.group(1) + f'"{spotify_id}"',
                    content,
                    flags=re.MULTILINE,
                )
                if new_content != content:
                    content = new_content
                    changed = True

            if spotify_secret:
                new_content = re.sub(
                    r'^(      clientSecret:\s*)"[^"]*"',
                    lambda m: m.group(1) + f'"{spotify_secret}"',
                    content,
                    flags=re.MULTILINE,
                )
                if new_content != content:
                    content = new_content
                    changed = True

            if yt_token:
                # Handles both commented-out (#refreshToken or # refreshToken)
                # and already-set refreshToken lines.
                new_content = re.sub(
                    r'^( +)(#\s*)?refreshToken:\s*"[^"]*"',
                    lambda m: m.group(1) + f'refreshToken: "{yt_token}"',
                    content,
                    flags=re.MULTILINE,
                )
                # Enable skipInitialization now that a token is present.
                new_content = re.sub(
                    r"^( +skipInitialization:\s*)false",
                    r"\g<1>true",
                    new_content,
                    flags=re.MULTILINE,
                )
                if new_content != content:
                    content = new_content
                    changed = True

            if changed:
                with open(config_path, "w") as f:
                    f.write(content)
                print(
                    f"{bcolors.OKGREEN}Preserved credentials in {config_name}{bcolors.ENDC}"
                )
        except OSError:
            pass


def install(response: requests.Response, version: str) -> None:
    """Extract and install the downloaded release, preserving user files.

    Args:
        response: HTTP response containing the zip archive.
        version:  Version tag that was downloaded.
    """
    user_input = input(
        f"{bcolors.WARNING}"
        "--------------------------------------------------------------------------\n"
        "Note: Before proceeding, please ensure that there are no personal files or\n"
        "sensitive information in the directory you're about to replace. This action\n"
        "is irreversible, so it's important to double-check that you're making the\n"
        f"right decision. {bcolors.ENDC} Continue with caution? (Y/n) "
    )

    if user_input.lower() not in ("y", "yes"):
        print("Update canceled!")
        return

    # Capture credentials from existing docker configs before they are overwritten.
    secrets = _read_docker_secrets()

    print("Installing ...")
    zfile = zipfile.ZipFile(BytesIO(response.content))
    zfile.extractall(ROOT_DIR)

    # Detect the top-level directory name from the zip archive (e.g. discord-music-bot-main).
    source_dir_name = zfile.namelist()[0].split("/")[0]
    source_dir = os.path.join(ROOT_DIR, source_dir_name)

    if os.path.exists(source_dir):
        skip_names = set(IGNORE_FILES + [source_dir_name])
        for filename in os.listdir(ROOT_DIR):
            if filename in skip_names:
                continue
            filename_path = os.path.join(ROOT_DIR, filename)
            if os.path.isdir(filename_path):
                shutil.rmtree(filename_path)
            else:
                os.remove(filename_path)
        for filename in os.listdir(source_dir):
            dst = os.path.join(ROOT_DIR, filename)
            if filename in IGNORE_FILES and os.path.exists(dst):
                # The destination already contains user data that must be
                # preserved.  Moving the archive copy into an existing
                # directory would cause shutil.move to nest it (e.g.
                # data/data), so skip it entirely.
                continue
            shutil.move(os.path.join(source_dir, filename), dst)
        shutil.rmtree(source_dir)

    # Restore preserved credentials in the freshly extracted docker configs.
    _patch_docker_files(secrets)

    if _is_docker_setup():
        _run_docker_compose_build()
        print(f"{bcolors.OKGREEN}Version {version} installed successfully!{bcolors.ENDC}")
    else:
        _run_pip_install()
        print(
            f"{bcolors.OKGREEN}Version {version} installed successfully! "
            f"Run `{PYTHON_CMD_NAME} -m bot.main` to start your bot.{bcolors.ENDC}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update script for discord-music-bot."
    )
    parser.add_argument(
        "-c", "--check",
        action="store_true",
        help="Check the current version of the bot.",
    )
    parser.add_argument(
        "-v", "--version",
        type=str,
        metavar="VERSION",
        help="Install a specific version (e.g. v1.2.0).",
    )
    parser.add_argument(
        "-l", "--latest",
        action="store_true",
        help="Install the latest release from GitHub.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.check:
        check_version(with_msg=True)

    elif args.version:
        response = download_file(args.version)
        install(response, args.version)

    elif args.latest:
        version = check_version()
        if version == __version__:
            print(
                f"{bcolors.OKGREEN}Your bot is already up-to-date! ({version}){bcolors.ENDC}"
            )
        else:
            response = download_file(version)
            install(response, version)

    else:
        print(
            f"{bcolors.FAIL}No arguments provided. "
            f"Run `{PYTHON_CMD_NAME} update.py -h` for help.{bcolors.ENDC}"
        )


if __name__ == "__main__":
    main()
