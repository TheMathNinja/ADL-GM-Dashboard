import sys
import unittest
import io
import json
import tempfile
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_chi_team_model_refresh import snapshot_key, signature, ensure_site_model_contract


class SnapshotKeyTest(unittest.TestCase):
    def test_accepts_flat_site_response(self):
        self.assertEqual(snapshot_key({"snapshotKey": "flat"}), "flat")

    def test_accepts_nested_site_response(self):
        self.assertEqual(snapshot_key({"metadata": {"snapshotKey": "nested"}}), "nested")

    def test_accepts_wrapped_site_response(self):
        self.assertEqual(snapshot_key({"data": {"metadata": {"snapshotKey": "wrapped"}}}), "wrapped")

    def test_missing_key_is_none(self):
        self.assertIsNone(snapshot_key({"metadata": {}}))

    def test_generated_receipt_does_not_change_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / 'data/player_strength'
            data.mkdir(parents=True)
            (data / 'player_weeks.csv').write_text('week,score\n7,10\n')
            before = signature(root)
            (data / 'refresh_receipt.json').write_text('{"generatedAt":"new"}')
            self.assertEqual(before, signature(root))
            (data / 'player_weeks.csv').write_text('week,score\n7,11\n')
            self.assertNotEqual(before, signature(root))

    def check_contract(self, version, weights=None, season=2026):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'data').mkdir()
            (root / 'data/adl_scoring_model.json').write_text(json.dumps({'2026': {'version': 'v4', 'cases': {'forecast': {'weights': [.35, 0, .55, .1]}}}}))
            response = {'contractVersion': 1, 'season': season, 'supportedADLModelVersions': [version], 'adlWeights': weights if weights is not None else [.35, 0, .55, .1]}
            with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(response).encode())):
                ensure_site_model_contract(root, {'OAI-Sites-Authorization': 'Bearer test'})

    def test_compatible_site_contract(self):
        self.check_contract('v4')

    def test_old_site_rejected_before_expensive_build(self):
        with self.assertRaisesRegex(RuntimeError, 'does not support ADL model v4'):
            self.check_contract('v3')

    def test_wrong_weights_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'weights disagree'):
            self.check_contract('v4', [1, 0, 0, 0])

    def test_wrong_season_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'incompatible'):
            self.check_contract('v4', season=2025)

    def test_uploader_uses_the_same_fingerprint(self):
        source = (Path(__file__).resolve().parents[1] / 'scripts/sync_chi_team_model.py').read_text()
        self.assertIn('from check_chi_team_model_refresh import signature, snapshot_key, ensure_site_model_contract', source)
        self.assertNotIn('def signature(', source)


if __name__ == "__main__":
    unittest.main()
