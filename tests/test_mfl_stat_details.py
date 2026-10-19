import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mfl_stat_details import parse_details,fetch_details

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

if __name__=='__main__':unittest.main()
