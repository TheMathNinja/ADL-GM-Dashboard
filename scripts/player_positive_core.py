"""Nonnegative player-signal updates and prior-only predictive-shape calibration.

Player-bias updates use a constrained linear state estimator with Joseph error
covariance. Position-bias updates use a shared empirical-Bayes residual offset;
nonnegative weights in that case refer to the explicitly corrected FS feature.
"""
import numpy as np
from scipy.optimize import minimize,minimize_scalar
from scipy import stats
from player_strength_core import mapped

MODES=['off','none','position','player']
SHAPES=['Normal original SD','Normal fitted SD','Student-t5','Student-t12','Skew Normal','NIG','Empirical residual','Normal ability SD']

def prepare(study,year,pos,fit):
 c=study.cubes[year,pos];factors=np.ones_like(c['active_score'])
 if fit['opponent']:
  factors=np.array([1+fit['opponent_effect']*study.context(year,pos,fit['opponent'],w-1,c['team'][w-1],w)[0] for w in range(1,18)])
 valid=np.isfinite(c['projection'][:12])&~c['known_out'][:12]
 for w in range(12):valid[w]&=np.array([(year,w+1,str(t)) in study.opp for t in c['team'][w]])
 return dict(c,actual=c['active_score'][:12]/factors[:12],factors=factors[:12],fs_valid=valid)

def position_variance(fit):
 if 'position_variance' in fit:return float(fit['position_variance'])
 means=[]
 for r in fit['train']:
  x=mapped(fit['weekly'],r['cube']['projection'][:12])/r['factors'][:12];good=r['fs_valid']&np.isfinite(r['actual']);diff=np.where(good,x-r['actual'],np.nan)
  if np.isfinite(diff).any():means.append(float(np.nanmean(diff)))
 return max(.001*fit['Ra'],float(np.var(means)) if len(means)>1 else .01*fit['Ra'])

def run(cube,fit,mode,q,keep_weights=False):
 n=len(cube['ids']);initial=np.asarray(cube.get('initial_mean',mapped(fit['prior'],cube['first_fs'])),dtype=float);assert initial.shape==(n,) and np.isfinite(initial).all() and (initial>=0).all();m=np.column_stack([initial,np.zeros(n)]);P=np.zeros((n,2,2));P[:,0,0]=fit['Pa'];P[:,1,1]=fit['Pb'] if mode=='player' else 0.
 # All new models start with zero ability/bias covariance. Prior mixing
 # restrictions apply to each individual corrected measurement, not just totals.
 B=np.zeros((n,2,25));B[:,0,0]=1.;states=[];loss=[];nums=np.zeros(n);sums=np.zeros(n);Vp=position_variance(fit);clipped=0;updates=0
 def update(z,H,R,index):
  nonlocal m,P,B,clipped,updates
  ok=np.isfinite(z)
  if not ok.any():return
  ph=P@H;S=ph@H+R;K=ph/S[:,None];K[~ok]=0.;one=np.zeros(25);one[index]=1.;direction=one[None]-np.einsum('j,njk->nk',H,B)
  bounds=np.divide(B[:,0],-direction,out=np.full_like(direction,np.inf),where=direction < -1e-13);cap=np.maximum(0,np.minimum(1,np.min(bounds,axis=1)));old=K[:,0].copy();K[:,0]=np.minimum(np.maximum(0,K[:,0]),cap);clipped+=int(np.sum(ok&(abs(old-K[:,0])>1e-10)));updates+=int(ok.sum())
  innovation=np.where(ok,z-m@H,0.);m+=K*innovation[:,None];A=np.eye(2)[None]-K[:,:,None]*H[None,None,:];P=A@P@np.swapaxes(A,1,2)+R*K[:,:,None]*K[:,None,:];P=(P+np.swapaxes(P,1,2))/2
  B+=K[:,:,None]*direction[:,None,:]
  assert np.min(B[:,0])>=-1e-9
 for w in range(12):
  if w:P[:,0,0]+=q
  fs=mapped(fit['weekly'],cube['projection'][w])/cube['factors'][w];fs=np.where(cube['fs_valid'][w],fs,np.nan);pb=0.;pv=0.
  if mode=='position':
   enough=nums>0;v=fit['Pb']+np.divide(fit['Ra']+fit['Rf'],nums,out=np.zeros(n),where=enough);precision=1/Vp+np.sum(np.divide(1.,v,out=np.zeros(n),where=enough));pv=1/precision;pb=pv*np.sum(np.divide(sums,nums*v,out=np.zeros(n),where=enough))
  if mode!='off' and w:
   if mode=='player':update(fs,np.array([1.,1.]),fit['Rf'],13+w)
   else:
    corrected=np.maximum(0,fs-pb);update(corrected,np.array([1.,0.]),fit['Rf']+fit['Pb']+pv,13+w)
  # Forecast before observing the current actual. Source diagnostics describe
  # calibrated signals; a position offset is explicitly separate from weights.
  states.append(dict(mean=m[:,0].copy(),variance=P[:,0,0].copy(),position_bias=float(pb),position_bias_variance=float(pv),bias=m[:,1].copy(),weights=np.column_stack([B[:,0,0],B[:,0,1:13].sum(1),B[:,0,13:].sum(1)]),minimum_coefficient=float(B[:,0].min())))
  y=cube['actual'][w];ok=np.isfinite(y);var=P[:,0,0]+fit['Ra'];err=np.where(ok,y-m[:,0],0.)
  if ok.any():loss.append(float(np.mean((np.log(var)+err**2/var)[ok])))
  update(y,np.array([1.,0.]),fit['Ra'],1+w)
  paired=ok&np.isfinite(fs);nums+=paired;sums+=np.where(paired,fs-y,0.)
 return states,float(np.mean(loss)),dict(constrained_updates=clipped,total_updates=updates)

