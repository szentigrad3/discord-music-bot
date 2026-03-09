"""Tests for update_lavalink.py — Lavalink JAR and plugin auto-update helpers."""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import update_lavalink  # noqa: E402


# ---------------------------------------------------------------------------
# fetch_latest_github_tag
# ---------------------------------------------------------------------------

class TestFetchLatestGithubTag(unittest.TestCase):
    """Tests for fetch_latest_github_tag()."""

    def test_strips_v_prefix(self):
        """fetch_latest_github_tag must strip a leading 'v' from the tag name.

        Many GitHub projects tag releases as 'v1.2.3'.  Plugin versions in the
        Lavalink config use bare version strings ('1.2.3'), so the prefix must
        be removed before writing the config.
        """
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tag_name": "v4.0.8"}
        with patch("requests.get", return_value=mock_resp):
            tag = update_lavalink.fetch_latest_github_tag("http://example.com/releases/latest")
        self.assertEqual(tag, "4.0.8")

    def test_returns_tag_without_v_prefix_unchanged(self):
        """fetch_latest_github_tag must return tags that have no 'v' prefix unchanged."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"tag_name": "4.0.8"}
        with patch("requests.get", return_value=mock_resp):
            tag = update_lavalink.fetch_latest_github_tag("http://example.com/releases/latest")
        self.assertEqual(tag, "4.0.8")


# ---------------------------------------------------------------------------
# update_lavalink_jar
# ---------------------------------------------------------------------------

class TestUpdateLavalinkJar(unittest.TestCase):
    """Tests for update_lavalink_jar()."""

    def test_skips_when_jar_absent(self):
        """update_lavalink_jar must return False when Lavalink.jar does not exist.

        Docker installations and setups that manage Lavalink externally do not
        have a local Lavalink.jar.  The function must exit early without making
        any network requests.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            absent_jar = os.path.join(tmpdir, "Lavalink.jar")
            with patch.object(update_lavalink, "LAVALINK_JAR_PATH", absent_jar):
                result = update_lavalink.update_lavalink_jar()
        self.assertFalse(result)

    def test_skips_when_already_up_to_date(self):
        """update_lavalink_jar must return False when the JAR is already at the latest version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jar_path = os.path.join(tmpdir, "Lavalink.jar")
            version_file = os.path.join(tmpdir, ".lavalink-version")
            open(jar_path, "w").close()
            with open(version_file, "w") as f:
                f.write("4.0.8")
            with (
                patch.object(update_lavalink, "LAVALINK_JAR_PATH", jar_path),
                patch.object(update_lavalink, "LAVALINK_VERSION_FILE", version_file),
                patch.object(update_lavalink, "fetch_latest_github_tag", return_value="4.0.8"),
            ):
                result = update_lavalink.update_lavalink_jar()
        self.assertFalse(result)

    def test_downloads_jar_and_records_version_when_newer_available(self):
        """update_lavalink_jar must download the JAR and record the new version tag.

        After the download the .lavalink-version file must contain the newly
        installed version so that the next invocation can skip a redundant
        re-download.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            jar_path = os.path.join(tmpdir, "Lavalink.jar")
            version_file = os.path.join(tmpdir, ".lavalink-version")
            open(jar_path, "w").close()
            with open(version_file, "w") as f:
                f.write("4.0.7")

            mock_resp = MagicMock()
            mock_resp.content = b"fake-jar-content"
            with (
                patch.object(update_lavalink, "LAVALINK_JAR_PATH", jar_path),
                patch.object(update_lavalink, "LAVALINK_VERSION_FILE", version_file),
                patch.object(update_lavalink, "fetch_latest_github_tag", return_value="4.0.8"),
                patch.object(update_lavalink, "LAVALINK_JAR_URL", "http://example.com/Lavalink.jar"),
                patch("requests.get", return_value=mock_resp),
            ):
                result = update_lavalink.update_lavalink_jar()

            with open(version_file) as f:
                recorded = f.read().strip()

        self.assertTrue(result)
        self.assertEqual(recorded, "4.0.8")

    def test_unknown_version_triggers_download(self):
        """update_lavalink_jar must download the JAR when the installed version is unknown.

        If .lavalink-version is absent (e.g. after a manual install), the
        function cannot confirm the current version is up-to-date, so it must
        re-download to be safe.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            jar_path = os.path.join(tmpdir, "Lavalink.jar")
            version_file = os.path.join(tmpdir, ".lavalink-version")
            open(jar_path, "w").close()
            # No version file — _read_local_lavalink_version returns "unknown".

            mock_resp = MagicMock()
            mock_resp.content = b"fake-jar-content"
            with (
                patch.object(update_lavalink, "LAVALINK_JAR_PATH", jar_path),
                patch.object(update_lavalink, "LAVALINK_VERSION_FILE", version_file),
                patch.object(update_lavalink, "fetch_latest_github_tag", return_value="4.0.8"),
                patch.object(update_lavalink, "LAVALINK_JAR_URL", "http://example.com/Lavalink.jar"),
                patch("requests.get", return_value=mock_resp),
            ):
                result = update_lavalink.update_lavalink_jar()

        self.assertTrue(result)


# ---------------------------------------------------------------------------
# update_lavalink_plugins
# ---------------------------------------------------------------------------

_SAMPLE_CONFIG = """\
lavalink:
  plugins:
    - dependency: "dev.lavalink.youtube:youtube-plugin:1.18.0"
      snapshot: false
    - dependency: "com.github.topi314.lavasrc:lavasrc-plugin:4.8.1"
      snapshot: false
