"""Tests for update.py — bot auto-update helpers."""

import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import update  # noqa: E402


# ---------------------------------------------------------------------------
# Minimal docker config file contents used across tests
# ---------------------------------------------------------------------------

_DOCKER_COMPOSE_DEFAULT = """\
services:
  lavalink:
    environment:
      - LAVALINK_SERVER_PASSWORD=youshallnotpass
      - SERVER_PORT=2333
"""

_LAVALINK_DOCKER_YML_DEFAULT = """\
server:
  port: 2333
lavalink:
  server:
    password: "youshallnotpass"
    oauth:
      enabled: true
      # refreshToken: "your refresh token, only supply this if you have one!"
      skipInitialization: false
plugins:
  lavasrc:
    spotify:
      clientId: ""
      clientSecret: ""
"""

_LAVALINK_DOCKER_YML_WITH_TOKEN = """\
server:
  port: 2333
lavalink:
  server:
    password: "youshallnotpass"
    oauth:
      enabled: true
      refreshToken: "old-yt-token"
      skipInitialization: true
plugins:
  lavasrc:
    spotify:
      clientId: ""
      clientSecret: ""
"""

_LAVALINK_YML_DEFAULT = """\
server:
  port: 2333
lavalink:
  server:
    password: "youshallnotpass"
    oauth:
      enabled: true
      #refreshToken: "your refresh token, only supply this if you have one!"
      skipInitialization: false
plugins:
  lavasrc:
    spotify:
      clientId: ""
      clientSecret: ""
"""

_LAVALINK_YML_WITH_TOKEN = """\
server:
  port: 2333
lavalink:
  server:
    password: "youshallnotpass"
    oauth:
      enabled: true
      refreshToken: "old-yt-token"
      skipInitialization: true
plugins:
  lavasrc:
    spotify:
      clientId: ""
      clientSecret: ""
"""


