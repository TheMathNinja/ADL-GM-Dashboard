import unittest,sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import bonus_predictor as e
class BonusPredictorTests(unittest.TestCase):
 def test_midpoint_cutoffs_and_completed_outcomes(self):
  s=np.tile(np.arange(32,dtype=float),(12,1));p=s+10;r=e.event_forecasts(s,p,12,np.zeros((2,0,32)),np.zeros(32),'ADL')
  self.assertEqual(r['Q1']['win_cutoff'],49.5);self.assertEqual(r['Q1']['tie_cutoff'],43.5);self.assertEqual(r['All-Season']['win_cutoff'],198)
  np.testing.assert_allclose(r['Q1']['probabilities'].sum(0),[15,2,15]);self.assertEqual(r['Q1']['probabilities'][31,2],1)
 def test_unstarted_quarters_and_no_future_truth(self):
  rng=np.random.default_rng(19);s=rng.normal(150,30,(12,32));p=s+10;future=e.draw_future(np.full(32,150.),30,8,'FAFL',2026,4,2000);a=e.event_forecasts(s,p,4,future,np.ones(32)*10,'FAFL');s[4:]=np.nan;p[4:]=np.nan;b=e.event_forecasts(s,p,4,future,np.ones(32)*10,'FAFL')
  for label in a:np.testing.assert_array_equal(a[label]['probabilities'],b[label]['probabilities'])
  np.testing.assert_array_equal(a['Q3']['probabilities'],a['Q4']['probabilities']);self.assertEqual(a['Q3']['win_cutoff'],a['Q4']['win_cutoff'])
 def test_t5_same_center_and_variance(self):
  mu=np.full(32,10000.);a=e.draw_future(mu,30,0,'FAFL',2026,9,20000)-mu;b=e.draw_future(mu,30,0,'ADL',2026,9,20000)-mu
  self.assertAlmostEqual(a.mean(),0,places=10);self.assertAlmostEqual(b.mean(),0,places=10);self.assertLess(abs(a.var()/900-1),.03);self.assertGreater(np.mean(abs(a)>120),np.mean(abs(b)>120))
 def test_persistent_strength_is_shared(self):
  a=e.draw_future(np.full(32,10000.),0,10,'ADL',2026,9,2000);np.testing.assert_array_equal(a[:,0],a[:,1]);np.testing.assert_array_equal(a[:,1],a[:,2])
 def test_current_future_not_used_in_adl_mean(self):
  rng=np.random.default_rng(49);data={y:(list(range(32)),rng.normal(150,30,(12,32)),rng.normal(180,30,(12,32))) for y in range(2018,2027)};a=e.adl_parameters(data,2026,4);data[2026][1][4:]=np.nan;data[2026][2][4:]=np.nan;b=e.adl_parameters(data,2026,4)
  for i in range(4):np.testing.assert_array_equal(a[i],b[i])
  self.assertEqual(a[4]['training_years'],list(range(2018,2026)))
 def test_potential_breaks_exact_ap_and_pf_ties_in_both_leagues(self):
  s=np.ones((12,32))*100.;p=s+np.arange(32)[None,:]
  for league in ['ADL','FAFL']:
   r=e.event_forecasts(s,p,12,np.zeros((2,0,32)),np.zeros(32),league)
   self.assertEqual(r['Q1']['probabilities'][31,2],1.)
   self.assertEqual(r['Q1']['probabilities'][0,0],1.)
  future=np.ones((2,2,32))*100;future_pot=future+np.arange(32)[None,None,:]
  a,o=e.segment_samples(s,p,1,future,np.zeros(32),'ADL',0,3,future_pot)
  self.assertTrue((o[:,31]==2).all());self.assertTrue((o[:,0]==0).all())
 def test_invalid_simulation_count(self):
  with self.assertRaises(ValueError):e.draw_future(np.ones(32),1,1,'FAFL',2026,1,3)
 def test_new_mean_keeps_legacy_noise(self):
  rng=np.random.default_rng(55);data={y:(list(range(32)),rng.normal(150,30,(12,32)),rng.normal(180,30,(12,32))) for y in range(2018,2027)}
  new=e.adl_parameters(data,2026,4);old=e.adl_legacy_parameters(data,2026,4)
  self.assertEqual(new[1],old[1]);self.assertEqual(new[2],old[2]);self.assertEqual(new[4]['model'],'adl_eb_potential_normal')
if __name__=='__main__':unittest.main()
