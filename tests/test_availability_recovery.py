import json,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from availability_recovery import predict,design
from player_positive_core import expected_player_points
class AvailabilityRecoveryTest(unittest.TestCase):
 def setUp(self):
  self.model=json.loads((ROOT/'data/player_strength/availability_recovery_2026.json').read_text())
  self.c=dict(ids=['x'],active_score=np.full((17,1),np.nan),points=np.zeros((17,1)),injury_status=np.full((17,1),'',dtype='U20'),inactive=np.zeros((17,1)))
  self.scheduled=np.ones((17,1),bool)
 def test_recovered_player_not_punished_like_ongoing_ir(self):
  self.c['injury_status'][:3]='IR';self.c['inactive'][:3]=1
  ir=predict(self.model,self.c,'DT',3,4,self.scheduled)[0]
  self.c['active_score'][3]=12;self.c['points'][3]=12
  recovered=predict(self.model,self.c,'DT',4,5,self.scheduled)[0]
  self.assertGreater(recovered,.7);self.assertGreater(recovered,ir+.3)
 def test_future_data_cannot_change_forecast(self):
  self.c['active_score'][:3]=10;before=predict(self.model,self.c,'WR',3,7,self.scheduled)
  self.c['active_score'][3:]=99;self.c['injury_status'][3:]='IR';self.c['inactive'][3:]=1
  np.testing.assert_allclose(before,predict(self.model,self.c,'WR',3,7,self.scheduled))
 def test_bye_does_not_become_injury_and_hard_absence_still_zero(self):
  self.c['active_score'][0]=10;self.c['inactive'][1]=1;self.scheduled[1]=False
  x=design(self.c,2,3,self.scheduled);self.assertEqual(x[0,1:6].sum(),0)
  np.testing.assert_allclose(expected_player_points([10],[1],[.95],[True],[True]),[0])
 def test_future_report_conflict_does_not_erase_observed_active_score(self):
  self.c['injury_status'][:3]='OUT';self.c['active_score'][:3]=10;self.c['points'][:3]=10
  self.assertEqual(design(self.c,3,4,self.scheduled)[0,1:6].sum(),0)
if __name__=='__main__':unittest.main()
