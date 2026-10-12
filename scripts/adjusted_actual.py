"""Adjusted actual PF: preserve active starters, fill eligible vacancies by weekly projection."""
import json,argparse,csv
from collections import defaultdict
from types import SimpleNamespace
from pathlib import Path
from lineup_status import many,ident,number,scheduled_teams,INACTIVE
from status_credits import status_code
from adjusted_lineup_selection import choose,replacement_rating

def calculate(data):
 season=int(data['season']);through=min(int(data['week']),12);rules=data['rules']['league']['starters'];limits={}
 for v in many(rules['position']):
  lohi=list(map(int,v['limit'].split('-')));p=v['name'];limits[p]=(lohi[0],lohi[-1],'off' if p in {'QB','RB','WR','TE'} else 'st' if p in {'PK','PN'} else 'def')
 totals={'off':int(rules['iop_starters']),'def':int(rules['idp_starters'])};totals['st']=int(rules['count'])-sum(totals.values())
 played=scheduled_teams(data['schedule']);statuses={w:{ident(r['id']):status_code(r['status']) for r in many(data['injuries'][str(w)]['injuries']['injury'])} for w in range(1,through+1)}
 roster=defaultdict(dict);members=defaultdict(dict);scores=[]
 for r in data['starters']:
  w=int(r['week']);fid=ident(r['franchise_id']).zfill(4)
  if w<=through:roster[w,fid][ident(r['player_id'])]=r
 for r in data['rosters']:members[int(r['week']),ident(r['franchise_id']).zfill(4)][ident(r['player_id'])]=str(r.get('roster_status','ROSTER')).upper()
 for r in data['scores']:
  w=int(r['week']);points=number(r.get('points'));pid=ident(r['player_id']);team=r.get('team','')
  if w<=through and (points!=0 or (statuses[w].get(pid,'') not in INACTIVE and team in played[w])):scores.append((w,pid,points))
 ids=sorted({fid for w,fid in roster});rows=[]
 if len(ids)!=32:raise ValueError('Expected 32 weekly rosters')
 for w in range(1,through+1):
  if str(w) not in data.get('projections',{}):raise ValueError('Missing weekly projection feed for adjusted PPG')
  body=data['projections'][str(w)];body=body.get('projectedScores',body);proj={ident(r['id']):number(r.get('score'),None) for r in many(body.get('playerScore'))}
  prior=defaultdict(list)
  for ww,pid,pts in scores:
   if ww<w:prior[pid].append(pts)
  for fid in ids:
   fixed=[];pool=[]
   for pid,r in roster[w,fid].items():
    active=statuses[w].get(pid,'') not in INACTIVE and r.get('team','') in played[w];starter=r.get('starter_status')=='starter'
    if not active or r.get('pos') not in limits:continue
    if starter:fixed.append(SimpleNamespace(player_id=pid,pos=r['pos'],player_score=number(r.get('player_score'))));continue
    if members[w,fid].get(pid,'UNKNOWN') not in {'ROSTER',''}:continue
    rating,source=replacement_rating(proj.get(pid),sum(prior[pid])/len(prior[pid]) if prior[pid] else 0.)
    pool.append(SimpleNamespace(player_id=pid,pos=r['pos'],player_score=number(r.get('player_score')),rating=rating))
   added=choose(fixed,pool,limits,totals);rows.append(dict(season=season,week=w,franchise_id=fid,adjusted_pf=sum(r.player_score for r in fixed+added)))
 return rows

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args();rows=calculate(json.loads(Path(a.input).read_text(encoding='utf-8-sig')));path=Path(a.output)
 old=list(csv.DictReader(path.open())) if path.exists() else [];season=rows[0]['season'];old=[r for r in old if int(r['season'])!=season]
 with path.open('w',newline='',encoding='utf8') as f:
  out=csv.DictWriter(f,fieldnames=['season','week','franchise_id','adjusted_pf']);out.writeheader();out.writerows(old+rows)
