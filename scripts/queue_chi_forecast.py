"""Queue the personal refresh only after both league publications are available."""
import hashlib,json,os,time,urllib.request
from pathlib import Path
from check_chi_team_model_refresh import ensure_site_model_contract
SITE='https://chi-team-tools.dreamytang7.chatgpt.site'
def call(method='GET',payload=None,endpoint='forecast-refresh'):
 token=os.environ['CHI_SITE_SERVICE_TOKEN'].removeprefix('Bearer ')
 req=urllib.request.Request(SITE+'/api/'+endpoint+('?worker=1'if method=='GET'else ''),data=json.dumps(payload).encode()if payload is not None else None,headers={'OAI-Sites-Authorization':'Bearer '+token,'Content-Type':'application/json'},method=method)
 with urllib.request.urlopen(req,timeout=120)as r:return json.load(r)
def main():
 import subprocess
 requested=os.environ.get('THROUGH_WEEK','').strip();receipts={}
 for league in ['ADL','FAFL']:
  receipt=json.loads(subprocess.check_output(['gh','api',f'repos/TheMathNinja/{league}-GM-Dashboard/contents/data/preliminary_refresh_complete.json','-H','Accept: application/vnd.github.raw+json']))
  receipts[league]=receipt
 week=select_week(receipts,requested)
 if week is None:
  if not requested:raise RuntimeError('League publications disagree; cannot publish a mixed-week personal forecast.')
  print('Both league publications must match the requested week. The final league stage will retry.');return
 ensure_site_model_contract(Path(__file__).resolve().parents[1],{'OAI-Sites-Authorization':'Bearer '+os.environ['CHI_SITE_SERVICE_TOKEN'].removeprefix('Bearer ')})
 cycle=os.environ.get('REFRESH_CYCLE','').strip()
 revisions={league:json.loads(subprocess.check_output(['gh','api',f'repos/TheMathNinja/{league}-GM-Dashboard/commits/main']))['sha']for league in receipts}
 signature=refresh_signature(receipts,cycle,revisions)
 current=call().get('current')or{}
 if current.get('receipt',{}).get('upstreamSignature')==signature:print('Personal forecasts already reflect these league publications.');return

 job=call('PUT',{'type':'queue','season':2026,'throughWeek':week,'league':os.environ['SOURCE_LEAGUE'],'upstreamSignature':signature,'upstreamRun':os.environ.get('UPSTREAM_RUN',''),'engineRevisions':revisions,'reuseReports':not bool(cycle) and current.get('throughWeek')==week})['job'];print('Personal refresh queued after league publications; completed results through Week',week)
 deadline=time.monotonic()+105*60
 while time.monotonic()<deadline:
  state=call();j=state.get('job')or{};current=state.get('current')or{}
  if current.get('throughWeek',0)>=week and current.get('receipt',{}).get('upstreamSignature')==signature:
   manifest=call(endpoint='weekly-values').get('manifest')or{}
   if manifest.get('forecastGeneratedAt')==current.get('generatedAt'):
    print('Personal forecasts and prepared player values published through Week',week);return
  if j.get('id')==job['id']and j.get('status')=='failed':raise RuntimeError(j.get('error','Personal refresh failed'))
  time.sleep(30)
 raise RuntimeError('Personal refresh did not finish. The previous forecast is preserved; check the existing Windows projections runner.')

def select_week(receipts,requested=''):
 weeks=[r.get('week',0) for r in receipts.values()]
 if len(weeks)!=2 or any(r.get('status')!='success' for r in receipts.values()) or len(set(weeks))!=1:return None
 week=weeks[0]
 if not isinstance(week,int) or not 1<=week<=16:return None
 return week if not requested or week==int(requested) else None

def refresh_signature(receipts,cycle='',revisions=None):
 # Scheduled provider recaptures must run even when score receipts are unchanged.
 value={'receipts':receipts,'captureCycle':cycle} if cycle else receipts
 if revisions:value={'publication':value,'engineRevisions':revisions}
 return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()
if __name__=='__main__':main()
