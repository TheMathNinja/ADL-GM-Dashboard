import sys,json,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from player_positive_core import run,position_variance
class WeeklySharksTests(unittest.TestCase):
 def test_exported_prior_fits_are_prior_only(self):
  rows=json.loads((ROOT/'data/player_strength/weekly_sharks_fits.json').read_text())
  for row in rows:
   self.assertLess(max(row['training_years']),row['year']);self.assertGreater(row['Rf'],0);self.assertGreater(row['position_variance'],0)
   self.assertEqual(position_variance({**row,'train':[]}),row['position_variance'])
 def test_weekly_fs_changes_state_without_future_actuals(self):
  f={'prior':{'kind':'affine','coefficients':[0.,1.],'knots':[]},'weekly':{'kind':'affine','coefficients':[0.,1.],'knots':[]},'Pa':10.,'Ra':10.,'Rf':3.,'Pb':1.,'position_variance':1.,'train':[]}
  c={'ids':['a'],'first_fs':np.array([10.]),'projection':np.full((12,1),20.),'factors':np.ones((12,1)),'fs_valid':np.ones((12,1),bool),'actual':np.full((12,1),10.)}
  on=run(c,f,'position',.1)[0];off=run(c,f,'off',.1)[0];self.assertGreater(on[1]['mean'][0],off[1]['mean'][0]);before=on[3]['mean'].copy();c['actual'][3:]=9999;c['projection'][4:]=9999;after=run(c,f,'position',.1)[0];np.testing.assert_array_equal(before,after[3]['mean'])
if __name__=='__main__':unittest.main()
