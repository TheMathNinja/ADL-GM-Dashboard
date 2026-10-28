"""Update the owner-private Trade Analyzer with the canonical ADL team model.

No credentials, raw private requests, pending trades or valuations are exported.
"""
from pathlib import Path
import base64, datetime, json, os, urllib.request, urllib.error
import numpy as np
import pandas as pd
from quarterly_bonus import forecast
from export_full_team_model import export_full_team_model
from check_chi_team_model_refresh import signature, snapshot_key, ensure_site_model_contract

ROOT=Path(__file__).resolve().parents[1]
SITE='https://chi-team-tools.dreamytang7.chatgpt.site'

def build(root,key):
    def get(kind):
        req=urllib.request.Request(f'https://api.myfantasyleague.com/2026/export?TYPE={kind}&L=60206&JSON=1',headers={'User-Agent':'CHI-Team-Tools/2.0'})
        with urllib.request.urlopen(req,timeout=60) as r:return json.load(r)[kind]
    league=get('league');schedule=get('schedule');ids=[f'{i:04}' for i in range(1,33)]
    franchises={r['id']:r for r in league['franchises']['franchise']}
    opp=np.full((12,32),-1,int)
    for w in schedule['weeklySchedule']:
        week=int(w['week'])
        if week>12:continue
        for match in w['matchup']:
            a,b=[ids.index(t['id']) for t in match['franchise']];opp[week-1,a]=b;opp[week-1,b]=a
    assert (opp>=0).all()
    division=league['divisions']['division'];divmap={r['id']:r['conference'] for r in division}
    conf=[[i for i,t in enumerate(ids) if divmap[franchises[t]['division']]==c] for c in sorted(set(divmap.values()))]
    div=[[i for i,t in enumerate(ids) if franchises[t]['division']==d['id']] for d in division]
    current=pd.read_csv(root/'data/weekly_team_metrics.csv',dtype={'franchise_id':str}).rename(columns={'franchise_score':'points','potential_points':'potential'})
    week=int(current.week.max());n=2048
    if week>=12:return None
    f=forecast(root,current,'ADL',2026,week,n);assert f['ids']==ids
    paths=np.stack([f['future'],f['future_potential']],axis=-1).astype('<f8')
    rules=league['starters'];limits={}
    for p in rules['position']:
        a=list(map(int,p['limit'].split('-')));name=p['name'];limits[name]=[a[0],a[-1],'off' if name in ['QB','RB','WR','TE'] else 'st' if name in ['PK','PN'] else 'def']
    totals={'off':int(rules.get('iop_starters',7)),'def':int(rules['idp_starters'])};totals['st']=int(rules['count'])-sum(totals.values())
    nfl=pd.read_csv(root/'data/nfl_schedule_2026.csv');played={str(w):g.loc[~g.is_bye.astype(str).str.upper().eq('TRUE'),'mfl_team'].tolist() for w,g in nfl.groupby('week')}
    m=dict(league='ADL',season=2026,throughWeek=week,startWeek=week+1,endWeek=12,simulations=n,ids=ids,opp=opp.tolist(),conf=conf,div=div,observed=f['s'].tolist(),observedPotential=f['p'].tolist(),limits=limits,totals=totals,played=played,model=f['model'],revision=os.environ.get('GITHUB_SHA','local'),generatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),snapshotKey=key)
    m['fullModel']=export_full_team_model(root,week,m,f)
    return dict(metadata=m,paths=base64.b64encode(paths.tobytes()).decode())

def main():
    token=os.environ['CHI_SITE_SERVICE_TOKEN'];key=signature(ROOT);headers={'OAI-Sites-Authorization':'Bearer '+token,'User-Agent':'CHI-Team-Tools/2.0'}
    contract=ensure_site_model_contract(ROOT,headers)
    if snapshot_key(contract)==key:print('ADL team model inputs unchanged.');return
    payload=build(ROOT,key)
    if payload is None:print('Regular-season scoring complete; no remaining team forecast.');return
    headers['Content-Type']='application/json'
    req=urllib.request.Request(SITE+'/api/team-projection-sync',data=json.dumps(payload,allow_nan=False,separators=(',',':')).encode(),headers=headers,method='POST')
    try:
        with urllib.request.urlopen(req,timeout=120) as response:result=json.load(response)
    except urllib.error.HTTPError as e:
        # Only predefined diagnostic fields are safe to expose in Actions logs.
        reason='request rejected'
        try:
            error=json.load(e)
            if isinstance(error,dict) and error.get('error') in ('Unsupported ADL model version','Invalid ADL model weights'):
                reason=error['error']
        except (ValueError,TypeError):pass
        raise RuntimeError(f'Private team model upload failed (HTTP {e.code}): {reason}') from None
    if not result.get('ok'):raise RuntimeError('Private team model upload was rejected')
    # The normal GET is pinned to the completed forecast package, not this upload.
    with urllib.request.urlopen(urllib.request.Request(SITE+'/api/team-projections?version='+key,headers=headers),timeout=30) as response:verified=json.load(response)
    if snapshot_key(verified)!=key:raise RuntimeError('Private team model upload did not verify on read-back')
    if snapshot_key(ensure_site_model_contract(ROOT,headers))!=key:raise RuntimeError('Private team model upload pointer did not verify')
    print('ADL private team model updated through Week',payload['metadata']['throughWeek'])

if __name__=='__main__':main()
