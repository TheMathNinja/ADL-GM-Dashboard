import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from weekly_pairs import draw_pairs,rows,predict

class PairTests(unittest.TestCase):
    def test_random_conditional_pairs_preserve_pf_and_distribution(self):
        rng=np.random.default_rng(17)
        history=pd.DataFrame([dict(season=y,week=w,franchise_id=str(t),points=pf,potential=pf+gap) for y in range(2018,2024) for w in range(1,13) for t in range(4) for pf,gap in [(rng.uniform(120,250),rng.gamma(3,15))]])
        pf=np.full((20000,1,1),200.)
        observed=np.full((2,1),190.);potential=observed+45
        a=draw_pairs(pf,history,observed,potential,k=100)
        np.testing.assert_array_equal(a[...,0],pf)
        np.testing.assert_array_equal(a,draw_pairs(pf,history,observed,potential,k=100))
        self.assertTrue((a[...,1]>=a[...,0]).all())
        self.assertGreater(a[...,1].std(),10)
        expected=predict(rows(history),pd.DataFrame([dict(x=200/190,prior=45/190,half=0,scale=190)]),'team',100)[0]
        self.assertLess(abs((a[...,1]-200).mean()-expected.mean()),.6)
        self.assertLess(abs((a[...,1]-200).std()-expected.std()),.6)
    def test_invalid_pair_rejected(self):
        with self.assertRaises(ValueError):draw_pairs(np.ones((2,1,1)),pd.DataFrame(),np.ones((1,1))*2,np.ones((1,1)))
    def test_bye_distribution_keeps_randomness_and_reduces_gap(self):
        history=pd.DataFrame([dict(season=y,week=w,franchise_id=str(t),points=200.,potential=200.+(60 if w<=6 else 20)+t,byes=0 if w<=6 else 6) for y in range(2018,2024) for w in range(1,13) for t in range(8)])
        pf=np.full((4000,2,1),200.)
        paired=draw_pairs(pf,history,np.full((1,1),200.),np.full((1,1),240.),kind='pf_bye',k=100,future_byes=[0,6])
        self.assertGreater(paired[:,0,0,1].mean()-paired[:,1,0,1].mean(),30)
        self.assertGreater(paired[:,0,0,1].std(),1)
        self.assertGreater(paired[:,1,0,1].std(),1)

if __name__=='__main__':unittest.main()