def choose_q(fit,mode):
 grid=[.0001,.0025,.005,.01,.02,.05];values=[]
 for fraction in grid:
  scores=[]
  for item in fit['train']:
   c=dict(item['cube'],actual=item['actual'],factors=item['factors'][:12],fs_valid=item['fs_valid']);scores.append(run(c,fit,mode,fraction*fit['Ra'])[1])
  values.append(float(np.mean(scores)))
 best=int(np.argmin(values));return grid[best]*fit['Ra'],dict(grid=grid,losses=values,fraction=grid[best],criterion='training prequential Gaussian actual-score likelihood')

def pack(study,year,pos,fit,states,q):
 c=study.cubes[year,pos];rows=[];statesrows=[]
 for w,state in enumerate(states):
  if year==2026 and w>=5:break
  mu=state['mean'];V=state['variance'];last=5 if year==2026 else 17
  pieces=[];forecast_means=[];forecast_playing=[]
  for target in range(w+1,18):
   if fit['opponent']:
    d,v,play=study.context(year,pos,fit['opponent'],w,c['team'][w],target);f=1+fit['opponent_effect']*d;extra=(fit['opponent_effect']*mu)**2*v
   else:f=np.ones(len(mu));extra=np.zeros(len(mu));play=np.array([(year,target,str(t)) in study.opp for t in c['team'][w]])
   pred=mu*f;sd=np.sqrt(np.maximum(1e-8,f*f*(V+fit['Ra']+(target-w-1)*q)+extra));y=c['active_score'][target-1];good=np.isfinite(y)
   forecast_means.append(pred);forecast_playing.append(play)
   if good.any() and target<=last:pieces.append((target,good,pred,sd,y))
  rem={}
  for endpoint in [12,17]:
   count=max(0,endpoint-w);planned=np.array(forecast_playing[:count]);forecast=np.array(forecast_means[:count]);rem[endpoint]=np.divide(np.where(planned,forecast,0).sum(0),planned.sum(0),out=mu.copy(),where=planned.sum(0)>0)
  for target,good,pred,sd,y in pieces:rows.append(np.column_stack([np.full(good.sum(),w+1),np.full(good.sum(),target),np.flatnonzero(good),y[good],pred[good],sd[good],rem[12][good],rem[17][good]]))
  statesrows.append(dict(week=w+1,prior_weight=float(state['weights'][:,0].mean()),score_weight=float(state['weights'][:,1].mean()),fs_weight=float(state['weights'][:,2].mean()),min_coefficient=state.get('minimum_coefficient',float(state['weights'].min())),position_bias=state.get('position_bias',0.)))
 return np.concatenate(rows) if rows else np.empty((0,8)),statesrows

def weights_for(p):
 w=np.zeros(len(p))
 for origin in np.unique(p[:,0]):
  ix=p[:,0]==origin;w[ix]=1/ix.sum()
 return w/w.sum()

