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
import os
import shutil
import subprocess
import sys
import zipfile
from io import BytesIO

import requests

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
__version__ = "v1.0.0"

PYTHON_CMD_NAME = os.path.basename(sys.executable)
GITHUB_API_URL = "https://api.github.com/repos/szentigrad3/discord-music-bot/releases/latest"
DOWNLOAD_URL = "https://github.com/szentigrad3/discord-music-bot/archive/"

# Files and directories to preserve across updates.
IGNORE_FILES = ["settings.json", "data", "logs", ".venv", "venv"]


class bcolors:
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    OKGREEN = "\033[92m"
    ENDC = "\033[0m"


def check_version(with_msg: bool = False) -> str:
    """Check for the latest release on GitHub.

    Args:
        with_msg: When True, print whether the bot is up-to-date.

    Returns:
        The latest version tag string (e.g. ``"v1.2.0"``).
    """
    response = requests.get(GITHUB_API_URL, timeout=10)
    response.raise_for_status()
    latest_version = response.json().get("name", __version__)
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
    """Download a release zip from GitHub.

    Args:
        version: Tag name to download.  Fetches the latest release when omitted.

    Returns:
        The HTTP response whose content is the downloaded zip archive.
    """
    if version is None:
        version = check_version()
    print(f"Downloading discord-music-bot version: {version}")
    response = requests.get(DOWNLOAD_URL + version + ".zip", timeout=60)
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

    print("Installing ...")
    zfile = zipfile.ZipFile(BytesIO(response.content))
    zfile.extractall(ROOT_DIR)

    # The extracted folder is named discord-music-bot-<version without "v">.
    version_without_v = version.lstrip("v")
    source_dir = os.path.join(ROOT_DIR, f"discord-music-bot-{version_without_v}")

    if os.path.exists(source_dir):
        skip_names = set(IGNORE_FILES + [f"discord-music-bot-{version_without_v}"])
        for filename in os.listdir(ROOT_DIR):
            if filename in skip_names:
                continue
            filename_path = os.path.join(ROOT_DIR, filename)
            if os.path.isdir(filename_path):
                shutil.rmtree(filename_path)
            else:
                os.remove(filename_path)
        for filename in os.listdir(source_dir):
            shutil.move(
                os.path.join(source_dir, filename),
                os.path.join(ROOT_DIR, filename),
            )
        os.rmdir(source_dir)

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
        response = download_file(version)
        install(response, version)

    else:
        print(
            f"{bcolors.FAIL}No arguments provided. "
            f"Run `{PYTHON_CMD_NAME} update.py -h` for help.{bcolors.ENDC}"
        )


if __name__ == "__main__":
    main()
