import importlib.util,io,json,os,unittest.mock as mock,datetime
from pathlib import Path

def test_temporary_refresh_session():
 p=Path(__file__).resolve().parents[1]/'scripts/sync_chi_team_tools.py';spec=importlib.util.spec_from_file_location('sync',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 class Opener:
  def open(self,request,timeout):
   if request.full_url.endswith('/login'):return io.BytesIO(b'<status MFL_USER_ID="fake-owner-session" MFL_PW_SEQ="fake-seq"/>')
   if 'TYPE=pendingTrades' in request.full_url:return io.BytesIO(b'{"pendingTrades":{}}')
   return io.BytesIO(b'{"rosters":{"franchise":[]}}')
 seen=[]
 def upload(req,timeout):
  body=json.loads(req.data);seen.append(body);assert req.headers.get('Cookie') is None;assert body['session']['uid']=='fake-owner-session';assert body['session']['seq']=='fake-seq';s=body['session'];assert datetime.datetime.fromisoformat(s['expiresAt'])-datetime.datetime.fromisoformat(s['createdAt'])==datetime.timedelta(hours=6);assert 'password' not in body and 'username' not in body;return io.BytesIO(b'{"ok":true}')
 out=io.StringIO()
 with mock.patch.dict(os.environ,{'MFL_USERNAME':'fake-owner','MFL_PASSWORD':'fake-password','CHI_SITE_SERVICE_TOKEN':'fake-service'}),mock.patch.object(m.urllib.request,'build_opener',return_value=Opener()),mock.patch.object(m.urllib.request,'urlopen',side_effect=upload),mock.patch('sys.stdout',out):m.run()
 assert {x['league'] for x in seen}=={'ADL','FAFL'}
 assert not any(secret in out.getvalue() for secret in ['fake-owner-session','fake-seq','fake-password','fake-owner','fake-service'])
 

if __name__=='__main__':
 test_temporary_refresh_session()
 print('PASS: temporary MFL refresh-session upload for both leagues without password, cookie or log leakage.')
