import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from live_win_probability import bonus_outcomes,add_bonus_probabilities

class BonusProbabilityTests(unittest.TestCase):
 def test_final_rank_and_potential(self):
  pf=np.tile(np.arange(32),(5,1));ap=np.zeros_like(pf)
  probs=bonus_outcomes(ap,pf,np.tile(np.arange(32),(5,1)),np.ones(32,dtype=bool))
  self.assertEqual(probs[31].tolist(),[1,0,0]);self.assertEqual(probs[16].tolist(),[0,1,0]);self.assertEqual(probs[14].tolist(),[0,0,1])
  # Potential is the third key, never franchise ID.
  probs=bonus_outcomes(ap,np.zeros_like(pf),pf,np.ones(32,dtype=bool))
  self.assertEqual(probs[31].tolist(),[1,0,0])
 def test_unresolved_ties_share_boundary(self):
  z=np.zeros((4,32));probs=bonus_outcomes(z,z,z,np.zeros(32,dtype=bool))
  np.testing.assert_allclose(probs,np.tile([15/32,2/32,15/32],(32,1)))
  np.testing.assert_allclose(probs.sum(0),[15,2,15]);np.testing.assert_allclose(probs.sum(1),1)
 def test_apw_precedes_points(self):
  ap=np.tile(np.arange(32),(4,1));pf=-ap
  p=bonus_outcomes(ap,pf,pf,np.ones(32,dtype=bool));self.assertEqual(p[31,0],1)
 def test_quarter_season_carryforward(self):
  teams=[dict(id=str(i),potential=float(i),potentialComplete=True) for i in range(32)]
  history=[dict(week=w,teams=[dict(id=str(i),score=float(31-i),potential=float(31-i)) for i in range(32)]) for w in range(1,6)]
  s=dict(week=6,teams=teams,completed=history)
  add_bonus_probabilities(s,{str(i):np.full(20,i) for i in range(32)})
  for race in ['quarter','season']:
   probs=np.array([[t['liveBonusProbabilities'][race][k] for k in ['win','tie','loss']] for t in teams])
   np.testing.assert_allclose(probs.sum(0),[15,2,15]);np.testing.assert_allclose(probs.sum(1),1)
  self.assertEqual(teams[0]['liveBonusProbabilities']['quarter']['win'],1)
  self.assertEqual(teams[31]['liveBonusProbabilities']['quarter']['loss'],1)
 def test_missing_history_unavailable(self):
  s=dict(week=2,teams=[dict(id=str(i),potential=i) for i in range(32)],completed=[])
  with self.assertRaises(ValueError):add_bonus_probabilities(s,{str(i):np.full(3,i) for i in range(32)})

if __name__=='__main__':unittest.main()
