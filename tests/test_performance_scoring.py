import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from performance_scoring import scoring_details

class PerformanceScoringTests(unittest.TestCase):
 def test_scoring_events_ignore_unscored_kick_return_yards(self):
  rules={'positionRules':[{'positions':'TE','rule':[
   {'event':'PY','range':'-999-999','points':'*0.2'},
   {'event':'RY','range':'-999-999','points':'*0.2'}]}]}
  result=scoring_details('13424|PY 22|RY 112|KY 69',rules,'13424','TE',{'PY':'Passing Yards','RY':'Rushing Yards'},['PY','RY'])
  self.assertEqual(result['total'],26.8)
  self.assertEqual([r['eventCode'] for r in result['rows']],['RY','PY'])

 def test_per_event_rounding_and_field_goal_thresholds(self):
  rules={'positionRules':[{'positions':'PK','rule':[
   {'event':'FG','range':'40-120','points':'0.4/1','thresholdPoints':'3'},
   {'event':'F','range':'0-99','points':'*-0.15'}]}]}
  result=scoring_details('1|FG 40,52|F 1',rules,'1','PK',{'FG':'Field Goal Distance','F':'Penalties'},['FG','F'])
  self.assertEqual([r['points'] for r in result['rows']],[3,7.8,-.1])
  self.assertEqual(result['total'],10.7)

 def test_saved_breakdowns_reconcile_and_hill_has_no_return_yard_points(self):
  data=json.loads((ROOT/'docs/trophy-room/top-performances.json').read_bytes())
  for key,d in data['details'].items():
   if d['kind']!='player':continue
   scoring=d['scoring']
   self.assertAlmostEqual(sum(r['points'] for r in scoring['rows']),scoring['total'],places=6,msg=key)
   if d['mode']=='current':self.assertAlmostEqual(scoring['total'],d['score'],places=6,msg=key)
  hill=data['details']['current:player:2022:5:13424']
  self.assertEqual(hill['scoring']['total'],47.8)
  self.assertNotIn('KY',{r['eventCode'] for r in hill['scoring']['rows']})
  self.assertNotIn('Kick return yards',{r['event'] for r in hill['scoring']['rows']})

if __name__=='__main__':unittest.main()
