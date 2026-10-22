import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from queue_chi_forecast import select_week,refresh_signature
class RefreshTests(unittest.TestCase):
 def test_same_cutoff_required(self):
  receipts={'ADL':{'status':'success','week':6},'FAFL':{'status':'success','week':6}}
  self.assertEqual(select_week(receipts),6)
  self.assertEqual(select_week(receipts,'6'),6)
  self.assertIsNone(select_week(receipts,'5'))
  receipts['FAFL']['week']=7
  self.assertIsNone(select_week(receipts))
 def test_provider_refresh_without_score_changes(self):
  r={'ADL':{'week':6},'FAFL':{'week':6}}
  self.assertEqual(refresh_signature(r,'run1'),refresh_signature(r,'run1'))
  self.assertNotEqual(refresh_signature(r,'run1'),refresh_signature(r,'run2'))
  self.assertEqual(refresh_signature(r),refresh_signature(dict(reversed(list(r.items())))))
if __name__=='__main__':unittest.main()
