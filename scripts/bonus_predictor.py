"""Selected Bonus Games predictors shared with quarterly playoff forecasts."""
from pathlib import Path
import numpy as np
import pandas as pd
EVENTS=[('Q1',0,3),('Q2',3,6),('Q3',6,9),('Q4',9,12),('All-Season',0,12)]
def ap(x):return (x[..., :,None]>x[...,None,:]).sum(-1)+.5*((x[..., :,None]==x[...,None,:]).sum(-1)-1)
def outcomes(a,p,pot):
 order=np.lexsort((-pot,-p,-a),axis=-1);rank=np.argsort(order,axis=-1)
 return np.where(rank<15,2,np.where(rank<17,1,0))
def ridge(x,y,z):
 mean=x.mean(0);sd=x.std(0);sd[sd<1e-8]=1;X=np.column_stack([np.ones(len(x)),(x-mean)/sd]);Z=np.column_stack([np.ones(len(z)),(z-mean)/sd]);penalty=np.eye(X.shape[1])*10;penalty[0,0]=0
 return Z@np.linalg.solve(X.T@X+penalty,X.T@y)
def load_adl(root,season):
 d=pd.read_csv(root/'data/bonus_history.csv',dtype={'franchise_id':str});d=d[(d.season>=2018)&(d.season<season)&(d.week<=12)];d.franchise_id=d.franchise_id.str.zfill(4);data={}
 for year,g in d.groupby('season'):
  ids=sorted(g.franchise_id.unique());s=g.pivot(index='week',columns='franchise_id',values='points_for_week').reindex(index=range(1,13),columns=ids).to_numpy();p=g.pivot(index='week',columns='franchise_id',values='potential_points_week').reindex(index=range(1,13),columns=ids).to_numpy()
  if len(ids)!=32 or not np.isfinite(s).all() or not np.isfinite(p).all():raise ValueError('Incomplete ADL Bonus Games training season')
  data[int(year)]=(ids,s,p)
 if not data:raise ValueError('Missing ADL training history')
 return data
def blend_mean(data,train,year,week):
 def x(y):return np.column_stack([data[y][1][:week].mean(0),data[y][2][:week].mean(0)])
 return ridge(np.vstack([x(t) for t in train]),np.concatenate([data[t][1][week:].mean(0) for t in train]),x(year))
def adl_legacy_parameters(data,year,week):
 train=sorted(t for t in data if 2018<=t<year);mu=blend_mean(data,train,year,week);v=np.stack([data[t][1] for t in train]);res=v-v.mean(1,keepdims=True);sigma=float(np.sqrt(np.mean(res**2)*12/11));errors=[]
 for t in train:
  prior=[q for q in train if q<t]
  if not prior:continue
  err=data[t][1][week:].mean(0)-blend_mean(data,prior,t,week);errors.extend(err-err.mean())
 tau=float(np.sqrt(max(0,np.mean(np.square(errors))-sigma**2/(12-week)))) if errors else 0.
 gap=np.maximum(0,(data[year][2][:week]-data[year][1][:week]).mean(0))
 return mu,sigma,tau,gap,dict(model='adl_blend_persistent',distribution='normal',training_years=train)
def adl_parameters(data,year,week):
 # Published EB Potential-only Normal: preserve the screened legacy noise.
 _,sigma,tau,gap,legacy=adl_legacy_parameters(data,year,week)
 train=legacy['training_years'];within=[];between=[]
 for prior in train:
  pf,pot=data[prior][1:];scale=max(1e-8,float(pf.std()));x=np.stack([(pf-pf.mean())/scale,(pot-pot.mean())/scale],axis=-1)
  team=x.mean(0);res=x-team[None,:,:];within.append(np.einsum('wti,wtj->ij',res,res)/(32*11));centered=team-team.mean(0);between.append(centered.T@centered/31)
 W=np.mean(within,axis=0);A=np.mean(between,axis=0)-W/12;values,vectors=np.linalg.eigh(A);A=(vectors*np.maximum(values,0))@vectors.T
 pf=data[year][1][:week];pot=data[year][2][:week];scale=max(1e-8,float(pf.std()));weight=float((np.linalg.pinv((A+W/week)[1:2,1:2])@A[0,1:2])[0]);mu=pf.mean()+weight*(pot.mean(0)-pot.mean())
 return mu,sigma,tau,gap,dict(model='adl_eb_potential_normal',mean_engine='Empirical-Bayes Potential-only',distribution='normal',training_years=train,season_normalization='Separate actual/Potential centers; shared season PF SD',potential_weight=weight,weekly_volatility='legacy blend pooled weekly SD',strength_uncertainty='legacy blend week-specific persistent SD',reg_season_model='adl_eb_potential_normal')

