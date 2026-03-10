"""Tests for update.py — bot auto-update helpers."""

import io
import os
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import update  # noqa: E402


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


if __name__ == "__main__":
    unittest.main()