def _make_zip(top_dir: str, files: dict[str, str]) -> bytes:
    """Build an in-memory zip whose contents mirror a GitHub archive.

    Args:
        top_dir: The top-level folder name inside the archive
                 (e.g. ``discord-music-bot-main``).
        files:   Mapping of relative paths (inside ``top_dir``) to file content.

    Returns:
        Raw bytes of the zip archive.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for rel_path, content in files.items():
            zf.writestr(f"{top_dir}/{rel_path}", content)
    return buf.getvalue()


class TestInstall(unittest.TestCase):
    """Tests for install()."""

    def _make_response(self, zip_bytes: bytes) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.content = zip_bytes
        return mock_resp

    def test_install_main_branch_moves_files(self):
        """install() must correctly handle a zip whose top dir is discord-music-bot-main.

        This is the root-cause scenario from the bug report: GitHub archives for
        the ``main`` branch produce a folder called ``discord-music-bot-main``, not
        ``discord-music-bot-master``.  The old hardcoded name caused the extracted
        directory to be left behind instead of being unpacked into ROOT_DIR.
        """
        zip_bytes = _make_zip(
            "discord-music-bot-main",
            {"bot/__init__.py": "", "version.txt": "v2.0.0"},
        )
        response = self._make_response(zip_bytes)

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(update, "ROOT_DIR", tmpdir),
                patch("builtins.input", return_value="y"),
                patch.object(update, "_run_pip_install"),
            ):
                update.install(response, "v2.0.0")

            # Files from the archive must be present directly in ROOT_DIR.
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "version.txt")))
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "bot")))
            # The temporary extracted directory must have been removed.
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, "discord-music-bot-main"))
            )

    def test_install_master_branch_moves_files(self):
        """install() must also work correctly for a discord-music-bot-master zip."""
        zip_bytes = _make_zip(
            "discord-music-bot-master",
            {"bot/__init__.py": "", "version.txt": "v1.9.0"},
        )
        response = self._make_response(zip_bytes)

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(update, "ROOT_DIR", tmpdir),
                patch("builtins.input", return_value="y"),
                patch.object(update, "_run_pip_install"),
            ):
                update.install(response, "v1.9.0")

            self.assertTrue(os.path.exists(os.path.join(tmpdir, "version.txt")))
            self.assertFalse(
                os.path.exists(os.path.join(tmpdir, "discord-music-bot-master"))
            )

    def test_install_preserves_ignore_files(self):
        """install() must not delete files listed in IGNORE_FILES (e.g. settings.json)."""
        zip_bytes = _make_zip(
            "discord-music-bot-main",
            {"version.txt": "v2.0.0"},
        )
        response = self._make_response(zip_bytes)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a user settings file that must be preserved.
            settings_path = os.path.join(tmpdir, "settings.json")
            with open(settings_path, "w") as f:
                f.write('{"token": "secret"}')

            with (
                patch.object(update, "ROOT_DIR", tmpdir),
                patch("builtins.input", return_value="y"),
                patch.object(update, "_run_pip_install"),
            ):
                update.install(response, "v2.0.0")

            self.assertTrue(
                os.path.exists(settings_path),
                "settings.json must be preserved across updates",
            )

    def test_install_canceled_on_no(self):
        """install() must abort when the user declines the confirmation prompt."""
        zip_bytes = _make_zip("discord-music-bot-main", {"version.txt": "v2.0.0"})
        response = self._make_response(zip_bytes)

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                patch.object(update, "ROOT_DIR", tmpdir),
                patch("builtins.input", return_value="n"),
                patch.object(update, "_run_pip_install") as mock_pip,
            ):
                update.install(response, "v2.0.0")
                mock_pip.assert_not_called()

            self.assertFalse(os.path.exists(os.path.join(tmpdir, "version.txt")))


class TestDownloadUrlUseMainBranch(unittest.TestCase):
    """Verify that the module-level URL constants reference the main branch."""

    def test_download_url_uses_main(self):
        """DOWNLOAD_URL must point to the main branch archive."""
        self.assertIn("main", update.DOWNLOAD_URL)
        self.assertNotIn("master", update.DOWNLOAD_URL)

    def test_version_url_uses_main(self):
        """VERSION_URL must point to the main branch version.txt."""
        self.assertIn("main", update.VERSION_URL)
        self.assertNotIn("master", update.VERSION_URL)


class TestReadDockerSecrets(unittest.TestCase):
    """Tests for _read_docker_secrets()."""

    def test_reads_password_from_settings_json(self):
        """_read_docker_secrets must return the Lavalink password from settings.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = {"lavalink": {"password": "supersecret"}}
            with open(os.path.join(tmpdir, "settings.json"), "w") as f:
                json.dump(settings, f)
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertEqual(secrets["lavalink_password"], "supersecret")

    def test_falls_back_to_docker_compose_for_password(self):
        """_read_docker_secrets must read the password from docker-compose.yml when settings.json has none."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_path = os.path.join(tmpdir, "docker-compose.yml")
            with open(compose_path, "w") as f:
                f.write(_DOCKER_COMPOSE_DEFAULT.replace("youshallnotpass", "composepass"))
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertEqual(secrets["lavalink_password"], "composepass")

    def test_settings_json_password_takes_priority_over_docker_compose(self):
        """settings.json password must be preferred over docker-compose.yml password."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = {"lavalink": {"password": "from-settings"}}
            with open(os.path.join(tmpdir, "settings.json"), "w") as f:
                json.dump(settings, f)
            compose_path = os.path.join(tmpdir, "docker-compose.yml")
            with open(compose_path, "w") as f:
                f.write(_DOCKER_COMPOSE_DEFAULT.replace("youshallnotpass", "from-compose"))
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertEqual(secrets["lavalink_password"], "from-settings")

    def test_reads_youtube_refresh_token_from_lavalink_docker_yml(self):
        """_read_docker_secrets must return the YouTube refresh token from application.docker.yml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.docker.yml"), "w") as f:
                f.write(_LAVALINK_DOCKER_YML_WITH_TOKEN)
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertEqual(secrets["youtube_refresh_token"], "old-yt-token")

    def test_youtube_refresh_token_is_none_when_commented_out(self):
        """_read_docker_secrets must return None for youtube_refresh_token when the line is commented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.docker.yml"), "w") as f:
                f.write(_LAVALINK_DOCKER_YML_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertIsNone(secrets["youtube_refresh_token"])

    def test_returns_none_when_no_files_exist(self):
        """_read_docker_secrets must return None values when no config files are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertIsNone(secrets["lavalink_password"])
        self.assertIsNone(secrets["youtube_refresh_token"])

    def test_reads_youtube_refresh_token_from_lavalink_yml_as_fallback(self):
        """_read_docker_secrets must fall back to application.yml for the refresh token."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            # Only the non-docker file is present.
            with open(os.path.join(lavalink_dir, "application.yml"), "w") as f:
                f.write(_LAVALINK_YML_WITH_TOKEN)
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertEqual(secrets["youtube_refresh_token"], "old-yt-token")

    def test_docker_yml_token_takes_priority_over_nondocker_yml(self):
        """application.docker.yml refresh token must be preferred over application.yml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.docker.yml"), "w") as f:
                f.write(_LAVALINK_DOCKER_YML_WITH_TOKEN.replace("old-yt-token", "docker-token"))
            with open(os.path.join(lavalink_dir, "application.yml"), "w") as f:
                f.write(_LAVALINK_YML_WITH_TOKEN.replace("old-yt-token", "nondocker-token"))
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertEqual(secrets["youtube_refresh_token"], "docker-token")

    def test_reads_port_from_settings_json(self):
        """_read_docker_secrets must return the Lavalink port from settings.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = {"lavalink": {"port": 3456, "password": "pass"}}
            with open(os.path.join(tmpdir, "settings.json"), "w") as f:
                json.dump(settings, f)
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertEqual(secrets["lavalink_port"], "3456")

    def test_reads_spotify_credentials_from_settings_json(self):
        """_read_docker_secrets must return Spotify credentials from settings.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = {
                "spotify_client_id": "my-sp-id",
                "spotify_client_secret": "my-sp-secret",
            }
            with open(os.path.join(tmpdir, "settings.json"), "w") as f:
                json.dump(settings, f)
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertEqual(secrets["spotify_client_id"], "my-sp-id")
        self.assertEqual(secrets["spotify_client_secret"], "my-sp-secret")

    def test_spotify_credentials_none_when_empty_in_settings(self):
        """_read_docker_secrets must return None for empty Spotify credentials."""
        with tempfile.TemporaryDirectory() as tmpdir:
            settings = {"spotify_client_id": "", "spotify_client_secret": ""}
            with open(os.path.join(tmpdir, "settings.json"), "w") as f:
                json.dump(settings, f)
            with patch.object(update, "ROOT_DIR", tmpdir):
                secrets = update._read_docker_secrets()
        self.assertIsNone(secrets["spotify_client_id"])
        self.assertIsNone(secrets["spotify_client_secret"])


class TestPatchDockerFiles(unittest.TestCase):
    """Tests for _patch_docker_files()."""

    def _full_secrets(self, **overrides):
        """Return a secrets dict with all keys set to None, then apply overrides."""
        base = {
            "lavalink_password": None,
            "lavalink_port": None,
            "spotify_client_id": None,
            "spotify_client_secret": None,
            "youtube_refresh_token": None,
        }
        base.update(overrides)
        return base

    def test_updates_password_in_docker_compose(self):
        """_patch_docker_files must write the preserved password into docker-compose.yml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_path = os.path.join(tmpdir, "docker-compose.yml")
            with open(compose_path, "w") as f:
                f.write(_DOCKER_COMPOSE_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(self._full_secrets(lavalink_password="newpass"))
            with open(compose_path) as f:
                content = f.read()
        self.assertIn("LAVALINK_SERVER_PASSWORD=newpass", content)
        self.assertNotIn("=youshallnotpass", content)

    def test_updates_port_in_docker_compose(self):
        """_patch_docker_files must write the preserved port into docker-compose.yml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_path = os.path.join(tmpdir, "docker-compose.yml")
            with open(compose_path, "w") as f:
                f.write(_DOCKER_COMPOSE_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(self._full_secrets(lavalink_port="3456"))
            with open(compose_path) as f:
                content = f.read()
        self.assertIn("SERVER_PORT=3456", content)
        self.assertNotIn("SERVER_PORT=2333", content)

    def test_updates_password_in_lavalink_docker_yml(self):
        """_patch_docker_files must write the preserved password into application.docker.yml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.docker.yml"), "w") as f:
                f.write(_LAVALINK_DOCKER_YML_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(self._full_secrets(lavalink_password="newpass"))
            with open(os.path.join(lavalink_dir, "application.docker.yml")) as f:
                content = f.read()
        self.assertIn('password: "newpass"', content)
        self.assertNotIn('password: "youshallnotpass"', content)

    def test_uncomments_and_sets_youtube_refresh_token(self):
        """_patch_docker_files must uncomment the refreshToken line and set the saved value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.docker.yml"), "w") as f:
                f.write(_LAVALINK_DOCKER_YML_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(
                    self._full_secrets(youtube_refresh_token="my-yt-token")
                )
            with open(os.path.join(lavalink_dir, "application.docker.yml")) as f:
                content = f.read()
        self.assertIn('refreshToken: "my-yt-token"', content)
        self.assertNotIn("# refreshToken:", content)
        self.assertIn("skipInitialization: true", content)
        self.assertNotIn("skipInitialization: false", content)

    def test_replaces_existing_youtube_refresh_token(self):
        """_patch_docker_files must replace an already-set refreshToken with the new value."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.docker.yml"), "w") as f:
                f.write(_LAVALINK_DOCKER_YML_WITH_TOKEN)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(
                    self._full_secrets(youtube_refresh_token="new-yt-token")
                )
            with open(os.path.join(lavalink_dir, "application.docker.yml")) as f:
                content = f.read()
        self.assertIn('refreshToken: "new-yt-token"', content)
        self.assertNotIn("old-yt-token", content)

    def test_no_changes_when_secrets_are_none(self):
        """_patch_docker_files must not modify files when all credentials are None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            compose_path = os.path.join(tmpdir, "docker-compose.yml")
            with open(compose_path, "w") as f:
                f.write(_DOCKER_COMPOSE_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(self._full_secrets())
            with open(compose_path) as f:
                content = f.read()
        self.assertEqual(content, _DOCKER_COMPOSE_DEFAULT)

    def test_updates_password_in_lavalink_yml(self):
        """_patch_docker_files must write the preserved password into application.yml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.yml"), "w") as f:
                f.write(_LAVALINK_YML_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(self._full_secrets(lavalink_password="newpass"))
            with open(os.path.join(lavalink_dir, "application.yml")) as f:
                content = f.read()
        self.assertIn('password: "newpass"', content)
        self.assertNotIn('password: "youshallnotpass"', content)

    def test_uncomments_and_sets_youtube_refresh_token_in_lavalink_yml(self):
        """_patch_docker_files must uncomment the refreshToken line in application.yml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.yml"), "w") as f:
                f.write(_LAVALINK_YML_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(
                    self._full_secrets(youtube_refresh_token="my-yt-token")
                )
            with open(os.path.join(lavalink_dir, "application.yml")) as f:
                content = f.read()
        self.assertIn('refreshToken: "my-yt-token"', content)
        self.assertNotIn("#refreshToken:", content)
        self.assertIn("skipInitialization: true", content)
        self.assertNotIn("skipInitialization: false", content)

    def test_updates_both_lavalink_config_files(self):
        """_patch_docker_files must update both application.docker.yml and application.yml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.docker.yml"), "w") as f:
                f.write(_LAVALINK_DOCKER_YML_DEFAULT)
            with open(os.path.join(lavalink_dir, "application.yml"), "w") as f:
                f.write(_LAVALINK_YML_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(self._full_secrets(lavalink_password="sharedpass"))
            for fname in ("application.docker.yml", "application.yml"):
                with open(os.path.join(lavalink_dir, fname)) as f:
                    content = f.read()
                self.assertIn('password: "sharedpass"', content, msg=fname)
                self.assertNotIn('password: "youshallnotpass"', content, msg=fname)

    def test_updates_port_in_both_lavalink_config_files(self):
        """_patch_docker_files must write the preserved port into both lavalink config files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.docker.yml"), "w") as f:
                f.write(_LAVALINK_DOCKER_YML_DEFAULT)
            with open(os.path.join(lavalink_dir, "application.yml"), "w") as f:
                f.write(_LAVALINK_YML_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(self._full_secrets(lavalink_port="3456"))
            for fname in ("application.docker.yml", "application.yml"):
                with open(os.path.join(lavalink_dir, fname)) as f:
                    content = f.read()
                self.assertIn("port: 3456", content, msg=fname)
                self.assertNotIn("port: 2333", content, msg=fname)

    def test_updates_spotify_credentials_in_both_lavalink_config_files(self):
        """_patch_docker_files must write Spotify credentials into both lavalink config files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.docker.yml"), "w") as f:
                f.write(_LAVALINK_DOCKER_YML_DEFAULT)
            with open(os.path.join(lavalink_dir, "application.yml"), "w") as f:
                f.write(_LAVALINK_YML_DEFAULT)
            with patch.object(update, "ROOT_DIR", tmpdir):
                update._patch_docker_files(
                    self._full_secrets(spotify_client_id="sp-id", spotify_client_secret="sp-sec")
                )
            for fname in ("application.docker.yml", "application.yml"):
                with open(os.path.join(lavalink_dir, fname)) as f:
                    content = f.read()
                self.assertIn('clientId: "sp-id"', content, msg=fname)
                self.assertIn('clientSecret: "sp-sec"', content, msg=fname)
                self.assertNotIn('clientId: ""', content, msg=fname)
                self.assertNotIn('clientSecret: ""', content, msg=fname)

class TestInstallPreservesDockerCredentials(unittest.TestCase):
    """Tests that install() preserves docker credentials end-to-end."""

    def _make_response(self, zip_bytes: bytes) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.content = zip_bytes
        return mock_resp

    def test_install_preserves_lavalink_password_in_docker_compose(self):
        """install() must carry the existing Lavalink password into the new docker-compose.yml."""
        zip_bytes = _make_zip(
            "discord-music-bot-main",
            {
                "version.txt": "v2.0.0",
                "docker-compose.yml": _DOCKER_COMPOSE_DEFAULT,
                "lavalink/application.docker.yml": _LAVALINK_DOCKER_YML_DEFAULT,
            },
        )
        response = self._make_response(zip_bytes)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write old docker-compose.yml with a custom password.
            with open(os.path.join(tmpdir, "docker-compose.yml"), "w") as f:
                f.write(_DOCKER_COMPOSE_DEFAULT.replace("youshallnotpass", "myoldpass"))
            # Write settings.json with matching password (preserved across updates).
            settings = {"lavalink": {"password": "myoldpass"}}
            with open(os.path.join(tmpdir, "settings.json"), "w") as f:
                json.dump(settings, f)

            with (
                patch.object(update, "ROOT_DIR", tmpdir),
                patch("builtins.input", return_value="y"),
                patch.object(update, "_run_pip_install"),
            ):
                update.install(response, "v2.0.0")

            compose_path = os.path.join(tmpdir, "docker-compose.yml")
            self.assertTrue(os.path.exists(compose_path))
            with open(compose_path) as f:
                content = f.read()
        self.assertIn("LAVALINK_SERVER_PASSWORD=myoldpass", content)
        self.assertNotIn("youshallnotpass", content)

    def test_install_preserves_youtube_refresh_token(self):
        """install() must carry the YouTube refresh token into the new application.docker.yml."""
        zip_bytes = _make_zip(
            "discord-music-bot-main",
            {
                "version.txt": "v2.0.0",
                "lavalink/application.docker.yml": _LAVALINK_DOCKER_YML_DEFAULT,
            },
        )
        response = self._make_response(zip_bytes)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write old lavalink config with a refresh token.
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            with open(os.path.join(lavalink_dir, "application.docker.yml"), "w") as f:
                f.write(_LAVALINK_DOCKER_YML_WITH_TOKEN)
            with open(os.path.join(tmpdir, "settings.json"), "w") as f:
                json.dump({}, f)

            with (
                patch.object(update, "ROOT_DIR", tmpdir),
                patch("builtins.input", return_value="y"),
                patch.object(update, "_run_pip_install"),
            ):
                update.install(response, "v2.0.0")

            config_path = os.path.join(tmpdir, "lavalink", "application.docker.yml")
            self.assertTrue(os.path.exists(config_path))
            with open(config_path) as f:
                content = f.read()
        self.assertIn('refreshToken: "old-yt-token"', content)
        self.assertNotIn("# refreshToken:", content)
        self.assertIn("skipInitialization: true", content)

    def test_install_preserves_credentials_in_nondocker_lavalink_yml(self):
        """install() must carry credentials into the new lavalink/application.yml (non-Docker)."""
        zip_bytes = _make_zip(
            "discord-music-bot-main",
            {
                "version.txt": "v2.0.0",
                "lavalink/application.yml": _LAVALINK_YML_DEFAULT,
            },
        )
        response = self._make_response(zip_bytes)

        with tempfile.TemporaryDirectory() as tmpdir:
            lavalink_dir = os.path.join(tmpdir, "lavalink")
            os.makedirs(lavalink_dir)
            # Old non-docker config has a token set.
            with open(os.path.join(lavalink_dir, "application.yml"), "w") as f:
                f.write(_LAVALINK_YML_WITH_TOKEN)
            settings = {"lavalink": {"password": "nondockerpass"}}
            with open(os.path.join(tmpdir, "settings.json"), "w") as f:
                json.dump(settings, f)

            with (
                patch.object(update, "ROOT_DIR", tmpdir),
                patch("builtins.input", return_value="y"),
                patch.object(update, "_run_pip_install"),
            ):
                update.install(response, "v2.0.0")

            config_path = os.path.join(tmpdir, "lavalink", "application.yml")
            self.assertTrue(os.path.exists(config_path))
            with open(config_path) as f:
                content = f.read()
        self.assertIn('password: "nondockerpass"', content)
        self.assertNotIn('password: "youshallnotpass"', content)
        self.assertIn('refreshToken: "old-yt-token"', content)
        self.assertNotIn("#refreshToken:", content)
        self.assertIn("skipInitialization: true", content)

    def test_install_preserves_port_and_spotify_in_both_config_files(self):
        """install() must carry port and Spotify credentials into both lavalink config files."""
        zip_bytes = _make_zip(
            "discord-music-bot-main",
            {
                "version.txt": "v2.0.0",
                "lavalink/application.docker.yml": _LAVALINK_DOCKER_YML_DEFAULT,
                "lavalink/application.yml": _LAVALINK_YML_DEFAULT,
            },
        )
        response = self._make_response(zip_bytes)

        settings = {
            "lavalink": {"port": 3456, "password": "mypass"},
            "spotify_client_id": "sp-id",
            "spotify_client_secret": "sp-sec",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "settings.json"), "w") as f:
                json.dump(settings, f)

            with (
                patch.object(update, "ROOT_DIR", tmpdir),
                patch("builtins.input", return_value="y"),
                patch.object(update, "_run_pip_install"),
            ):
                update.install(response, "v2.0.0")

            lavalink_dir = os.path.join(tmpdir, "lavalink")
            for fname in ("application.docker.yml", "application.yml"):
                with open(os.path.join(lavalink_dir, fname)) as f:
                    content = f.read()
                self.assertIn("port: 3456", content, msg=fname)
                self.assertNotIn("port: 2333", content, msg=fname)
                self.assertIn('password: "mypass"', content, msg=fname)
                self.assertIn('clientId: "sp-id"', content, msg=fname)
                self.assertIn('clientSecret: "sp-sec"', content, msg=fname)


class TestReadLocalVersion(unittest.TestCase):
    """Tests for _read_local_version()."""

    def test_reads_version_from_file(self):
        """_read_local_version must return the contents of version.txt, stripped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_path = os.path.join(tmpdir, "version.txt")
            with open(version_path, "w") as f:
                f.write("v1.2.3\n")
            with patch.object(update, "VERSION_FILE", version_path):
                result = update._read_local_version()
        self.assertEqual(result, "v1.2.3")

    def test_returns_unknown_when_file_missing(self):
        """_read_local_version must return 'unknown' when version.txt does not exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = os.path.join(tmpdir, "version.txt")
            with patch.object(update, "VERSION_FILE", missing_path):
                result = update._read_local_version()
        self.assertEqual(result, "unknown")

    def test_version_txt_has_valid_version(self):
        """version.txt in the repository must contain a valid vX.Y.Z version string."""
        import re
        actual_version = update._read_local_version()
        self.assertRegex(
            actual_version,
            r"^v\d+\.\d+\.\d+$",
            msg=(
                f"version.txt contains '{actual_version}', which is not a valid "
                "vX.Y.Z version string. Make sure version.txt is updated when "
                "releasing a new version."
            ),
        )


class TestCheckVersion(unittest.TestCase):
    """Tests for check_version()."""

    def _mock_response(self, text: str) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.text = text
        return mock_resp

    def test_returns_remote_version(self):
        """check_version must return the version string fetched from the remote URL."""
        with patch("update.requests.get", return_value=self._mock_response("v1.2.3\n")):
            result = update.check_version()
        self.assertEqual(result, "v1.2.3")

    def test_prints_up_to_date_when_versions_match(self):
        """check_version(with_msg=True) must print an up-to-date message when local==remote."""
        with patch("update.requests.get", return_value=self._mock_response("v1.2.3")):
            with patch.object(update, "__version__", "v1.2.3"):
                with patch("builtins.print") as mock_print:
                    update.check_version(with_msg=True)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("up-to-date", printed)
        self.assertIn("v1.2.3", printed)

    def test_prints_not_up_to_date_when_versions_differ(self):
        """check_version(with_msg=True) must warn about the newer version when local!=remote."""
        with patch("update.requests.get", return_value=self._mock_response("v1.2.4")):
            with patch.object(update, "__version__", "v1.2.3"):
                with patch("builtins.print") as mock_print:
                    update.check_version(with_msg=True)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("not up-to-date", printed)
        self.assertIn("v1.2.4", printed)
        self.assertIn("v1.2.3", printed)


class TestMainLatestFlag(unittest.TestCase):
    """Tests for main() --latest / -l behaviour."""

    def _mock_response(self, text: str) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.text = text
        return mock_resp

    def test_already_up_to_date_message_when_versions_match(self):
        """main() with --latest must print 'already up-to-date' and skip install when local==remote."""
        with patch("sys.argv", ["update.py", "--latest"]):
            with patch("update.requests.get", return_value=self._mock_response("v1.2.3")):
                with patch.object(update, "__version__", "v1.2.3"):
                    with patch("builtins.print") as mock_print:
                        with patch("update.download_file") as mock_dl:
                            update.main()
        mock_dl.assert_not_called()
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        self.assertIn("already up-to-date", printed)
        self.assertIn("v1.2.3", printed)

    def test_install_triggered_when_new_version_available(self):
        """main() with --latest must download and install when remote version is newer."""
        mock_http_resp = self._mock_response("v1.2.4")
        fake_dl_response = MagicMock()
        with patch("sys.argv", ["update.py", "--latest"]):
            with patch("update.requests.get", return_value=mock_http_resp):
                with patch.object(update, "__version__", "v1.2.3"):
                    with patch("update.download_file", return_value=fake_dl_response) as mock_dl:
                        with patch("update.install") as mock_install:
                            update.main()
        mock_dl.assert_called_once_with("v1.2.4")
        mock_install.assert_called_once_with(fake_dl_response, "v1.2.4")


if __name__ == "__main__":
    unittest.main()
