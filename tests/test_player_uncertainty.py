import json,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from player_uncertainty import distribution,quantile,moments_with_availability,team_noise
from bonus_nig import standardized_nig
class PlayerUncertaintyTests(unittest.TestCase):
 def setUp(self):self.model=json.loads((ROOT/'data/player_strength/player_uncertainty_2026.json').read_text())
 def test_mean_preserved_and_smooth(self):
  z,weights=np.polynomial.hermite.hermgauss(60);z*=np.sqrt(2);weights/=np.sqrt(np.pi)
  for mu in [0.,4.,12.,25.]:
   d=distribution(self.model,'DT',mu,5.,25.);raw=np.sinh((z-d['a'])/d['tail']);points=mu+d['scale']*(raw-d['raw_mean'])/d['raw_sd'];self.assertAlmostEqual(float(points@weights),mu,places=8);self.assertAlmostEqual(float(((points-mu)**2)@weights),float(d['scale']**2),places=7)
   a=quantile(distribution(self.model,'DT',mu+1e-5,5.,25.),.95);b=quantile(d,.95);self.assertLess(abs(float(a-b)),.001)
 def test_intervals_ordered_and_availability_moments(self):
  d=distribution(self.model,'WR',np.linspace(0,40,101),np.full(101,6.),36.);q=np.stack([quantile(d,x) for x in [.01,.05,.5,.95,.99]]);self.assertTrue(np.isfinite(q).all());self.assertTrue((np.diff(q,axis=0)>0).all());v,t=moments_with_availability(d,0.);np.testing.assert_allclose(v,0);np.testing.assert_allclose(t,0);v,t=moments_with_availability(d,1.);np.testing.assert_allclose(v,d['scale']**2)
 def test_sampler_backwards_compatible(self):
  a=standardized_nig(np.random.default_rng(3),[4.,.2],(100,2,3));b=standardized_nig(np.random.default_rng(3),dict(a=4.,ratio=np.full((2,3),.2)),(100,2,3));np.testing.assert_allclose(a,b,rtol=1e-13,atol=1e-13)
 def test_team_variance_curve_has_no_rank_cutoff(self):
  import pandas as pd
  rows=pd.DataFrame([dict(week=11,target_week=12,franchise_id=str(i),lineup_variance=v,lineup_third_moment=0.) for i,v in enumerate([100.,200.,400.])]);m,s=team_noise(self.model,rows,['0','1','2'],11);self.assertAlmostEqual(float(np.exp(np.log(m).mean())),1.,places=12);self.assertTrue((np.diff(m[0])>0).all());np.testing.assert_allclose(s,0.)
if __name__=='__main__':unittest.main()
