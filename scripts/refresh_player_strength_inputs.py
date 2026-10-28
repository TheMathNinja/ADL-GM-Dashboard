"""Refresh public player-model inputs from the same completed-week score run."""
from pathlib import Path
import argparse,json,re,unicodedata
import numpy as np,pandas as pd
from lineup_status import many,ident,number
from status_credits import status_code
ALIASES={'NE':'NEP','SF':'SFO','GB':'GBP','KC':'KCC','NO':'NOS','TB':'TBB','JAX':'JAC','ARZ':'ARI','LV':'LVR','OAK':'LVR','SD':'LAC','SDC':'LAC','LA':'LAR','STL':'LAR','WSH':'WAS','WFT':'WAS'}
def club(v):return ALIASES.get(str(v),str(v))

def canonical_player_name(value):
 text=str(value)
 if ',' in text:
  last,first=text.split(',',1);text=first+' '+last
 text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode().casefold()
 words=re.sub(r'[^a-z0-9]+',' ',text).split()
 while words and words[-1] in {'jr','sr','ii','iii','iv','v'}:words.pop()
 return ' '.join(words)

def restore_verified_historical_teams(scores,archive,schedule,season):
 # MFL's current player team can become FA after a release. Reuse only the
 # exact prior season/week/player score, never infer past teams from ownership.
 result=scores.copy()
 if archive.empty:return result
 archive=archive[archive.season.eq(season)].copy();archive.player_id=archive.player_id.map(ident)
 if archive.duplicated(['week','player_id']).any():raise ValueError('Ambiguous historical player-score identity')
 prior=archive.set_index(['week','player_id']);games=set(zip(schedule.week,schedule.team))
 for index,row in result.iterrows():
  key=(row.week,row.player_id)
  if (row.week,row.team) in games or key not in prior.index:continue
  old=prior.loc[key];team=club(old.team)
  if (row.week,team) not in games or str(old.pos)!=str(row.pos):continue
  if not np.isfinite(row.points) or not np.isfinite(old.points) or abs(row.points-old.points)>1e-9:continue
  if canonical_player_name(old.player_name)!=canonical_player_name(row.player_name):continue
  result.at[index,'team']=team
 return result
