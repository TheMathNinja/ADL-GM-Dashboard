"""Selected four-input EB team model; same mean and posterior for every event."""
from pathlib import Path
import json
import numpy as np,pandas as pd
VERSION='adl-player-blend-35-5-50-10-smooth-player-uncertainty-v7'

def adjusted_actual_ppg(root,season,week,ids):
 d=pd.read_csv(Path(root)/'data/adjusted_actual_weekly.csv',dtype={'franchise_id':str})
 d=d[(d.season==season)&(d.week<=week)].copy();d.franchise_id=d.franchise_id.str.zfill(4)
 if d.duplicated(['week','franchise_id']).any():raise ValueError('Duplicate adjusted actual score')
 table=d.pivot(index='week',columns='franchise_id',values='adjusted_pf').reindex(index=range(1,week+1),columns=ids)
 if not np.isfinite(table.to_numpy()).all():raise ValueError('Missing as-of adjusted actual PPG')
 return table.mean(0).to_numpy()

def parameters(root,data,season,week,credit,adjusted_ppg=None,case='forecast'):
 root=Path(root);saved=json.loads((root/'data/adl_scoring_model.json').read_text());f=saved[str(season)]
 supported={VERSION,'adl-player-blend-35-5-50-10-status-aware-availability-v6','adl-player-blend-35-5-50-10-full-recalibration-v5'} if season>=2026 else {VERSION,'adl-player-blend-35-5-50-10-full-recalibration-v5','adl-player-blend-35-0-55-10-weekly-sharks-nig-v4'}
 if f.get('version') not in supported:raise ValueError('Selected player blend has not been fitted for '+str(season))
 if max(f['training_years']+f['innovation_training_years'])>=season:raise ValueError('Training leakage')
 if not 1<=week<12:raise ValueError('Forecast needs 1â€“11 observed weeks')
 c=f['cases'][case];ids,pf,pot=data[season];pf=pf[:week];pot=pot[:week];credit=np.zeros(32) if credit is None else np.asarray(credit)
 if credit.shape!=(32,) or not np.isfinite(credit).all() or (credit<0).any():raise ValueError('Invalid availability credits')
 feature_path=root/f'data/player_strength/team_strength_{season}.csv'
 if not feature_path.exists() and season<2026:feature_path=root/'data/player_strength/historical_team_strength.csv'
 q=pd.read_csv(feature_path,dtype={'franchise_id':str});q=q[(q.season==season)&(q.week==week)];fields=[]
 for key in ['starter_strength','roster_strength']:
  a=q.pivot(index='target_week',columns='franchise_id',values=key).reindex(index=range(week+1,13),columns=ids).to_numpy()
  if not np.isfinite(a).all():raise ValueError('Missing current-roster player strength '+str(week))
  fields.append(a)
 shape=fields[0].shape
 actual=adjusted_actual_ppg(root,season,week,ids) if adjusted_ppg is None and c['weights'][1] else np.zeros(32) if adjusted_ppg is None else np.asarray(adjusted_ppg,dtype=float)
 if actual.shape!=(32,) or not np.isfinite(actual).all():raise ValueError('Invalid adjusted actual PPG')
 x=np.stack([np.broadcast_to(pot.mean(0)+credit,shape),np.broadcast_to(actual,shape),*fields],-1)*np.asarray(c['conversion']);x-=x.mean(1,keepdims=True);signal=x@np.asarray(c['weights']);den=c['input_latent']+c['input_measurement']/week;b=c['cross']/max(den,1e-12);level=float(pf.mean());mu=level+b*signal;sigma=level*np.sqrt(f['actual_weekly']);tau=level*np.sqrt(max(0,f['actual_latent']-c['cross']**2/max(den,1e-12)));gap=np.maximum(0,(pot-pf).mean(0))
 taper=f.get('persistent_uncertainty') if case=='forecast' else None
 if taper is not None:
  if taper['family']!='nonnegative_direct_linear' or max(taper['training_years'])>=season:raise ValueError('Invalid persistent uncertainty calibration')
  end,decline=np.asarray(taper['coef'],dtype=float)
  if not np.isfinite([end,decline]).all() or min(end,decline)<0:raise ValueError('Invalid nonnegative linear SD')
  tau=level*(end+decline*(11-week)/10)
 weekly_shape=f['shape']
 uncertainty_path=root/f'data/player_strength/player_uncertainty_{season}.json'
 if case=='forecast' and uncertainty_path.exists():
  from player_uncertainty import team_noise
  uncertainty=json.loads(uncertainty_path.read_text())
  if max(uncertainty['training_years'])>=season:raise ValueError('Uncertainty training leakage')
  mult,skew=team_noise(uncertainty,q,ids,week)
  weekly_shape=dict(a=float(f['shape'][0]),ratio=np.tanh(np.arctanh(f['shape'][1])+skew).tolist(),sd_multiplier=mult.tolist())
 return mu,float(sigma),float(tau),gap,{**f,'weights':c['weights'],'rating_model':'0/0/90/10','blend_reliability':b,'potential_weight':c['weights'][0]*b,'potential_input':'35% adjusted Potential + 5% adjusted actual PPG + 50% Starter Strength + 10% Roster Strength','weekly_shape':weekly_shape,'strength_uncertainty':'relative direct linear SD' if taper is not None else 'fully refitted EB posterior', 'player_ability_update':'fully refitted injury-aware weekly Sharks with shared position bias','reg_season_model':VERSION}
