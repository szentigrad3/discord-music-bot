#!/usr/bin/env python3
"""
Discord Music Bot — One-Click Installer
Interactive Python installer with Docker support.
Supports Windows, macOS, and Linux.
"""

import os
import sys
import platform
import subprocess
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

class Colors:
    """ANSI colour codes for terminal output (disabled on Windows without VT)."""
    RED       = '\033[91m'
    GREEN     = '\033[92m'
    YELLOW    = '\033[93m'
    BLUE      = '\033[94m'
    PURPLE    = '\033[95m'
    CYAN      = '\033[96m'
    WHITE     = '\033[97m'
    BOLD      = '\033[1m'
    END       = '\033[0m'

    @staticmethod
    def clear_screen() -> None:
        os.system('cls' if os.name == 'nt' else 'clear')


# ---------------------------------------------------------------------------
# Configuration manager
# ---------------------------------------------------------------------------

class ConfigurationManager:
    """Collects and validates configuration from the user."""

    REQUIRED_FIELDS: dict[str, dict] = {
        'bot_token': {
            'prompt': 'Discord Bot Token',
            'description': (
                "Your Discord bot's secret token.\n\n"
                "How to get it:\n"
                "  1. Go to https://discord.com/developers/applications\n"
                "  2. Select your bot application (or create a new one)\n"
                "  3. Go to the \"Bot\" section\n"
                "  4. Click \"Reset Token\" to reveal your bot token\n"
                "  5. Copy the token (keep it secret!)"
            ),
        },
        'client_id': {
            'prompt': 'Discord Client ID (Application ID)',
            'description': (
                "Your Discord application's client ID.\n\n"
                "How to get it:\n"
                "  1. Go to https://discord.com/developers/applications\n"
                "  2. Select your bot application\n"
                "  3. In \"General Information\" copy the \"Application ID\""
            ),
        },
        'discord_client_secret': {
            'prompt': 'Discord Client Secret',
            'description': (
                "Your Discord application's client secret (OAuth2).\n\n"
                "How to get it:\n"
                "  1. Go to https://discord.com/developers/applications\n"
                "  2. Select your bot application\n"
                "  3. Go to \"OAuth2\" → \"General\"\n"
                "  4. Click \"Reset Secret\" and copy the value"
            ),
        },
    }

    LAVALINK_FIELDS: dict[str, dict] = {
        'lavalink_port': {
            'prompt': 'Lavalink Port',
            'default': '2333',
            'description': (
                "Port for the Lavalink audio server.\n"
                "Default: 2333 — make sure it is not used by another service."
            ),
        },
        'lavalink_password': {
            'prompt': 'Lavalink Password',
            'default': 'youshallnotpass',
            'description': (
                "Password that the bot uses to authenticate with Lavalink.\n"
                "Default: youshallnotpass — change this for production."
            ),
        },
        'spotify_client_id': {
            'prompt': 'Spotify Client ID (optional)',
            'default': '',
            'description': (
                "Spotify client ID for Spotify track/playlist support (optional).\n\n"
                "How to get it:\n"
                "  1. Go to https://developer.spotify.com/dashboard\n"
                "  2. Create or open an app\n"
                "  3. Copy the Client ID"
            ),
        },
        'spotify_client_secret': {
            'prompt': 'Spotify Client Secret (optional)',
            'default': '',
            'description': (
                "Spotify client secret for Spotify track/playlist support (optional).\n\n"
                "How to get it:\n"
                "  1. Go to https://developer.spotify.com/dashboard\n"
                "  2. Open your app settings\n"
                "  3. Click \"Show client secret\" and copy the value"
            ),
        },
        'youtube_refresh_token': {
            'prompt': 'YouTube Refresh Token (optional)',
            'default': '',
            'description': (
                "YouTube OAuth2 refresh token for authenticated playback (optional).\n"
                "Providing this token allows the bot to play age-restricted and\n"
                "region-locked YouTube content.\n\n"
                "How to get it:\n"
                "  1. Follow the youtube-source OAuth guide:\n"
                "     https://github.com/lavalink-devs/youtube-source#oauth-token\n"
                "  2. Paste your refresh token here, or leave blank to skip"
            ),
        },
    }

    DASHBOARD_FIELDS: dict[str, dict] = {
        'dashboard_port': {
            'prompt': 'Dashboard Port',
            'default': '3000',
            'description': (
                "Port the web dashboard will listen on.\n"
                "Default: 3000 — access at http://localhost:3000"
            ),
        },
        'discord_callback_url': {
            'prompt': 'Discord OAuth2 Callback URL',
            'default': 'http://localhost:3000/auth/discord/callback',
            'description': (
                "OAuth2 redirect URI registered in your Discord application.\n"
                "Default: http://localhost:3000/auth/discord/callback\n\n"
                "Add this URL in Discord Developer Portal → OAuth2 → Redirects."
            ),
        },
        'session_secret': {
            'prompt': 'Dashboard Session Secret',
            'default': '',
            'description': (
                "Long random string used to encrypt dashboard sessions.\n"
                "Use a password generator to create a 50+ character random string."
            ),
        },
    }

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _display_help(field_config: dict) -> None:
        if 'description' in field_config:
            print(f"\n{Colors.CYAN}{'─' * 60}{Colors.END}")
            print(f"{Colors.CYAN}ℹ  Help:{Colors.END}")
            print(field_config['description'])
            print(f"{Colors.CYAN}{'─' * 60}{Colors.END}")
        print()

    @staticmethod
    def _section(title: str, color: str = Colors.PURPLE) -> None:
        print(f"\n{color}{'=' * 60}{Colors.END}")
        print(f"{color}{Colors.BOLD}{title}{Colors.END}")
        print(f"{color}{'=' * 60}{Colors.END}")

    def get_required(self, prompt: str, field_config: dict) -> str:
        self._display_help(field_config)
        while True:
            value = input(f"{Colors.YELLOW}{prompt}: {Colors.END}").strip()
            if value:
                Colors.clear_screen()
                return value
            print(f"{Colors.RED}This field is required. Please enter a value.{Colors.END}")

    def get_optional(self, prompt: str, default: str, field_config: dict) -> str:
        self._display_help(field_config)
        display = (
            f"{Colors.YELLOW}{prompt} [{default}]: {Colors.END}"
            if default
            else f"{Colors.YELLOW}{prompt} (optional, press Enter to skip): {Colors.END}"
        )
        value = input(display).strip()
        Colors.clear_screen()
        return value if value else default

    def yes_no(self, prompt: str, default: bool = True) -> bool:
        hint = "Y/n" if default else "y/N"
        while True:
            ans = input(f"{prompt} ({hint}): ").strip().lower()
            if not ans:
                Colors.clear_screen()
                return default
            if ans in ('y', 'yes'):
                Colors.clear_screen()
                return True
            if ans in ('n', 'no'):
                Colors.clear_screen()
                return False
            print(f"{Colors.RED}Please enter 'y' or 'n'{Colors.END}")

    # ------------------------------------------------------------------ sections

    def collect_basic(self) -> dict[str, Any]:
        self._section("🤖  BASIC BOT CONFIGURATION")
        config: dict[str, Any] = {}
        for i, (field, fc) in enumerate(self.REQUIRED_FIELDS.items()):
            if i > 0:
                self._section("🤖  BASIC BOT CONFIGURATION")
            print(f"\n{Colors.BOLD}{Colors.YELLOW}📋  {fc['prompt']}{Colors.END}")
            config[field] = self.get_required(fc['prompt'], fc)
        print(f"\n{Colors.GREEN}✅  Basic configuration completed!{Colors.END}")
        return config

    def collect_lavalink(self) -> dict[str, Any]:
        self._section("🎵  LAVALINK CONFIGURATION", Colors.CYAN)
        config: dict[str, Any] = {}
        for i, (field, fc) in enumerate(self.LAVALINK_FIELDS.items()):
            if i > 0:
                self._section("🎵  LAVALINK CONFIGURATION", Colors.CYAN)
            print(f"\n{Colors.BOLD}{Colors.YELLOW}📋  {fc['prompt']}{Colors.END}")
            config[field] = self.get_optional(fc['prompt'], fc['default'], fc)
        print(f"\n{Colors.GREEN}✅  Lavalink configuration completed!{Colors.END}")
        return config

    def collect_dashboard(self) -> dict[str, Any]:
        self._section("🌐  DASHBOARD CONFIGURATION", Colors.CYAN)
        config: dict[str, Any] = {}
        for i, (field, fc) in enumerate(self.DASHBOARD_FIELDS.items()):
            if i > 0:
                self._section("🌐  DASHBOARD CONFIGURATION", Colors.CYAN)
            print(f"\n{Colors.BOLD}{Colors.YELLOW}📋  {fc['prompt']}{Colors.END}")
            config[field] = self.get_optional(fc['prompt'], fc['default'], fc)
        print(f"\n{Colors.GREEN}✅  Dashboard configuration completed!{Colors.END}")
        return config

    def collect_install_dir(self, default: Path) -> Path:
        self._section("📁  INSTALLATION DIRECTORY")
        fc = {
            'description': (
                f"Directory where the bot will be installed.\n"
                f"The installer will create it if it does not exist.\n"
                f"Default: {default}"
            ),
        }
        print(f"\n{Colors.BOLD}{Colors.YELLOW}📋  Installation directory{Colors.END}")
        raw = self.get_optional("Installation directory", str(default), fc)
        return Path(raw)


