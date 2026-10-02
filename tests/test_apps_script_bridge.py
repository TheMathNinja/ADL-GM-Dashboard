import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import apps_script_bridge as bridge


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'APPS_SCRIPT_BRIDGE_URL': 'https://example.test/bridge',
            'APPS_SCRIPT_BRIDGE_TOKEN': 'secret',
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def response(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'status': 'success'}).encode()
        return response

    @patch('apps_script_bridge.time.sleep')
    @patch('apps_script_bridge.urllib.request.urlopen')
    def test_transient_failure_is_retried(self, urlopen, sleep):
        urlopen.side_effect = [OSError('temporary'), self.response()]
        self.assertEqual(bridge.request_bridge(attempts=2)['status'], 'success')
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once_with(5)

    def test_missing_credentials_fail_immediately(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'not configured'):
                bridge.request_bridge()


if __name__ == '__main__':
    unittest.main()
