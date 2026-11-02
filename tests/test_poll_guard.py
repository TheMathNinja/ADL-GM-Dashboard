import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from poll_guard import guarded

class TransportIncidentTests(unittest.TestCase):
 def test_first_failure_backoff_probe_recovery_and_recurrence(self):
  with tempfile.TemporaryDirectory() as directory:
   file=Path(directory)/'incident.json'
   def offline():raise TimeoutError('upstream unavailable')
   with self.assertRaises(TimeoutError):guarded(offline,file,'w8',lambda:1000)
   saved=file.read_text()
   check=Mock();guarded(check,file,'w8',lambda:1001);check.assert_not_called()
   file.write_text(saved);guarded(offline,file,'w8',lambda:1301)
   self.assertEqual(json.loads(file.read_text())['count'],2)
   guarded(check,file,'w8',lambda:2000);check.assert_called_once()
   with self.assertRaises(TimeoutError):guarded(offline,file,'w8',lambda:2001)
 def test_different_week_and_nontransport_failure_not_suppressed(self):
  with tempfile.TemporaryDirectory() as directory:
   file=Path(directory)/'incident.json'
   file.write_text(json.dumps(dict(cycle='w7',key='old',probe_at=2000)))
   with self.assertRaises(ValueError):guarded(Mock(side_effect=ValueError('bad scores')),file,'w8',lambda:1500)
