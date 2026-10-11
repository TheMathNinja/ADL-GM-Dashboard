"""Selected zero-mean/unit-variance NIG weekly noise; original SD unchanged."""
from pathlib import Path
import json,numpy as np

def standardized_nig(rng,shape,size,normal=None):
 a,ratio=map(float,shape);b=a*ratio
 if not np.isfinite([a,b]).all() or a<=0 or abs(b)>=a:raise ValueError('Invalid NIG shape')
 gamma=np.sqrt(a*a-b*b);v=rng.wald(1/gamma,1,size=size)
 x=b*v+np.sqrt(v)*(rng.normal(size=size) if normal is None else normal)
 return (x-b/gamma)/(a/gamma**1.5)

def parameters(root,data,season):
 path=Path(root)/'data/bonus_nig_shapes.json';saved=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
 if str(season) in saved:
  f=saved[str(season)]
  if f['scale']!=1 or max(f['training_years'])>=season:raise ValueError('Invalid NIG prior fit')
  return f
 # New seasons use the same prior-only research likelihood, never current PF.
 from scipy.stats import norminvgauss
 from scipy.special import logsumexp
 from scipy.optimize import minimize
 import bonus_predictor as e
 r=[];v=[];t=[];weights=[];years=[]
 for y in sorted(y for y in data if 2020<=y<season):
  years.append(y)
  for w in range(1,12):
   mu,sd,tau,_,_=e.adl_parameters(data,y,w);m=12-w
   r.extend((data[y][1][w:]-mu).ravel());v.extend([sd]*(m*32));t.extend([tau]*(m*32));weights.extend([1/m]*(m*32))
 if not years:raise ValueError('Missing prior NIG residual history')
 r,v,t,weights=map(np.asarray,[r,v,t,weights]);nodes,hw=np.polynomial.hermite.hermgauss(12);nodes*=np.sqrt(2);lh=np.log(hw/np.sqrt(np.pi))
 def loss(p):
  a,ratio=p;rv=norminvgauss(a,a*ratio);mean,var=rv.stats(moments='mv');sd=np.sqrt(var);z=(r[:,None]-t[:,None]*nodes)/v[:,None]
  ll=logsumexp(rv.logpdf(z*sd+mean)+np.log(sd)-np.log(v[:,None])+lh,axis=1)
  return -float(np.average(ll,weights=weights))
 fit=minimize(loss,[3,.05],bounds=[(.7,12),(-.6,.6)],method='L-BFGS-B',options={'maxiter':150})
 if not fit.success:raise ValueError('NIG prior fit failed: '+fit.message)
 f=dict(family='Normal-inverse-Gaussian',vol='original SD',test_year=season,shape=fit.x.tolist(),scale=1.,training_years=years)
 saved[str(season)]=f;path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(saved,indent=2),encoding='utf8');return f
