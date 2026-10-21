"""Queue the personal refresh only after both league publications are available."""
import hashlib,json,os,time,urllib.request
SITE='https://chi-team-tools.dreamytang7.chatgpt.site'
def call(method='GET',payload=None):
 token=os.environ['CHI_SITE_SERVICE_TOKEN'].removeprefix('Bearer ')
 req=urllib.request.Request(SITE+'/api/forecast-refresh'+('?worker=1'if method=='GET'else ''),data=json.dumps(payload).encode()if payload is not None else None,headers={'OAI-Sites-Authorization':'Bearer '+token,'Content-Type':'application/json'},method=method)
 with urllib.request.urlopen(req,timeout=120)as r:return json.load(r)
def main():
 import subprocess
 week=int(os.environ['THROUGH_WEEK']);receipts={}
 for league in ['ADL','FAFL']:
  receipt=json.loads(subprocess.check_output(['gh','api',f'repos/TheMathNinja/{league}-GM-Dashboard/contents/data/preliminary_refresh_complete.json','-H','Accept: application/vnd.github.raw+json']))
  receipts[league]=receipt
  if receipt.get('status')!='success'or receipt.get('week',0)<week:
   print(league+' publication is still pending. Its final personal stage will queue the combined refresh.');return
 signature=hashlib.sha256(json.dumps(receipts,sort_keys=True).encode()).hexdigest()
 current=call().get('current')or{}
 if current.get('receipt',{}).get('upstreamSignature')==signature:print('Personal forecasts already reflect these league publications.');return
 job=call('PUT',{'type':'queue','season':2026,'throughWeek':week,'league':os.environ['SOURCE_LEAGUE'],'upstreamSignature':signature,'upstreamRun':os.environ.get('UPSTREAM_RUN','')})['job'];print('Personal refresh queued after league publications; completed results through Week',week)
 deadline=time.monotonic()+105*60
 while time.monotonic()<deadline:
  state=call();j=state.get('job')or{};current=state.get('current')or{}
  if current.get('throughWeek',0)>=week and (current.get('generatedAt','')>=job['requestedAt']):print('Personal forecast snapshot published through Week',week);return
  if j.get('id')==job['id']and j.get('status')=='failed':raise RuntimeError(j.get('error','Personal refresh failed'))
  time.sleep(30)
 raise RuntimeError('Personal refresh did not finish. The previous forecast is preserved; check the existing Windows projections runner.')
if __name__=='__main__':main()
