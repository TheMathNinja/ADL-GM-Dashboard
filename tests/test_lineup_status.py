import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from lineup_status import player_value,scheduled_teams
from status_credits import best_lineup,player_credit

class StatusTests(unittest.TestCase):
 def test_empty_future_schedule_week(self):
  schedule={'fullNflSchedule':{'nflSchedule':[{'week':'1','matchup':{'team':[{'id':'SEA'},{'id':'SF'}]}},{'week':'19'}]}}
  self.assertEqual(scheduled_teams(schedule),{1:{'SEA','SF'}})
 def test_taper_and_missing(self):
  self.assertEqual(player_value(10,[20,20],2),15)
  self.assertEqual(player_value(None,[],2),0)
  self.assertEqual(player_value(10,[],2),10)
  self.assertEqual(player_value(None,[20],2),20)
 def test_only_explicit_eligible_zero_scores(self):
  p=dict(id='1',pos='RB',points=0,estimated_ppg=20,nfl_status='O')
  self.assertEqual(player_credit(p,{'O':.5}),10)
  self.assertEqual(player_credit(dict(p,nfl_status='IR'),{'O':.5}),0)
  self.assertEqual(player_credit(dict(p,points=1),{'O':.5}),0)
 def test_bench_value_is_not_all_added(self):
  ps=[dict(id='1',pos='RB',points=15,estimated_ppg=15,nfl_status=''),
      dict(id='2',pos='RB',points=0,estimated_ppg=20,nfl_status='O')]
  limits={'RB':(1,1,'off')};totals={'off':1}
  self.assertEqual(best_lineup(ps,limits,totals,True,{'O':.5}),15)
  self.assertEqual(best_lineup(ps,limits,totals,True,{'O':1}),20)
 def test_negative_required_score_stays(self):
  ps=[dict(id='1',pos='QB',points=-3)]
  self.assertEqual(best_lineup(ps,{'QB':(1,1,'off')},{'off':1}),-3)

if __name__=='__main__':unittest.main()
