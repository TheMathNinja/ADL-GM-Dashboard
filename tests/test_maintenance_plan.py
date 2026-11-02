import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from maintenance_plan import prior_delivery,REQUIRED

class DailyDeliveryTest(unittest.TestCase):
 def test_requires_every_component_matching_intent_and_eastern_day(self):
  now=dict(id=3,workflow_id=9,created_at='2026-11-03T02:00:00Z')
  prev=dict(now,id=2,created_at='2026-11-02T11:00:00Z',head_branch='main',conclusion='success')
  jobs=[dict(name=k,conclusion='success') for k in REQUIRED|{'intent'}]
  check=lambda history,rows,intent='intent':prior_delivery(now,history,intent,lambda _:rows)
  self.assertEqual(check([prev],jobs),'2')
  self.assertFalse(check([prev],jobs,'different'))
  self.assertFalse(check([dict(prev,created_at='2026-11-02T02:00:00Z')],jobs))
  self.assertFalse(check([dict(prev,conclusion='failure')],jobs))
  self.assertFalse(check([prev],[dict(j,conclusion='skipped') for j in jobs]))
