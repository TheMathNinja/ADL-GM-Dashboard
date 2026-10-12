"""Fit the selected adjusted-Potential EB mean using completed prior seasons only."""
from pathlib import Path
import argparse,json,numpy as np,pandas as pd
from scipy.optimize import nnls

def fit(root,season):
 h=pd.read_csv(root/'data/bonus_history.csv',dtype={'franchise_id':str});c=pd.read_csv(root/'data/h2h_eb_training_credits.csv',dtype={'franchise_id':str});years=list(range(2022,season));moments=[];F=[]
 for y in years:
  q=h[(h.season==y)&(h.week<=12)];ids=sorted(q.franchise_id.unique());s=q.pivot(index='week',columns='franchise_id',values='points_for_week').reindex(index=range(1,13),columns=ids).to_numpy();p=q.pivot(index='week',columns='franchise_id',values='potential_points_week').reindex(index=range(1,13),columns=ids).to_numpy()
  if s.shape!=(12,32) or not np.isfinite(s).all() or not np.isfinite(p).all():raise ValueError('Incomplete training season '+str(y))
  scale=s.std();team=s.mean(0);weekly=((s-team)**2).sum()/(32*11);F.append(max(0,float(team.var(ddof=1)-weekly/12))/scale**2)
  for w in range(1,12):
   r=c[(c.season==y)&(c.week==w)].set_index('franchise_id').reindex(ids)
   if len(r)!=32 or r.credit.isna().any():raise ValueError('Missing prior availability credits')
   x=p[:w].mean(0)+r.credit.to_numpy();x=(x-x.mean())/scale;target=s[w:].mean(0);z=(target-target.mean())/scale;moments.append((w,float(x@x/32),float(x@z/32)))
 X=np.array([[1,1/w] for w,v,cross in moments]);V=np.array([v for w,v,cross in moments]);latent,weekly=nnls(X,V)[0];cross=float(np.mean([cross for w,v,cross in moments]));limit=np.sqrt(latent*np.mean(F));cross=float(np.clip(cross,-limit,limit))
 return dict(version='adl-h2h-adjusted-eb-v1',forecast_season=season,training_years=years,max_week=12,latent_potential_variance=float(latent),weekly_potential_variance=float(weekly),latent_cross_covariance=cross,latent_actual_variance=float(np.mean(F)),input='ytd_availability_adjusted_potential_centered',league_level='observed_ytd_actual_ppg',normalization='prior-season full PF SD; within-season centering',weekly_sd='unchanged_native',persistent_sd='unchanged_native',distribution='Normal')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--season',type=int,default=2026);a=p.parse_args();root=Path(a.root);model=fit(root,a.season);(root/'data/h2h_eb_model.json').write_text(json.dumps(model,indent=2)+'\n',encoding='utf8');print('Fitted',model['version'],'on',model['training_years'])
