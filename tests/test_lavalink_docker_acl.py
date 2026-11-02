"""Docker bind-mount permissions for Lavalink's non-root UID 322."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, call

from scripts.prepare_lavalink_docker import prepare, main


class LavalinkACLTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'lavalink').mkdir()
        self.config = self.root / 'lavalink/application.docker.local.yml'
        self.config.write_text('private test YAML content', encoding='utf-8')
        self.config.chmod(0o600)
        (self.root / 'settings.json').write_text('private settings', encoding='utf-8')
        (self.root / '.env').write_text('private env', encoding='utf-8')

    def test_dry_run_leaves_secrets_and_permissions_untouched(self):
        operations = prepare(self.root)
        self.assertEqual(operations, [
            ('lavalink', 'x'),
            ('lavalink/application.docker.local.yml', 'r'),
            ('lavalink/plugins', 'rwx'),
        ])
        self.assertFalse((self.root / 'lavalink/plugins').exists())
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)

    def test_apply_grants_narrow_named_user_permissions(self):
        with patch('scripts.prepare_lavalink_docker.shutil.which', return_value='/usr/bin/setfacl'), \
             patch('scripts.prepare_lavalink_docker.subprocess.run') as command:
            prepare(self.root, apply=True)
        self.assertTrue((self.root / 'lavalink/plugins').is_dir())
        self.assertEqual(command.call_count, 3)
        self.assertEqual(command.call_args_list[0].args[0][2], 'u:322:x')
        self.assertEqual(command.call_args_list[1].args[0][2], 'u:322:r')
        self.assertEqual(command.call_args_list[2].args[0][2], 'u:322:rwx')
        self.assertEqual((self.root / 'settings.json').read_text(), 'private settings')
        self.assertEqual((self.root / '.env').read_text(), 'private env')
        self.assertEqual(self.config.read_text(), 'private test YAML content')

    def test_existing_plugin_files_get_read_write_access(self):
        plugins = self.root / 'lavalink/plugins'
        plugins.mkdir()
        jar = plugins / 'example-plugin.jar'
        jar.write_bytes(b'jar')
        with patch('scripts.prepare_lavalink_docker.shutil.which', return_value='/usr/bin/setfacl'), \
             patch('scripts.prepare_lavalink_docker.subprocess.run') as command:
            operations = prepare(self.root, apply=True)
        self.assertIn(('lavalink/plugins/example-plugin.jar', 'rw'), operations)
        args = [c.args[0] for c in command.call_args_list]
        self.assertIn(['setfacl', '-m', 'u:322:rw', str(jar)], args)

    def test_missing_acl_utility_fails_before_any_changes(self):
        with patch('scripts.prepare_lavalink_docker.shutil.which', return_value=None), \
             patch('scripts.prepare_lavalink_docker.subprocess.run') as command:
            with self.assertRaisesRegex(RuntimeError, 'setfacl'):
                prepare(self.root, apply=True)
            command.assert_not_called()
        self.assertFalse((self.root / 'lavalink/plugins').exists())

    def test_symlinked_config_is_rejected(self):
        self.config.unlink()
        self.config.symlink_to(self.root / 'settings.json')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            prepare(self.root, apply=True)

    def test_symlinked_plugin_directory_is_rejected(self):
        (self.root / 'lavalink/plugins').symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            prepare(self.root, apply=True)

    def test_missing_config_is_rejected(self):
        self.config.unlink()
        with self.assertRaises(FileNotFoundError):
            prepare(self.root)

    def test_invalid_uid_rejected(self):
        for uid in (0, -1, True):
            with self.subTest(uid=uid), self.assertRaises(ValueError):
                prepare(self.root, uid=uid)