def fit_shapes(p):
 z=(p[:,3]-p[:,4])/p[:,5];mu=p[:,4];wt=weights_for(p);keep=np.isfinite(z);z=z[keep];mu=mu[keep];wt=wt[keep];wt/=wt.sum()
 # Bounded deterministic subsample only for numerical shape optimization.
 if len(z)>5000:
  idx=np.linspace(0,len(z)-1,5000).astype(int);z=z[idx];mu=mu[idx];wt=wt[idx];wt/=wt.sum()
 def optimize(fn,bounds,x0):
  def objective(x):
   lp=fn(x,z);return float(-np.sum(wt*np.clip(lp,-1000,100))) if np.isfinite(lp).all() else 1e6
  result=minimize(objective,x0,bounds=bounds,method='L-BFGS-B',options={'maxiter':60});return result.x.tolist()
 models={};models['Normal original SD']=dict(family='normal',scale=1.)
 scale=float(np.sqrt(np.sum(wt*z*z)));models['Normal fitted SD']=dict(family='normal',scale=scale)
 for df in [5,12]:
  sd=np.sqrt(df/(df-2));x=optimize(lambda x,z:stats.t.logpdf(z*sd/np.exp(x[0]),df)+np.log(sd)-x[0],[(-1.5,1.5)],[np.log(max(.3,scale))]);models[f'Student-t{df}']=dict(family='t',df=df,scale=float(np.exp(x[0])))
 def skewpdf(x,z):
  a=x[0];s=np.exp(x[1]);delta=a/np.sqrt(1+a*a);mean=delta*np.sqrt(2/np.pi);sd=np.sqrt(1-2*delta*delta/np.pi);return stats.skewnorm.logpdf(z*sd/s+mean,a)+np.log(sd)-np.log(s)
 x=optimize(skewpdf,[(0,20),(-1.5,1.5)],[2.,np.log(max(.3,scale))]);models['Skew Normal']=dict(family='skewnorm',alpha=x[0],scale=float(np.exp(x[1])))
 def nigpdf(x,z):
  a=np.exp(x[0]);b=x[1]*a;s=np.exp(x[2]);gamma=np.sqrt(a*a-b*b);mean=b/gamma;sd=a/gamma**1.5;return stats.norminvgauss.logpdf(z*sd/s+mean,a,b)+np.log(sd)-np.log(s)
 x=optimize(nigpdf,[(-2,4),(-.95,.95),(-1.5,1.5)],[1.,.4,np.log(max(.3,scale))]);models['NIG']=dict(family='nig',a=float(np.exp(x[0])),rho=x[1],scale=float(np.exp(x[2])))
 order=np.argsort(z);zs=z[order];ws=wt[order];q=(np.arange(2048)+.5)/2048;quant=np.interp(q,np.cumsum(ws)-ws/2,zs);quant-=np.mean(quant);models['Empirical residual']=dict(family='empirical',quantiles=quant.tolist(),scale=1.)
 feature=np.log1p(np.maximum(0,mu));x=optimize(lambda x,z:stats.norm.logpdf(z/np.exp(x[0]+x[1]*feature))-(x[0]+x[1]*feature),[(-2,2),(-.75,.75)],[np.log(max(.3,scale)),0.]);models['Normal ability SD']=dict(family='ability',intercept=x[0],power=x[1])
 for name,m in models.items():m['prior_residual_count']=len(p)
 return models

def quantiles(model):
 p=(np.arange(2048)+.5)/2048;f=model['family'];scale=model.get('scale',1.)
 if f in ['normal','ability']:q=stats.norm.ppf(p)
 elif f=='t':q=stats.t.ppf(p,model['df'])*np.sqrt((model['df']-2)/model['df'])
 elif f=='skewnorm':
  a=model['alpha'];delta=a/np.sqrt(1+a*a);q=(stats.skewnorm.ppf(p,a)-delta*np.sqrt(2/np.pi))/np.sqrt(1-2*delta*delta/np.pi)
 elif f=='nig':
  from scipy.integrate import cumulative_trapezoid
  a=model['a'];b=model['rho']*a;gamma=np.sqrt(a*a-b*b);mean=b/gamma;sd=a/gamma**1.5;grid=np.linspace(-80,160,65536);pdf=stats.norminvgauss.pdf(grid*sd+mean,a,b)*sd;cdf=cumulative_trapezoid(pdf,grid,initial=0);q=np.interp(p,cdf/cdf[-1],grid)
 else:q=np.array(model['quantiles'])
 q=q*scale;q-=q.mean();return q

def evaluate_shape(p,model):
 q=quantiles(model);sd=p[:,5].copy()
 if model['family']=='ability':sd*=np.exp(model['intercept']+model['power']*np.log1p(np.maximum(0,p[:,4])))
 z=(p[:,3]-p[:,4])/sd;n=len(q);idx=np.searchsorted(q,z);prefix=np.r_[0,np.cumsum(q)];E=(z*(2*idx-n)+prefix[-1]-2*prefix[idx])/n;half_gini=np.sum((2*np.arange(n)-n+1)*q)/(n*n);crps=sd*(E-half_gini);qs=np.interp([.025,.1,.9,.975],(np.arange(n)+.5)/n,q);cdf=np.interp(z,q,(np.arange(n)+.5)/n,left=0,right=1)
 return dict(crps=crps,low95=z<qs[0],high95=z>qs[3],coverage95=(z>=qs[0])&(z<=qs[3]),coverage80=(z>=qs[1])&(z<=qs[2]),width95=sd*(qs[3]-qs[0]),cdf=cdf)