def refresh(root,data):
 if not data.get('current_rosters'):raise ValueError('A freshly fetched current fantasy roster is required')
 d=Path(root)/'data/player_strength';season=int(data['season']);through=min(int(data['week']),17);scores=pd.DataFrame(data['scores']);scores['player_id']=scores.player_id.map(ident);scores=scores[scores.week.between(1,through)].copy();scores['points']=pd.to_numeric(scores.points,errors='coerce');scores.team=scores.team.map(club)
 if scores.duplicated(['week','player_id']).any():raise ValueError('Duplicate public player score')
 nfl=pd.DataFrame(data['nfl_rosters']);nfl=nfl[nfl.game_type=='REG'].copy();nfl.week=pd.to_numeric(nfl.week).astype(int);bridge=pd.read_csv(d/'player_ids.csv',dtype=str);resolved=[]
 for field in ['gsis_id','espn_id','sportradar_id','pfr_id']:
  if field not in nfl:continue
  ids=bridge[['mfl_id',field]].dropna().drop_duplicates();ids=ids[~ids[field].duplicated(keep=False)];nf=nfl.copy();nf[field]=nf[field].astype(str);x=nf.merge(ids,on=field);resolved.append(x[['week','mfl_id','team','status']])
 # New MFL IDs can precede the public crosswalk. Match a full name only when
 # it identifies exactly one MFL player and one NFL identity across the archive.
 if 'player_name' in scores and 'full_name' in nfl:
  names=scores[['player_id','player_name']].dropna().drop_duplicates('player_id').copy();names['name_key']=names.player_name.map(canonical_player_name);names=names[names.name_key.ne('')&~names.name_key.duplicated(keep=False)]
  identity_field='gsis_id' if 'gsis_id' in nfl else 'espn_id';nf=nfl.copy();nf['name_key']=nf.full_name.map(canonical_player_name);ambiguous=nf.groupby('name_key')[identity_field].nunique();nf=nf[nf.name_key.isin(ambiguous[ambiguous==1].index)];x=nf.merge(names,on='name_key');x=x.rename(columns={'player_id':'mfl_id'});resolved.append(x[['week','mfl_id','team','status']])
 if not resolved:raise ValueError('No NFL roster identity matches')
 identity=pd.concat(resolved).rename(columns={'mfl_id':'player_id','team':'resolved_team','status':'nfl_status'});identity['priority']=identity.nfl_status.map({'ACT':0,'INA':1,'RES':2}).fillna(3);identity=identity.sort_values('priority').drop_duplicates(['week','player_id']);identity.resolved_team=identity.resolved_team.map(club);scores=scores.merge(identity[['week','player_id','resolved_team','nfl_status']],on=['week','player_id'],how='left',validate='one_to_one');scores.team=scores.resolved_team.fillna(scores.team)
 sched=data['schedule'].get('fullNflSchedule',data['schedule']);schedule=[]
 for wk in many(sched['nflSchedule']):
  w=int(wk['week'])
  if w>17:continue
  for game in many(wk.get('matchup')):
   a,b=many(game['team']);schedule.extend([dict(season=season,week=w,team=club(a['id']),opponent=club(b['id'])),dict(season=season,week=w,team=club(b['id']),opponent=club(a['id']))])
 schedule=pd.DataFrame(schedule)
 archive_path=d/'score_archive.csv'
 if archive_path.exists():scores=restore_verified_historical_teams(scores,pd.read_csv(archive_path,dtype={'player_id':str}),schedule,season)
 scores=scores.merge(schedule,on=['week','team'],how='left',suffixes=('','_schedule'));scores['season']=season
 flags=[]
 for key,body in data['injuries'].items():
  for row in many(body['injuries'].get('injury')):flags.append(dict(week=int(key),player_id=ident(row['id']),injury_status=row.get('status','').upper().strip()))
 flags=pd.DataFrame(flags,columns=['week','player_id','injury_status']).drop_duplicates(['week','player_id'],keep='last');scores=scores.merge(flags,on=['week','player_id'],how='left');scores.injury_status=scores.injury_status.fillna('');scores['inactive']=(scores.injury_status.isin(['OUT','O','SUSPENDED','S','IR','IR-R','INJURED RESERVE - DESIGNATED FOR RETURN'])|scores.nfl_status.isin(['INA','RES','DEV','CUT','RET','SUS']))&scores.points.fillna(0).eq(0);scores['scheduled_bye']=scores.opponent.isna().astype(int);scores['active_score']=scores.points.where(~scores.inactive&scores.scheduled_bye.eq(0));scores['realized_points']=scores.points;scores['league']='ADL'
 bad=scores[scores.points.fillna(0).ne(0)&scores.opponent.isna()]
 if len(bad):raise ValueError('Unresolved nonzero NFL scores: '+str(bad.player_id.tolist()[:10]))
 valid=scores[scores.points.notna()&scores.opponent.notna()];allowed=valid.groupby(['season','week','opponent','pos']).agg(allowed=('points','sum'),scored_players=('player_id','size')).reset_index().rename(columns={'opponent':'team'});allowed['league']='ADL';allowed['unresolved_nonzero']=0;old=pd.read_csv(d/'opponent_games.csv');pd.concat([old[old.season!=season],allowed],ignore_index=True).to_csv(d/'opponent_games.csv',index=False)
 week1=data['projections']['1'];week1=week1.get('projectedScores',week1);first=pd.DataFrame([dict(player_id=ident(r['id']),first_fs=number(r.get('score'),np.nan)) for r in many(week1.get('playerScore'))]);meta=scores.sort_values('week').drop_duplicates('player_id')[['player_id','pos','team']].rename(columns={'team':'week1_team'});cohort=first.merge(meta,on='player_id');cohort=cohort[cohort.first_fs.notna()];panel=cohort.merge(pd.DataFrame({'week':range(1,18)}),how='cross');cols=['week','player_id','team','points','active_score','realized_points','inactive','injury_status','scheduled_bye'];panel=panel.merge(scores[cols],on=['week','player_id'],how='left');panel=panel.sort_values(['player_id','week']);panel.team=panel.groupby('player_id').team.ffill().fillna(panel.week1_team);panel['projection']=np.where(panel.week==1,panel.first_fs,np.nan);panel['season']=season;panel['league']='ADL'
 projections=[]
 for wk,body in data['projections'].items():
  body=body.get('projectedScores',body)
  projections.extend(dict(week=int(wk),player_id=ident(r['id']),weekly_projection=number(r.get('score'),np.nan)) for r in many(body.get('playerScore')))
 proj=pd.DataFrame(projections).drop_duplicates(['week','player_id']);panel=panel.merge(proj,on=['week','player_id'],how='left',validate='one_to_one');panel['projection']=panel.weekly_projection;panel=panel.drop(columns='weekly_projection')
 future=data.get('forecast_injuries')
 if future:
  flags={ident(r['id']):r.get('status','').upper().strip() for r in many(future['injuries'].get('injury'))};mask=panel.week.eq(through+1);panel.loc[mask,'injury_status']=panel.loc[mask,'player_id'].map(flags).fillna('')
 current=pd.DataFrame(data.get('current_rosters',[]))
 if not current.empty:
  current['player_id']=current.player_id.map(ident);clubs=current.drop_duplicates('player_id').set_index('player_id').team.map(club);mask=panel.week>through;panel.loc[mask,'team']=panel.loc[mask,'player_id'].map(clubs).fillna(panel.loc[mask,'team'])
 panel.to_csv(d/'player_weeks.csv',index=False);scores.to_csv(d/'score_archive.csv',index=False);schedule.to_csv(d/'nfl_schedule.csv',index=False)
 rosters=pd.DataFrame(data['rosters']);current=pd.DataFrame(data.get('current_rosters',[]))
 if not current.empty:
  current['week']=through;rosters=pd.concat([rosters[rosters.week!=through],current],ignore_index=True)
 rosters['player_id']=rosters.player_id.map(ident);rosters['franchise_id']=rosters.franchise_id.map(ident).str.zfill(4);rosters=rosters[rosters.week.between(1,min(through,12))].copy();rosters.team=rosters.team.map(club);rosters['roster_status']=rosters.roster_status.fillna('ROSTER').str.upper();rosters[['week','franchise_id','player_id','pos','team','roster_status']].drop_duplicates(['week','franchise_id','player_id']).to_csv(d/'fantasy_rosters.csv',index=False);(d/'rules.json').write_text(json.dumps(data['rules']))
 import hashlib
 receipt=dict(season=season,through_week=through,current_rosters_fetched_at=data.get('current_rosters_fetched_at'),roster_sha256=hashlib.sha256((d/'fantasy_rosters.csv').read_bytes()).hexdigest(),sources='same shared score inputs; public Week 1 and as-of weekly Sharks; NFL weekly roster IDs; current fantasy ownership',players=int(panel.player_id.nunique()),unresolved_nonzero=0,model='R05_L17_weekly_calibrated_Sharks',upcoming_week_sharks_used=True,later_future_sharks_used=False);(d/'refresh_receipt.json').write_text(json.dumps(receipt,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--input',type=Path,required=True);a=p.parse_args();refresh(a.root,json.loads(a.input.read_text(encoding='utf-8-sig')));print('Refreshed player strength inputs')
