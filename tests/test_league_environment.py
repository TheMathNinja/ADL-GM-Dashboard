import unittest,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from league_environment import apply_environment
class EnvironmentTests(unittest.TestCase):
 def setUp(self):
  self.pf=np.broadcast_to(np.linspace(100,300,32),(12000,3,32)).copy();self.pot=self.pf+60
  self.fit=dict(family='shared_linear',coef=[.04,.02,.03],training_years=[2021,2022,2023,2024,2025],mean_adjustment=False)
 def test_shared_factor_keeps_rankings_and_legal_pairs(self):
  pf,pot,m=apply_environment(self.pf,self.pot,2026,9,self.fit)
  self.assertTrue((pot>=pf).all());self.assertTrue((np.diff(pf,axis=2)>0).all())
  np.testing.assert_allclose(pot/pot[:,:,:1],self.pot/self.pot[:,:,:1],rtol=1e-12)
  self.assertLess(np.max(abs(np.array(m['factor_mean_by_week'])-1)),.002)
  np.testing.assert_array_equal(self.pf,np.broadcast_to(np.linspace(100,300,32),(12000,3,32)))
 def test_zero_factor_matches_existing_score_grid(self):
  self.fit['coef']=[0,0,0];pf=np.round(self.pf,1);p,pot,_=apply_environment(pf,self.pot,2026,9,self.fit)
  np.testing.assert_array_equal(p,pf);np.testing.assert_array_equal(pot,self.pot)
 def test_rejects_leakage_and_unapproved_mean_adjustments(self):
  self.fit['training_years']=[2026]
  with self.assertRaises(ValueError):apply_environment(self.pf,self.pot,2026,9,self.fit)
  self.fit['training_years']=[2025];self.fit['mean_adjustment']=True
  with self.assertRaises(ValueError):apply_environment(self.pf,self.pot,2026,9,self.fit)
 def test_real_quarterly_entry_point_uses_shared_world(self):
  import pandas as pd
  from quarterly_bonus import forecast
  import bonus_predictor as predictor
  q=pd.read_csv(ROOT/'data/weekly_team_metrics.csv',dtype={'franchise_id':str}).rename(columns={'franchise_score':'points','potential_points':'potential'})
  w=int(q.week.max());result=forecast(ROOT,q,'ADL',2026,w,200)
  self.assertEqual(result['model']['league_environment']['expected_factor'],1.)
  self.assertIn('all 32 teams',result['model']['league_environment']['scope'])
  raw=predictor.draw_future(result['mu'],result['sigma'],result['tau'],'ADL',2026,w,200,shape=result['model']['weekly_shape'])
  self.assertFalse(np.array_equal(raw,result['future']))
  np.testing.assert_array_equal(result['native_future'],result['future'])
  self.assertTrue((result['future_potential']>=result['future']).all())
  np.testing.assert_allclose(result['quarterly_credits'].sum(2),16)
  np.testing.assert_allclose(result['reg_season_credits'].sum(1),16)
if __name__=='__main__':unittest.main()
