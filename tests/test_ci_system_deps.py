import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from install_ci_system_deps import parse_plan
class AptPlanTests(unittest.TestCase):
 def test_signed_index_plan_and_other_output(self):self.assertEqual(parse_plan("Reading package lists...\n'https://archive.ubuntu.com/ubuntu/pool/r.deb' r_1_amd64.deb 123 MD5Sum:abc"),[('https://archive.ubuntu.com/ubuntu/pool/r.deb','r_1_amd64.deb',123)])
 def test_unsafe_or_incomplete_target_rejected(self):
  for text in ["'https://host/r.deb' ../r.deb 123", "'file:///etc/passwd' r.deb 1", "'https://host/r.deb' r.deb -1", "'https://host/r.deb' r.deb"]:
   with self.assertRaises(ValueError):parse_plan(text)
