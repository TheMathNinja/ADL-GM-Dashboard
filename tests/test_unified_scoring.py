import unittest,json,sys
from unittest.mock import patch
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import bonus_predictor as e
from quarterly_bonus import forecast
import player_blend_scoring
class UnifiedTests(unittest.TestCase):
 def test_adjusted_actual_points_affect_relative_forecasts(self):
  ids=[f'{i:04}' for i in range(1,33)];s=np.full((12,32),200.);p=np.full((12,32),260.);a=np.full(32,200.)
  before=e.adl_parameters({2026:(ids,s,p)},2026,4,adjusted_ppg=a)
  a[0]+=50.;after=e.adl_parameters({2026:(ids,s,p)},2026,4,adjusted_ppg=a)
  c=after[4]['cases']['forecast'];gain=c['weights'][1]*c['cross']/(c['input_latent']+c['input_measurement']/4)
  np.testing.assert_allclose(after[0]-before[0],np.broadcast_to(gain*(a-a.mean()),before[0].shape))
  self.assertEqual(c['weights'][1],0.);np.testing.assert_array_equal(after[0],before[0]);self.assertAlmostEqual(after[0].mean(),before[0].mean())
  for i in [1,2,3]:np.testing.assert_array_equal(before[i],after[i])
 def test_adjusted_actual_input_excludes_future_weeks(self):
  ids=[f'{i:04}' for i in range(1,33)];rows=[dict(season=2026,week=w,franchise_id=fid,adjusted_pf=200+i) for w in range(1,5) for i,fid in enumerate(ids)];rows += [dict(season=2026,week=5,franchise_id=fid,adjusted_pf=999999.) for fid in ids]
  with patch.object(player_blend_scoring.pd,'read_csv',return_value=pd.DataFrame(rows)):
   np.testing.assert_allclose(player_blend_scoring.adjusted_actual_ppg(ROOT,2026,4,ids),np.arange(32)+200)
 def test_pre_recalibration_benchmark_is_immutable(self):
  import hashlib
  folder=ROOT/'data/model_benchmarks/pre-full-recalibration-2026-10-28';manifest=json.loads((folder/'manifest.json').read_text())
  self.assertEqual(manifest['weights'],[.35,0,.55,.1]);self.assertEqual(manifest['source_commit'],'1698d78e231109cf207e87c6b8fd709282a88464')
  for path,digest in manifest['files'].items():self.assertEqual(hashlib.sha256((folder/path).read_bytes()).hexdigest(),digest)
 def test_exact_selected_research_mean_and_posterior(self):
  f=pd.read_csv(ROOT/'tests/fixtures/h2h_eb_expected_means.csv');model=json.loads((ROOT/'data/adl_scoring_model.json').read_text())['2026']
  for w,q in f.groupby('week'):
   ids=[f'{i:04}' for i in range(1,33)];s=np.tile(q.observed_ppg.to_numpy(),(int(w),1));p=np.tile(q.adjusted_potential.to_numpy(),(int(w),1));data={2026:(ids,s,p)}
   original=pd.read_csv
   def read_csv(path,*args,**kwargs):
    if str(path).endswith('team_strength_2026.csv'):
     result=original(ROOT/'tests/fixtures/player_team_strength_expected.csv',*args,**kwargs);result['lineup_variance']=1.;result['lineup_third_moment']=0.;return result
    return original(path,*args,**kwargs)
   with patch.object(player_blend_scoring.pd,'read_csv',side_effect=read_csv):
    mu,sd,tau,gap,m=e.adl_parameters(data,2026,int(w),adjusted_ppg=q.adjusted_ppg.to_numpy())
   np.testing.assert_allclose(mu.mean(0),q.expected_mu,atol=1e-9)
   d=model['input_latent']+model['input_measurement']/w;level=s.mean()
   self.assertAlmostEqual(sd,level*np.sqrt(model['actual_weekly'])*model['forecast_noise']['weekly_sd_multiplier'])
   t=model.get('persistent_uncertainty');expected_tau=level*(t['coef'][0]+t['coef'][1]*(11-w)/10) if t else level*np.sqrt(model['actual_latent']-model['cross']**2/d)
   self.assertAlmostEqual(tau,expected_tau)
   self.assertEqual(m['weekly_shape']['a'],model['forecast_noise']['alpha']);np.testing.assert_allclose(m['weekly_shape']['ratio'],model['forecast_noise']['rho']);np.testing.assert_allclose(m['weekly_shape']['sd_multiplier'],1.);self.assertLess(max(m['training_years']+m['innovation_training_years']),2026)
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
