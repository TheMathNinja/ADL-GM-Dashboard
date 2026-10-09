import sys,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import quarterly_bonus as shared
import bonus_predictor as model

class SharedQuarterlyTests(unittest.TestCase):
 def setUp(self):
  # These tests isolate quarterly aggregation; paired-draw fitting is tested separately.
  self.pairs=patch.object(shared,'future_pairs',side_effect=lambda root,current,league,season,week,future:(np.stack([future,future+30],axis=-1),{'method':'test'}))
  self.pairs.start();self.addCleanup(self.pairs.stop)
  self.legacy=patch.object(model,'adl_legacy_parameters',return_value=(np.full(32,130.),30.,12.,np.full(32,30.),{'model':'legacy'}));self.legacy_mock=self.legacy.start();self.addCleanup(self.legacy.stop)

 def current(self,w=4):
  return pd.DataFrame([dict(season=2026,week=k,franchise_id=f'{t:04}',points=100+t+k,potential=130+t+k) for k in range(1,w+1) for t in range(32)])
 def test_quarters_are_separate_and_totals_are_valid(self):
  with patch.object(model,'load_adl',return_value={}),patch.object(model,'adl_parameters',return_value=(np.linspace(110,140,32),30.,12.,np.full(32,30.),{'model':'test'})):
   result=shared.forecast(ROOT,self.current(),'ADL',2026,4,400)
  self.assertEqual(result['quarterly_credits'].shape,(400,4,32))
  np.testing.assert_allclose(result['quarterly_credits'].sum(2),16)
  self.assertTrue(np.any(result['quarterly_credits'][:,2]!=result['quarterly_credits'][:,3]))
  np.testing.assert_array_equal(result['events']['Q3']['probabilities'],result['events']['Q4']['probabilities'])
  for q in ['Q1','Q2']:
   idx=int(q[1])-1;prob=result['events'][q]['probabilities']
   np.testing.assert_allclose(result['quarterly_credits'][:,idx].mean(0),prob[:,2]+.5*prob[:,1])
 def test_future_actuals_do_not_enter_shared_forecast(self):
  params=(np.full(32,130.),30.,12.,np.full(32,30.),{'model':'test'})
  with patch.object(model,'load_adl',return_value={}),patch.object(model,'adl_parameters',return_value=params):
   before=shared.forecast(ROOT,self.current(4),'ADL',2026,4,100)
   newer=self.current(5);newer.loc[newer.week==5,'points']=999999
   after=shared.forecast(ROOT,newer,'ADL',2026,4,100)
  np.testing.assert_array_equal(before['quarterly_credits'],after['quarterly_credits'])
 def test_completed_quarters_have_no_simulation_uncertainty(self):
  result=shared.forecast(ROOT,self.current(12),'ADL',2026,12,100)
  np.testing.assert_array_equal(result['quarterly_credits'],np.broadcast_to(result['quarterly_credits'][:1],(100,4,32)))
 def test_native_season_and_h2h_are_preserved_when_quarters_change(self):
  if not (ROOT/'scripts/rules.py').exists():self.skipTest('FAFL rule integration')
  from rules import fafl_outcomes
  rng=np.random.default_rng(10);scores=rng.normal(150,35,(10,12,32));pot=scores+30
  opp=np.tile(np.arange(32)^1,(12,1));conf=[np.arange(16),np.arange(16,32)];div=[np.arange(i,i+4) for i in range(0,32,4)]
  old=fafl_outcomes(scores,pot,opp,conf,div)
  oldquarters=np.stack([model.segment_samples(scores[0,:0],pot[0,:0],0,scores,np.full(32,30.),'FAFL',a,b)[1]/2 for _,a,b in model.EVENTS[:4]],1)
  replacement=np.roll(oldquarters,1,axis=2)
  new=fafl_outcomes(scores,pot,opp,conf,div,quarterly_credits=replacement)
  np.testing.assert_allclose(new[3]-old[3],(replacement-oldquarters).sum(1))
  np.testing.assert_array_equal(new[4],old[4]);np.testing.assert_array_equal(new[5],old[5])

 def test_bonus_distribution_edits_do_not_change_native_scores(self):
  params=(np.full(32,130.),30.,12.,np.full(32,30.),{'model':'test'})
  ids=[f'{t:04}' for t in range(32)]
  primary=dict(ids=ids,mu=[140.]*32,sigma=35.,tau=10.)
  with patch.object(model,'load_adl',return_value={}),patch.object(model,'adl_parameters',return_value=params):
   before=shared.forecast(ROOT,self.current(),'ADL',2026,4,100,primary)
   with patch.object(model,'draw_future',return_value=np.full((100,8,32),999.)):
    after=shared.forecast(ROOT,self.current(),'ADL',2026,4,100,primary)
  np.testing.assert_array_equal(before['native_future'],after['native_future'])

 def test_reg_season_uses_selected_scores_and_shared_credits(self):
  params=(np.linspace(110,170,32),30.,12.,np.full(32,30.),{'model':'adl_eb_potential_normal'})
  with patch.object(model,'load_adl',return_value={}),patch.object(model,'adl_parameters',return_value=params):
   result=shared.forecast(ROOT,self.current(),'ADL',2026,4,100)
  expected=model.event_forecasts(result['s'],result['p'],4,result['future'],params[3],'ADL',result['future_potential'])['All-Season']
  np.testing.assert_array_equal(result['events']['All-Season']['probabilities'],expected['probabilities'])
  self.assertEqual(result['events']['All-Season']['win_cutoff'],expected['win_cutoff'])
  self.assertEqual(result['reg_season_credits'].shape,(100,32))
  np.testing.assert_allclose(result['reg_season_credits'].sum(1),16)
  np.testing.assert_allclose(result['reg_season_credits'].mean(0),expected['probabilities'][:,2]+.5*expected['probabilities'][:,1])
  self.legacy_mock.assert_not_called()
