import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from weekly_pairs import draw_pairs

class WarningTests(unittest.TestCase):
    def setUp(self):
        self.history=pd.DataFrame([dict(season=2024,week=w,franchise_id='0001',points=200.,potential=240.) for w in range(1,13)])
        self.pf=np.full((10,1,1),200.)
    def test_known_anomaly_warns_without_mutating_scores(self):
        actual=np.array([[200.]]);potential=np.array([[190.]])
        with self.assertWarnsRegex(RuntimeWarning,'MFL potential'):
            result=draw_pairs(self.pf,self.history,actual,potential,allow_reported_potential_below_pf=True)
        np.testing.assert_array_equal(actual,[[200.]])
        np.testing.assert_array_equal(potential,[[190.]])
        np.testing.assert_array_equal(result[...,0],self.pf)
        self.assertTrue(np.isfinite(result).all())
    def test_other_errors_still_block(self):
        for pf,potential in [(self.pf,[[np.nan]]),(-self.pf,[[210.]])]:
            with self.assertRaises(ValueError):
                draw_pairs(pf,self.history,[[200.]],potential,allow_reported_potential_below_pf=True)
    def test_valid_outputs_unchanged(self):
        args=(self.pf,self.history,[[200.]],[[240.]])
        np.testing.assert_array_equal(draw_pairs(*args),draw_pairs(*args,allow_reported_potential_below_pf=True))
