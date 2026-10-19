import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from live_win_probability import simulate,add_probabilities,nig_increment

MODEL=dict(id='test',shape='NIG',a=2.,b=.6,paceVariance=.05,advantageVariance=.1,referenceLevel=10.,trainingYears=[2021,2022],positions={},fallback=dict(floorVariance=1.,projectionVariance=0.))
def player(pid='a',f=1,mu=10,side=1):return dict(id=pid,seconds=f*3600,pregameProjection=mu,position='LB',nflGame='CHI|GBP',gameSide=side)
def team(tid,score,p):return dict(id=tid,score=score,starters=p,opponentIds=['B' if tid=='A' else 'A'])

class LiveWinTests(unittest.TestCase):
    def test_increment_moments(self):
        for f in [1,.5,.05]:
            x=nig_increment(np.random.default_rng(721),2,.6,f,250000)
            self.assertAlmostEqual(x.mean(),0,delta=.01)
            self.assertAlmostEqual(x.var(),f,delta=.015)
    def test_final_and_ties(self):
        for scores,expected in [([100,99],1),([99,100],0),([100,100],0)]:
            s=dict(teams=[team('A',scores[0],[]),team('B',scores[1],[])])
            add_probabilities(s,MODEL,1000);a=s['teams'][0]['liveMatchups']['B'];b=s['teams'][1]['liveMatchups']['A']
            self.assertEqual(a['win'],expected);self.assertEqual(a['win'],b['loss']);self.assertEqual(a['tie'],int(scores[0]==scores[1]));self.assertAlmostEqual(sum(a.values()),1)
    def test_reciprocal_stable(self):
        s=dict(teams=[team('A',5,[player()]),team('B',0,[player('b',.5,15,-1)])])
        add_probabilities(s,MODEL,8000);first=s['teams'][0]['liveMatchups']['B'].copy();add_probabilities(s,MODEL,8000)
        self.assertEqual(first,s['teams'][0]['liveMatchups']['B']);self.assertEqual(first['win'],s['teams'][1]['liveMatchups']['A']['loss'])
    def test_mean_time_and_dependence(self):
        teams=[team('A',5,[player()]),team('B',0,[player('b',1,10,-1)])]
        x=simulate(teams,MODEL,150000)
        self.assertAlmostEqual(x['A'].mean(),15,delta=.12)
        self.assertLess(np.cov(x['A'],x['B'])[0,1],-2)
        half=simulate([team('A',5,[player(f=.5)])],MODEL,150000)['A']
        self.assertAlmostEqual(half.mean(),10,delta=.1);self.assertAlmostEqual(half.var()/x['A'].var(),.5,delta=.02)
    def test_missing_projection_and_finished(self):
        p=player(f=.5,mu=None);x=simulate([team('A',5,[p])],MODEL,1000)['A']
        self.assertTrue(np.isfinite(x).all())
        x=simulate([team('A',-2,[player(f=0)])],MODEL,1000)['A'];self.assertTrue(np.all(x==-2))

if __name__=='__main__':unittest.main()