"""


class TestUpdateLavalinkPlugins(unittest.TestCase):
    """Tests for update_lavalink_plugins()."""

    def test_updates_plugin_versions_in_config(self):
        """update_lavalink_plugins must replace pinned versions with the latest release versions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "application.yml")
            with open(config_path, "w") as f:
                f.write(_SAMPLE_CONFIG)

            with (
                patch.object(update_lavalink, "LAVALINK_CONFIG_FILES", [config_path]),
                patch.object(
                    update_lavalink, "PLUGIN_RELEASES",
                    {
                        "dev.lavalink.youtube:youtube-plugin":          "http://api.example.com/yt",
                        "com.github.topi314.lavasrc:lavasrc-plugin":    "http://api.example.com/src",
                    },
                ),
                patch.object(
                    update_lavalink, "fetch_latest_github_tag",
                    side_effect=lambda url: "1.19.0" if "yt" in url else "4.9.0",
                ),
            ):
                result = update_lavalink.update_lavalink_plugins()

            with open(config_path) as f:
                content = f.read()

        self.assertTrue(result)
        self.assertIn('youtube-plugin:1.19.0"', content)
        self.assertIn('lavasrc-plugin:4.9.0"', content)

    def test_returns_false_when_all_plugins_up_to_date(self):
        """update_lavalink_plugins must return False when all plugin versions are current."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "application.yml")
            with open(config_path, "w") as f:
                f.write(_SAMPLE_CONFIG)

            with (
                patch.object(update_lavalink, "LAVALINK_CONFIG_FILES", [config_path]),
                patch.object(
                    update_lavalink, "PLUGIN_RELEASES",
                    {
                        "dev.lavalink.youtube:youtube-plugin":          "http://api.example.com/yt",
                        "com.github.topi314.lavasrc:lavasrc-plugin":    "http://api.example.com/src",
                    },
                ),
                patch.object(
                    update_lavalink, "fetch_latest_github_tag",
                    side_effect=lambda url: "1.18.0" if "yt" in url else "4.8.1",
                ),
            ):
                result = update_lavalink.update_lavalink_plugins()

        self.assertFalse(result)

    def test_skips_absent_config_files(self):
        """update_lavalink_plugins must skip config files that do not exist.

        A non-Docker install may have only application.yml; or neither file
        may be present if the user manages configs manually.  The function
        must not raise an error in either case.
        """
        with (
            patch.object(
                update_lavalink, "LAVALINK_CONFIG_FILES",
                ["/nonexistent/application.yml"],
            ),
            patch.object(
                update_lavalink, "PLUGIN_RELEASES",
                {"dev.lavalink.youtube:youtube-plugin": "http://api.example.com/yt"},
            ),
            patch.object(update_lavalink, "fetch_latest_github_tag", return_value="1.19.0"),
        ):
            result = update_lavalink.update_lavalink_plugins()

        self.assertFalse(result)

    def test_updates_both_config_files(self):
        """update_lavalink_plugins must update every config file that exists.

        application.yml and application.docker.yml must be kept in sync so
        that Docker and non-Docker deployments always run the same plugin
        versions.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config1 = os.path.join(tmpdir, "application.yml")
            config2 = os.path.join(tmpdir, "application.docker.yml")
            for p in (config1, config2):
                with open(p, "w") as f:
                    f.write(_SAMPLE_CONFIG)

            with (
                patch.object(update_lavalink, "LAVALINK_CONFIG_FILES", [config1, config2]),
                patch.object(
                    update_lavalink, "PLUGIN_RELEASES",
                    {"dev.lavalink.youtube:youtube-plugin": "http://api.example.com/yt"},
                ),
                patch.object(update_lavalink, "fetch_latest_github_tag", return_value="1.19.0"),
            ):
                update_lavalink.update_lavalink_plugins()

            for p in (config1, config2):
                with open(p) as f:
                    content = f.read()
                self.assertIn(
                    'youtube-plugin:1.19.0"',
                    content,
                    f"{os.path.basename(p)} was not updated.",
                )


if __name__ == "__main__":
    unittest.main()
