"""Tests for Lavalink application.yml configuration."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from install import Installer  # noqa: E402


LAVALINK_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "lavalink", "application.yml"
)

LAVALINK_DOCKER_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "lavalink", "application.docker.yml"
)

# The only OAuth-compatible client in the youtube-source plugin.
# See: https://github.com/lavalink-devs/youtube-source?tab=readme-ov-file#available-clients
OAUTH_COMPATIBLE_CLIENTS = {"TV"}


class TestLavalinkConfig(unittest.TestCase):
    """Validates the Lavalink application.yml is correctly configured."""

    def setUp(self):
        with open(LAVALINK_CONFIG_PATH, "r") as f:
            self.config = yaml.safe_load(f)

    def _get_youtube_config(self):
        return self.config["plugins"]["youtube"]

    def test_oauth_compatible_client_registered_when_oauth_enabled(self):
        """When OAuth is enabled, at least one OAuth-compatible client must be registered.

        Without an OAuth-compatible client the youtube-source plugin logs:
        'OAuth has been enabled without registering any OAuth-compatible clients.'
        The only OAuth-compatible client is TV.
        """
        youtube = self._get_youtube_config()
        oauth_config = youtube.get("oauth", {})
        if not oauth_config.get("enabled", False):
            self.skipTest("OAuth is not enabled; skipping OAuth client check.")

        clients = youtube.get("clients", [])
        registered_oauth_clients = OAUTH_COMPATIBLE_CLIENTS.intersection(clients)
        self.assertTrue(
            registered_oauth_clients,
            f"OAuth is enabled but no OAuth-compatible clients are registered. "
            f"Add at least one of {OAUTH_COMPATIBLE_CLIENTS} to the 'clients' list. "
            f"Current clients: {clients}",
        )

    def test_youtube_source_enabled(self):
        """The youtube-source plugin must be enabled."""
        youtube = self._get_youtube_config()
        self.assertTrue(youtube.get("enabled", False))

    def test_tv_client_in_clients_list(self):
        """TV client must be present to support OAuth-based playback.

        TV is the only OAuth-compatible client. It must always be registered so that
        enabling OAuth does not trigger the 'no OAuth-compatible clients' warning.
        """
        youtube = self._get_youtube_config()
        clients = youtube.get("clients", [])
        self.assertIn(
            "TV",
            clients,
            "The 'TV' client is required for OAuth-compatible playback. "
            "See https://github.com/lavalink-devs/youtube-source?tab=readme-ov-file#available-clients",
        )

    def test_remote_cipher_configured(self):
        """A remoteCipher URL must be configured to handle YouTube sig function extraction.

        The TV (TVHTML5) client fails with 'Must find sig function from script' when
        YouTube changes their obfuscated player script. Configuring a remote cipher server
        (https://github.com/kikkia/yt-cipher) delegates this work to an external service
        that uses yt-dlp to reliably extract signature functions.
        """
        youtube = self._get_youtube_config()
        remote_cipher = youtube.get("remoteCipher", {})
        self.assertTrue(
            remote_cipher.get("url", "").strip(),
            "plugins.youtube.remoteCipher.url must be set to a yt-cipher server URL. "
            "See https://github.com/kikkia/yt-cipher",
        )


class TestLavalinkDockerConfig(unittest.TestCase):
    """Validates the Docker-specific lavalink/application.docker.yml is correctly configured."""

    def setUp(self):
        with open(LAVALINK_DOCKER_CONFIG_PATH, "r") as f:
            self.config = yaml.safe_load(f)

    def _get_youtube_config(self):
        return self.config["plugins"]["youtube"]

    def test_remote_cipher_uses_internal_docker_hostname(self):
        """application.docker.yml must point remoteCipher at the internal yt-cipher Docker service.

        The Docker Compose network resolves 'yt-cipher' to the yt-cipher container.
        Using the public URL here would bypass the local yt-cipher service.
        """
        youtube = self._get_youtube_config()
        remote_cipher = youtube.get("remoteCipher", {})
        self.assertEqual(
            remote_cipher.get("url", "").strip(),
            "http://yt-cipher:8001",
            "application.docker.yml remoteCipher.url must use the internal Docker "
            "service hostname 'http://yt-cipher:8001'.",
        )

    def test_youtube_source_enabled(self):
        """The youtube-source plugin must be enabled in the Docker config."""
        youtube = self._get_youtube_config()
        self.assertTrue(youtube.get("enabled", False))

    def test_tv_client_in_clients_list(self):
        """TV client must be present in the Docker config to support OAuth-based playback."""
        youtube = self._get_youtube_config()
        clients = youtube.get("clients", [])
        self.assertIn("TV", clients)


class TestInstallerGeneratedConfig(unittest.TestCase):
    """Validates that install.py generates Lavalink configs with all required settings."""

    def _generate_config(self, config_overrides=None, use_docker=True):
        """Generate a lavalink application.yml using Installer and return parsed YAML."""
        config = {
            'lavalink_port': '2333',
            'lavalink_password': 'youshallnotpass',
            'spotify_client_id': '',
            'spotify_client_secret': '',
            'youtube_refresh_token': '',
        }
        if config_overrides:
            config.update(config_overrides)
        with tempfile.TemporaryDirectory() as tmpdir:
            Installer._write_lavalink_config(Path(tmpdir), config, use_docker=use_docker)
            filename = 'application.docker.yml' if use_docker else 'application.yml'
            config_path = Path(tmpdir) / 'lavalink' / filename
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)

    def _generate_docker_compose(self, enable_lavalink=True, enable_dashboard=False):
        """Generate a docker-compose.yml using Installer and return its contents."""
        config = {
            'lavalink_port': '2333',
            'lavalink_password': 'youshallnotpass',
            'dashboard_port': '3000',
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            Installer._write_docker_compose(Path(tmpdir), config, enable_lavalink, enable_dashboard)
            compose_path = Path(tmpdir) / 'docker-compose.yml'
            with open(compose_path, 'r') as f:
                return yaml.safe_load(f)

    def test_generated_config_has_remote_cipher(self):
        """install.py must generate application.yml with remoteCipher configured when using Docker.

        Without remoteCipher, the TV (TVHTML5) client falls back to LocalSignatureCipherManager
        which fails with 'Must find sig function from script' when YouTube changes their
        obfuscated player script. The yt-cipher service is deployed in docker-compose but
        must be wired up via remoteCipher in application.yml.
        """
        config = self._generate_config(use_docker=True)
        youtube = config["plugins"]["youtube"]
        remote_cipher = youtube.get("remoteCipher", {})
        self.assertTrue(
            remote_cipher.get("url", "").strip(),
            "install.py must write plugins.youtube.remoteCipher.url to application.yml "
            "for Docker deployments. See https://github.com/kikkia/yt-cipher",
        )

    def test_generated_config_uses_public_cipher_when_not_docker(self):
        """install.py must configure remoteCipher to the public yt-cipher instance for non-Docker.

        Non-Docker deployments cannot resolve the 'yt-cipher' Docker hostname, so the
        installer points Lavalink at the public https://cipher.kikkia.dev/ instance instead.
        The config is written to ./lavalink/application.yml for non-Docker installs.
        """
        config = self._generate_config(use_docker=False)
        youtube = config["plugins"]["youtube"]
        remote_cipher = youtube.get("remoteCipher", {})
        self.assertEqual(
            remote_cipher.get("url", "").strip(),
            "https://cipher.kikkia.dev/",
            "install.py must write remoteCipher.url = 'https://cipher.kikkia.dev/' "
            "for non-Docker deployments.",
        )

    def test_generated_compose_has_yt_cipher_service(self):
        """install.py must generate docker-compose.yml with yt-cipher service when lavalink is enabled.

        The yt-cipher service provides remote signature cipher resolution for the TV (TVHTML5)
        client, preventing 'Must find sig function from script' errors.
        """
        compose = self._generate_docker_compose(enable_lavalink=True)
        self.assertIn(
            "yt-cipher",
            compose.get("services", {}),
            "docker-compose.yml must include the yt-cipher service when lavalink is enabled.",
        )

    def test_generated_compose_lavalink_depends_on_yt_cipher(self):
        """The lavalink service must depend on yt-cipher so it starts after the cipher server."""
        compose = self._generate_docker_compose(enable_lavalink=True)
        lavalink = compose.get("services", {}).get("lavalink", {})
        depends_on = lavalink.get("depends_on", [])
        self.assertIn(
            "yt-cipher",
            depends_on,
            "The lavalink service must list yt-cipher in depends_on.",
        )

    def test_generated_compose_lavalink_mounts_docker_config_to_opt_lavalink(self):
        """Docker compose must use a single directory mount ./lavalink:/opt/lavalink.

        Docker uses /opt/lavalink as its config/data directory (inside the container).
        Non-Docker uses ./lavalink directly on the host.
        SPRING_CONFIG_LOCATION tells Lavalink to load application.docker.yml so it
        does not accidentally use application.yml (the non-Docker config).
        """
        compose = self._generate_docker_compose(enable_lavalink=True)
        lavalink = compose.get("services", {}).get("lavalink", {})
        volumes = lavalink.get("volumes", [])
        self.assertIn(
            "./lavalink:/opt/lavalink",
            volumes,
            f"Docker lavalink service must use single directory mount "
            f"'./lavalink:/opt/lavalink'. Got: {volumes}",
        )

    def test_generated_compose_lavalink_sets_spring_config_location(self):
        """Docker compose must set SPRING_CONFIG_LOCATION to application.docker.yml.

        Without this, Lavalink defaults to application.yml (the non-Docker config),
        which points remoteCipher at the public instance instead of the internal
        yt-cipher Docker service.
        """
        compose = self._generate_docker_compose(enable_lavalink=True)
        lavalink = compose.get("services", {}).get("lavalink", {})
        environment = lavalink.get("environment", [])
        self.assertIn(
            "SPRING_CONFIG_LOCATION=file:/opt/lavalink/application.docker.yml",
            environment,
            f"Docker lavalink service must set SPRING_CONFIG_LOCATION. Got: {environment}",
        )

    def test_generated_config_docker_uses_internal_cipher_hostname(self):
        """Docker install must write application.docker.yml with the internal yt-cipher hostname.

        Inside Docker Compose the 'yt-cipher' hostname resolves to the yt-cipher container.
        """
        config = self._generate_config(use_docker=True)
        youtube = config["plugins"]["youtube"]
        remote_cipher = youtube.get("remoteCipher", {})
        self.assertEqual(
            remote_cipher.get("url", "").strip(),
            "http://yt-cipher:8001",
            "Docker install.py must write remoteCipher.url = 'http://yt-cipher:8001' "
            "in application.docker.yml.",
        )

    def test_generated_compose_no_yt_cipher_when_lavalink_disabled(self):
        """When lavalink is disabled, yt-cipher should not be included in docker-compose."""
        compose = self._generate_docker_compose(enable_lavalink=False)
        self.assertNotIn(
            "yt-cipher",
            compose.get("services", {}),
            "yt-cipher should not be present when lavalink is disabled.",
        )


if __name__ == "__main__":
    unittest.main()
