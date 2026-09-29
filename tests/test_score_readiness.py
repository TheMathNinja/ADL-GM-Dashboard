import copy, importlib.util, unittest
from datetime import datetime, timezone
from pathlib import Path
spec=importlib.util.spec_from_file_location('readiness',Path(__file__).parents[1]/'scripts/score_readiness.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ReadinessTest(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,9,29,6,tzinfo=timezone.utc)
  self.s={'franchise':[dict(id=f'{i:04}',h2hw=2 if i<=16 else 1,h2hl=1 if i<=16 else 2,h2ht=0,all_play_wlt='47-46-0' if i<=16 else '46-47-0') for i in range(1,33)]}
  self.r={'week':'3','franchise':[dict(id=f'{i:04}',score='20',opt_pts='25',starters=str(i),player=[dict(id=str(i),status='starter',score='20')]) for i in range(1,33)]}
  self.p={'week':'3','playerScore':[dict(id=str(i),score='20') for i in range(1,33)]}
  self.n={'week':'3','matchup':[dict(kickoff='1',gameSecondsRemaining='0')]}
 def valid(self):return m.validate(self.s,self.r,self.p,self.n,3,self.now)[0]
 def test_complete(self):self.assertTrue(self.valid())
 def test_stale_records(self):self.s['franchise'][0]['h2hw']=1;self.assertFalse(self.valid())
 def test_unbalanced_records(self):self.s['franchise'][0].update(h2hw=3,h2hl=0);self.assertFalse(self.valid())
 def test_stale_allplay(self):self.s['franchise'][0]['all_play_wlt']='31-31-0';self.assertFalse(self.valid())
 def test_missing_team(self):self.r['franchise'].pop();self.assertFalse(self.valid())
 def test_live_game(self):self.n['matchup'][0]['gameSecondsRemaining']='1';self.assertFalse(self.valid())
 def test_future_kickoff(self):self.n['matchup'][0]['kickoff']='9999999999';self.assertFalse(self.valid())
 def test_wrong_week(self):self.r['week']='2';self.assertFalse(self.valid())
 def test_missing_potential(self):del self.r['franchise'][0]['opt_pts'];self.assertFalse(self.valid())
 def test_missing_starters(self):self.r['franchise'][0]['player']=[];self.assertFalse(self.valid())
 def test_player_scores_lag(self):self.p['playerScore'][0]['score']='10';self.assertFalse(self.valid())
 def test_inactive_starter(self):del self.r['franchise'][0]['player'][0]['score'];self.p['playerScore'].pop(0);self.assertTrue(self.valid())
 def test_ties(self):
  for f in self.s['franchise']:f.update(h2hw=1,h2hl=1,h2ht=1)
  self.assertTrue(self.valid())
 def test_postseason_uses_allplay_not_regular_record(self):
  for f in self.s['franchise']:f.update(h2hw=6,h2hl=6,h2ht=0,all_play_wlt='201-201-1')
  for obj in [self.r,self.p,self.n]:obj['week']='13'
  self.assertTrue(m.validate(self.s,self.r,self.p,self.n,13,self.now)[0])
 def test_window(self):
  for when,w in [('2026-09-15T03:29:00+00:00',None),('2026-09-15T03:30:00+00:00',1),('2026-09-15T04:00:00+00:00',1),('2026-09-16T03:59:00+00:00',1),('2026-09-16T04:00:00+00:00',None),('2026-11-10T04:30:00+00:00',9),('2026-11-10T05:00:00+00:00',9),('2026-09-08T04:00:00+00:00',None),('2027-01-05T05:00:00+00:00',17),('2027-01-12T05:00:00+00:00',None)]:
   self.assertEqual(m.target_week(datetime.fromisoformat(when),2026),w,when)
 def test_duplicate_and_retry(self):
  for status,conclusion in [('queued',None),('in_progress',None),('completed','success')]:
   self.assertIsNotNone(m.duplicate([dict(display_title='key',status=status,conclusion=conclusion)],'key'))
  failed=dict(display_title='key',status='completed',conclusion='failure')
  self.assertIsNone(m.duplicate([failed],'key'))
  with self.assertRaises(RuntimeError):m.duplicate([failed]*3,'key')
if __name__=='__main__':unittest.main()
