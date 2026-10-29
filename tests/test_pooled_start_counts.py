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
class HunterTests(unittest.TestCase):
 def test_personal_fs_override_is_independent_of_roster_status_and_starts(self):
  cal=dict(CAL,playerFSOverrides={'17074':dict(intercept=8.,slope=.1)})
  for starter in [True,False]:
   self.assertAlmostEqual(calibrated_projection(2,'WR','Fantasy Sharks',cal,submitted_starter=starter,player_id='17074'),8.2)
  self.assertEqual(calibrated_projection(2,'WR','Fantasy Sharks',cal,player_id='other'),2)
  self.assertEqual(calibrated_projection(2,'WR','YTD PPG',cal,player_id='17074'),2)
  self.assertIsNone(calibrated_projection(None,'WR','Fantasy Sharks',cal,player_id='17074'))
 def test_personal_override_used_by_collector_and_unavailable_stays_zero(self):
  cal=dict(CAL,playerFSOverrides={'17074':dict(intercept=8.,slope=0.)})
  for status in ['', 'I','O','H','S']:
   r=player_projection(dict(id='17074',status='starter',score=0,gameSecondsRemaining=3600),{'17074':dict(position='WR',team='JAX',injuryStatus=status)},{'17074':1.1},calibration=cal)
   self.assertEqual(r['calibratedPregameProjection'],0 if status else 8.)

class UnifiedYTDTests(unittest.TestCase):
 def test_ytd_includes_both_leagues_and_ignores_own_starter_status(self):
  spec=dict(intercept=1.,slope=.5,adlIncrements=[1.,2.],faflIncrements=[3.,4.])
  cal=dict(unifiedYTDPositions={'WR':spec},unifiedYTDGeneralPositions={'WR':spec})
  for feed in [True,False]:
   for starter in [True,False]:
    self.assertEqual(calibrated_projection(10,'WR','YTD PPG',cal,feed,starter,{'ADL':2,'FAFL':1}),12.)
  with self.assertRaises(ValueError):calibrated_projection(10,'WR','YTD PPG',cal)
 def test_hunter_fs_and_ytd_both_keep_start_effects(self):
  spec=dict(intercept=2.,slope=1.,adlIncrements=[1.,2.],faflIncrements=[3.,4.])
  cal=dict(playerFSOverrides={'17074':spec},playerYTDOverrides={'17074':spec})
  for source in ['Fantasy Sharks','YTD PPG']:
   self.assertEqual(calibrated_projection(5,'WR',source,cal,start_counts={'ADL':1,'FAFL':1},player_id='17074'),11.)
   self.assertEqual(calibrated_projection(5,'WR',source,cal,start_counts={'ADL':0,'FAFL':0},player_id='17074'),7.)
 def test_collector_ytd_override_and_unavailable(self):
  spec=dict(intercept=2.,slope=1.,adlIncrements=[1.,2.],faflIncrements=[3.,4.])
  cal=dict(id='test',playerYTDOverrides={'17074':spec},_startCounts={'17074':{'ADL':1,'FAFL':1}})
  for status in ['', 'O']:
   r=player_projection(dict(id='17074',status='starter',score=0,gameSecondsRemaining=3600),{'17074':dict(position='WR',team='JAX',injuryStatus=status)},{},ytd_ppg={'17074':5},calibration=cal)
   self.assertEqual(r['calibratedPregameProjection'],0 if status else 11.)

if __name__=='__main__':unittest.main()
