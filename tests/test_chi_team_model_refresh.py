import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_chi_team_model_refresh import snapshot_key


class SnapshotKeyTest(unittest.TestCase):
    def test_accepts_flat_site_response(self):
        self.assertEqual(snapshot_key({"snapshotKey": "flat"}), "flat")

    def test_accepts_nested_site_response(self):
        self.assertEqual(snapshot_key({"metadata": {"snapshotKey": "nested"}}), "nested")

    def test_accepts_wrapped_site_response(self):
        self.assertEqual(snapshot_key({"data": {"metadata": {"snapshotKey": "wrapped"}}}), "wrapped")

    def test_missing_key_is_none(self):
        self.assertIsNone(snapshot_key({"metadata": {}}))


if __name__ == "__main__":
    unittest.main()
