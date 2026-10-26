import datetime as dt,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_live_bonus import current_player_score,Collector

class ScoreSourceTests(unittest.TestCase):
 def details(self,total=12.9,age=0):
  return dict(total=total,rows=[dict(points=total)],week=1,sourceUpdatedAt=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=age)).isoformat())
 def test_advance_and_correction(self):
  for value in [12.9,4.1,-2.0,0.0]:
   score,source,stamp=current_player_score(dict(score=8.7),self.details(value))
   self.assertEqual(score,value);self.assertEqual(source,'MFL live raw stats');self.assertIsNotNone(stamp)
 def test_fallback(self):
  for d in [None,self.details(12.9,121),self.details(12.9,-40),dict(total=12.9,rows=[]),{**self.details(),'rows':[dict(points=1)]},self.details(float('nan'))]:
   self.assertEqual(current_player_score(dict(score=8.7),d)[:2],(8.7,'MFL liveScoring'))
 def test_collect_consistent_team_and_potential(self):
  for lg in ['ADL','FAFL']:
   c=Collector(lg);fs=[dict(id=f'{i:04}',score='2',players=dict(player=[dict(id='1',score='2',status='starter',gameSecondsRemaining='1800')])) for i in range(1,33)]
   data={'liveScoring':dict(week='1',franchise=fs),'league':dict(starters=dict(count='1',iop_starters='0',idp_starters='1',position=[dict(name='LB',limit='1')])),'players':dict(player=[dict(id='1',name='Test, Player',position='LB',team='DEN')]),'rosters':dict(franchise=[dict(id=f['id'],player=[dict(id='1',status='ROSTER')]) for f in fs]),'projectedScores':dict(week='1',playerScore=[dict(id='1',score='12')]),'playerScores':dict(playerScore=[]),'injuries':dict(injury=[])}
   c.get=lambda kind,*args,**kwargs:data[kind]
   c.game_states=lambda week:{'DEN':dict(state='in',period=2,clock=0)}
   c.scoring_details=lambda week,players:{'1':self.details(12.9)}
   model=types.SimpleNamespace(load_model=lambda league:{},add_probabilities=lambda snap,model:snap)
   with patch.dict(sys.modules,{'live_win_probability':model}), patch('collect_live_bonus.load_calibration',return_value={'id':'fixture','positions':{'LB':{'intercept':2,'slope':1.2}}}):s=c.collect()
   for t in s['teams']:
    self.assertEqual(t['score'],12.9);self.assertEqual(t['potential'],12.9);self.assertAlmostEqual(t['projectedScore'],21.1);self.assertAlmostEqual(t['projectedPotential'],21.1)
    self.assertEqual(t['score'],sum(p['score'] for p in t['starters']));self.assertEqual(t['mflReportedScore'],2)
    self.assertEqual(t['starters'][0]['score'],t['starters'][0]['scoringDetails']['total'])
if __name__=='__main__':unittest.main()
