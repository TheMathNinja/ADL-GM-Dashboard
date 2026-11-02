import copy,itertools,json,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from exact_clinching import ClinchModel,certify,normalize,adjudicate,z3

def toy(scores,potential=None,wins2=None,week=None):
 n=len(scores[0]);w=len(scores) if week is None else week;m=len(scores)
 return dict(week=w,max_week=m,teams=[dict(id=str(i),conference='C',division='D',wins2=(wins2 or [0]*n)[i]) for i in range(n)],scores=scores[:w],potential=(potential or scores)[:w],opp=[[i^1 for i in range(n)] for k in range(m)],bonus_specs=[],bonus_win_count=0,bonus_tie_count=0,wild_cards=0)

class ExactTests(unittest.TestCase):
 def test_final_tie_has_no_identity_fallback(self):
  r=toy([[100,100]],wins2=[1,1]);c=certify(r)
  self.assertTrue(all(not t['clinch'] for t in c['teams'].values()))
 def test_potential_breaks_final_tie(self):
  r=toy([[100,100]],[[101,102]],[1,1]);c=certify(r)
  self.assertEqual(c['teams']['0001']['clinch'],'b');self.assertEqual(c['teams']['0000']['clinch'],'e')
 def test_late_irreversible_clinch(self):
  r=toy([[200,100],[200,100],[0,0]],wins2=[4,0],week=2);c=certify(r)
  self.assertEqual(c['teams']['0000']['clinch'],'b');self.assertEqual(c['teams']['0001']['clinch'],'e')
 def test_ties_count_half(self):
  r=toy([[100,100]],wins2=[1,1]);m=ClinchModel(r);self.assertEqual([z3.simplify(v).as_long() for v in m.h[0]],[1,1])
 def test_nonzero_simulation_certainty_is_not_required(self):
  r=toy([[200,100],[0,0]],wins2=[2,0],week=1);c=certify(r)
  self.assertEqual(c['teams']['0000']['clinch'],'');self.assertEqual(c['teams']['0001']['clinch'],'')
 def test_incomplete_schedule_fails(self):
  r=toy([[1,2]]);r['opp']=[[1,1]]
  with self.assertRaises(ValueError):ClinchModel(r)
 def test_fractional_win_tick_rejected(self):
  r=toy([[1,2]],wins2=[.2,0])
  with self.assertRaises(ValueError):ClinchModel(r)
 def test_final_seed_ignores_winning_percentage(self):
  r=toy([[200,100,150,50],[200,100,150,50]],wins2=[2,4,0,2]);r['teams'][2]['division']='E';r['teams'][3]['division']='E';r['wild_cards']=1
  c=certify(r);self.assertTrue(c['teams']['0000']['bye']);self.assertFalse(c['teams']['0001']['bye'])
 def test_division_mini_league_precedes_all_play(self):
  r=toy([[101,100,300,0]],wins2=[1,1,0,0]);r['teams'][2]['division']='E';r['teams'][3]['division']='E';r['wild_cards']=0
  c=certify(r);self.assertTrue(c['teams']['0000']['division']);self.assertFalse(c['teams']['0001']['division'])
 def test_exhaustive_one_week_grid_never_contradicts_certificate(self):
  r=toy([[100,90],[0,0]],wins2=[2,0],week=1);c=certify(r);nr=normalize(r)
  for a,b,pa,pb in itertools.product(range(3),repeat=4):
   p=[nr['scores'][0],[a,b]];v=[nr['potential'][0],[a+pa,b+pb]];world=adjudicate(nr,p,v)
   for i,team in enumerate(nr['ids']):
    if c['teams'][team]['division']:self.assertTrue(world['division'][i])
    if c['teams'][team]['eliminated']:self.assertFalse(world['division'][i])
 def test_bonus_tie_allocations_are_enforced(self):
  r=toy([[4,3,2,1]],wins2=[0,0,0,0],week=0);r['bonus_specs']=[[0,1]];r['bonus_win_count']=1;r['bonus_tie_count']=2;r['scores']=[];r['potential']=[]
  m=ClinchModel(r);m.feasibility();world=adjudicate(m.r,[[4,3,2,1]],[[4,3,2,1]])
  self.assertEqual(world['bonus']['0'],[2,1,1,0]);self.assertEqual(sum(world['bonus']['0']),4)
 def test_no_false_tag_on_timeout(self):
  r=toy([[200,100],[0,0]],wins2=[2,0],week=1);m=ClinchModel(r,1);m.feasibility();result=m.check('playoffs',0)
  self.assertFalse(result['certified'])
 def test_wildcard_omits_head_to_head(self):
  r=toy([[150,100,140,101],[200,180,50,0]],wins2=[3,2,4,2]);r['opp']=[[2,3,0,1],[1,0,3,2]]
  r['teams'][2]['division']='E';r['teams'][3]['division']='E';r['wild_cards']=1
  c=certify(r);self.assertTrue(c['teams']['0001']['playoffs']);self.assertTrue(c['teams']['0003']['eliminated'])
 def test_head_to_head_and_all_play_share_scores(self):
  r=toy([[0,0]],week=0);m=ClinchModel(r);m.solver.add(m.p[0][0]<m.p[0][1],m.h[0][0]==2)
  self.assertEqual(m.solver.check(),z3.unsat)
 def test_future_potential_cannot_be_less_than_score(self):
  r=toy([[0,0]],week=0);m=ClinchModel(r);m.solver.add(m.v[0][0]<m.p[0][0])
  self.assertEqual(m.solver.check(),z3.unsat)

if __name__=='__main__':unittest.main()
