"""R05/L17 current-roster inputs, shared team forecast and historical rating."""
from pathlib import Path
from types import SimpleNamespace
from collections import defaultdict
import argparse,json,warnings
import numpy as np,pandas as pd
from player_strength_core import Study,POSITIONS,CLUBS,mapped
from player_positive_core import prepare,run
from adjusted_lineup_selection import choose
warnings.filterwarnings('ignore',message='Mean of empty slice')

RATING_HISTORY_START = 2022

def _rating_index(rows,ids,week,rating_case):
 """Return a league-centred pure roster index for one season/checkpoint."""
 rows=rows[rows.week==week];fields=[]
 for key in ['starter_strength','roster_strength']:
  a=rows.pivot(index='target_week',columns='franchise_id',values=key).reindex(index=range(week+1,13),columns=ids).to_numpy()
  if not np.isfinite(a).all():raise ValueError('Missing historical roster strength '+str(week))
  fields.append(a)
 raw=(np.stack(fields,-1)*np.asarray(rating_case['conversion'][2:]))@np.asarray(rating_case['weights'][2:]);raw=raw.mean(0)
 return 100*raw/raw.mean()

def historical_roster_rating(root,season,week,ids,current_rows,rating_case):
 """Map roster strength to 0–10 against same-week ADL history."""
 root=Path(root);archive=pd.read_csv(root/'data/player_strength/historical_team_strength.csv',dtype={'franchise_id':str});archive=archive[(archive.season>=RATING_HISTORY_START)&(archive.season<season)];reference=[]
 for year,g in archive.groupby('season'):
  if week not in set(g.week):continue
  year_ids=sorted(g.franchise_id.unique())
  if len(year_ids)!=32:raise ValueError('Incomplete historical roster-strength season '+str(year))
  reference.extend(_rating_index(g,year_ids,week,rating_case))
 current=_rating_index(current_rows,ids,week,rating_case);reference=np.asarray(reference+current.tolist())
 if len(reference)<=len(current):raise ValueError('Missing prior same-week roster-strength history')
 lo,hi=float(reference.min()),float(reference.max())
 if not lo<100<hi:raise ValueError('Invalid historical roster-strength anchors')
 scaled=np.where(current<=100,5*(current-lo)/(100-lo),5+5*(current-100)/(hi-100))
 return np.clip(scaled,0,10),dict(minimum=lo,average=100.,maximum=hi,start=RATING_HISTORY_START,end=season,week=week)

class RuntimeStudy(Study):
 def __init__(self,root,season):
  self.league='ADL';self.opp_cache={};self.allowed={};self.cubes={};d=Path(root)/'data/player_strength'
  self.panel=pd.read_csv(d/'player_weeks.csv',dtype={'player_id':str});self.games=pd.read_csv(d/'opponent_games.csv');self.schedule=pd.read_csv(d/'nfl_schedule.csv');self.opp={(int(r.season),int(r.week),r.team):r.opponent for r in self.schedule.itertuples()}
  for (year,pos),g in self.games.groupby(['season','pos']):self.allowed[int(year),pos]=g.pivot(index='week',columns='team',values='allowed').reindex(index=range(1,18),columns=CLUBS).to_numpy()
  for (year,pos),g in self.panel[self.panel.first_fs.notna()].groupby(['season','pos']):
   ids=sorted(g.player_id.unique());c={'ids':ids}
   for col in ['active_score','realized_points','points','projection','team','injury_status','inactive','scheduled_bye']:c[col]=g.pivot(index='week',columns='player_id',values=col).reindex(index=range(1,18),columns=ids).to_numpy()
   c['first_fs']=g[g.week==1].set_index('player_id').reindex(ids).first_fs.to_numpy();c['known_out']=np.isin(c['injury_status'],['OUT','O','SUSPENDED','S','IR','IR-R','INJURED RESERVE - DESIGNATED FOR RETURN']);self.cubes[int(year),pos]=c

