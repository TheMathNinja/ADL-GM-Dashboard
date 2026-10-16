"""R05/L17 current-roster inputs, shared team forecast and 100-centred rating."""
from pathlib import Path
from types import SimpleNamespace
from collections import defaultdict
import argparse,json,warnings
import numpy as np,pandas as pd
from player_strength_core import Study,POSITIONS,CLUBS,mapped
from player_positive_core import prepare,run
from adjusted_lineup_selection import choose
warnings.filterwarnings('ignore',message='Mean of empty slice')

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
  credit=adl_availability_credit(root,season,w,ids);mu,sd,tau,gap,meta=parameters(root,data,season,w,credit);rating_mu,_,_,_,_=parameters(root,data,season,w,credit,case='roster_rating');rating=100*rating_mu.mean(0)/scores[:w].mean();ranks=pd.Series(np.round(rating,6)).rank(ascending=False,method='min').astype(int)
  for i,fid in enumerate(ids):rows.append(dict(season=season,week=w,franchise_id=fid,forecast_mean=float(mu[:,i].mean()),roster_strength=float(rating[i]),roster_strength_rank=int(ranks.iloc[i]),rating_model='0/0/90/10',forecast_model='35/0/55/10'))
 pd.DataFrame(rows).to_csv(root/f'data/player_team_outlooks_{season}.csv',index=False)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--season',type=int,default=2026);p.add_argument('--week',type=int,required=True);a=p.parse_args();build(a.root,a.season,a.week);write_outlooks(a.root,a.season,a.week);print('Updated player-based team strength through',a.week)
