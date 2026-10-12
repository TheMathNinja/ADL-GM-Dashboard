import sys,json,unittest
from pathlib import Path
import numpy as np
from scipy.stats import norminvgauss,skew
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from bonus_nig import standardized_nig,parameters
import bonus_predictor as bonus
class NIGTests(unittest.TestCase):
 def test_sampler_has_selected_shape_center_and_original_variance(self):
  a,ratio=[5.531141987626106,.19081835152289467];rv=norminvgauss(a,a*ratio);mean,var,expected_skew=rv.stats(moments='mvs')
  z=standardized_nig(np.random.default_rng(85),[a,ratio],(600000,))
  self.assertLess(abs(z.mean()),.006);self.assertLess(abs(z.var()-1),.012);self.assertLess(abs(skew(z)-expected_skew),.025)
  np.testing.assert_allclose(np.quantile(z,[.025,.1,.5,.9,.975]),(rv.ppf([.025,.1,.5,.9,.975])-mean)/np.sqrt(var),atol=.016)
  self.assertGreater(skew(z),.15)
 def test_shape_is_prior_only_and_current_truth_is_irrelevant(self):
  f=parameters(ROOT,{},2026);self.assertEqual(f['scale'],1.);self.assertLess(max(f['training_years']),2026)
  self.assertEqual(parameters(ROOT,{2026:'unused'},2026),f)
 def test_invalid_shape_rejected(self):
  for shape in [[0,.1],[2,1],[2,float('nan')]]:
   with self.assertRaises(ValueError):standardized_nig(np.random.default_rng(1),shape,(2,))
 def test_selected_draws_are_repeatable(self):
  x=bonus.draw_future(np.full(32,250.),40.,8.,'ADL',2026,4,1000);y=bonus.draw_future(np.full(32,250.),40.,8.,'ADL',2026,4,1000)
  np.testing.assert_array_equal(x,y)
if __name__=='__main__':unittest.main()
