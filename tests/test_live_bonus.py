import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import datetime as dt,unittest
from collect_live_bonus import window,near_window,legal_potential,franchises,player_projection
class LiveBonusTests(unittest.TestCase):
 def test_starter_live_projection(self):
  def project(seconds,projection=20):
   return player_projection(dict(id='1',score='7',gameSecondsRemaining=str(seconds)),{'1':dict(name='Player',position='LB')},{'1':projection})
  self.assertEqual(project(3600)['liveProjection'],27)
  self.assertEqual(project(1800)['liveProjection'],17)
  self.assertEqual(project(0)['liveProjection'],7)
  self.assertEqual(project(900)['liveProjection'],12)
  self.assertEqual(project(1800,None)['liveProjection'],7)
  self.assertIsNone(project(1800,None)['pregameProjection'])
  self.assertEqual(project(1800,-2)['liveProjection'],6)
 def test_eastern_windows_and_dst(self):
  for date,expected in [('2026-10-18T16:59:00+00:00',False),('2026-10-18T17:00:00+00:00',True),('2026-10-19T03:45:00+00:00',True),('2026-10-19T03:46:00+00:00',False),('2026-10-20T00:00:00+00:00',True),('2026-10-20T03:46:00+00:00',False),('2026-11-01T17:59:00+00:00',False),('2026-11-01T18:00:00+00:00',True),('2026-11-03T01:00:00+00:00',True)]:
   self.assertEqual(window(dt.datetime.fromisoformat(date)),expected,date)
  self.assertTrue(near_window(dt.datetime.fromisoformat('2026-10-18T16:50:00+00:00')))
 def test_legal_potential_and_partial_lineup(self):
  r=dict(count='2',iop_starters='2',idp_starters='0',position=[dict(name='QB',limit='1'),dict(name='RB',limit='1')])
  self.assertEqual(legal_potential([('QB',-2),('QB',12),('RB',5)],r),17)
  self.assertEqual(legal_potential([('QB',-2)],r),-2)
 def test_incomplete_feed_rejected(self):
  with self.assertRaises(ValueError):franchises({'franchise':[dict(id='0001',score='0')]})
  rows=[dict(id=f'{i:04}',score='1') for i in range(1,33)]
  self.assertEqual(len(franchises({'matchup':[{'franchise':rows}]})),32)
if __name__=='__main__':unittest.main()
