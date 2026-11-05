import importlib.util
from pathlib import Path
import unittest
from unittest.mock import MagicMock, Mock
from urllib.error import HTTPError, URLError

spec = importlib.util.spec_from_file_location('dispatch', Path(__file__).resolve().parents[1] / 'scripts/request_failure_report.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DispatchTests(unittest.TestCase):
    def response(self):
        result = MagicMock()
        result.__enter__.return_value.status = 204
        return result

    def error(self, code):
        return HTTPError(module.URL, code, 'error', {}, None)

    def test_transient_recovery(self):
        fetch = Mock(side_effect=[self.error(500), URLError('timeout'), self.response()])
        sleep = Mock()
        module.dispatch('test', fetch, sleep)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [5, 15])

    def test_permanent_failures_are_not_hidden(self):
        for code in (401, 403, 404, 422):
            fetch, sleep = Mock(side_effect=self.error(code)), Mock()
            with self.assertRaisesRegex(RuntimeError, str(code)):
                module.dispatch('test', fetch, sleep)
            self.assertEqual(fetch.call_count, 1)
            sleep.assert_not_called()

    def test_exhaustion_remains_failure(self):
        fetch = Mock(side_effect=self.error(503))
        with self.assertRaisesRegex(RuntimeError, 'after 5 attempts'):
            module.dispatch('test', fetch, Mock())
        self.assertEqual(fetch.call_count, 5)

    def test_success_does_not_retry(self):
        fetch, sleep = Mock(return_value=self.response()), Mock()
        module.dispatch('test', fetch, sleep)
        self.assertEqual(fetch.call_count, 1)
        sleep.assert_not_called()

    def test_missing_token(self):
        fetch = Mock()
        with self.assertRaisesRegex(RuntimeError, 'credential'):
            module.dispatch('', fetch, Mock())
        fetch.assert_not_called()
