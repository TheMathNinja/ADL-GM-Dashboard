"""Regression: compacted Playoffs HTML must not swallow trailing JavaScript."""
from pathlib import Path
import json,shutil,subprocess,unittest

class GmProfileParser(unittest.TestCase):
 @unittest.skipUnless(shutil.which('node'),'Node is needed for the browser parser test')
 def test_compacted_profiles_and_escaped_strings(self):
  template=(Path(__file__).resolve().parents[1]/'scripts/bonus_template.html').read_text(encoding='utf8')
  function='function parseGmProfiles'+template.split('function parseGmProfiles',1)[1].split('function loadGmProfiles',1)[0]
  profiles={'Team':{'gm':'Quote \"; braces }; { and slash \\\\','bestYears':[2024]}}
  source='const gmProfiles='+json.dumps(profiles)+';const popup={};throw Error(\"Never execute page source\");'
  script=function+'\nconsole.log(JSON.stringify(parseGmProfiles('+json.dumps(source)+')))'
  r=subprocess.run(['node','-e',script],capture_output=True,text=True,encoding='utf8',check=True)
  self.assertEqual(json.loads(r.stdout),profiles)

if __name__=='__main__':unittest.main()