# ---------------------------------------------------------------------------
# File manager
# ---------------------------------------------------------------------------

class FileManager:
    """Downloads remote files and creates local directories."""

    @staticmethod
    def download(url: str, destination: Path) -> bool:
        try:
            print(f"{Colors.CYAN}Downloading {url.split('/')[-1]} …{Colors.END}")
            urllib.request.urlretrieve(url, destination)
            print(f"{Colors.GREEN}  → {destination}{Colors.END}")
            return True
        except Exception as exc:
            print(f"{Colors.RED}Failed to download {url}: {exc}{Colors.END}")
            return False

    @staticmethod
    def mkdir(path: Path) -> bool:
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as exc:
            print(f"{Colors.RED}Failed to create directory {path}: {exc}{Colors.END}")
            return False


# ---------------------------------------------------------------------------
# Docker manager
# ---------------------------------------------------------------------------

class DockerManager:
    """Runs Docker / Docker Compose commands."""

    @staticmethod
    def _clean_corrupted_plugins(plugins_dir: Path) -> None:
        """Remove corrupted plugin JAR files so Lavalink can re-download them.

        A corrupted JAR (e.g. from an interrupted download) causes a
        ``ZipException: zip END header not found`` that prevents Lavalink from
        starting.  Removing the bad file lets Lavalink fetch a fresh copy.
        """
        for jar in plugins_dir.glob('*.jar'):
            try:
                with zipfile.ZipFile(jar) as zf:
                    if zf.testzip() is not None:
                        raise zipfile.BadZipFile('CRC check failed')
            except (zipfile.BadZipFile, OSError):
                print(f"{Colors.YELLOW}Removing corrupted plugin JAR: {jar.name}{Colors.END}")
                try:
                    jar.unlink()
                except OSError as exc:
                    print(f"{Colors.RED}Could not remove {jar.name}: {exc}{Colors.END}")

    @staticmethod
    def run(cmd: str, timeout: int = 1800) -> tuple[bool, str, str]:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=timeout
            )
            return result.returncode == 0, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return False, '', 'Command timed out'
        except Exception as exc:
            return False, '', str(exc)

    def check(self) -> tuple[bool, bool]:
        docker_ok, _, _ = self.run('docker --version')
        compose_v2, _, _ = self.run('docker compose version')
        compose_v1, _, _ = self.run('docker-compose --version')
        return docker_ok, (compose_v2 or compose_v1)

    def start(self, install_dir: Path) -> bool:
        original = os.getcwd()
        try:
            os.chdir(install_dir)
            plugins_dir = install_dir / 'lavalink' / 'plugins'
            if plugins_dir.exists():
                DockerManager._clean_corrupted_plugins(plugins_dir)
            print(f"{Colors.CYAN}Pulling Docker images …{Colors.END}")
            self.run('docker compose pull')
            print(f"{Colors.CYAN}Starting services …{Colors.END}")
            ok, stdout, stderr = self.run('docker compose up -d')
            if ok:
                print(f"{Colors.GREEN}Services started successfully!{Colors.END}")
                status_ok, status_out, _ = self.run('docker compose ps')
                if status_ok:
                    print(f"\n{Colors.BLUE}Service Status:{Colors.END}")
                    print(status_out)
                return True
            print(f"{Colors.RED}Failed to start services: {stderr}{Colors.END}")
            return False
        finally:
            os.chdir(original)


