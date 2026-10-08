"""Selected Bonus Games predictors. No changes to the separate playoff engine."""
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
def adl_parameters(data,year,week):
 train=sorted(t for t in data if 2018<=t<year);mu=blend_mean(data,train,year,week);v=np.stack([data[t][1] for t in train]);res=v-v.mean(1,keepdims=True);sigma=float(np.sqrt(np.mean(res**2)*12/11));errors=[]
 for t in train:
  prior=[q for q in train if q<t]
  if not prior:continue
  err=data[t][1][week:].mean(0)-blend_mean(data,prior,t,week);errors.extend(err-err.mean())
 tau=float(np.sqrt(max(0,np.mean(np.square(errors))-sigma**2/(12-week)))) if errors else 0.
 gap=np.maximum(0,(data[year][2][:week]-data[year][1][:week]).mean(0))
 return mu,sigma,tau,gap,dict(model='adl_blend_persistent',distribution='normal',training_years=train)
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
def event_forecasts(s,p,w,future,gap,league):
 n=len(future);result={}
 for label,a,b in EVENTS:
  seen=max(0,min(w,b)-a);obs=s[a:min(w,b)] if seen else s[:0];obsp=p[a:min(w,b)] if seen else p[:0];remaining=b-a-seen
  # Unstarted quarters have identical marginal outlooks under stationary scoring assumptions.
  scores=np.concatenate([np.broadcast_to(obs,(n,seen,32)),future[:,:remaining]],axis=1);pots=np.concatenate([np.broadcast_to(obsp,(n,seen,32)),future[:,:remaining]+gap],axis=1)
  aps=ap(scores).sum(1);pts=scores.sum(1);third=pots.sum(1) if league=='FAFL' else np.zeros_like(pts);out=outcomes(aps,pts,third);prob=np.stack([(out==i).mean(0) for i in range(3)],1)
  ordered=np.sort(aps,axis=1)[:,::-1];cut=np.column_stack([(ordered[:,14]+ordered[:,15])/2,(ordered[:,16]+ordered[:,17])/2]);q=np.quantile(cut,[.1,.9],axis=0)
  if not np.allclose(prob.sum(0),[15,2,15]) or not np.allclose(prob.sum(1),1):raise ValueError('Invalid Bonus Game probability totals')
  result[label]=dict(probabilities=prob,win_cutoff=float(cut[:,0].mean()),tie_cutoff=float(cut[:,1].mean()),win_low=float(q[0,0]),win_high=float(q[1,0]),tie_low=float(q[0,1]),tie_high=float(q[1,1]))
 return result
