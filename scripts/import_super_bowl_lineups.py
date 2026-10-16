"""Refresh archived Super Bowl starters from season-specific public MFL exports.

Run from either dashboard: python scripts/import_super_bowl_lineups.py --league ADL
(or --league FAFL). Published finals remain unchanged; source differences are
retained explicitly for the lineup popover. Re-run after scoring corrections.
"""
import argparse,json,tempfile,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def arr(value):return value if isinstance(value,list) else ([] if value is None else [value])
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--league',choices=['ADL','FAFL'],required=True)
 args=parser.parse_args();league=args.league
 archive=json.loads((ROOT/'docs/trophy-room/data.json').read_text(encoding='utf8'))
 history=json.loads((ROOT/'data/gm_career_seasons.json').read_text(encoding='utf8'))
 def export(year,kind,**params):
  from urllib.parse import urlencode
  url=f'https://api.myfantasyleague.com/{year}/export?'+urlencode(dict(TYPE=kind,JSON=1,**params))
  req=urllib.request.Request(url,headers={'User-Agent':f'{league}-GM-Dashboard-Trophy-Room/1.0'})
  with urllib.request.urlopen(req,timeout=90) as response:raw=json.load(response)
  if kind not in raw:raise ValueError(f'Missing MFL {kind} payload: {year}')
  return raw[kind],url
 result={}
 for champion in archive['champions']:
  year=champion['year'];week=16 if year<2021 else 17
  league_id=60206 if league=='ADL' else {2014:37677,2015:27312}.get(year,22686)
  weekly,url=export(year,'weeklyResults',L=league_id,W=week,MISSING_AS_BYE=1)
  metadata,_=export(year,'players');players={p['id']:p for p in arr(metadata['player'])}
  franchises=arr(weekly.get('franchise'))+[f for m in arr(weekly.get('matchup')) for f in arr(m.get('franchise'))]
  teams=[]
  for name,final in zip([champion['champion'],champion['runner']],map(float,champion['score'].split(' - '))):
   fid=next(r['franchise_id'] for r in history if r['season']==year and r['name']==name)
   source=next(f for f in franchises if f['id']==fid)
   lineup=[dict(id=p['id'],name=players[p['id']]['name'],position=players[p['id']].get('position',''),nflTeam=players[p['id']].get('team',''),points=float(p.get('score') or 0)) for p in arr(source.get('player')) if p.get('status')=='starter']
   assert lineup and len({p['id'] for p in lineup})==len(lineup),(year,name,'invalid lineup')
   teams.append(dict(franchise=name,franchiseId=fid,total=float(source['score']),starterTotal=round(sum(p['points'] for p in lineup),1),publishedTotal=final,players=lineup))
  result[str(year)]=dict(year=year,week=week,teams=teams,source=url)
 for relative in ['data/trophy_room/super_bowl_lineups.json','docs/trophy-room/lineups.json']:
  dest=ROOT/relative;dest.parent.mkdir(parents=True,exist_ok=True)
  dest.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
 print(f'{league}: imported {len(result)} Super Bowl lineups from MFL')
if __name__=='__main__':main()
