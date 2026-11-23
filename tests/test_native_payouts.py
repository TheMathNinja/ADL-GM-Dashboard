import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_payouts import build_snapshot, participant_rows
from nfl_teams import CONTRACT, MFL_TEAMS, mfl_team, provider_team


class NativePayoutTests(unittest.TestCase):
    def setUp(self):
        self.rules = json.loads((ROOT / 'config/payouts.json').read_text())

    def test_ties_preserve_the_full_prize_and_keep_adjustments_separate(self):
        scores = {(name, 1): [1, 1, 1, 2] for name, _, _ in self.rules['teams']}
        with (patch('build_payouts.load_scores', return_value=(scores, 1)),
              patch('build_payouts.certified_qualifiers', return_value=(set(), 'proof'))):
            snapshot, _, _ = build_snapshot(ROOT, self.rules['league'], self.rules['season'], 1)
        self.assertEqual({team['code'] for team in snapshot['teams']}, MFL_TEAMS)
        prize = self.rules['prizes'][19][1]
        self.assertEqual(snapshot['totals']['earned'], 2 * prize)
        self.assertEqual(snapshot['totals']['hostingFee'], self.rules['hostingFee'])
        self.assertEqual(sum(team['earned'] for team in snapshot['teams']), 2 * prize)
        for team in snapshot['teams']:
            self.assertEqual(team['earned'], prize / 16)
            self.assertEqual(team['adjustment'], self.rules['adjustments'].get(team['code'], 0))
            self.assertEqual(team['payout'], team['earned'] + team['adjustment'])
            self.assertEqual(team['adjustmentNote'], self.rules['adjustmentNotes'].get(team['code']))
        self.assertEqual(len(snapshot['awards']), 23)
        self.assertEqual(sum(row['settled'] for row in snapshot['prizes']), 1)
        self.assertEqual(snapshot['awards'][1]['winners'], [[] for _ in range(8)])

    def test_only_certified_participants_are_paid_and_ranked_by_all_play(self):
        teams = self.rules['teams']
        nfc = [code for _, code, conf in teams if conf == 'NFC']
        afc = [code for _, code, conf in teams if conf == 'AFC']
        score_for = {nfc[0]: 70, nfc[1]: 40, nfc[2]: 90, afc[0]: 60}
        scores = {(name, 1): [0, 0, 100, score_for.get(code, 10)] for name, code, _ in teams}
        qualified = {nfc[0], nfc[1], afc[0]}
        self.assertEqual(participant_rows(teams, scores, 1, qualified)[:3],
                         [[nfc[0], afc[0]], [nfc[1], ''], ['', '']])
        with (patch('build_payouts.load_scores', return_value=(scores, 1)),
              patch('build_payouts.certified_qualifiers', return_value=(qualified, 'proof'))):
            snapshot, _, _ = build_snapshot(ROOT, self.rules['league'], self.rules['season'], 1)
        first, second, third = snapshot['prizes'][7:10]
        self.assertEqual(first['recipients'], {'NFC': [nfc[0]], 'AFC': [afc[0]]})
        self.assertEqual(second['recipients'], {'NFC': [nfc[1]], 'AFC': []})
        self.assertTrue(first['settled'])
        self.assertFalse(second['settled'])
        self.assertFalse(third['settled'])
        prize = self.rules['prizes'][7][1]
        self.assertEqual(next(t['earned'] for t in snapshot['teams'] if t['code'] == nfc[1]), prize)

    def test_all_team_codes_and_provider_round_trips(self):
        for code in MFL_TEAMS:
            for provider in CONTRACT['providers']:
                self.assertEqual(mfl_team(provider_team(code, provider), strict=True), code)
        for alias, code in CONTRACT['aliases'].items():
            self.assertEqual(mfl_team(alias, strict=True), code)
        self.assertEqual(mfl_team('FA', strict=True), 'FA')
        self.assertIsNone(mfl_team(None, strict=True))
        self.assertEqual(mfl_team('', strict=True), '')
        with self.assertRaises(ValueError):
            mfl_team('UNKNOWN', strict=True)


if __name__ == '__main__':
    unittest.main()
