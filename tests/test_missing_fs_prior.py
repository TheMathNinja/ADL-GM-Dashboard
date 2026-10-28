import json,sys,tempfile,unittest
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from missing_fs_prior import missing_fs_initial_mean
from player_positive_core import run
class MissingFsPriorTests(unittest.TestCase):
 def test_applies_only_to_missing_players_and_uses_adl_week_one_ownership(self):
  with tempfile.TemporaryDirectory(dir=ROOT/"tests") as temp:
   root=Path(temp);d=root/'data/player_strength';d.mkdir(parents=True)
   (d/'missing_fs_priors.json').write_text(json.dumps({'2026':{'training_years':[2021,2022,2023,2024,2025],'positions':{'TE':{'intercept':1.,'last_ppg':.5,'rostered':2.}}}}))
   pd.DataFrame({'season':[2025,2025],'player_id':['1','2'],'ppg':[10.,20.]}).to_csv(d/'fallback_previous_ppg.csv',index=False)
   membership=pd.DataFrame({'week':[1,2],'player_id':['1','3']})
   result=missing_fs_initial_mean(root,2026,'TE',['1','2','3'],[0.,7.,0.],[True,False,True],membership)
   np.testing.assert_allclose(result,[8.,7.,1.])
 def test_override_is_used_before_observations(self):
  cube={'ids':['1','2'],'first_fs':np.array([0.,2.]),'initial_mean':np.array([8.,3.]),'projection':np.full((12,2),np.nan),'factors':np.ones((12,2)),'fs_valid':np.zeros((12,2),bool),'actual':np.full((12,2),np.nan)}
  fit={'prior':{'kind':'affine','coefficients':[1.,1.],'knots':[]},'weekly':{'kind':'affine','coefficients':[0.,1.],'knots':[]},'Pa':4.,'Pb':1.,'Ra':10.,'Rf':2.,'position_variance':1.}
  states,_,_=run(cube,fit,'position',.1)
  np.testing.assert_allclose(states[0]['mean'],[8.,3.])
if __name__=='__main__':unittest.main()

