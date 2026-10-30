import json,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from simple_availability import predict
class SimpleAvailabilityTest(unittest.TestCase):
 def setUp(self):
  self.model=json.loads((ROOT/'data/player_strength/availability_recovery_2026.json').read_text())
  self.c=dict(ids=['x'],active_score=np.full((17,1),10.),points=np.full((17,1),10.),injury_status=np.full((17,1),'',dtype=object),inactive=np.zeros((17,1)),team=np.full((17,1),'AAA'),previous_ppg=np.array([10.]),mfl_return_date=np.full((17,1),'',dtype=object),availability_calendar={'season_end':'2027-01-11','games':{'7':{'AAA':'2026-10-25'}}})
  self.play=np.ones((17,1),bool)
 def test_ppg_cannot_reduce_appearance(self):
  before=predict(self.model,self.c,'WR',3,7,self.play);self.c['active_score'][:3]=20.;self.c['points'][:3]=20.
  self.assertGreaterEqual(predict(self.model,self.c,'WR',3,7,self.play)[0],before[0])
 def test_earlier_return_cannot_reduce_probability(self):
  self.c['mfl_return_date'][2]='2026-11-15';later=predict(self.model,self.c,'WR',3,7,self.play)[0]
  self.c['mfl_return_date'][2]='2026-10-11';self.assertGreaterEqual(predict(self.model,self.c,'WR',3,7,self.play)[0],later)
 def test_next_season_probability_is_small_but_not_zero(self):
  self.c['mfl_return_date'][2]='2027-02-10';beyond=predict(self.model,self.c,'WR',3,7,self.play)[0]
  self.c['mfl_return_date'][2]='2026-12-27';within=predict(self.model,self.c,'WR',3,7,self.play)[0]
  self.assertGreater(beyond,0);self.assertLessEqual(beyond,within)
 def test_future_scores_status_and_dates_do_not_leak(self):
  before=predict(self.model,self.c,'WR',3,7,self.play);self.c['mfl_return_date'][3:]='2027-02-10';self.c['active_score'][3:]=999.;self.c['injury_status'][3:]='IR'
  np.testing.assert_array_equal(before,predict(self.model,self.c,'WR',3,7,self.play))
if __name__=='__main__':unittest.main()
