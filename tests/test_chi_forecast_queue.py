import unittest,sys
import json,os
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from queue_chi_forecast import select_week,refresh_signature
import queue_chi_forecast as queue
class RefreshTests(unittest.TestCase):
 def test_incompatible_upload_contract_stops_before_expensive_job(self):
  receipt=json.dumps({'week':7,'status':'success'}).encode()
  with patch.dict(os.environ,{'THROUGH_WEEK':'7','CHI_SITE_SERVICE_TOKEN':'test'}),patch('subprocess.check_output',return_value=receipt),patch.object(queue,'ensure_site_model_contract',side_effect=RuntimeError('unsupported model')),patch.object(queue,'call')as call:
   with self.assertRaisesRegex(RuntimeError,'unsupported model'):queue.main()
   call.assert_not_called()
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
