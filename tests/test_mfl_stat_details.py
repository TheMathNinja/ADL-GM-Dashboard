import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mfl_stat_details import parse_details,fetch_details,details_from_raw,rule_points

class ScoringDetailTests(unittest.TestCase):
 def fixture(self):
  p=Path(__file__).parent/'fixtures/mfl_detailed_scoring.html'
  return p.read_text(encoding='utf8')
 def test_reference_table_and_negative_points(self):
  result=parse_details(self.fixture(),2026,'60206',2,['16150'])['16150']
  self.assertEqual(result['total'],28.)
  self.assertEqual(len(result['rows']),11)
  self.assertEqual(result['rows'][0],dict(points=-2.6,event='13 Penalty Yards'))
  self.assertEqual(result['rows'][2],dict(points=-55.,event='55 Pass Attempts'))
  self.assertEqual(result['rows'][-1],dict(points=8.,event='16 First Downs'))
  self.assertAlmostEqual(sum(r['points'] for r in result['rows']),result['total'])
 def test_wrong_week_rejected(self):
  with self.assertRaises(ValueError):parse_details(self.fixture(),2026,'60206',6,['16150'])
 def test_unrelated_ids_are_not_exposed(self):
  self.assertEqual(parse_details(self.fixture(),2026,'60206',2,['99999']),{})
 def test_no_stats_is_not_a_fabricated_zero(self):
  html='<h1>Week 6 Detailed Results</h1><table class="report"><tr><th>Player</th><th>Event</th></tr></table>'
  self.assertEqual(parse_details(html,2026,'60206',6,['16150']),{})
 def test_error_page_rejected(self):
  with self.assertRaises(ValueError):parse_details('<h1>Error</h1>',2026,'60206',6,['16150'])
 def test_batches_obey_report_limit(self):
  urls=[]
  class Reply:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return b'<h1>Week 6 Detailed Results</h1><table class="report"></table>'
  def get(req,timeout):urls.append(req.full_url);return Reply()
  with patch('mfl_stat_details.urllib.request.urlopen',get):fetch_details(2026,'60206',6,[str(10000+i) for i in range(672)])
  self.assertEqual(len(urls),6)
  self.assertTrue(all(len(u.split('&P=')[1].split('&')[0])<750 for u in urls))
 def test_raw_feed_negative_half_tenths(self):
  def rule(code,form):return dict(event=code,range='-999-999',points=form)
  rules=dict(positionRules=[dict(positions='DT',rule=[rule(k,v) for k,v in [('PD','*3'),('TK','*2.5'),('AS','*1.5'),('F','*-0.5'),('FY','*-0.2'),('SK','*-0.5'),('SKY','*0.2'),('QH','*1.5')]])])
  text='14153|PD 2\r|TK 2\r|AS 3\r|F 1\r|FY 5\r|SK 0.5\r|SKY 7\r|QH 1\r\n'
  labels={k:k for k in ['PD','TK','AS','F','FY','SK','SKY','QH']}
  d=details_from_raw(text,rules,{'14153':'DT'},2026,'60206',6,labels)['14153']
  self.assertEqual(d['total'],16.7);self.assertEqual(next(r['points'] for r in d['rows'] if r['event']=='0.5 SK'),-.2)
 def test_raw_field_goal_lengths_and_thresholds(self):
  rules=dict(positionRules=[dict(positions='PK',rule=[dict(event='FG',range='0-29',points='0.05/1',thresholdPoints='-0.5'),dict(event='FG',range='30-39',points='0.2/1',thresholdPoints='1'),dict(event='FG',range='40-120',points='0.4/1',thresholdPoints='3'),dict(event='EP',range='0-99',points='*0.3'),dict(event='#M',range='0-99',points='*-6'),dict(event='TK',range='0-99',points='*1')])])
  text='11936|FG 20,39,52,58\r|EP 2\r|#M 1\r|TK 1\r\n'
  d=details_from_raw(text,rules,{'11936':'PK'},2026,'60206',6,{'FG':'yd Field Goal','EP':'Extra Points','#M':'Field Goals Missed','TK':'Tackles'})['11936']
  self.assertEqual(d['total'],16.9);self.assertEqual([r['points'] for r in d['rows'][:4]],[.5,2.8,7.8,10.2])
 def test_scoring_form_is_not_executed(self):
  with self.assertRaises(ValueError):rule_points(1,dict(range='0-99',points='__import__("os")'))

if __name__=='__main__':unittest.main()
