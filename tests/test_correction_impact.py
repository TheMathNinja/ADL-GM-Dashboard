import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import correction_impact as m


class CorrectionImpactTest(unittest.TestCase):
    def test_ext_state_requires_current_calculator_eligibility(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / 'data'
            data.mkdir()
            (data / 'ext_pr_summary.csv').write_text(
                'player_id,pr_current_final,pr_current_pos\n1,6,RB\n2,53.5,DE\n', encoding='utf-8')
            (data / 'ext_candidates.csv').write_text(
                'player_id,player_name,player_pos,eligibility_note\n'
                '1,"Conner, James",RB,Likely EXT eligible\n'
                '2,"Verse, Jared",DE,Ineligible: 2+ current contract years\n', encoding='utf-8')
            state = m.ext_state(Path(directory))
        self.assertEqual(set(state), {'1'})
        self.assertEqual(state['1']['name'], 'James Conner')

    def test_only_final_ext_rank_and_material_team_results_are_reported(self):
        before = {'season': 2026, 'week': 5, 'player_scores': {'1': 12, '2': 3.5},
                  'ext': {'1': {'name': 'James Conner', 'position': 'RB', 'rank': 7},
                          '2': {'name': 'Jared Verse', 'position': 'DE', 'rank': 52}},
                  'all_play': {'0001': {'name': 'Carolina Panthers', 'wins': 13}},
                  'bonus': {'Q1:0001': {'name': 'Carolina Panthers', 'event': 'Q1', 'result': 'T'}}}
        after = {'season': 2026, 'week': 5, 'player_scores': {'1': 13, '2': 3.5},
                 'ext': {'1': {'name': 'James Conner', 'position': 'RB', 'rank': 6},
                         '2': {'name': 'Jared Verse', 'position': 'DE', 'rank': 53.5}},
                 'all_play': {'0001': {'name': 'Carolina Panthers', 'wins': 12}},
                 'bonus': {'Q1:0001': {'name': 'Carolina Panthers', 'event': 'Q1', 'result': 'L'}}}
        with patch.dict(os.environ, {'GITHUB_RUN_ID': '123'}):
            impact = m.changed(before, after, 'ADL')
        self.assertEqual(impact['ext_pr'][0]['old_rank'], 7)
        self.assertEqual(impact['ext_pr'][0]['new_rank'], 6)
        self.assertEqual([row['player'] for row in impact['ext_pr']], ['James Conner'])
        self.assertEqual(impact['all_play'][0]['new_wins'], 12)
        self.assertEqual(impact['bonus_games'][0]['new_result'], 'L')


if __name__ == '__main__':
    unittest.main()
