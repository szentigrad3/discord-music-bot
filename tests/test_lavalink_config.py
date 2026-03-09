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

    def test_mweb_client_in_clients_list(self):
        """MWEB client must be present as a cipher-free fallback.

        When the remote cipher service fails (e.g. yt-dlp/ejs 'no solutions' error caused
        by YouTube updating their obfuscated player script), the TV (TVHTML5) client cannot
        decrypt stream URLs. The MWEB (mobile web) client does not require cipher decryption,
        so it provides a working fallback. See:
        https://github.com/lavalink-devs/youtube-source?tab=readme-ov-file#available-clients
        """
        youtube = self._get_youtube_config()
        clients = youtube.get("clients", [])
        self.assertIn(
            "MWEB",
            clients,
            "The 'MWEB' client is required as a cipher-free fallback when the remote "
            "cipher service cannot solve YouTube's obfuscated player script. "
            "See https://github.com/lavalink-devs/youtube-source?tab=readme-ov-file#available-clients",
        )


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


class TestInstallerGeneratedConfig(unittest.TestCase):
    """Validates that install.py generates Lavalink configs with all required settings."""

    def _generate_config(self, config_overrides=None, use_docker=True):
        """Generate Lavalink configs using Installer and return parsed YAML for the
        requested deployment type (application.docker.yml for Docker, application.yml otherwise)."""
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
            Installer._write_lavalink_config(Path(tmpdir), config)
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

    def test_generated_config_docker_uses_internal_cipher_hostname(self):
        """Docker install must write application.yml with the internal yt-cipher hostname.

        Inside Docker Compose the 'yt-cipher' hostname resolves to the yt-cipher container.
        """
        config = self._generate_config(use_docker=True)
        youtube = config["plugins"]["youtube"]
        remote_cipher = youtube.get("remoteCipher", {})
        self.assertEqual(
            remote_cipher.get("url", "").strip(),
            "http://yt-cipher:8001",
            "Docker install.py must write remoteCipher.url = 'http://yt-cipher:8001' "
            "in application.yml.",
        )

    def test_generated_compose_no_yt_cipher_when_lavalink_disabled(self):
        """When lavalink is disabled, yt-cipher should not be included in docker-compose."""
        compose = self._generate_docker_compose(enable_lavalink=False)
        self.assertNotIn(
            "yt-cipher",
            compose.get("services", {}),
            "yt-cipher should not be present when lavalink is disabled.",
        )

    def test_generated_compose_has_watchtower_when_lavalink_enabled(self):
        """install.py must generate docker-compose.yml with Watchtower when lavalink is enabled.

        Watchtower monitors yt-cipher and automatically pulls and restarts it when a
        new image is published. This ensures cipher fixes are applied without requiring
        a manual restart. yt-dlp/ejs (which yt-cipher depends on) releases fixes for
        YouTube player script changes, and without Watchtower users must manually run
        'docker compose pull && docker compose up -d' to get those fixes.
        """
        compose = self._generate_docker_compose(enable_lavalink=True)
        self.assertIn(
            "watchtower",
            compose.get("services", {}),
            "docker-compose.yml must include the watchtower service when lavalink is enabled "
            "so that yt-cipher cipher fixes are applied automatically.",
        )

    def test_generated_compose_no_watchtower_when_lavalink_disabled(self):
        """When lavalink is disabled, watchtower should not be included in docker-compose."""
        compose = self._generate_docker_compose(enable_lavalink=False)
        self.assertNotIn(
            "watchtower",
            compose.get("services", {}),
            "watchtower should not be present when lavalink is disabled.",
        )

    def test_generated_compose_yt_cipher_has_watchtower_label(self):
        """yt-cipher must have the Watchtower enable label so it is auto-updated.

        Without the label, Watchtower (running in --label-enable mode) will not
        monitor yt-cipher, and cipher fixes will not be applied automatically.
        """
        compose = self._generate_docker_compose(enable_lavalink=True)
        yt_cipher = compose.get("services", {}).get("yt-cipher", {})
        labels = yt_cipher.get("labels", [])
        self.assertIn(
            "com.centurylinklabs.watchtower.enable=true",
            labels,
            "The yt-cipher service must have the Watchtower enable label so Watchtower "
            "can auto-update it when cipher fixes are released.",
        )

    def test_generated_config_has_mweb_client(self):
        """install.py must include MWEB in the YouTube clients list.

        MWEB (mobile web) does not require cipher decryption. When the remote cipher
        service fails (e.g. yt-dlp/ejs 'no solutions' for a new YouTube player script),
        MWEB provides a working fallback for video playback.
        """
        config = self._generate_config(use_docker=True)
        clients = config["plugins"]["youtube"].get("clients", [])
        self.assertIn(
            "MWEB",
            clients,
            "install.py must include MWEB in the youtube clients list as a cipher-free "
            "fallback. See https://github.com/lavalink-devs/youtube-source?tab=readme-ov-file#available-clients",
        )


        """_write_lavalink_config must always write both application.yml and application.docker.yml.

        application.yml  — non-Docker config (public cipher)
        application.docker.yml — Docker config (internal cipher)
        Both are written on every run so users can switch deployment modes without re-running the installer.
        """
        config = {
            'lavalink_port': '2333',
            'lavalink_password': 'youshallnotpass',
            'spotify_client_id': '',
            'spotify_client_secret': '',
            'youtube_refresh_token': '',
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            Installer._write_lavalink_config(Path(tmpdir), config)
            self.assertTrue(
                (Path(tmpdir) / 'lavalink' / 'application.yml').exists(),
                "application.yml must be written by _write_lavalink_config.",
            )
            self.assertTrue(
                (Path(tmpdir) / 'lavalink' / 'application.docker.yml').exists(),
                "application.docker.yml must be written by _write_lavalink_config.",
            )

    def test_generated_compose_lavalink_uses_spring_config_location(self):
        """Docker compose lavalink service must set SPRING_CONFIG_LOCATION to application.docker.yml.

        Without SPRING_CONFIG_LOCATION, Lavalink loads application.yml (the non-Docker config)
        which points remoteCipher at the public https://cipher.kikkia.dev/ instance instead of
        the internal yt-cipher Docker service.
        """
        compose = self._generate_docker_compose(enable_lavalink=True)
        lavalink = compose.get("services", {}).get("lavalink", {})
        env = lavalink.get("environment", [])
        self.assertIn(
            "SPRING_CONFIG_LOCATION=file:/opt/lavalink/application.docker.yml",
            env,
            "Docker lavalink service must set SPRING_CONFIG_LOCATION to "
            "file:/opt/lavalink/application.docker.yml so it uses the Docker-specific config.",
        )

    def test_generated_compose_lavalink_has_spring_config_import(self):
        """Docker compose lavalink service must set SPRING_CONFIG_IMPORT=optional:configserver:.

        Without this, newer Lavalink versions fail to start with:
        'No spring.config.import property has been defined'
        Setting it to 'optional:configserver:' disables the Spring Cloud Config import check.
        """
        compose = self._generate_docker_compose(enable_lavalink=True)
        lavalink = compose.get("services", {}).get("lavalink", {})
        env = lavalink.get("environment", [])
        self.assertIn(
            "SPRING_CONFIG_IMPORT=optional:configserver:",
            env,
            "Docker lavalink service must set SPRING_CONFIG_IMPORT=optional:configserver: "
            "to prevent Spring Cloud Config startup failure.",
        )

    def test_generated_compose_lavalink_has_native_access_jvm_flag(self):
        """Docker compose lavalink service must pass --enable-native-access=ALL-UNNAMED to the JVM.

        Lavalink runs on Java 21+ where sun.misc.Unsafe::allocateMemory and
        java.lang.System::loadLibrary (used by Netty) are restricted. Without this flag,
        Lavalink logs 'WARNING: A terminally deprecated method in sun.misc.Unsafe has been called'
        and 'WARNING: Restricted methods will be blocked in a future release unless native access
        is enabled' on every startup, and those calls will eventually be blocked entirely.
        """
        compose = self._generate_docker_compose(enable_lavalink=True)
        lavalink = compose.get("services", {}).get("lavalink", {})
        env = lavalink.get("environment", [])
        java_options = next(
            (e for e in env if isinstance(e, str) and e.startswith("_JAVA_OPTIONS=")),
            None,
        )
        self.assertIsNotNone(java_options, "Lavalink service must set _JAVA_OPTIONS.")
        self.assertIn(
            "--enable-native-access=ALL-UNNAMED",
            java_options,
            "Lavalink _JAVA_OPTIONS must include --enable-native-access=ALL-UNNAMED to "
            "suppress sun.misc.Unsafe and restricted-method warnings from Netty.",
        )

    def test_generated_compose_watchtower_has_docker_api_version(self):
        """Docker compose watchtower service must set DOCKER_API_VERSION=1.44.

        By default, Watchtower negotiates Docker API version 1.25. Docker daemons shipped
        with modern Docker Engine (24+) require at least API 1.44 and reject older clients
        with 'client version 1.25 is too old. Minimum supported API version is 1.44'.
        Setting DOCKER_API_VERSION=1.44 forces the Watchtower Docker client to use a
        compatible API version.
        """
        compose = self._generate_docker_compose(enable_lavalink=True)
        watchtower = compose.get("services", {}).get("watchtower", {})
        env = watchtower.get("environment", [])
        self.assertIn(
            "DOCKER_API_VERSION=1.44",
            env,
            "Watchtower service must set DOCKER_API_VERSION=1.44 so it is compatible with "
            "modern Docker daemons that require at least API version 1.44.",
        )


DOCKER_COMPOSE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "docker-compose.yml"
)


