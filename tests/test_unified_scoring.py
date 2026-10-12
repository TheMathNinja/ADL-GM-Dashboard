import unittest,json,sys
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import bonus_predictor as e
from quarterly_bonus import forecast
class UnifiedTests(unittest.TestCase):
 def test_exact_selected_research_mean_and_posterior(self):
  f=pd.read_csv(ROOT/'tests/fixtures/h2h_eb_expected_means.csv');model=json.loads((ROOT/'data/adl_scoring_model.json').read_text())['2026']
  for w,q in f.groupby('week'):
   ids=[f'{i:04}' for i in range(1,33)];s=np.tile(q.observed_ppg.to_numpy(),(int(w),1));p=np.tile(q.adjusted_potential.to_numpy(),(int(w),1));data={2026:(ids,s,p)}
   mu,sd,tau,gap,m=e.adl_parameters(data,2026,int(w))
   np.testing.assert_allclose(mu,q.expected_mu,atol=1e-9)
   d=model['input_latent']+model['input_measurement']/w;level=s.mean()
   self.assertAlmostEqual(sd,level*np.sqrt(model['actual_weekly']))
   self.assertAlmostEqual(tau,level*np.sqrt(model['actual_latent']-model['cross']**2/d))
   self.assertEqual(m['weekly_shape'],model['shape']);self.assertLess(max(m['training_years']+m['innovation_training_years']),2026)
 def test_one_joint_score_world_in_real_forecast(self):
  current=pd.read_csv(ROOT/'data/weekly_team_metrics.csv',dtype={'franchise_id':str}).rename(columns={'franchise_score':'points','potential_points':'potential'})
  w=int(current.week.max());ids=sorted(current.franchise_id.unique())
  a=forecast(ROOT,current,'ADL',2026,w,200,dict(ids=ids,mu=[999.]*32,sigma=99,tau=99))
  np.testing.assert_array_equal(a['native_future'],a['future']);self.assertTrue((a['future_potential']>=a['future']).all())
  for i,(_,start,end) in enumerate(e.EVENTS[:4]):
   credit=e.segment_samples(a['s'],a['p'],w,a['native_future'],a['gap'],'ADL',start,end,a['future_potential'])[1]/2
   np.testing.assert_array_equal(credit,a['quarterly_credits'][:,i])
  np.testing.assert_array_equal(e.segment_samples(a['s'],a['p'],w,a['native_future'],a['gap'],'ADL',0,12,a['future_potential'])[1]/2,a['reg_season_credits'])
  altered=current.copy();extra=current[current.week==w].copy();extra.week=w+1;extra.points=999999;extra.potential=999999;altered=pd.concat([altered,extra])
  b=forecast(ROOT,altered,'ADL',2026,w,200)
  np.testing.assert_array_equal(a['future'],b['future']);np.testing.assert_array_equal(a['future_potential'],b['future_potential'])
if __name__=='__main__':unittest.main()
