import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_quarterly_sync import verify_snapshot
class PublishedPrecisionTests(unittest.TestCase):
 def compare(self,value,credit):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as d:
   root=Path(d);p=root/'docs/playoff-picture';p.mkdir(parents=True)
   data={'NFC':[dict(franchise_id='0001',winDetails=dict(bonusGames=[dict(label='Q2 Bonus Game',probability=value)]),actualDetails=dict(bonusGames=[]))],'AFC':[]}
   (p/'index.html').write_text('const data='+json.dumps(data)+';')
   bonus={'weeks':{'2':[dict(id='0001',events=[dict(event='Q2',completed=False,credit=credit)])]}}
   return verify_snapshot(root,'FAFL',bonus,2,'index.html')
 def test_half_rounding_boundary_is_not_a_model_difference(self):self.assertEqual(self.compare(.35454166666666664,.3545),1)
 def test_real_difference_still_blocks(self):
  with self.assertRaises(ValueError):self.compare(.356,.3545)
