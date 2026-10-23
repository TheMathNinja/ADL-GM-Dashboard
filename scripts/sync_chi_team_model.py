"""Update the owner-private Trade Analyzer with the canonical ADL team model.

No credentials, raw private requests, pending trades or valuations are exported.
"""
from pathlib import Path
import base64, datetime, hashlib, json, os, urllib.request, urllib.error
import numpy as np
import pandas as pd
from quarterly_bonus import forecast
from export_full_team_model import export_full_team_model

ROOT=Path(__file__).resolve().parents[1]
SITE='https://chi-team-tools.dreamytang7.chatgpt.site'

def snapshot_key(payload):
    return payload.get('snapshotKey') or (payload.get('metadata') or {}).get('snapshotKey')

def signature(root):
    h=hashlib.sha256()
    names=['data/weekly_team_metrics.csv','data/adl_scoring_model.json','data/lineup_status_credits_2026.csv']
    names += [str(p.relative_to(root)).replace('\\','/') for p in sorted((root/'data/player_strength').glob('*')) if p.suffix in ['.json','.csv']]
    names += ['scripts/sync_chi_team_model.py','scripts/export_full_team_model.py','scripts/player_team_strength.py','scripts/player_blend_scoring.py','scripts/bonus_predictor.py','scripts/quarterly_bonus.py','scripts/weekly_pairs.py']
    # No generated timestamp is part of the fingerprint unless its source changed.
    names=[n for n in names if not n.endswith('refresh_receipt.json')]
    for name in names:
        p=root/name
        if p.exists():h.update(name.encode());h.update(p.read_bytes())
    return h.hexdigest()

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
    try:
        with urllib.request.urlopen(urllib.request.Request(SITE+'/api/team-projections',headers=headers),timeout=30) as r:prior=json.load(r)
        if snapshot_key(prior)==key:print('ADL team model inputs unchanged.');return
    except urllib.error.HTTPError as e:
        if e.code!=404:raise RuntimeError('Cannot verify existing private team model') from None
    payload=build(ROOT,key)
    if payload is None:print('Regular-season scoring complete; no remaining team forecast.');return
    headers['Content-Type']='application/json'
    req=urllib.request.Request(SITE+'/api/team-projection-sync',data=json.dumps(payload,allow_nan=False,separators=(',',':')).encode(),headers=headers,method='POST')
    with urllib.request.urlopen(req,timeout=120) as response:result=json.load(response)
    if not result.get('ok'):raise RuntimeError('Private team model upload was rejected')
    print('ADL private team model updated through Week',payload['metadata']['throughWeek'])

if __name__=='__main__':main()
