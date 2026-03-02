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
        'discord_client_secret': {
            'prompt': 'Discord OAuth2 Client Secret (for dashboard login)',
            'default': '',
            'description': (
                "Discord OAuth2 client secret used by the dashboard.\n\n"
                "How to get it:\n"
                "  1. Go to https://discord.com/developers/applications\n"
                "  2. Open your app → OAuth2 → General\n"
                "  3. Click \"Reset Secret\" and copy the value"
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

        lavalink_service = f"""
  lavalink:
    image: {Installer.LAVALINK_IMAGE}
    restart: unless-stopped
    environment:
      - _JAVA_OPTIONS=-Xmx1G
      - SERVER_PORT={lavalink_port}
      - LAVALINK_SERVER_PASSWORD={lavalink_password}
    volumes:
      - ./lavalink/application.yml:/opt/Lavalink/application.yml
      - ./lavalink/plugins:/opt/Lavalink/plugins
      - ./lavalink/logs:/opt/Lavalink/logs
    expose:
      - "{lavalink_port}"
""" if enable_lavalink else ''

        bot_depends = ''
        if enable_lavalink:
            bot_depends = '\n    depends_on:\n      - lavalink'

        dashboard_service = f"""
  dashboard:
    build: .
    restart: unless-stopped
    env_file: .env
    command: ["python", "-m", "bot.dashboard.app"]
    ports:
      - "{dashboard_port}:{dashboard_port}"
    volumes:
      - ./data:/app/data
""" if enable_dashboard else ''

        content = (
            f"services:\n"
            f"  bot:\n"
            f"    build: .\n"
            f"    restart: unless-stopped\n"
            f"    env_file: .env\n"
            f"    volumes:\n"
            f"      - ./data:/app/data\n"
            f"{bot_depends}\n"
            f"{lavalink_service}"
            f"{dashboard_service}"
        )

        dest = install_dir / 'docker-compose.yml'
        dest.write_text(content, encoding='utf-8')
        print(f"{Colors.GREEN}Wrote docker-compose.yml{Colors.END}")

    # ------------------------------------------------------------------ .env writer

    @staticmethod
    def _write_env(install_dir: Path, config: dict[str, Any]) -> None:
        lines = [
            '# Discord Bot',
            f"DISCORD_TOKEN={config['bot_token']}",
            f"DISCORD_CLIENT_ID={config['client_id']}",
            f"DISCORD_CLIENT_SECRET={config.get('discord_client_secret', '')}",
            f"DISCORD_CALLBACK_URL={config.get('discord_callback_url', 'http://localhost:3000/auth/discord/callback')}",
            '',
            '# Spotify (optional)',
            f"SPOTIFY_CLIENT_ID={config.get('spotify_client_id', '')}",
            f"SPOTIFY_CLIENT_SECRET={config.get('spotify_client_secret', '')}",
            '',
            '# Dashboard',
            f"SESSION_SECRET={config.get('session_secret', '')}",
            f"DASHBOARD_PORT={config.get('dashboard_port', '3000')}",
            '',
            '# Database',
            'DATABASE_URL=file:./data/bot.db',
            '',
            '# Lavalink',
            f"LAVALINK_HOST=lavalink",
            f"LAVALINK_PORT={config.get('lavalink_port', '2333')}",
            f"LAVALINK_PASSWORD={config.get('lavalink_password', 'youshallnotpass')}",
        ]
        dest = install_dir / '.env'
        dest.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f"{Colors.GREEN}Wrote .env{Colors.END}")

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

        content = f"""\
server:
  port: {port}
  address: 0.0.0.0
  http2:
    enabled: true

plugins:
  youtube:
    enabled: true
    allowSearch: true
    allowDirectVideoIds: true
    allowDirectPlaylistIds: true
    clients:
      - TV
      - MUSIC
      - ANDROID_VR
      - ANDROID_MUSIC
      - WEB
  lavasrc:
    providers:
      - 'ytsearch:"%ISRC%"'
      - "ytsearch:%QUERY%"
    sources:
      spotify: {"true" if sp_id else "false"}
      youtube: false
    spotify:
      clientId: "{sp_id}"
      clientSecret: "{sp_secret}"
      countryCode: "US"
      playlistLoadLimit: 6
      albumLoadLimit: 6

lavalink:
  plugins:
    - dependency: "dev.lavalink.youtube:youtube-plugin:1.18.0"
      snapshot: false
    - dependency: "com.github.topi314.lavasrc:lavasrc-plugin:4.8.1"
      snapshot: false
  server:
    password: "{password}"
    sources:
      youtube: false
      bandcamp: true
      soundcloud: true
      twitch: true
      vimeo: true
      http: true
      local: false
    filters:
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
    bufferDurationMs: 400
    frameBufferDurationMs: 5000
    opusEncodingQuality: 10

logging:
  file:
    path: ./logs/
  level:
    root: INFO
    lavalink: INFO
"""
        lavalink_dir = install_dir / 'lavalink'
        FileManager.mkdir(lavalink_dir)
        FileManager.mkdir(lavalink_dir / 'plugins')
        FileManager.mkdir(lavalink_dir / 'logs')

        dest = lavalink_dir / 'application.yml'
        dest.write_text(content, encoding='utf-8')
        print(f"{Colors.GREEN}Wrote lavalink/application.yml{Colors.END}")

    # ------------------------------------------------------------------ run

    def run(self) -> bool:
        try:
            Colors.clear_screen()
            self._banner()

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
                config.setdefault('discord_client_secret', '')
                config.setdefault('discord_callback_url', 'http://localhost:3000/auth/discord/callback')
                config.setdefault('session_secret', '')

            # Write configuration files
            self.cfg_mgr._section("📝  WRITING CONFIGURATION FILES", Colors.BLUE)
            self._write_env(install_dir, config)
            self._write_docker_compose(install_dir, config, enable_lavalink, enable_dashboard)
            if enable_lavalink:
                self._write_lavalink_config(install_dir, config)

            # Create data directory
            FileManager.mkdir(install_dir / 'data' / 'sfx')
            print(f"{Colors.GREEN}Created data directories.{Colors.END}")

            # Start services
            self.cfg_mgr._section("🚀  STARTING SERVICES", Colors.GREEN)
            if not self.docker.start(install_dir):
                return False

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
            print(f"\n{Colors.CYAN}Management commands (run from {install_dir}):{Colors.END}")
            print("  docker compose up -d    # Start services")
            print("  docker compose down     # Stop services")
            print("  docker compose logs -f  # View logs")
            print("  docker compose pull     # Update images")
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
