"""Prior-only matched EB mean and hierarchical 2018+ NIG innovations."""
from pathlib import Path
import json,argparse,numpy as np,pandas as pd
from scipy.optimize import nnls,minimize
from scipy.special import logsumexp
from scipy.stats import norm,norminvgauss

def logpdf(z,family,p):
 if family=='Normal':return norm.logpdf(z)
 a,ratio=p;b=a*ratio;rv=norminvgauss(a,b);mean,var=rv.stats(moments='mv');sd=np.sqrt(var)
 return rv.logpdf(z*sd+mean)+np.log(sd)

class Fit:
 def __init__(self,root,season):
  from bonus_predictor import load_adl
  self.y=season;self.data=load_adl(root,season)
 def scale(self,s):return max(1e-8,float(s.mean()))
 def noise(self,blocks,family,calibrate,center=False):
  nodes,hw=np.polynomial.hermite.hermgauss(24);nodes*=np.sqrt(2);lh=np.log(hw/np.sqrt(np.pi));data=[]
  for b in blocks:
   r=b['r'];r=b['centered_r'] if center else r
   # Centered team errors require a finite-league variance correction.
   if center:r=r*np.sqrt(32/31)
   data.append((r,b['sigma'],b['tau']))
  def objective(v):
   ws,ts=np.exp(v[:2]) if calibrate else (1.,1.);shape=v[2:] if calibrate else v;total=0
   for r,sv,tv in data:
    m,n=r.shape;sd=sv*ws;tau=tv*ts
    if family=='Normal':
     variance=sd**2;tvar=tau**2;den=1+m*tvar/variance;q=(r*r).sum(0)/variance-tvar*r.sum(0)**2/(variance**2*den);ld=m*np.log(variance)+np.log(den);ll=-.5*(q+ld+m*np.log(2*np.pi))
    else:
     z=(r[:,:,None]-tau[None,:,None]*nodes[None,None,:])/sd[None,:,None];lp=logpdf(z,family,shape)-np.log(sd)[None,:,None];ll=logsumexp(lp.sum(0)+lh[None,:],axis=1)
    total-=float(np.mean(ll)/m)
   return total/len(data)
  if family=='Normal':
   if calibrate:
    result=minimize(objective,np.zeros(2),bounds=[(-1.2,1.2),(-3,1.2)],method='L-BFGS-B',options={'maxiter':180});assert result.success,result.message;v=result.x
   else:v=np.array([])
  else:
   normal=self.noise(blocks,'Normal',calibrate,center);initial=([np.log(normal['weekly_multiplier']),np.log(normal['strength_multiplier'])] if calibrate else [])+[3.,.05];bounds=([(-1.2,1.2),(-3,1.2)] if calibrate else [])+[(.7,50),(-.6,.6)];results=[]
   for init in [initial,initial[:-2]+[12.,0.]]:
    result=minimize(objective,np.array(init),bounds=bounds,method='L-BFGS-B',options={'maxiter':180,'ftol':1e-8});
    if result.success and np.isfinite(result.fun):results.append(result)
   if not results:raise RuntimeError('NIG joint likelihood did not converge')
   result=min(results,key=lambda r:r.fun);v=result.x
  ws,ts=np.exp(v[:2]) if calibrate else (1.,1.);shape=v[2:].tolist() if calibrate else v.tolist();return dict(weekly_multiplier=float(ws),strength_multiplier=float(ts),shape=shape if family!='Normal' else [],loss=float(objective(v)),fit='cross-fitted full remaining-week block likelihood',centered_team_errors=center,shape_reestimated=family!='Normal',calibrated_scales=calibrate)
 def innovation_model(self,family):
  blocks=[];F=[];W=[]
  for t in range(2018,self.y):
   scores=self.data[t][1];scale=self.scale(scores);team=scores.mean(0);weekly=((scores-team)**2).sum()/(32*11)/scale**2;W.append(weekly);F.append(max(0,float(team.var(ddof=1)/scale**2-weekly/12)))
  variance=float(np.mean(F));weekly=float(np.mean(W))
  for t in range(2018,self.y):
   scores=self.data[t][1];blocks.append(dict(r=(scores-scores.mean())/self.scale(scores),sigma=np.full(32,np.sqrt(weekly)),tau=np.full(32,np.sqrt(variance))))
  f=self.noise(blocks,family,True,False);f.update(actual_weekly=weekly*f['weekly_multiplier']**2,actual_latent=variance*f['strength_multiplier']**2,training_years=list(range(2018,self.y)),fit='full team-season latent-strength likelihood; no historical adjusted-Potential inputs required');return f

