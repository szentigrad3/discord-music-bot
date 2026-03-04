"""Tests for Lavalink application.yml configuration."""

import os
import unittest

import yaml


LAVALINK_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "lavalink", "application.yml"
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


if __name__ == "__main__":
    unittest.main()
