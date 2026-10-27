import sys, unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from refresh_player_strength_inputs import canonical_player_name,restore_verified_historical_teams

class IdentityRecoveryTests(unittest.TestCase):
 def test_payouts_precedes_forecast_failure_gate(self):
  workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/refresh_extension_calculator.yml').read_text(encoding='utf-8')
  names=['Build playoff bracket from official workbook Elo','Synchronize and verify Payouts','Build playoff forecast and Tuesday Game of the Week swing data','Require synchronized quarterly forecasts before publication']
  offsets=[workflow.index('- name: '+name) for name in names]
  self.assertEqual(offsets,sorted(offsets))
  for name in names:self.assertEqual(workflow.count('- name: '+name),1)
 def test_suffix_and_comma_order(self):
  self.assertEqual(canonical_player_name('Williams, Wydett'),canonical_player_name('Wydett Williams Jr.'))
  self.assertNotEqual(canonical_player_name('Wydett Williams'),canonical_player_name('Another Williams'))
 def test_released_player_retains_verified_historical_team(self):
  scores=pd.DataFrame([dict(week=3,player_id='17797',player_name='Williams, Wydett',pos='S',team='FA',points=1.5)])
  old=scores.assign(season=2026,team='ARI')
  schedule=pd.DataFrame([dict(week=3,team='ARI')])
  self.assertEqual(restore_verified_historical_teams(scores,old,schedule,2026).team.iloc[0],'ARI')
  self.assertEqual(restore_verified_historical_teams(scores,old.assign(points=2),schedule,2026).team.iloc[0],'FA')
  self.assertEqual(restore_verified_historical_teams(scores,old.assign(season=2025),schedule,2026).team.iloc[0],'FA')
  self.assertEqual(restore_verified_historical_teams(scores,old.assign(player_name='Another Williams'),schedule,2026).team.iloc[0],'FA')
  self.assertEqual(restore_verified_historical_teams(scores,old.assign(pos='LB'),schedule,2026).team.iloc[0],'FA')
 def test_current_valid_weekly_team_is_not_overwritten(self):
  scores=pd.DataFrame([dict(week=3,player_id='17797',player_name='Williams, Wydett',pos='S',team='BUF',points=1.5)])
  old=scores.assign(season=2026,team='ARI')
  schedule=pd.DataFrame([dict(week=3,team='ARI'),dict(week=3,team='BUF')])
  self.assertEqual(restore_verified_historical_teams(scores,old,schedule,2026).team.iloc[0],'BUF')

if __name__=='__main__':unittest.main()
