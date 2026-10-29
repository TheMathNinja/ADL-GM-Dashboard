import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pooled_start_counts import start_counts,with_start_counts
from fs_pregame_calibration import calibrated_projection
from collect_live_bonus import player_projection

CAL=dict(id='unified-fixture',unifiedFSPositions={'QB':dict(intercept=1.,slope=.5,adlIncrements=[2.,1.],faflIncrements=[.5,.25])})
def feed(week=8):
 return dict(week=str(week),matchup=[dict(franchise=[dict(id=f'{i:04}',players=dict(player=[dict(id='p',status='starter')]*2 if i in [1,2] else [])) for i in range(1,33)])])
class UnifiedTests(unittest.TestCase):
 def test_count_actual_franchise_appearances_not_duplicate_rows(self):
  self.assertEqual(start_counts(feed(),8),{'p':2})
  with self.assertRaises(ValueError):start_counts(feed(7),8)
  q=feed();q['matchup'][0]['franchise'].pop()
  with self.assertRaises(ValueError):start_counts(q,8)
 def test_same_projection_on_all_rosters_and_monotone_effects(self):
  last=-1
  for a in range(3):
   v=calibrated_projection(20,'QB','Fantasy Sharks',CAL,start_counts={'ADL':a,'FAFL':1})
   self.assertGreaterEqual(v,last);last=v
   self.assertEqual(v,calibrated_projection(20,'QB','Fantasy Sharks',CAL,submitted_starter=False,start_counts={'ADL':a,'FAFL':1}))
  self.assertNotEqual(calibrated_projection(20,'QB','Fantasy Sharks',CAL,start_counts={'ADL':2,'FAFL':0}),calibrated_projection(20,'QB','Fantasy Sharks',CAL,start_counts={'ADL':0,'FAFL':2}))
  with self.assertRaises(ValueError):calibrated_projection(20,'QB','Fantasy Sharks',CAL)
 def test_collector_preserves_counts_and_source(self):
  cal=dict(CAL,_startCounts={'p':{'ADL':2,'FAFL':1}})
  rows=[player_projection(dict(id='p',status=status,score=0,gameSecondsRemaining=3600),{'p':dict(position='QB',team='CHI')},{'p':20},calibration=cal) for status in ['starter','nonstarter']]
  for r in rows:self.assertEqual(r['calibratedPregameProjection'],14.5);self.assertEqual(r['pooledStarts'],{'ADL':2,'FAFL':1});self.assertEqual(r['pregameCalibrationId'],CAL['id'])
 def test_unavailable_remains_zero(self):
  cal=dict(CAL,_startCounts={'p':{'ADL':2,'FAFL':2}})
  for status in ['H','S','O','I']:
   p=player_projection(dict(id='p',status='starter',score=0,gameSecondsRemaining=3600),{'p':dict(position='QB',team='CHI',injuryStatus=status)},{'p':20},calibration=cal)
   self.assertEqual(p['liveProjection'],0)
if __name__=='__main__':unittest.main()
