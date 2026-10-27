import sys, unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from refresh_player_strength_inputs import canonical_player_name,restore_verified_historical_teams

class IdentityRecoveryTests(unittest.TestCase):
 def test_payouts_precedes_forecast_failure_gate(self):
  workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/refresh_extension_calculator.yml').read_text(encoding='utf-8')
  names=['Synchronize and verify Payouts','Build playoff forecast and Tuesday Game of the Week swing data','Build playoff bracket from official workbook Elo','Synchronize and verify postseason Payouts','Require synchronized quarterly forecasts before publication']
  offsets=[workflow.index('- name: '+name) for name in names]
  self.assertEqual(offsets,sorted(offsets))
  for name in names:self.assertEqual(workflow.count('- name: '+name),1)
 def test_regular_season_prizes_need_no_bracket(self):
  from sync_payouts import postseason_prizes
  self.assertEqual(postseason_prizes({},[],7,2026),[['',''] for _ in range(15)])
  with self.assertRaisesRegex(ValueError,'stale'):
   postseason_prizes({'completedWeek':6,'season':2026},[],12,2026)
 def test_manual_preview_cannot_publish(self):
  workflow=(Path(__file__).resolve().parents[1]/'.github/workflows/refresh_extension_calculator.yml').read_text(encoding='utf-8')
  for name in ['Commit generated data','Publish updated reports on GitHub Pages','Dispatch independent calculator deployment']:
   block=workflow.split('- name: '+name,1)[1].split('- name:',1)[0]
   self.assertIn('inputs.authorize_official_writes == true',block)
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
