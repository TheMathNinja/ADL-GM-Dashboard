"""Preserve published outlook values and their matching Playoff pages."""
from pathlib import Path
from copy import deepcopy
import json
import numpy as np
DESCRIPTIONS={
 'ADL':'Quarterly and Reg Season forecasts estimate team scoring ability from Potential PPG using Empirical-Bayes estimates trained on normalized seasons beginning in 2018. The simulations include Normal weekly scoring variation and week-specific uncertainty about team strength. Bonus Games and Playoffs share these Bonus Game forecasts.',
 'FAFL':'Forecasts use the playoff engine’s scoring estimates and week-specific uncertainty about team strength. Quarterly simulations use Student-t scoring variation with 5 degrees of freedom; Reg Season simulations use Normal scoring variation. Bonus Games and Playoffs share these Bonus Game forecasts.'}

def observed_weeks(ids,s,p):
 result={}
 for week,(points,potential) in enumerate(zip(s,p),1):
  wins=(points[:,None]>points[None,:]).sum(1);ties=(points[:,None]==points[None,:]).sum(1)-1;ap=wins+.5*ties;rank=np.argsort(np.lexsort((-potential,-points,-ap)))+1;rows=[]
  for i,team in enumerate(ids):
   equal=(ap==ap[i])&(points==points[i])&(potential==potential[i]);rows.append(dict(id=team,points=float(points[i]),potential=float(potential[i]),record=f'{int(wins[i])}-{int(31-wins[i]-ties[i])}-{int(ties[i])}',ap=float(ap[i]),rank=int(rank[i]),tied=bool(equal.sum()>1)))
  result[str(week)]=rows
 return result

def merge_outlooks(payload,previous):
 """Older published weeks are immutable; the active week may be refreshed."""
 if previous and int(previous['season'])==int(payload['season']):
  if int(previous['through_week'])>int(payload['through_week']):raise ValueError('Refusing to roll published outlooks backwards')
  for w in range(1,int(payload['through_week'])):
   key=str(w)
   if key not in previous['weeks'] or previous.get('outlooks',{}).get(key,{}).get('kind')=='reconstructed':continue
   for section in ['weeks','cutoffs','models','observations','outlooks']:
    if key in previous.get(section,{}):payload.setdefault(section,{})[key]=deepcopy(previous[section][key])
 return payload

def preserve_playoff_pages(root,out,payload):
 """Keep past Playoffs and Bonus outlooks on the same saved forecast."""
 season=int(payload['season']);last=int(payload['through_week']);archive=out/'outlooks'/str(season);archive.mkdir(parents=True,exist_ok=True)
 for w in range(1,last+1):
  saved=archive/f'through-week-{w:02}-playoffs.html'
  target=root/'docs/playoff-picture'/('index.html' if w==last else f'ADL_{season}_W{w+1:02}_playoff_and_draft_forecast.html' if payload['league']=='ADL' else f'week-{w+1:02}.html')
  if w<last:
   if payload['outlooks'][str(w)].get('kind')=='reconstructed':
    if not target.exists():raise ValueError('Missing reconstructed Playoff page')
    saved.write_bytes(target.read_bytes())
   else:
    if not saved.exists():raise ValueError(f'Missing archived Playoff outlook: {saved}')
    target.write_bytes(saved.read_bytes())
  else:
   if not target.exists():raise ValueError('Missing current Playoff page')
   saved.write_bytes(target.read_bytes())
 for w in range(1,last+1):
  key=str(w);packet={name:payload[name][key] for name in ['weeks','cutoffs','models','observations','outlooks']};packet.update(league=payload['league'],season=season,through_week=w)
  (archive/f'through-week-{w:02}.json').write_text(json.dumps(packet,indent=2,allow_nan=False),encoding='utf8')
