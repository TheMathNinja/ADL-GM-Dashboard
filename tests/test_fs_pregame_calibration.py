import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from collect_live_bonus import player_projection
from fs_pregame_calibration import calibrated_projection,load_calibration
from live_win_probability import simulate,add_probabilities

CAL=dict(id='fixture',positions={'LB':dict(intercept=2,slope=1.2)})
MODEL=dict(id='fixture',shape='Normal',paceVariance=0.,advantageVariance=0.,referenceLevel=10,trainingYears=[2021],positions={},fallback=dict(floorVariance=0.,projectionVariance=0.))
class CalibrationTests(unittest.TestCase):
 def make(self,projections,ytd=None,seconds=1800,games=None):
  return player_projection(dict(id='p',score=7,gameSecondsRemaining=seconds),{'p':dict(position='LB',team='CHI')},projections,games,ytd,CAL)
 def test_raw_is_preserved_but_live_and_simulation_use_calibration(self):
  p=self.make({'p':10})
  self.assertEqual(p['pregameProjection'],10);self.assertEqual(p['calibratedPregameProjection'],14)
  self.assertEqual(p['liveProjection'],14)
  t=dict(id='A',score=7,starters=[p],opponentIds=['B'])
  self.assertTrue(np.all(simulate([t],MODEL,1000)['A']==p['liveProjection']))
 def test_ytd_is_not_transformed_and_missing_remains_missing(self):
  p=self.make({},dict(p=10));self.assertEqual(p['projectionSource'],'YTD PPG');self.assertEqual(p['calibratedPregameProjection'],10)
  self.assertEqual(p['liveProjection'],12);self.assertIsNone(p['pregameCalibrationId'])
  p=self.make({});self.assertIsNone(p['calibratedPregameProjection']);self.assertEqual(p['liveProjection'],7)
 def test_final_has_no_remaining_projection_but_pending_ot_does(self):
  p=self.make({'p':10},seconds=0,games={'CHI':dict(period=4,state='post',clock=0,completed=True,scores=[20,17])})
  self.assertEqual(p['liveProjection'],7)
  p=self.make({'p':10},seconds=0,games={'CHI':dict(period=4,state='in',clock=0,completed=False,scores=[20,20])})
  self.assertAlmostEqual(p['liveProjection'],7+14/6,places=5)
 def test_zero_fs_value_is_distinct_from_missing(self):
  self.assertEqual(calibrated_projection(0,'LB','Fantasy Sharks',CAL),2)
  self.assertIsNone(calibrated_projection(None,'LB','Fantasy Sharks',CAL))
 def test_reciprocal_odds_use_calibrated_points(self):
  p=self.make({'p':10});s=dict(teams=[dict(id='A',score=7,starters=[p],opponentIds=['B']),dict(id='B',score=13,starters=[],opponentIds=['A'])])
  add_probabilities(s,MODEL,1000)
  self.assertEqual(s['teams'][0]['liveMatchups']['B']['win'],1)
  self.assertEqual(s['teams'][1]['liveMatchups']['A']['loss'],1)
 def test_real_configuration_has_nonnegative_matched_parameters(self):
  league=Path(__file__).resolve().parents[1].name
  m=json.loads((Path(__file__).resolve().parents[1]/'data/live_win_probability.json').read_text())[league]
  self.assertEqual(m['pregameCalibration'],load_calibration(league));self.assertEqual(m['shape'],'Normal')
  self.assertEqual(m['trainingYears'],list(range(2021,2027)))
  for p in m['pregameCalibration']['positions'].values():self.assertGreaterEqual(p['slope'],0);self.assertGreaterEqual(p['intercept'],0)
  self.assertLessEqual(m['paceVariance']+m['advantageVariance'],.6)
if __name__=='__main__':unittest.main()
