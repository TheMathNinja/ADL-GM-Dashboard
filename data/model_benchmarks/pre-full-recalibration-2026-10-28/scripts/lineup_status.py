"""Availability-adjusted potential PPG, using weekly MFL evidence only."""
import argparse, csv, json, math
from collections import defaultdict
from pathlib import Path
from status_credits import best_lineup, player_credit, status_code

INACTIVE={'O','S','IR-R','IR','I','IR-PUP','IR-NFI','PUP','NFI'}
def many(x):
    return x if isinstance(x,list) else ([] if x is None else [x])
def ident(x):
    return str(x).removesuffix('.0')
def number(x, default=0.):
    try:
        v=float(x)
        return v if math.isfinite(v) else default
    except (TypeError,ValueError): return default
def player_value(pre, scores, k):
    actual=sum(scores)/len(scores) if scores else None
    if pre is None:return max(0,actual or 0)
    if actual is None:return max(0,pre)
    return (k*max(0,pre)+len(scores)*max(0,actual))/(k+len(scores))

def scheduled_teams(schedule):
    schedule=schedule.get('fullNflSchedule',schedule)
    # MFL includes empty future postseason weeks in the current-year ALL feed.
    return {int(w['week']):{t['id'] for g in many(w['matchup']) for t in many(g['team'])}
            for w in many(schedule['nflSchedule']) if w.get('matchup')}

def calculate(data, model, preseason):
    season=int(data['season']);through=min(int(data['week']),11)
    if season<=max(model['training_years']):raise ValueError('Production fit cannot backcast training seasons')
    weights=model['status_weights']
    assert all(0<=v<=1 for v in weights.values())
    starters=data['rules']['league']['starters'];limits={}
    for p in many(starters['position']):
        a=list(map(int,p['limit'].split('-')));pos=p['name']
        group='off' if pos in {'QB','RB','WR','TE'} else ('st' if pos in {'PK','PN'} else 'def')
        limits[pos]=(a[0],a[-1],group)
    totals={'off':int(starters['iop_starters']),'def':int(starters['idp_starters'])}
    totals['st']=int(starters['count'])-sum(totals.values())
    played=scheduled_teams(data['schedule'])
    if not all(w in played for w in range(1,through+1)):raise ValueError('Missing completed NFL schedule week')
    teams=set.union(*played.values());status={}
    for w in range(1,through+1):
        r=data['injuries'][str(w)]['injuries']
        if int(r['week'])!=w or not r.get('injury'):raise ValueError(f'Missing MFL injury report week {w}')
        status[w]={ident(p['id']):status_code(p['status']) for p in many(r['injury'])}
    groups=defaultdict(list);ir=defaultdict(list);score_rows=defaultdict(list)
    for r in data['starters']:
        w=int(r['week'])
        if w<=through:groups[w,ident(r['franchise_id']).zfill(4)].append(r)
    for r in data['rosters']:
        if str(r['roster_status']).upper() in {'INJURED_RESERVE','IR','INJURED RESERVE'}:
            ir[int(r['week']),ident(r['franchise_id']).zfill(4)].append(r)
    seen=set()
    for r in data['scores']:
        w=int(r['week']);pid=ident(r['player_id']);key=(w,pid)
        if w>through:continue
        if key in seen:raise ValueError('Duplicate player score')
        seen.add(key);p=number(r['points'])
        if not (p==0 and status[w].get(pid,'') in INACTIVE):score_rows[pid].append((w,p))
    ids=sorted({f for w,f in groups});assert len(ids)==32
    basegames={}
    for w in range(1,through+1):
        for fid in ids:
            rows=groups[w,fid]
            if not rows:raise ValueError(f'Missing weekly lineup {w} {fid}')
            ps=[dict(id=ident(r['player_id']),pos=r['pos'],points=number(r['player_score']),team=r['team']) for r in rows]
            ps += [dict(id=f'empty_{pos}_{i}',pos=pos,points=0,team='')
                   for pos,(lo,_,_) in limits.items() for i in range(max(0,lo-sum(p['pos']==pos for p in ps)))]
            baseline=best_lineup(ps,limits,totals)
            known={p['id'] for p in ps}
            ps += [dict(id=ident(r['player_id']),pos=r['pos'],points=0,team=r['team'],virtual_ir=True)
                   for r in ir[w,fid] if ident(r['player_id']) not in known and r['pos'] in limits]
            for p in ps:
                s=status[w].get(p['id'],'')
                if s not in INACTIVE and p['team'] in teams-played[w]:s='BYE'
                p['nfl_status']=s
            basegames[w,fid]=(ps,baseline)
    output=[]
    for cutoff in range(1,through+1):
        for fid in ids:
            total=0
            for w in range(1,cutoff+1):
                ps,base=basegames[w,fid];adjusted=[]
                for p in ps:
                    q=dict(p,estimated_ppg=player_value(preseason.get(p['id']),
                           [s for wk,s in score_rows[p['id']] if wk<=cutoff],model['k']))
                    if not q.get('virtual_ir') or player_credit(q,weights)>0:adjusted.append(q)
                total+=max(0,best_lineup(adjusted,limits,totals,True,weights)-base)
            output.append(dict(season=season,week=cutoff,franchise_id=fid,lineup_credit_ppg=total/cutoff,model_version=model['version']))
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();data=json.loads(Path(a.input).read_text(encoding='utf-8-sig'))
    model=json.loads(Path('data/lineup_status_model.json').read_text())
    pre={r['player_id']:float(r['preseason_ppg']) for r in csv.DictReader(open(f"data/lineup_preseason_{data['season']}.csv",encoding='utf-8-sig'))}
    rows=calculate(data,model,pre)
    with open(a.output,'w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(f"Built {len(rows)} team/cutoff lineup credits: {model['version']}")
