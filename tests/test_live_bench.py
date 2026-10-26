import sys,types,datetime as dt,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_live_bonus import Collector,archive_record
from live_win_probability import simulate
import numpy as np
class BenchTests(unittest.TestCase):
 def test_bench_is_archived_with_details_but_not_added_to_team_score(self):
  c=Collector('ADL');players=[dict(id='s',score='5',status='starter',gameSecondsRemaining='1800'),dict(id='b',score='7',status='nonstarter',gameSecondsRemaining='1800')]
  fs=[dict(id=f'{i:04}',score='5',players=dict(player=players)) for i in range(1,33)]
  data={'liveScoring':dict(week='1',franchise=fs),'league':dict(starters=dict(count='1',iop_starters='0',idp_starters='1',position=[dict(name='LB',limit='1')])),'players':dict(player=[dict(id=p['id'],name=p['id'],position='LB',team='DEN') for p in players]),'rosters':dict(franchise=[dict(id=f['id'],player=[dict(id=p['id'],status='ROSTER') for p in players]) for f in fs]),'projectedScores':dict(week='1',playerScore=[dict(id='s',score='10'),dict(id='b',score='20')]),'playerScores':dict(playerScore=[]),'injuries':dict(injury=[])}
  c.get=lambda kind,*args,**kwargs:data[kind];c.game_states=lambda week:{'DEN':dict(state='in',period=2,clock=0)}
  c.scoring_details=lambda week,players:{p['id']:dict(total=float(p['score']),rows=[dict(points=float(p['score']))],week=1,sourceUpdatedAt=dt.datetime.now(dt.timezone.utc).isoformat()) for p in data['liveScoring']['franchise'][0]['players']['player']}
  model=types.SimpleNamespace(load_model=lambda league:{},add_probabilities=lambda snapshot,model:snapshot)
  cal={'id':'test','positions':{'LB':dict(intercept=0,slope=1)},'fsBenchPositions':{'LB':dict(intercept=0,slope=.5)}}
  with patch.dict(sys.modules,{'live_win_probability':model}),patch('collect_live_bonus.load_calibration',return_value=cal):s=c.collect()
  for t in s['teams']:
   self.assertEqual(t['score'],5);self.assertEqual(t['projectedScore'],10)
   self.assertEqual(len(t['starters']),1);self.assertEqual(len(t['bench']),1)
   b=t['bench'][0];self.assertEqual(b['score'],7);self.assertEqual(b['pregameProjection'],20);self.assertEqual(b['calibratedPregameProjection'],10);self.assertEqual(b['liveProjection'],12)
   self.assertEqual(b['scoringDetails']['total'],7)
  _,_,raw=archive_record(s);self.assertIn(b'"bench"',raw)
 def test_bench_does_not_change_joint_starter_simulation(self):
  m=dict(shape='Normal',positions={},fallback=dict(floorVariance=1,projectionVariance=0),referenceLevel=10,paceVariance=0,advantageVariance=0)
  p=dict(id='s',position='LB',pregameProjection=10,calibratedPregameProjection=12,seconds=1800,nflGame='a',gameSide=1)
  t=dict(id='A',score=5,starters=[p]);before=simulate([t],m,1000,17)['A'];t['bench']=[dict(p,id='b',pregameProjection=9999,calibratedPregameProjection=9999)]
  np.testing.assert_array_equal(before,simulate([t],m,1000,17)['A'])
if __name__=='__main__':unittest.main()