def fafl_parameters(root,current,year,week):
 import build as native
 native.ROOT=root
 history=native.historical();links=native.load_links();seen=current[current.week<=week].copy();pred,details=native.fit_means(history,seen,year,week,links);ids=sorted(seen.franchise_id.unique());s=seen.pivot(index='week',columns='franchise_id',values='points').reindex(index=range(1,week+1),columns=ids).to_numpy();past=history[(history.season>=2021)&(history.season<year)&(history.week<=12)].groupby(['season','franchise_id']).points.std().to_numpy();sigma=float(np.nanmean(np.r_[past,s.std(0,ddof=1) if week>1 else []]));tau=native.strength_uncertainty(history,year,week,links)
 return pred[:,0],sigma,tau,pred[:,1]-pred[:,0],dict(model='fafl_current_t5',distribution='Student-t',df=5,training_years=details['training_years'])
def draw_future(mu,sigma,tau,league,season,week,n):
 if n<2 or n%2:raise ValueError('Simulations must be a positive even number')
 rng=np.random.default_rng(890817+season*100+week);z=rng.normal(size=(n//2,12-week,32));offset=rng.normal(size=(n//2,1,32))
 if league=='FAFL':z*=np.sqrt(3/rng.chisquare(5,size=z.shape))
 z=np.concatenate([z,-z]);offset=np.concatenate([offset,-offset]);return np.round(np.maximum(0,mu[None,None,:]+z*sigma+offset*tau),1)
def segment_samples(s,p,w,future,gap,league,a,b,future_potential=None):
 n=len(future);seen=max(0,min(w,b)-a);remaining=b-a-seen;obs=s[a:min(w,b)] if seen else s[:0];obsp=p[a:min(w,b)] if seen else p[:0]
 # Use each quarter's own future weeks, retaining the shared team-strength draw.
 first=max(0,a-w);draws=future[:,first:first+remaining]
 scores=np.concatenate([np.broadcast_to(obs,(n,seen,32)),draws],axis=1);pots=np.concatenate([np.broadcast_to(obsp,(n,seen,32)),(draws+gap if future_potential is None else future_potential[:,first:first+remaining])],axis=1)
 aps=ap(scores).sum(1);pts=scores.sum(1);third=pots.sum(1)
 return aps,outcomes(aps,pts,third)

def event_forecasts(s,p,w,future,gap,league,future_potential=None):
 result={}
 for label,a,b in EVENTS:
  aps,out=segment_samples(s,p,w,future,gap,league,a,b,future_potential);prob=np.stack([(out==i).mean(0) for i in range(3)],1)
  ordered=np.sort(aps,axis=1)[:,::-1];cut=np.column_stack([(ordered[:,14]+ordered[:,15])/2,(ordered[:,16]+ordered[:,17])/2]);q=np.quantile(cut,[.1,.9],axis=0)
  if not np.allclose(prob.sum(0),[15,2,15]) or not np.allclose(prob.sum(1),1):raise ValueError('Invalid Bonus Game probability totals')
  result[label]=dict(probabilities=prob,expected_ap=aps.mean(0),win_cutoff=float(cut[:,0].mean()),tie_cutoff=float(cut[:,1].mean()),win_low=float(q[0,0]),win_high=float(q[1,0]),tie_low=float(q[0,1]),tie_high=float(q[1,1]))
 # Unstarted quarters are exchangeable. Pool only their marginal summaries;
 # keep separate simulated outcomes for correct season/playoff dependence.
 labels=[label for label,a,b in EVENTS[:4] if a>=w]
 if len(labels)>1:
  pooled={key:np.mean([result[label][key] for label in labels],axis=0) for key in result[labels[0]]}
  for label in labels:result[label]={key:value.copy() if isinstance(value,np.ndarray) else float(value) for key,value in pooled.items()}
 return result