# ---------------------------------------------------------------------------
# Main installer
# ---------------------------------------------------------------------------

class Installer:
    """Orchestrates the full installation."""

    # Lavalink Docker image
    LAVALINK_IMAGE = 'ghcr.io/lavalink-devs/lavalink:latest'
    # Lavalink JAR download URL
    LAVALINK_JAR_URL = (
        'https://github.com/lavalink-devs/Lavalink/releases/latest/download/Lavalink.jar'
    )

    def __init__(self) -> None:
        self.cfg_mgr  = ConfigurationManager()
        self.file_mgr = FileManager()
        self.docker   = DockerManager()

    # ------------------------------------------------------------------ banner

    @staticmethod
    def _banner() -> None:
        print('=' * 60)
        print(f"{Colors.BOLD}{Colors.CYAN}DISCORD MUSIC BOT INSTALLER{Colors.END}")
        print('=' * 60)
        print(f"{Colors.BLUE}System:       {platform.system()} {platform.release()}{Colors.END}")
        print(f"{Colors.BLUE}Architecture: {platform.machine()}{Colors.END}")
        print('=' * 60)

    # ------------------------------------------------------------------ pip requirements

    @staticmethod
    def _install_requirements(install_dir: Path) -> None:
        req_file = install_dir / 'requirements.txt'
        if not req_file.exists():
            return
        print(f"{Colors.BLUE}Installing Python dependencies from requirements.txt…{Colors.END}")
        subprocess.run(
            [sys.executable, '-m', 'pip', 'install', '-r', str(req_file)],
            check=True,
        )
        print(f"{Colors.GREEN}✅  Python dependencies installed.{Colors.END}")

    # ------------------------------------------------------------------ docker-compose writer

    @staticmethod
    def _write_docker_compose(
        install_dir: Path,
        config: dict[str, Any],
        enable_lavalink: bool,
        enable_dashboard: bool,
    ) -> None:
        lavalink_port     = config.get('lavalink_port', '2333')
        lavalink_password = config.get('lavalink_password', 'youshallnotpass')
        dashboard_port    = config.get('dashboard_port', '3000')

        yt_cipher_service = """
  yt-cipher:
    # ghcr.io/kikkia/yt-cipher has no versioned release tags; 'master' is the only available tag.
    # The image uses a distroless base so CMD-SHELL healthchecks are not supported.
    # Lavalink only contacts yt-cipher when deciphering track signatures, so it does not
    # need yt-cipher to be fully ready before it starts.
    image: ghcr.io/kikkia/yt-cipher:master
    restart: unless-stopped
    expose:
      - "8001"
""" if enable_lavalink else ''

        lavalink_service = f"""
  lavalink:
    image: {Installer.LAVALINK_IMAGE}
    restart: unless-stopped
    environment:
      - _JAVA_OPTIONS=-Xmx1G
      - SERVER_PORT={lavalink_port}
      - LAVALINK_SERVER_PASSWORD={lavalink_password}
      - SPRING_CONFIG_LOCATION=file:/opt/lavalink/application.docker.yml
      # Quoted because the trailing colon would otherwise be parsed as a YAML mapping key.
      - "SPRING_CONFIG_IMPORT=optional:configserver:"
    volumes:
      - ./lavalink:/opt/lavalink
    expose:
      - "{lavalink_port}"
    depends_on:
      - yt-cipher
    healthcheck:
      # curl is available in the official Lavalink Docker image
      test: ["CMD-SHELL", "curl -sf http://localhost:{lavalink_port}/version -H \\"Authorization: $$LAVALINK_SERVER_PASSWORD\\" || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
""" if enable_lavalink else ''

        bot_depends = ''
        if enable_lavalink:
            bot_depends = '\n    depends_on:\n      lavalink:\n        condition: service_healthy'

        dashboard_service = f"""
  dashboard:
    build: .
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./settings.json:/app/settings.json
    command: ["python", "-m", "bot.dashboard.app"]
    ports:
      - "{dashboard_port}:{dashboard_port}"
""" if enable_dashboard else ''

        content = (
            f"services:\n"
            f"  bot:\n"
            f"    build: .\n"
            f"    restart: unless-stopped\n"
            f"    environment:\n"
            f"      - BOT_IN_DOCKER=true\n"
            f"    volumes:\n"
            f"      - ./data:/app/data\n"
            f"      - ./settings.json:/app/settings.json\n"
            f"    ports:\n"
            f"      - \"{dashboard_port}:{dashboard_port}\"\n"
            f"{bot_depends}\n"
            f"{yt_cipher_service}"
            f"{lavalink_service}"
            f"{dashboard_service}"
        )

        dest = install_dir / 'docker-compose.yml'
        dest.write_text(content, encoding='utf-8')
        print(f"{Colors.GREEN}Wrote docker-compose.yml{Colors.END}")

    # ------------------------------------------------------------------ settings.json writer

    @staticmethod
    def _write_settings(install_dir: Path, config: dict[str, Any]) -> None:
        data = {
            'token': config['bot_token'],
            'client_id': config['client_id'],
            'client_secret': config.get('discord_client_secret', ''),
            'callback_url': config.get('discord_callback_url', 'http://localhost:3000/auth/discord/callback'),

            'spotify_client_id': config.get('spotify_client_id', ''),
            'spotify_client_secret': config.get('spotify_client_secret', ''),

            'session_secret': config.get('session_secret', ''),
            'dashboard_port': int(config.get('dashboard_port', 3000)),

            'database_url': 'file:./data/bot.db',

            'log_level': 'INFO',
            '_log_level_note': 'Set to DEBUG to capture all internal activity (also overridable via LOG_LEVEL env var)',
            'lavalink': {
                'host': 'localhost',
                'port': int(config.get('lavalink_port', 2333)),
                'password': config.get('lavalink_password', 'youshallnotpass'),
            },
        }
        import json as _json
        dest = install_dir / 'settings.json'
        dest.write_text(_json.dumps(data, indent=4) + '\n', encoding='utf-8')
        print(f"{Colors.GREEN}Wrote settings.json{Colors.END}")

        example = install_dir / 'settings Example.json'
        if example.exists():
            example.unlink()
            print(f"{Colors.GREEN}Removed 'settings Example.json'{Colors.END}")

    # ------------------------------------------------------------------ lavalink config writer

    @staticmethod
    def _write_lavalink_config(
        install_dir: Path,
        config: dict[str, Any],
    ) -> None:
        port     = config.get('lavalink_port', '2333')
        password = config.get('lavalink_password', 'youshallnotpass')
        sp_id     = config.get('spotify_client_id', '')
        sp_secret = config.get('spotify_client_secret', '')
        yt_token  = config.get('youtube_refresh_token', '')

        spotify_enabled = "true" if sp_id else "false"
        # Escape backslashes and double-quotes so the token is safe inside a
        # YAML double-quoted scalar.
        yt_token_escaped = yt_token.replace('\\', '\\\\').replace('"', '\\"')
        if yt_token:
            youtube_oauth_section = (
                f"    oauth:\n"
                f"      enabled: true\n"
                f"      refreshToken: \"{yt_token_escaped}\"\n"
                f"      skipInitialization: true\n"
            )
        else:
            youtube_oauth_section = (
                f"    oauth:\n"
                f"      enabled: true\n"
                f"      # refreshToken: \"your refresh token, only supply this if you have one!\"\n"
                f"      skipInitialization: false\n"
            )
        # remoteCipher delegates YouTube signature extraction to the yt-cipher
        # Docker service (internal hostname) or the public instance (non-Docker).
        docker_remote_cipher_section = (
            "    remoteCipher:\n"
            "      url: \"http://yt-cipher:8001\""
            " # Remote cipher server for YouTube sig function extraction."
            " See https://github.com/kikkia/yt-cipher\n"
        )
        nondocker_remote_cipher_section = (
            "    remoteCipher:\n"
            "      url: \"https://cipher.kikkia.dev/\""
            " # Public yt-cipher instance for YouTube sig function extraction."
            " See https://github.com/kikkia/yt-cipher\n"
        )

        def _build_content(remote_cipher_section: str) -> str:
            return f"""\
server: # REST and WS server
  port: {port}
  address: 0.0.0.0
  http2:
    enabled: false # Disabled: voicelink uses HTTP/1.1 WebSocket; h2c causes empty-error connection failures
plugins:
  youtube:
    enabled: true # Whether this source can be used.
    allowSearch: true # Whether "ytsearch:" and "ytmsearch:" can be used.
    allowDirectVideoIds: true # Whether just video IDs can match. If false, only complete URLs will be loaded.
    allowDirectPlaylistIds: true # Whether just playlist IDs can match. If false, only complete URLs will be loaded.
    # The clients to use for track loading. See below for a list of valid clients.
    # Clients are queried in the order they are given (so the first client is queried first and so on...)
    clients:
      - MUSIC
      - ANDROID_VR
      - ANDROID_MUSIC
      - WEB
      - WEBEMBEDDED
      - TVHTML5_SIMPLY
      - TV
    # The below section of the config allows setting specific options for each client, such as the requests they will handle.
    # If an option, or client, is unspecified, then the default option value/client values will be used instead.
    # If a client is configured, but is not registered above, the options for that client will be ignored.
    # WARNING!: THE BELOW CONFIG IS FOR ILLUSTRATION PURPOSES. DO NOT COPY OR USE THIS WITHOUT
    # WARNING!: UNDERSTANDING WHAT IT DOES. MISCONFIGURATION WILL HINDER YOUTUBE-SOURCE'S ABILITY TO WORK PROPERLY.

    # Write the names of clients as they are specified under the heading "Available Clients".
    clientOptions:
      WEB:
        # Example: Disabling a client's playback capabilities.
        playback: false
        videoLoading: false # Disables loading of videos for this client. A client may still be used for playback even if this is set to 'false'.
      WEBEMBEDDED:
        # Example: Configuring a client to exclusively be used for video loading and playback.
        playlistLoading: false # Disables loading of playlists and mixes.
        searching: false # Disables the ability to search for videos.
{youtube_oauth_section}{remote_cipher_section}  lavasrc:
    providers: # Custom providers for track loading. This is the default
      # - "dzisrc:%ISRC%" # Deezer ISRC provider
      # - "dzsearch:%QUERY%" # Deezer search provider
      - "ytsearch:\\"%ISRC%\\"" # Will be ignored if track does not have an ISRC. See https://en.wikipedia.org/wiki/International_Standard_Recording_Code
      - "ytsearch:%QUERY%" # Will be used if track has no ISRC or no track could be found for the ISRC
      #  you can add multiple other fallback sources here
    sources:
      spotify: {spotify_enabled} # Enable Spotify source
      applemusic: false # Enable Apple Music source
      deezer: false # Enable Deezer source
      yandexmusic: false # Enable Yandex Music source
      flowerytts: false # Enable Flowery TTS source
      youtube: false # Enable YouTube search source (https://github.com/topi314/LavaSearch)
      vkmusic: false # Enable Vk Music source
    lyrics-sources:
      spotify: false # Enable Spotify lyrics source
      deezer: false # Enable Deezer lyrics source
      youtube: false # Enable YouTube lyrics source
      yandexmusic: false # Enable Yandex Music lyrics source
      vkmusic: false # Enable Vk Music lyrics source
    spotify:
      clientId: "{sp_id}"
      clientSecret: "{sp_secret}"
      # spDc: "your sp dc cookie" # the sp dc cookie used for accessing the spotify lyrics api
      countryCode: "US" # the country code you want to use for filtering the artists top tracks. See https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2
      playlistLoadLimit: 6 # The number of pages at 100 tracks each
      albumLoadLimit: 6 # The number of pages at 50 tracks each
      resolveArtistsInSearch: true # Whether to resolve artists in track search results (can be slow)
      localFiles: false # Enable local files support with Spotify playlists. Please note `uri` & `isrc` will be `null` & `identifier` will be `"local"`
      preferAnonymousToken: true # Whether to use the anonymous token for resolving tracks, artists and albums. Spotify generated playlists are always resolved with the anonymous tokens since they do not work otherwise. This requires the customTokenEndpoint to be set.
      customTokenEndpoint: "http://spotify-tokener:49152/api/token" # Optional custom endpoint for getting the anonymous token (internal Docker service; use HTTPS if exposed externally). If not set, spotify's default endpoint will be used which might not work. The response must match spotify's anonymous token response format.
    applemusic:
      countryCode: "US" # the country code you want to use for filtering the artists top tracks and language. See https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2
      mediaAPIToken: "your apple music api token" # apple music api token
      # or specify an apple music key
      keyID: "your key id"
      teamID: "your team id"
      musicKitKey: |
        -----BEGIN PRIVATE KEY-----
        your key
        -----END PRIVATE KEY-----      
      playlistLoadLimit: 6 # The number of pages at 300 tracks each
      albumLoadLimit: 6 # The number of pages at 300 tracks each
    deezer:
      masterDecryptionKey: "your master decryption key" # the master key used for decrypting the deezer tracks. (yes this is not here you need to get it from somewhere else)
      # arl: "your deezer arl" # the arl cookie used for accessing the deezer api this is optional but required for formats above MP3_128
      formats: [ "FLAC", "MP3_320", "MP3_256", "MP3_128", "MP3_64", "AAC_64" ] # the formats you want to use for the deezer tracks. "FLAC", "MP3_320", "MP3_256" & "AAC_64" are only available for premium users and require a valid arl
    yandexmusic:
      accessToken: "your access token" # the token used for accessing the yandex music api. See https://github.com/TopiSenpai/LavaSrc#yandex-music
      playlistLoadLimit: 1 # The number of pages at 100 tracks each
      albumLoadLimit: 1 # The number of pages at 50 tracks each
      artistLoadLimit: 1 # The number of pages at 10 tracks each
    flowerytts:
      voice: "default voice" # (case-sensitive) get default voice from here https://api.flowery.pw/v1/tts/voices
      translate: false # whether to translate the text to the native language of voice
      silence: 0 # the silence parameter is in milliseconds. Range is 0 to 10000. The default is 0.
      speed: 1.0 # the speed parameter is a float between 0.5 and 10. The default is 1.0. (0.5 is half speed, 2.0 is double speed, etc.)
      audioFormat: "mp3" # supported formats are: mp3, ogg_opus, ogg_vorbis, aac, wav, and flac. Default format is mp3
    youtube:
      countryCode: "US" # the country code you want to use for searching lyrics via ISRC. See https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2
    vkmusic:
      userToken: "your user token" # This token is needed for authorization in the api. Guide: https://github.com/topi314/LavaSrc#vk-music
      playlistLoadLimit: 1 # The number of pages at 50 tracks each
      artistLoadLimit: 1 # The number of pages at 10 tracks each
      recommendationsLoadLimit: 10 # Number of tracks
lavalink:
  plugins:
    - dependency: "dev.lavalink.youtube:youtube-plugin:1.18.0" # Please check the latest version at https://github.com/lavalink-devs/youtube-source/releases
      snapshot: false
    - dependency: "com.github.topi314.lavasrc:lavasrc-plugin:4.8.1" # Please check the latest version at https://github.com/topi314/LavaSrc/releases
      snapshot: false
#    - dependency: "com.github.example:example-plugin:1.0.0" # required, the coordinates of your plugin
#      repository: "https://maven.example.com/releases" # optional, defaults to the Lavalink releases repository by default
#      snapshot: false # optional, defaults to false, used to tell Lavalink to use the snapshot repository instead of the release repository
#  pluginsDir: "./plugins" # optional, defaults to "./plugins"
#  defaultPluginRepository: "https://maven.lavalink.dev/releases" # optional, defaults to the Lavalink release repository
#  defaultPluginSnapshotRepository: "https://maven.lavalink.dev/snapshots" # optional, defaults to the Lavalink snapshot repository
  server:
    password: "{password}"
    sources:
      # The default Youtube source is now deprecated and won't receive further updates. Please use https://github.com/lavalink-devs/youtube-source#plugin instead.
      youtube: false
      bandcamp: true
      soundcloud: true
      twitch: true
      vimeo: true
      nico: true # Enable Niconico (NicoVideo) source
      http: true # warning: keeping HTTP enabled without a proxy configured could expose your server's IP address.
      local: false
    filters: # All filters are enabled by default
      volume: true
      equalizer: true
      karaoke: true
      timescale: true
      tremolo: true
      vibrato: true
      distortion: true
      rotation: true
      channelMix: true
      lowPass: true
    nonAllocatingFrameBuffer: false # Setting to true reduces the number of allocations made by each player at the expense of frame rebuilding (e.g. non-instantaneous volume changes)
    bufferDurationMs: 400 # The duration of the NAS buffer. Higher values fare better against longer GC pauses. Duration <= 0 to disable JDA-NAS. Minimum of 40ms, lower values may introduce pauses.
    frameBufferDurationMs: 5000 # How many milliseconds of audio to keep buffered
    opusEncodingQuality: 10 # Opus encoder quality. Valid values range from 0 to 10, where 10 is best quality but is the most expensive on the CPU.
    resamplingQuality: LOW # Quality of resampling operations. Valid values are LOW, MEDIUM and HIGH, where HIGH uses the most CPU.
    trackStuckThresholdMs: 10000 # The threshold for how long a track can be stuck. A track is stuck if does not return any audio data.
    useSeekGhosting: true # Seek ghosting is the effect where whilst a seek is in progress, the audio buffer is read from until empty, or until seek is ready.
    youtubePlaylistLoadLimit: 6 # Number of pages at 100 each
    playerUpdateInterval: 5 # How frequently to send player updates to clients, in seconds
    youtubeSearchEnabled: true
    soundcloudSearchEnabled: true
    gc-warnings: true
    #ratelimit:
      #ipBlocks: ["1.0.0.0/8", "..."] # list of ip blocks
      #excludedIps: ["...", "..."] # ips which should be explicit excluded from usage by lavalink
      #strategy: "RotateOnBan" # RotateOnBan | LoadBalance | NanoSwitch | RotatingNanoSwitch
      #searchTriggersFail: true # Whether a search 429 should trigger marking the ip as failing
      #retryLimit: -1 # -1 = use default lavaplayer value | 0 = infinity | >0 = retry will happen this numbers times
    #youtubeConfig: # Required for avoiding all age restrictions by YouTube, some restricted videos still can be played without.
      #email: "" # Email of Google account
      #password: "" # Password of Google account
    #httpConfig: # Useful for blocking bad-actors from ip-grabbing your music node and attacking it, this way only the http proxy will be attacked
      #proxyHost: "localhost" # Hostname of the proxy, (ip or domain)
      #proxyPort: 3128 # Proxy port, 3128 is the default for squidProxy
      #proxyUser: "" # Optional user for basic authentication fields, leave blank if you don't use basic auth
      #proxyPassword: "" # Password for basic authentication

metrics:
  prometheus:
    enabled: false
    endpoint: /metrics

sentry:
  dsn: ""
  environment: ""
#  tags:
#    some_key: some_value
#    another_key: another_value

logging:
  file:
    path: ./logs/

  level:
    root: INFO
    lavalink: INFO

  request:
    enabled: true
    includeClientInfo: true
    includeHeaders: false
    includeQueryString: true
    includePayload: true
    maxPayloadLength: 10000


  logback:
    rollingpolicy:
      max-file-size: 1GB
      max-history: 30
"""
        lavalink_dir = install_dir / 'lavalink'
        FileManager.mkdir(lavalink_dir)
        FileManager.mkdir(lavalink_dir / 'logs')
        FileManager.mkdir(lavalink_dir / 'plugins')

        # Non-Docker config: uses public yt-cipher instance
        (lavalink_dir / 'application.yml').write_text(
            _build_content(nondocker_remote_cipher_section), encoding='utf-8'
        )
        print(f"{Colors.GREEN}Wrote lavalink/application.yml{Colors.END}")

        # Docker config: uses internal yt-cipher service hostname
        (lavalink_dir / 'application.docker.yml').write_text(
            _build_content(docker_remote_cipher_section), encoding='utf-8'
        )
        print(f"{Colors.GREEN}Wrote lavalink/application.docker.yml{Colors.END}")

    # ------------------------------------------------------------------ run

    def run(self) -> bool:
        try:
            Colors.clear_screen()
            self._banner()

            # Deployment mode
            self.cfg_mgr._section("🚀  DEPLOYMENT MODE", Colors.BLUE)
            print(f"\n{Colors.BLUE}Choose your deployment method:{Colors.END}")
            print(f"  {Colors.GREEN}Docker{Colors.END}     — runs bot + Lavalink as containers (recommended)")
            print(f"  {Colors.GREEN}Non-Docker{Colors.END} — runs bot directly with Python\n")
            use_docker = self.cfg_mgr.yes_no(
                f"{Colors.YELLOW}Use Docker?{Colors.END}"
            )

            if use_docker:
                # Check Docker
                docker_ok, compose_ok = self.docker.check()
                if not docker_ok:
                    print(f"{Colors.RED}Docker is not installed. Please install Docker and re-run.{Colors.END}")
                    return False
                if not compose_ok:
                    print(f"{Colors.RED}Docker Compose is not available. Please install it and re-run.{Colors.END}")
                    return False
                print(f"{Colors.GREEN}✅  Docker and Docker Compose are available.{Colors.END}")

            # Installation directory
            default_dir = Path(__file__).parent.resolve()
            install_dir = self.cfg_mgr.collect_install_dir(default_dir)
            FileManager.mkdir(install_dir)

            # Basic config
            config = self.cfg_mgr.collect_basic()
            config['install_dir'] = install_dir

            # Optional services
            self.cfg_mgr._section("🔧  OPTIONAL SERVICES", Colors.CYAN)

            print(f"\n{Colors.BLUE}🎵  Lavalink — high-quality audio streaming server (Recommended){Colors.END}")
            enable_lavalink = self.cfg_mgr.yes_no(
                f"{Colors.YELLOW}Enable Lavalink?{Colors.END}"
            )

            if enable_lavalink:
                lavalink_config = self.cfg_mgr.collect_lavalink()
                config.update(lavalink_config)
            else:
                config.setdefault('lavalink_port', '2333')
                config.setdefault('lavalink_password', 'youshallnotpass')
                config.setdefault('spotify_client_id', '')
                config.setdefault('spotify_client_secret', '')

            print(f"\n{Colors.BLUE}🌐  Dashboard — web interface for bot management{Colors.END}")
            enable_dashboard = self.cfg_mgr.yes_no(
                f"{Colors.YELLOW}Enable Dashboard?{Colors.END}",
                default=False,
            )

            if enable_dashboard:
                dashboard_config = self.cfg_mgr.collect_dashboard()
                config.update(dashboard_config)
            else:
                config.setdefault('dashboard_port', '3000')
                config.setdefault('discord_callback_url', 'http://localhost:3000/auth/discord/callback')
                config.setdefault('session_secret', '')

            # Write configuration files
            self.cfg_mgr._section("📝  WRITING CONFIGURATION FILES", Colors.BLUE)
            self._write_settings(install_dir, config)
            if use_docker:
                self._write_docker_compose(install_dir, config, enable_lavalink, enable_dashboard)
            if enable_lavalink:
                self._write_lavalink_config(install_dir, config)
                jar_dest = install_dir / 'lavalink' / 'Lavalink.jar'
                if not jar_dest.exists():
                    self.file_mgr.download(self.LAVALINK_JAR_URL, jar_dest)
                else:
                    print(f"{Colors.GREEN}Lavalink.jar already present, skipping download.{Colors.END}")

            # Create data directory
            FileManager.mkdir(install_dir / 'data' / 'sfx')
            print(f"{Colors.GREEN}Created data directories.{Colors.END}")

            # Install Python dependencies (not needed for Docker; handled inside the image)
            if not use_docker:
                self.cfg_mgr._section("📦  INSTALLING PYTHON DEPENDENCIES", Colors.BLUE)
                self._install_requirements(install_dir)

            # Start services
            self.cfg_mgr._section("🚀  STARTING SERVICES", Colors.GREEN)
            if use_docker:
                if not self.docker.start(install_dir):
                    return False
            else:
                print(f"{Colors.GREEN}✅  Installation complete. Run these commands from {install_dir}:{Colors.END}")
                if enable_lavalink:
                    print(f"\n{Colors.YELLOW}⚠  Start Lavalink before the bot (from {install_dir}):{Colors.END}")
                    print(f"  cd lavalink && java -jar Lavalink.jar")
                print(f"\n  python -m bot.main")
                if enable_dashboard:
                    print(f"  python -m bot.dashboard.app  # Start the dashboard")

            # Success message
            print('\n' + '=' * 60)
            print(f"{Colors.BOLD}{Colors.GREEN}INSTALLATION COMPLETED!{Colors.END}")
            print(
                f"{Colors.GREEN}Invite your bot:\n"
                f"  https://discord.com/oauth2/authorize"
                f"?client_id={config['client_id']}&permissions=8&scope=bot+applications.commands"
                f"{Colors.END}"
            )
            if enable_dashboard:
                print(f"{Colors.GREEN}Dashboard: http://localhost:{config.get('dashboard_port', '3000')}{Colors.END}")
            print('=' * 60)
            if use_docker:
                print(f"\n{Colors.CYAN}Management commands (run from {install_dir}):{Colors.END}")
                print("  docker compose up -d    # Start services")
                print("  docker compose down     # Stop services")
                print("  docker compose logs -f  # View logs")
                print("  docker compose pull     # Update images")
            else:
                print(f"\n{Colors.CYAN}Run commands (from {install_dir}):{Colors.END}")
                print(f"  python -m bot.main                            # Start the bot")
                if enable_lavalink:
                    print(f"  cd lavalink && java -jar Lavalink.jar         # Start Lavalink (run from lavalink/ dir)")
                if enable_dashboard:
                    print(f"  python -m bot.dashboard.app                   # Start the dashboard")
            print(f"\n{Colors.YELLOW}For support: https://github.com/szentigrad3/discord-music-bot{Colors.END}")
            print('=' * 60)
            return True

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Installation cancelled by user.{Colors.END}")
            return False
        except Exception as exc:
            print(f"\n{Colors.RED}Installation failed: {exc}{Colors.END}")
            return False


def main() -> None:
    installer = Installer()
    sys.exit(0 if installer.run() else 1)


if __name__ == '__main__':
    main()