class TestDockerCompose(unittest.TestCase):
    """Validates the committed docker-compose.yml is correctly configured."""

    def setUp(self):
        with open(DOCKER_COMPOSE_PATH, "r") as f:
            self.compose = yaml.safe_load(f)

    def _get_lavalink_env(self):
        return self.compose["services"]["lavalink"].get("environment", [])

    def test_lavalink_has_spring_config_import(self):
        """The committed docker-compose.yml lavalink service must set SPRING_CONFIG_IMPORT.

        Without SPRING_CONFIG_IMPORT=optional:configserver:, newer Lavalink versions fail to
        start with 'No spring.config.import property has been defined'.
        """
        env = self._get_lavalink_env()
        self.assertIn(
            "SPRING_CONFIG_IMPORT=optional:configserver:",
            env,
            "docker-compose.yml lavalink service must set "
            "SPRING_CONFIG_IMPORT=optional:configserver: to prevent Spring Cloud Config "
            "startup failure.",
        )

    def test_lavalink_has_spring_config_location(self):
        """The committed docker-compose.yml lavalink service must set SPRING_CONFIG_LOCATION."""
        env = self._get_lavalink_env()
        self.assertIn(
            "SPRING_CONFIG_LOCATION=file:/opt/lavalink/application.docker.yml",
            env,
            "docker-compose.yml lavalink service must set SPRING_CONFIG_LOCATION to "
            "file:/opt/lavalink/application.docker.yml.",
        )

    def test_compose_has_watchtower_service(self):
        """The committed docker-compose.yml must include the Watchtower service.

        Watchtower monitors yt-cipher and automatically pulls and restarts it when a
        new image is published. This ensures cipher fixes (e.g. for YouTube player
        script changes that cause 'no solutions' errors in yt-dlp/ejs) are applied
        without manual intervention.
        """
        self.assertIn(
            "watchtower",
            self.compose.get("services", {}),
            "docker-compose.yml must include the watchtower service so yt-cipher "
            "cipher fixes are applied automatically when new images are published.",
        )

    def test_compose_yt_cipher_has_watchtower_label(self):
        """The yt-cipher service in the committed docker-compose.yml must have the Watchtower enable label."""
        yt_cipher = self.compose.get("services", {}).get("yt-cipher", {})
        labels = yt_cipher.get("labels", [])
        self.assertIn(
            "com.centurylinklabs.watchtower.enable=true",
            labels,
            "The yt-cipher service must have the Watchtower enable label so Watchtower "
            "automatically updates it when new cipher-fixing images are published.",
        )

    def test_compose_lavalink_has_native_access_jvm_flag(self):
        """The committed docker-compose.yml lavalink service must pass --enable-native-access=ALL-UNNAMED.

        Lavalink runs on Java 21+ where sun.misc.Unsafe::allocateMemory and
        java.lang.System::loadLibrary (used by Netty) are restricted. Without this flag,
        Lavalink logs deprecation warnings on every startup and those calls will eventually
        be blocked entirely.
        """
        env = self._get_lavalink_env()
        java_options = next(
            (e for e in env if isinstance(e, str) and e.startswith("_JAVA_OPTIONS=")),
            None,
        )
        self.assertIsNotNone(java_options, "Lavalink service must set _JAVA_OPTIONS.")
        self.assertIn(
            "--enable-native-access=ALL-UNNAMED",
            java_options,
            "Lavalink _JAVA_OPTIONS must include --enable-native-access=ALL-UNNAMED to "
            "suppress sun.misc.Unsafe and restricted-method warnings from Netty.",
        )

    def test_compose_watchtower_has_docker_api_version(self):
        """The committed docker-compose.yml watchtower service must set DOCKER_API_VERSION=1.44.

        By default, Watchtower negotiates Docker API version 1.25. Docker daemons shipped
        with modern Docker Engine (24+) require at least API 1.44 and reject older clients
        with 'client version 1.25 is too old. Minimum supported API version is 1.44'.
        """
        watchtower = self.compose.get("services", {}).get("watchtower", {})
        env = watchtower.get("environment", [])
        self.assertIn(
            "DOCKER_API_VERSION=1.44",
            env,
            "Watchtower service must set DOCKER_API_VERSION=1.44 so it is compatible with "
            "modern Docker daemons that require at least API version 1.44.",
        )


