import sys,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import numpy as np
from player_availability import remaining_exposure,weekly_metadata
from collect_live_bonus import player_projection,injury_code
from live_continuous_nig import remaining_moments,projected_points
from live_win_probability import simulate
from fs_pregame_calibration import load_calibration
MODELS=json.loads((ROOT/'data/live_win_probability.json').read_text());LG=next(k for k,v in MODELS.items() if v.get('shape')=='ContinuousNIG');MODEL=MODELS[LG]
class AvailabilityTests(unittest.TestCase):
 def test_every_absence_blocks_sharks_and_fallback_and_simulated_upside(self):
  for status in ['H','S','O','I','IR','IR-R','HOLDOUT','INACTIVE','OUT','SUSPENDED']:
   for fs in [{},{'p':14.}]:
    with self.subTest(status=status,fs=fs):
     row=player_projection(dict(id='p',score=3.5,gameSecondsRemaining=3600),{'p':dict(position='WR',team='CHI',injuryStatus=status)},fs,{'CHI':dict(state='pre')},{'p':12.},load_calibration(LG))
     self.assertEqual(row['pregameProjection'],0);self.assertEqual(row['calibratedPregameProjection'],0);self.assertEqual(row['liveProjection'],3.5)
     self.assertEqual(remaining_moments(row,MODEL)[:2],(0.,0.));self.assertEqual(projected_points(row,MODEL),3.5)
     for model in [MODEL,{'shape':'Normal','referenceLevel':10.,'paceVariance':0.,'advantageVariance':0.,'positions':{},'fallback':{}}]:
      np.testing.assert_array_equal(simulate([dict(id='T',score=3.5,starters=[row])],model,64)['T'],np.full(64,3.5))
 def test_bye_overrides_stale_sixty_minute_clock(self):
  row=player_projection(dict(id='p',gameSecondsRemaining=3600),{'p':dict(position='WR',team='CHI')},{},{'GBP':dict(state='pre')},{'p':12.})
  self.assertEqual(row['gameStatus'],'Bye');self.assertEqual(row['liveProjection'],0);self.assertEqual(row['pregameProjection'],0)
 def test_questionable_and_missing_sharks_are_not_automatic_absences(self):
  for status in ['Q','D','']:
   row=player_projection(dict(id='p',gameSecondsRemaining=3600),{'p':dict(position='WR',team='CHI',injuryStatus=status)},{},{'CHI':dict(state='pre')},{'p':12.})
   self.assertGreater(row['liveProjection'],0);self.assertEqual(row['projectionSource'],'YTD PPG')
 def test_weekly_status_does_not_carry_forward(self):
  class Source:
   def get(self,kind,extra,ttl):return {'week':8,'injury':[{'id':'p','status':'I'}]} if extra=='&W=8' else {'week':9,'injury':[]}
  original={'p':{'injuryStatus':'O'}};week8=weekly_metadata(Source(),original,8);week9=weekly_metadata(Source(),week8,9)
  self.assertEqual(week8['p']['injuryStatus'],'I');self.assertEqual(week9['p']['injuryStatus'],'');self.assertEqual(original['p']['injuryStatus'],'O')
 def test_overtime_stays_random_when_available(self):
  self.assertGreater(remaining_exposure(dict(gameStatus='Awaiting OT',seconds=0,projectionSeconds=600)),0)
 def test_player_ability_inputs_and_forward_means_respect_absence(self):
  from player_positive_core import known_absence,expected_player_points
  labels=np.array([['H','I','O','S','Q','']]);cube=dict(injury_status=labels,active_score=np.zeros((1,6)))
  np.testing.assert_array_equal(known_absence(cube),[[True,True,True,True,False,False]])
  np.testing.assert_array_equal(expected_player_points(np.full(6,20.),1.,1.,[1,1,1,1,1,0],known_absence(cube)[0]),[0,0,0,0,20,0])
 def test_H_preserved(self):self.assertEqual(injury_code('H'),'H')
if __name__=='__main__':unittest.main()