def fit(root,season):
 c=Fit(root,season);credits=pd.read_csv(root/'data/h2h_eb_training_credits.csv',dtype={'franchise_id':str});adjusted=pd.read_csv(root/'data/adjusted_actual_weekly.csv',dtype={'franchise_id':str});moments=[];F=[]
 for y in range(2022,season):
  ids,s,p=c.data[y];scale=c.scale(s);team=s.mean(0);weekly=((s-team)**2).sum()/(32*11)/scale**2;F.append(max(0,float(team.var(ddof=1)/scale**2-weekly/12)))
  for w in range(1,12):
   q=credits[(credits.season==y)&(credits.week==w)].set_index('franchise_id').reindex(ids)
   if len(q)!=32 or q.credit.isna().any():raise ValueError('Missing prior availability credits')
   a=adjusted[(adjusted.season==y)&(adjusted.week<=w)].pivot(index='week',columns='franchise_id',values='adjusted_pf').reindex(index=range(1,w+1),columns=ids).to_numpy();
   if not np.isfinite(a).all():raise ValueError('Missing adjusted actual training scores')
   x=.85*(p[:w].mean(0)+q.credit.to_numpy())+.15*a.mean(0);x=(x-x.mean())/scale;z=s[w:].mean(0);z=(z-z.mean())/scale
   moments.append((w,float(x@x/32),float(x@z/32)))
 A,W=nnls(np.array([[1,1/w] for w,v,cross in moments]),np.array([v for w,v,cross in moments]))[0]
 inf=c.innovation_model('Normal-inverse-Gaussian');C=float(np.clip(np.mean([cross for w,v,cross in moments]),0,np.sqrt(A*np.mean(F))));C=float(np.clip(C,0,np.sqrt(A*inf['actual_latent'])))
 return dict(input_latent=float(A),input_measurement=float(W),cross=C,actual_latent=inf['actual_latent'],actual_weekly=inf['actual_weekly'],shape=inf['shape'],training_years=list(range(2022,season)),innovation_training_years=list(range(2018,season)),version='adl-coherent-fixed15-eb-nig-v2',model='EB fixed 15% adjusted PPG + adjusted Potential / NIG',adjusted_ppg_weight=.15,forecast_season=season,normalization='league PPG',distribution='Normal-inverse-Gaussian')

def parameters(root,data,season,week,credit):
 if not 1<=week<12:raise ValueError('Forecast needs 1-11 observed weeks')
 saved=json.loads((Path(root)/'data/adl_scoring_model.json').read_text());f=saved.get(str(season))
 if f is None:raise ValueError('Missing prior-only unified model: run fit_adl_scoring.py')
 if max(f['training_years']+f['innovation_training_years'])>=season:raise ValueError('Training leakage')
 pf=data[season][1][:week];pot=data[season][2][:week];credit=np.zeros(32) if credit is None else np.asarray(credit)
 if credit.shape!=(32,) or not np.isfinite(credit).all() or (credit<0).any():raise ValueError('Invalid availability credit')
 den=f['input_latent']+f['input_measurement']/week;weight=f['cross']/den;level=float(pf.mean());adjusted=pd.read_csv(Path(root)/'data/adjusted_actual_weekly.csv',dtype={'franchise_id':str});a=adjusted[(adjusted.season==season)&(adjusted.week<=week)].pivot(index='week',columns='franchise_id',values='adjusted_pf').reindex(index=range(1,week+1),columns=data[season][0]).to_numpy();
 if not np.isfinite(a).all():raise ValueError('Missing as-of adjusted actual scores')
 x=.85*(pot.mean(0)+credit)+.15*a.mean(0)
 mu=level+weight*(x-x.mean());sigma=level*np.sqrt(f['actual_weekly']);tau=level*np.sqrt(max(0,f['actual_latent']-f['cross']**2/den));gap=np.maximum(0,(pot-pf).mean(0))
 return mu,sigma,tau,gap,{**f,'potential_weight':weight,'potential_input':'85% availability-adjusted Potential + 15% adjusted actual PPG','weekly_shape':f['shape'],'weekly_volatility':'2018+ PPG-normalized scoring innovations','strength_uncertainty':'matched EB posterior','reg_season_model':f['version']}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--season',type=int,default=2026);a=p.parse_args();path=a.root/'data/adl_scoring_model.json';saved=json.loads(path.read_text()) if path.exists() else {}
 if str(a.season) not in saved or saved[str(a.season)].get('adjusted_ppg_weight')!=.15:saved[str(a.season)]=fit(a.root,a.season);path.write_text(json.dumps(saved,indent=2)+'\n')
 print('Unified ADL prior fit available for',a.season)
