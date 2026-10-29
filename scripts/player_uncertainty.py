"""Smooth mean-preserving active-game score distributions.
Strength is continuous, normalized by the fitted position noise scale.
No rank, star flag, or performance threshold enters the forecast.
"""
import numpy as np
from scipy import stats

def distribution(model,pos,mean,old_sd,position_variance):
 mean=np.asarray(mean,dtype=float);old_sd=np.asarray(old_sd,dtype=float)
 if not np.isfinite(mean).all() or not np.isfinite(old_sd).all() or (old_sd<=0).any():raise ValueError('Invalid player distribution input')
 b=np.asarray(model['coef']);x=np.log1p(np.maximum(0,mean)/np.sqrt(position_variance))-np.log(2)
 scale=old_sd*np.exp(b[model['positions'].index(pos)]+b[11]*x)
 a=2*np.tanh((b[12]+b[13]*x)/2);tail=np.exp(b[14]);m,var,skew=stats.johnsonsu.stats(a,tail,moments='mvs')
 return dict(mean=mean,scale=scale,a=a,tail=tail,raw_mean=m,raw_sd=np.sqrt(var),skew=skew)

def quantile(d,q):
 return d['mean']+d['scale']*(stats.johnsonsu.ppf(q,d['a'],d['tail'])-d['raw_mean'])/d['raw_sd']

def moments_with_availability(d,probability):
 p=np.asarray(probability);mu=d['mean'];v=d['scale']**2
 variance=p*v+p*(1-p)*mu**2
 third=p*d['skew']*d['scale']**3+3*p*(1-p)*mu*v+p*(1-p)*(1-2*p)*mu**3
 return variance,third

def team_noise(model,rows,ids,week):
 q=rows[rows.week.eq(week)]
 risk=q.pivot(index='target_week',columns='franchise_id',values='lineup_variance').reindex(index=range(week+1,13),columns=ids).to_numpy()
 third=q.pivot(index='target_week',columns='franchise_id',values='lineup_third_moment').reindex(index=range(week+1,13),columns=ids).to_numpy()
 if not np.isfinite(risk).all() or not np.isfinite(third).all() or (risk<=0).any():raise ValueError('Missing player-based team uncertainty')
 x=.5*np.log(risk);x-=x.mean(1,keepdims=True);skew=third/risk**1.5;skew-=skew.mean(1,keepdims=True)
 gamma=model['team_response']['coef'];mult=np.exp(gamma[0]*x)
 return mult,(gamma[1]*skew if len(gamma)>1 else np.zeros_like(skew))
