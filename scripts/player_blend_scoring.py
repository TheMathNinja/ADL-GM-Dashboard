"""Selected four-input EB team model; same mean and posterior for every event."""
from pathlib import Path
import json
import numpy as np,pandas as pd
VERSION='adl-player-blend-35-0-55-10-weekly-sharks-nig-v4'

def parameters(root,data,season,week,credit,adjusted_ppg=None,case='forecast'):
 root=Path(root);saved=json.loads((root/'data/adl_scoring_model.json').read_text());f=saved[str(season)]
 if f.get('version')!=VERSION:raise ValueError('Selected player blend has not been fitted for '+str(season))
 if max(f['training_years']+f['innovation_training_years'])>=season:raise ValueError('Training leakage')
 if not 1<=week<12:raise ValueError('Forecast needs 1–11 observed weeks')
 c=f['cases'][case];ids,pf,pot=data[season];pf=pf[:week];pot=pot[:week];credit=np.zeros(32) if credit is None else np.asarray(credit)
 if credit.shape!=(32,) or not np.isfinite(credit).all() or (credit<0).any():raise ValueError('Invalid availability credits')
 feature_path=root/f'data/player_strength/team_strength_{season}.csv'
 if not feature_path.exists() and season<2026:feature_path=root/'data/player_strength/historical_team_strength.csv'
 q=pd.read_csv(feature_path,dtype={'franchise_id':str});q=q[(q.season==season)&(q.week==week)];fields=[]
 for key in ['starter_strength','roster_strength']:
  a=q.pivot(index='target_week',columns='franchise_id',values=key).reindex(index=range(week+1,13),columns=ids).to_numpy()
  if not np.isfinite(a).all():raise ValueError('Missing current-roster player strength '+str(week))
  fields.append(a)
 shape=fields[0].shape;x=np.stack([np.broadcast_to(pot.mean(0)+credit,shape),np.zeros(shape),*fields],-1)*np.asarray(c['conversion']);x-=x.mean(1,keepdims=True);signal=x@np.asarray(c['weights']);den=c['input_latent']+c['input_measurement']/week;b=c['cross']/max(den,1e-12);level=float(pf.mean());mu=level+b*signal;sigma=level*np.sqrt(f['actual_weekly']);tau=level*np.sqrt(max(0,f['actual_latent']-c['cross']**2/max(den,1e-12)));gap=np.maximum(0,(pot-pf).mean(0))
 return mu,float(sigma),float(tau),gap,{**f,'weights':c['weights'],'rating_model':'0/0/90/10','blend_reliability':b,'potential_weight':c['weights'][0]*b,'potential_input':'35% availability-adjusted Potential + 55% Starter Strength + 10% Roster Strength','weekly_shape':f['shape'],'strength_uncertainty':'retained EB posterior; held-out Sharks uncertainty checks', 'player_ability_update':'calibrated weekly Sharks with shared position bias','reg_season_model':VERSION}