def build(root,season,through):
 root=Path(root);d=root/'data/player_strength';s=RuntimeStudy(root,season);fits={r['pos']:r for r in json.loads((d/f'fits_{season}.json').read_text())};membership=pd.read_csv(d/'fantasy_rosters.csv',dtype={'player_id':str,'franchise_id':str});rules=json.loads((d/'rules.json').read_text());rule=rules.get('league',rules)['starters'];limits={}
 for v in rule['position']:
  lohi=list(map(int,v['limit'].split('-')));p=v['name'];limits[p]=(lohi[0],lohi[-1],'off' if p in ['QB','RB','WR','TE'] else 'st' if p in ['PK','PN'] else 'def')
 totals={'off':int(rule.get('iop_starters',7)),'def':int(rule['idp_starters'])};totals['st']=int(rule['count'])-sum(totals.values());predictions={};fallback={}
 for pos in POSITIONS:
  rec=fits[pos];f={**rec['prior'],'train':[]};assert max(rec['training_years'])<season;c=s.cubes[season,pos];states,_,_=run(prepare(s,season,pos,f),f,'off',rec['q']);fallback[pos]=float(mapped(f['prior'],[0.])[0])
  for w in range(min(through,11)+1):
   state=states[w];past=np.where(np.isfinite(c['active_score'][:w]),1.,np.where(c['inactive'][:w]==1,0.,np.nan))
   for j in range(w):past[j]=np.where([(season,j+1,str(t)) in s.opp for t in c['team'][j]],past[j],np.nan)
   av=f['availability'];prob=(av['k']*av['mean']+np.nansum(past,0))/(av['k']+np.isfinite(past).sum(0))
   for target in range(w+1,13):
    delta,_,play=s.context(season,pos,f['opponent'],w,c['team'][w],target);allowed=play.copy()
    if target==w+1:allowed&=~c['known_out'][w]
    expected=np.maximum(0,state['mean']*(1+f['opponent_effect']*delta))*prob*allowed
    for pid,value in zip(c['ids'],expected):predictions[w,target,pid]=float(value)
 raw=pd.read_csv(d/'score_archive.csv',dtype={'player_id':str});history={str(pid):g for pid,g in raw.groupby('player_id')};fallback_cache={};rows=[]
 for w in range(1,min(through,11)+1):
  roster=membership[membership.week==w]
  if roster.franchise_id.nunique()!=32:raise ValueError('Incomplete fantasy ownership checkpoint '+str(w))
  for fid,g in roster.groupby('franchise_id'):
   for target in range(w+1,13):
    candidates=[];roster_total=0.;missing=0
    for r in g.itertuples():
     if r.pos not in limits:continue
     key=w,target,r.player_id;value=predictions.get(key)
     if value is None:
      missing+=1
      if key not in fallback_cache:
       f=fits[r.pos]['prior'];past=history.get(r.player_id,pd.DataFrame(columns=['week','active_score','team']));past=past[past.week<=w];a=past.active_score.dropna().to_numpy();gain=f['Pa']/(f['Pa']+f['Ra']/len(a)) if len(a) else 0.;ability=(1-gain)*fallback[r.pos]+gain*(a.mean() if len(a) else fallback[r.pos]);club=str(past.sort_values('week').iloc[-1].team) if len(past) else str(r.team);fallback_cache[key]=max(0,ability)*f['availability']['mean']*((season,target,club) in s.opp)
      value=fallback_cache[key]
     roster_total+=value
     if str(r.roster_status).upper() in ['ROSTER','ACTIVE','','STARTER','NONSTARTER']:candidates.append(SimpleNamespace(player_id=r.player_id,pos=r.pos,rating=value))
    selected=choose([],candidates,limits,totals);rows.append(dict(season=season,week=w,target_week=target,franchise_id=fid,starter_strength=sum(p.rating for p in selected),roster_strength=roster_total,fallback_players=missing,starter_count=len(selected)))
 result=pd.DataFrame(rows);assert np.isfinite(result[['starter_strength','roster_strength']]).all().all();result.to_csv(d/f'team_strength_{season}.csv',index=False);return result

def write_outlooks(root,season,through):
 from bonus_predictor import load_adl,adl_availability_credit
 from fit_adl_scoring import parameters
 root=Path(root);current=pd.read_csv(root/'data/weekly_team_metrics.csv',dtype={'franchise_id':str});ids=sorted(current.franchise_id.unique());data=load_adl(root,season);scores=current.pivot(index='week',columns='franchise_id',values='franchise_score').reindex(index=range(1,13),columns=ids).to_numpy();pot=current.pivot(index='week',columns='franchise_id',values='potential_points').reindex(index=range(1,13),columns=ids).to_numpy();data[season]=(ids,scores,pot);rows=[]
 for w in range(1,min(through,11)+1):
  credit=adl_availability_credit(root,season,w,ids);mu,sd,tau,gap,meta=parameters(root,data,season,w,credit);rating_case=meta['cases']['roster_rating'];team_rows=pd.read_csv(root/f'data/player_strength/team_strength_{season}.csv',dtype={'franchise_id':str});rating,anchors=historical_roster_rating(root,season,w,ids,team_rows,rating_case);ranks=pd.Series(np.round(rating,6)).rank(ascending=False,method='min').astype(int)
  for i,fid in enumerate(ids):rows.append(dict(season=season,week=w,franchise_id=fid,forecast_mean=float(mu[:,i].mean()),roster_strength=float(rating[i]),roster_strength_rank=int(ranks.iloc[i]),rating_model='historical-week-0-10 (0/0/90/10)',rating_history_start=anchors['start'],rating_history_end=anchors['end'],rating_anchor_week=anchors['week'],forecast_model='35/0/55/10'))
 pd.DataFrame(rows).to_csv(root/f'data/player_team_outlooks_{season}.csv',index=False)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--season',type=int,default=2026);p.add_argument('--week',type=int,required=True);a=p.parse_args();build(a.root,a.season,a.week);write_outlooks(a.root,a.season,a.week);print('Updated player-based team strength through',a.week)
