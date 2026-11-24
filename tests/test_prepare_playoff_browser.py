import runpy
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


class BrowserSetupTests(unittest.TestCase):
    def setUp(self):
        self.error = type('BrowserError', (Exception,), {})
        playwright = types.ModuleType('playwright.sync_api')
        playwright.Error = self.error
        playwright.sync_playwright = Mock()
        with patch.dict(sys.modules, {'playwright.sync_api': playwright}):
            values = runpy.run_path(str(Path(__file__).parents[1] / 'scripts/prepare_playoff_browser.py'))
        self.prepare = values['prepare']
        self.module = self.prepare.__globals__

    def test_warm_cache_must_launch_and_does_not_contact_downloads(self):
        with patch.dict(self.module, {'smoke': Mock(), 'download_shell': Mock()}):
            self.prepare()
            self.module['smoke'].assert_called_once()
            self.module['download_shell'].assert_not_called()

    def test_cold_cache_downloads_then_launches_without_apt(self):
        smoke = Mock(side_effect=[self.error("Executable doesn't exist"), None])
        with patch.dict(self.module, {'smoke': smoke, 'download_shell': Mock(), 'playwright': Mock()}):
            self.prepare()
            self.module['download_shell'].assert_called_once()
            self.module['playwright'].assert_not_called()
        self.assertEqual(smoke.call_count, 2)

    def test_download_retries_timeout_not_forbidden(self):
        timeout = subprocess.TimeoutExpired('playwright', 55)
        forbidden = subprocess.CalledProcessError(1, 'playwright', output='HTTP 403 Forbidden')
        download = self.module['download_shell']
        with patch.dict(self.module, {'sleep': Mock()}), patch.object(
                subprocess, 'run', side_effect=[timeout, types.SimpleNamespace(stdout='')]) as command:
            download()
            self.assertEqual(command.call_count, 2)
        with patch.object(subprocess, 'run', side_effect=forbidden) as command:
            with self.assertRaises(subprocess.CalledProcessError):
                download()
            command.assert_called_once()


if __name__ == '__main__':
    unittest.main()