class TestLavalinkDockerConfig(unittest.TestCase):
    """Validates the committed lavalink/application.docker.yml is correctly configured for Docker."""

    def setUp(self):
        with open(LAVALINK_DOCKER_CONFIG_PATH, "r") as f:
            self.config = yaml.safe_load(f)

    def _get_youtube_config(self):
        return self.config["plugins"]["youtube"]

    def test_docker_config_file_exists(self):
        """lavalink/application.docker.yml must exist as the committed Docker reference config."""
        self.assertTrue(
            os.path.exists(LAVALINK_DOCKER_CONFIG_PATH),
            "lavalink/application.docker.yml must exist for Docker deployments.",
        )

    def test_docker_config_uses_internal_cipher_hostname(self):
        """application.docker.yml must point remoteCipher at the internal yt-cipher service.

        Inside Docker Compose the 'yt-cipher' hostname resolves to the yt-cipher container.
        """
        youtube = self._get_youtube_config()
        remote_cipher = youtube.get("remoteCipher", {})
        self.assertEqual(
            remote_cipher.get("url", "").strip(),
            "http://yt-cipher:8001",
            "application.docker.yml remoteCipher.url must be 'http://yt-cipher:8001'.",
        )

    def test_docker_config_youtube_source_enabled(self):
        """The youtube-source plugin must be enabled in application.docker.yml."""
        youtube = self._get_youtube_config()
        self.assertTrue(youtube.get("enabled", False))

    def test_docker_config_tv_client_present(self):
        """TV client must be present in application.docker.yml for OAuth-compatible playback."""
        youtube = self._get_youtube_config()
        clients = youtube.get("clients", [])
        self.assertIn("TV", clients)

    def test_docker_config_mweb_client_present(self):
        """MWEB client must be present in application.docker.yml as a cipher-free fallback.

        When yt-cipher returns 'no solutions' (e.g. yt-dlp/ejs cannot handle a new YouTube
        player script variant), the TV (TVHTML5) client fails. MWEB does not require cipher
        decryption and provides a working fallback for video playback.
        """
        youtube = self._get_youtube_config()
        clients = youtube.get("clients", [])
        self.assertIn(
            "MWEB",
            clients,
            "application.docker.yml must include MWEB as a cipher-free fallback client.",
        )


if __name__ == "__main__":
    unittest.main()
