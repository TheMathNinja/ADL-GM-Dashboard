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
 def test_ytd_without_source_fit_and_missing_remain_unchanged(self):
  p=self.make({},dict(p=10));self.assertEqual(p['projectionSource'],'YTD PPG');self.assertEqual(p['calibratedPregameProjection'],10)
  self.assertEqual(p['liveProjection'],12);self.assertIsNone(p['pregameCalibrationId'])
  p=self.make({});self.assertIsNone(p['calibratedPregameProjection']);self.assertEqual(p['liveProjection'],7)
 def test_final_has_no_remaining_projection_but_pending_ot_does(self):
  p=self.make({'p':10},seconds=0,games={'CHI':dict(period=4,state='post',clock=0,completed=True,scores=[20,17])})
  self.assertEqual(p['liveProjection'],7)
  p=self.make({'p':10},seconds=0,games={'CHI':dict(period=4,state='in',clock=0,completed=False,scores=[20,20])})
  self.assertAlmostEqual(p['liveProjection'],7+14/6,places=5)
 def test_separate_ytd_and_missing_feed_lines(self):
  cal=dict(CAL,ytdPositions={'LB':dict(intercept=1,slope=.5)},ytdGeneralPositions={'LB':dict(intercept=3,slope=.8)},ytdRosteredPositions={'LB':dict(intercept=.5,slope=.2)})
  self.assertEqual(calibrated_projection(10,'LB','YTD PPG',cal),6)
  self.assertEqual(calibrated_projection(10,'LB','YTD PPG',cal,False),11)
  self.assertEqual(calibrated_projection(10,'LB','YTD PPG',cal,True,False),2.5)
  p=player_projection(dict(id='p',score=7,gameSecondsRemaining=1800),{'p':dict(position='LB',team='CHI')},{},None,{'p':10},cal)
  self.assertEqual(p['pregameProjection'],10);self.assertEqual(p['calibratedPregameProjection'],6);self.assertEqual(p['liveProjection'],10)
  self.assertEqual(p['projectionSource'],'YTD PPG');self.assertEqual(p['pregameCalibrationId'],'fixture')
 def test_fs_starter_and_bench_use_different_calibrations(self):
  cal=dict(CAL,fsBenchPositions={'LB':dict(intercept=1,slope=.4)})
  self.assertEqual(calibrated_projection(10,'LB','Fantasy Sharks',cal,True,True),14)
  self.assertEqual(calibrated_projection(10,'LB','Fantasy Sharks',cal,True,False),5)
  p=player_projection(dict(id='p',status='nonstarter',score=7,gameSecondsRemaining=1800),{'p':dict(position='LB',team='CHI')},{'p':10},None,None,cal)
  self.assertEqual(p['pregameProjection'],10);self.assertEqual(p['calibratedPregameProjection'],5);self.assertEqual(p['liveProjection'],9.5)
  self.assertEqual(p['pregameCalibrationId'],'fixture')
 def test_zero_fs_value_is_distinct_from_missing(self):
  self.assertEqual(calibrated_projection(0,'LB','Fantasy Sharks',CAL),2)
  self.assertIsNone(calibrated_projection(None,'LB','Fantasy Sharks',CAL))
 def test_reciprocal_odds_use_calibrated_points(self):
  p=self.make({'p':10});s=dict(teams=[dict(id='A',score=7,starters=[p],opponentIds=['B']),dict(id='B',score=13,starters=[],opponentIds=['A'])])
  add_probabilities(s,MODEL,1000)
  self.assertEqual(s['teams'][0]['liveMatchups']['B']['win'],1)
  self.assertEqual(s['teams'][1]['liveMatchups']['A']['loss'],1)
 def test_real_configuration_has_nonnegative_matched_parameters(self):
  models=json.loads((Path(__file__).resolve().parents[1]/'data/live_win_probability.json').read_text())
  league=next(key for key,value in models.items() if value.get('shape')=='ContinuousNIG')
  m=models[league]
  loaded=dict(load_calibration(league));loaded.pop('conditionalLiveModel',None)
  self.assertEqual(m['pregameCalibration'],loaded);self.assertEqual(m['shape'],'ContinuousNIG')
  self.assertEqual(m['trainingYears'],list(range(2021,2026)))
  for p in m['pregameCalibration']['positions'].values():self.assertGreaterEqual(p['slope'],0);self.assertGreaterEqual(p['intercept'],0)
  self.assertLessEqual(m['paceVariance']+m['advantageVariance'],.6)
if __name__=='__main__':unittest.main()
