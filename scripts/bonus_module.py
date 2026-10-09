"""Build a standalone weekly Bonus Games module from completed-week snapshots."""
from pathlib import Path
import argparse,json,re,html,sys
import numpy as np
import pandas as pd
import bonus_predictor as e
import quarterly_bonus as shared
from bonus_outlook_archive import DESCRIPTIONS,observed_weeks,merge_outlooks,preserve_playoff_pages
from datetime import datetime,timezone

def build(league,root,out,N=shared.DEFAULT_SIMULATIONS):
    previous_path=out/'snapshots.json'
    previous=json.loads(previous_path.read_text(encoding='utf8')) if previous_path.exists() else None
    data={}
    if league=='ADL':
        current=pd.read_csv(root/'data/weekly_team_metrics.csv',dtype={'franchise_id':str}).rename(columns={'franchise_score':'points','potential_points':'potential'})
        source=pd.read_csv(root/'data/score_metadata.csv').iloc[0].to_dict()
        raw=(root/'docs/playoff-picture/index.html').read_text(encoding='utf8')
        forecast=json.loads(re.search(r'const data=(.*?);\s*\n',raw).group(1))
        meta=[t for values in forecast.values() for t in values]
    else:
        current=pd.read_csv(root/'data/current_weekly.csv',dtype={'franchise_id':str})
        source=json.loads((root/'data/weekly_source_context.json').read_text())
        meta=source['meta']
        forecast=json.loads((root/'data/current_forecast.json').read_text())
        if 'conferences' in forecast:meta=[t for values in forecast['conferences'].values() for t in values]
    current.franchise_id=current.franchise_id.str.zfill(4)
    season=int(current.season.iloc[0]);last=min(12,int(current.week.max()));ids=sorted(current.franchise_id.unique())
    if int(source.get('week',last))<last:raise ValueError('Source metadata is behind current scores')
    if current.duplicated(['week','franchise_id']).any():raise ValueError('Duplicate current team-week')
    s=current.pivot(index='week',columns='franchise_id',values='points').reindex(index=range(1,last+1),columns=ids).to_numpy()
    p=current.pivot(index='week',columns='franchise_id',values='potential').reindex(index=range(1,last+1),columns=ids).to_numpy()
    assert len(ids)==32 and np.isfinite(s).all() and np.isfinite(p).all()
    # Training target never uses 2026. Pad future with NaNs to catch any accidental reads.
    data[season]=(ids,np.vstack([s,np.full((12-last,32),np.nan)]),np.vstack([p,np.full((12-last,32),np.nan)]))
    if league=="ADL":
        history=e.load_adl(root,season);history.update(data);data=history
    names={str(t.get('franchise_id',t.get('id'))).zfill(4):html.unescape(t.get('name','Team')) for t in meta}
    teams={str(t.get('franchise_id',t.get('id'))).zfill(4):t for t in meta}
    payload=dict(league=league,season=season,through_week=last,status=source.get('status',source.get('score_status','unknown')),updated_at=datetime.now(timezone.utc).isoformat(),simulations=N,weeks={},cutoffs={},models={})
    observed=observed_weeks(ids,s,p)
    payload['observations']={}
    payload['outlooks']={}
    for w in range(1,last+1):
        payload['observations'][str(w)]={str(j):observed[str(j)] for j in range(1,w+1)}
        payload['outlooks'][str(w)]=dict(kind='published' if w==last else 'reconstructed',published_at=payload['updated_at'],status=payload['status'])
        quarterly=shared.forecast(root,current,league,season,w,N)
        mu,sigma,tau,gap=quarterly['mu'],quarterly['sigma'],quarterly['tau'],quarterly['gap']
        payload['models'][str(w)]=dict(**quarterly['model'],weekly_sd=sigma,strength_sd=float(tau),team_means={team:float(mu[i]) for i,team in enumerate(ids)})
        payload['models'][str(w)]['description']=DESCRIPTIONS[league]
        forecasts=quarterly['events']
        probs={label:v['probabilities'] for label,v in forecasts.items()}
        payload['cutoffs'][str(w)]={label:{k:v for k,v in values.items() if k not in ['probabilities','expected_ap']} for label,values in forecasts.items()}
        rows=[]
        for i,team in enumerate(ids):
            events=[];bonus=[0,0,0]
            for label,a,b in e.EVENTS:
                seen=max(0,min(w,b)-a)
                aps=e.ap(s[a:min(w,b)]).sum(0) if seen else np.zeros(32)
                pts=s[a:min(w,b)].sum(0) if seen else np.zeros(32)
                pots=p[a:min(w,b)].sum(0) if seen else np.zeros(32)
                rank=np.argsort(np.lexsort((-(pots),-pts,-aps)))+1 if seen else np.full(32,np.nan)
                finished=w>=b
                if finished:
                    actual=e.outcomes(aps,pts,pots);pr=np.eye(3)[actual[i]];bonus[int(actual[i])]+=1
                else:pr=probs[label][i]
                events.append(dict(event=label,start=a+1,end=b,elapsed=seen,ap=float(aps[i]),projected_ap=float(forecasts[label]['expected_ap'][i]),ap_games=31*seen,rank=int(rank[i]) if seen else None,points=float(pts[i]),potential_points=float(pots[i]),p_loss=float(pr[0]),p_tie=float(pr[1]),p_win=float(pr[2]),credit=float(pr[2]+.5*pr[1]),completed=finished))
            allp=e.ap(s[:w]).sum(0);tie=((s[:w,:,None]==s[:w,None,:]).sum(-1)-1).sum(0)
            apwins=allp[i]-.5*tie[i];aploss=31*w-apwins-tie[i]
            # H2H records from saved matchup opponents, recomputed at this historical checkpoint.
            t=teams.get(team,{});games=t.get('actualDetails',{}).get('matchups',[])+t.get('winDetails',{}).get('matchups',[])
            byname={v:k for k,v in names.items()};hw=hl=ht=0;count=0
            for wk in range(1,w+1):
                matches=[g for g in games if int(g.get('week',0))==wk]
                if not matches:continue
                opponent=byname.get(html.unescape(matches[0].get('opponent','')))
                if opponent not in ids:continue
                diff=s[wk-1,i]-s[wk-1,ids.index(opponent)];hw+=int(diff>0);hl+=int(diff<0);ht+=int(diff==0);count+=1
            if league=='FAFL' and count!=w:
                context=json.loads((root/'data/weekly_source_context.json').read_text());opp=np.array(context['opp']);original=[str(f['id']).zfill(4) for f in context['meta']]
                j=original.index(team);hw=hl=ht=0
                for wk in range(w):
                    oi=ids.index(original[int(opp[wk,j])]);diff=s[wk,i]-s[wk,oi];hw+=int(diff>0);hl+=int(diff<0);ht+=int(diff==0)
                count=w
            record=f'{hw+bonus[2]}-{hl+bonus[0]}-{ht+bonus[1]}' if count==w else '—'
            rows.append(dict(id=team,name=names.get(team,team),logo=t.get('logo',''),record=record,h2h=f'{hw}-{hl}-{ht}' if count==w else '—',bonus=f'{bonus[2]}-{bonus[0]}-{bonus[1]}',allplay=f'{int(apwins)}-{int(aploss)}-{int(tie[i])}',ppg=float(s[:w,i].mean()),potential=float(p[:w,i].mean()),expected_bonus=sum(z['credit'] for z in events),events=events))
        payload['weeks'][str(w)]=rows
        print(league,'snapshot',w,flush=True)
    out.mkdir(parents=True,exist_ok=True)
    merge_outlooks(payload,previous)
    preserve_playoff_pages(root,out,payload)
    (out/'snapshots.json').write_text(json.dumps(payload,indent=2,allow_nan=False),encoding='utf8')
    template=(Path(__file__).parent/'bonus_template.html').read_text(encoding='utf8')
    groups=forecast.get('conferences',forecast)
    conference_by_id={str(t.get('franchise_id',t.get('id'))).zfill(4):conf for conf,items in groups.items() if conf in ['NFC','AFC'] for t in items}
    if len(conference_by_id)!=32:raise ValueError('Incomplete Bonus Games conference metadata')
    template=template.replace('__CONFERENCES__',json.dumps(conference_by_id))
    template=template.replace('__LEAGUE__',league).replace('__DATA__',json.dumps(payload,allow_nan=False).replace('</','<\\/'))
    (out/'index.html').write_text(template,encoding='utf8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--league',choices=['ADL','FAFL'],required=True);parser.add_argument('--root',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--simulations',type=int,default=shared.DEFAULT_SIMULATIONS);a=parser.parse_args()
    assert a.simulations>0 and a.simulations%2==0
    build(a.league,a.root,a.out,a.simulations)
