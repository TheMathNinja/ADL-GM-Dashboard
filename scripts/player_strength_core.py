from player_availability import unavailable_status
"""Prior-only player ability and positional opponent-strength research engines."""
from pathlib import Path
import sqlite3,json
import numpy as np,pandas as pd
from scipy.optimize import nnls,minimize
from scipy.special import ndtr

OUT=Path('outputs/player-strength-study')
POSITIONS='QB RB WR TE PK PN DT DE LB CB S'.split()
CLUBS='ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GBP HOU IND JAC KCC LAC LAR LVR MIA MIN NEP NOS NYG NYJ PHI PIT SEA SFO TBB TEN WAS'.split()

def design(x,kind,knots=None):
 x=np.maximum(0,np.asarray(x))
 if kind=='flat':return np.ones((len(x),1))
 if kind=='scale':return x[:,None]
 if kind=='affine':return np.column_stack([np.ones(len(x)),x])
 if kind=='hinge':
  a,b=knots
  return np.column_stack([np.ones(len(x)),np.minimum(x,a),np.clip(x-a,0,b-a),np.maximum(0,x-b)])
 raise ValueError(kind)

def mapping(x,y,kind,weights=None):
 x=np.asarray(x);y=np.asarray(y);ok=np.isfinite(x)&np.isfinite(y);x=x[ok];y=y[ok]
 weights=np.ones(len(x)) if weights is None else np.asarray(weights)[ok]
 if kind=='raw':return dict(kind=kind,coefficients=[1.],knots=[])
 knots=np.quantile(x,[1/3,2/3]).tolist() if kind=='hinge' else []
 X=design(x,kind,knots);coef=nnls(X*np.sqrt(weights)[:,None],y*np.sqrt(weights))[0]
 return dict(kind=kind,coefficients=coef.tolist(),knots=knots)

def mapped(f,x):
 x=np.asarray(x)
 if f['kind']=='isotonic':return np.interp(np.maximum(0,x),f['x'],f['y'])
 if f['kind']=='raw':return np.maximum(0,x)
 shape=x.shape
 return (design(x.ravel(),f['kind'],f['knots'])@np.asarray(f['coefficients'])).reshape(shape)

def select_map(data,target='season_ppg'):
 losses={}
 for kind in ['flat','scale','affine','hinge']:
  sums=[]
  for held in sorted(data.season.unique()):
   train=data[data.season!=held];test=data[data.season==held]
   if train.empty:continue
   f=mapping(train.first_fs,train[target],kind,train.active_games)
   sums.extend(np.square(mapped(f,test.first_fs)-test[target]))
  losses[kind]=float(np.mean(sums)) if sums else np.inf
 kind=min(losses,key=losses.get)
 return mapping(data.first_fs,data[target],kind,data.active_games),losses

class Study:
 def __init__(self,league):
  self.league=league;db=sqlite3.connect(OUT/'player_strength.sqlite')
  self.panel=pd.read_sql_query('SELECT * FROM player_weeks WHERE league=?',db,params=[league])
  self.people=pd.read_sql_query('SELECT * FROM player_seasons WHERE league=?',db,params=[league])
  self.games=pd.read_sql_query('SELECT * FROM opponent_games WHERE league=?',db,params=[league])
  self.schedule=pd.read_sql_query('SELECT * FROM nfl_schedule',db);self.opp={(int(r.season),int(r.week),r.team):r.opponent for r in self.schedule.itertuples()}
  self.allowed={};self.cubes={};self.opp_cache={}
  for (year,pos),g in self.games.groupby(['season','pos']):
   self.allowed[int(year),pos]=g.pivot(index='week',columns='team',values='allowed').reindex(index=range(1,18),columns=CLUBS).to_numpy()
  for (year,pos),g in self.panel.groupby(['season','pos']):
   ids=sorted(g.player_id.unique());cube=dict(ids=ids)
   for col in ['active_score','realized_points','points','projection','team','injury_status','inactive','scheduled_bye']:
    cube[col]=g.pivot(index='week',columns='player_id',values=col).reindex(index=range(1,18),columns=ids).to_numpy()
   cube['first_fs']=g[g.week==1].set_index('player_id').reindex(ids).first_fs.to_numpy()
   cube['known_out']=np.vectorize(unavailable_status)(cube['injury_status'])
   self.cubes[int(year),pos]=cube

 def opponent_fit(self,year,pos,kind):
  trainyears=[y for y in range(2019,year) if (y,pos) in self.allowed and (y-1,pos) in self.allowed]
  X=[];Y=[];R=[]
  for y in trainyears:
   a=self.allowed[y-1,pos];b=self.allowed[y,pos];X.extend(np.nanmean(a,0)/np.nanmean(a));Y.extend(np.nanmean(b,0)/np.nanmean(b))
   centered=(b-np.nanmean(b,0))/np.nanmean(b);R.extend(centered[np.isfinite(centered)]**2)
  X=np.asarray(X);Y=np.asarray(Y);ok=np.isfinite(X)&np.isfinite(Y);X=X[ok];Y=Y[ok]
  slope=float(np.clip(np.dot(X-1,Y-1)/max(1e-9,np.dot(X-1,X-1)),0,1))
  transform=dict(kind='flat',coefficients=[1.],knots=[]) if kind=='flat' else dict(kind='carryover',coefficients=[slope],knots=[])
  if kind=='hinge':transform=mapping(X,Y,'hinge')
  def prior(y):
   old=self.allowed[y-1,pos];x=np.nanmean(old,0)/np.nanmean(old)
   p=np.ones(32) if kind=='flat' else 1+slope*(x-1) if kind=='linear' else mapped(transform,x)
   return p/np.nanmean(p)-1
  R=float(np.mean(R));ks=[.25,.5,1,2,4,8,16,32,64,128];losses=[]
  for k in ks:
   errors=[]
   for y in trainyears:
    b=self.allowed[y,pos];p=prior(y)
    for w in range(1,13):
     seen=b[:w-1];level=np.nanmean(seen) if w>1 else np.nanmean(self.allowed[y-1,pos]);n=np.isfinite(seen).sum(0);total=np.nansum(seen,0)/level-n
     mu=(k*p+total)/(k+n);truth=b[w-1]/level-1;ok=np.isfinite(truth);errors.extend((mu[ok]-truth[ok])**2)
   losses.append(float(np.mean(errors)))
  k=float(ks[int(np.argmin(losses))]);return dict(kind=kind,transform=transform,slope=slope,k=k,R=R,train_years=trainyears,validation_mse=min(losses),k_grid=ks,k_losses=losses)

 def opponent_prior(self,year,pos,fit):
  a=self.allowed[year-1,pos];x=np.nanmean(a,0)/np.nanmean(a);kind=fit['kind']
  mu=np.ones(32) if kind=='flat' else 1+fit['slope']*(x-1) if kind=='linear' else mapped(fit['transform'],x)
  return mu/np.nanmean(mu)-1

 def ratings(self,year,pos,fit,asof):
  key=year,pos,fit['kind'],fit['slope'],fit['k'],tuple(fit['transform']['coefficients']),asof
  if key in self.opp_cache:return self.opp_cache[key]
  prior=self.opponent_prior(year,pos,fit);seen=self.allowed[year,pos][:asof];n=np.isfinite(seen).sum(0)
  level=float(np.nanmean(seen)) if asof else float(np.nanmean(self.allowed[year-1,pos]));k=fit['k'];delta=(k*prior+np.nansum(seen,0)/level-n)/(k+n);variance=fit['R']/(k+n);weights=k/(k+n)
  self.opp_cache[key]=delta,variance,weights,level
  return self.opp_cache[key]

 def context(self,year,pos,fit,asof,teams,target):
  delta,var,weights,level=self.ratings(year,pos,fit,asof)
  opponents=[self.opp.get((year,target,str(team))) for team in teams];idx=np.array([CLUBS.index(t) if t in CLUBS else 0 for t in opponents]);playing=np.array([t in CLUBS for t in opponents])
  return np.where(playing,delta[idx],0.),np.where(playing,var[idx],0.),playing

 def training(self,year,pos,prior_kind,opp_kind):
  people=self.people[(self.people.pos==pos)&(self.people.season<year)&self.people.season_ppg.notna()].copy()
  if prior_kind=='selected':prior,selection=select_map(people)
  else:prior=mapping(people.first_fs,people.season_ppg,prior_kind,people.active_games);selection={}
  oppfit=self.opponent_fit(year,pos,opp_kind) if opp_kind else None
  coefficient=0.
  if oppfit:
   xx=[];yy=[]
   for y in sorted(people.season.unique()):
    c=self.cubes[y,pos];mu0=mapped(prior,c['first_fs']);X=[]
    for w in range(1,18):X.append(mu0*self.context(y,pos,oppfit,w-1,c['team'][w-1],w)[0])
    X=np.array(X);Y=c['active_score'];ok=np.isfinite(Y);xm=np.nanmean(np.where(ok,X,np.nan),0);ym=np.nanmean(Y,0);xx.extend((X-xm)[ok]);yy.extend((Y-ym)[ok])
   xx=np.asarray(xx);yy=np.asarray(yy);coefficient=float(np.clip(np.dot(xx,yy)/max(1e-8,np.dot(xx,xx)),0,1))
   # Recalibrate priors to neutral-opponent production, avoiding two corrections.
   neutral=[]
   for y in sorted(people.season.unique()):
    c=self.cubes[y,pos];factors=np.array([1+coefficient*self.context(y,pos,oppfit,w-1,c['team'][w-1],w)[0] for w in range(1,18)])
    target=np.nanmean((c['active_score']/factors)[1:],0)
    neutral.extend(dict(season=y,player_id=pid,neutral_ppg=float(v)) for pid,v in zip(c['ids'],target))
   people=people.merge(pd.DataFrame(neutral),on=['season','player_id']);people=people[people.neutral_ppg.notna()]
   if prior_kind=='selected':prior,selection=select_map(people,'neutral_ppg')
   else:prior=mapping(people.first_fs,people.neutral_ppg,prior_kind,people.active_games)
  train=[];fsx=[];fsy=[]
  for y in sorted(people.season.unique()):
   c=self.cubes[y,pos];factors=np.ones_like(c['active_score'])
   if oppfit:factors=np.array([1+coefficient*self.context(y,pos,oppfit,w-1,c['team'][w-1],w)[0] for w in range(1,18)])
   z=c['active_score']/factors;center=np.nanmean(z[1:],0);mu0=mapped(prior,c['first_fs']);fs=c['projection'][:12];valid=np.isfinite(fs)&~c['known_out'][:12]&np.isfinite(center)[None]
   for w in range(12):
    _,_,playing=self.context(y,pos,oppfit,w,c['team'][w],w+1) if oppfit else (None,None,np.array([(y,w+1,str(t)) in self.opp for t in c['team'][w]]))
    valid[w]&=playing
   fsx.extend(fs[valid]);fsy.extend((center[None]*factors[:12])[valid])
   train.append(dict(year=y,cube=c,factors=factors,actual=z[:12],center=center,prior_mu=mu0,fs_valid=valid))
  weekly=mapping(fsx,fsy,'affine')
  rv=[];fv=[];priorerr=[];bvar=[];cov=[];centervar=[]
  for r in train:
   z=r['actual'];center=r['center'];fs=mapped(weekly,r['cube']['projection'][:12])/r['factors'][:12];fs=np.where(r['fs_valid'],fs,np.nan);r['fs']=fs
   rv.extend((z-center)[np.isfinite(z)&np.isfinite(center)[None]]**2)
   fcenter=np.nanmean(fs,0);fv.extend((fs-fcenter)[np.isfinite(fs)&np.isfinite(fcenter)[None]]**2)
   ok=np.isfinite(center);priorerr.extend((center-r['prior_mu'])[ok]);bvar.extend((fcenter-center)[ok]);cov.extend(((center-r['prior_mu'])*(fcenter-center))[ok]);centervar.extend(1/np.maximum(1,np.isfinite(z).sum(0))[ok])
  Ra=max(.05,float(np.mean(rv)));Rf=max(.01*Ra,float(np.mean(fv)));Pa=max(.05*Ra,float(np.nanmean(np.square(priorerr)))-Ra*np.mean(centervar));Pb=max(.05*Rf,float(np.nanvar(bvar))-Rf/6-Ra*np.mean(centervar));Cab=float(np.nanmean(cov))+Ra*np.mean(centervar);Cab=float(np.clip(Cab,-.8*np.sqrt(Pa*Pb),.8*np.sqrt(Pa*Pb)))
  labels=[]
  for r in train:
   c=r['cube'];a=np.where(np.isfinite(c['active_score'][:12]),1.,np.where((c['inactive'][:12]==1),0.,np.nan))
   scheduled=np.array([[(r['year'],w+1,str(t)) in self.opp for t in c['team'][w]] for w in range(12)])
   labels.append(np.where(scheduled,a,np.nan))
  p0=float(np.nanmean(np.concatenate([a.ravel() for a in labels])));ks=[.25,.5,1,2,4,8,16,32,64,128];losses=[]
  for k in ks:
   errors=[]
   for lab in labels:
    for w in range(12):
     count=np.isfinite(lab[:w]).sum(0);success=np.nansum(lab[:w],0);p=(k*p0+success)/(k+count);truth=lab[w:];ok=np.isfinite(truth);errors.extend(np.broadcast_to(p,truth.shape)[ok]-truth[ok])
   losses.append(float(np.mean(np.square(errors))))
  availability=dict(mean=p0,k=float(ks[int(np.argmin(losses))]),training_brier=min(losses),k_grid=ks,k_losses=losses)
  return dict(prior=prior,prior_selection=selection,weekly=weekly,opponent=oppfit,opponent_effect=coefficient,Ra=Ra,Rf=Rf,Pa=Pa,Pb=Pb,Cab=Cab,flat_unconditioned_prior=prior_kind=='flat',availability=availability,train=train,training_years=sorted(people.season.unique().astype(int).tolist()))

def run_filter(cube,fit,q=0.,use_scores=True,use_fs=True,bias_state=True,callback=None):
 n=len(cube['ids']);m=np.column_stack([mapped(fit['prior'],cube['first_fs']),np.zeros(n)])
 P=np.zeros((n,2,2));P[:,0,0]=fit['Pa'];P[:,1,1]=fit['Pb'] if bias_state else 0.;P[:,0,1]=P[:,1,0]=fit['Cab'] if bias_state else 0.
 W=np.zeros((n,2,3));W[:,0,0]=1.;Ra=fit['Ra'];Rf=fit['Rf']+(fit['Pb'] if not bias_state else 0.)
 states=[];loss=0.;count=0
 def update(z,H,R,source):
  nonlocal m,P,W,loss,count
  ok=np.isfinite(z)
  if not ok.any():return
  ph=P@H;S=ph@H+R;innovation=np.where(ok,z-m@H,0.);K=ph/S[:,None];K[~ok]=0
  loss+=float(np.sum(np.where(ok,.5*(np.log(S)+innovation**2/S),0.)));count+=int(ok.sum())
  m=m+K*innovation[:,None];P=P-K[:,:,None]*ph[:,None,:]
  projected=np.einsum('j,njk->nk',H,W);W=W+K[:,:,None]*(np.asarray(source)[None,None,:]-projected[:,None,:])
 for w in range(12):
  if w:P[:,0,0]+=q
  fs=mapped(fit['weekly'],cube['projection'][w])/cube['factors'][w]
  fs=np.where(cube['fs_valid'][w],fs,np.nan)
  if use_fs and (w or fit.get('flat_unconditioned_prior',False)):update(fs,np.array([1.,1.]),Rf,[0.,0.,1.])
  states.append(dict(mean=m[:,0].copy(),variance=P[:,0,0].copy(),weights=W[:,0].copy()))
  if callback:callback(w,states[-1])
  if use_scores:update(cube['actual'][w],np.array([1.,0.]),Ra,[0.,1.,0.])
 return states,loss/max(1,count)

def fit_process(fit,bias_state,dynamic):
 def objective(fraction):
  r=fit;q=fraction*r['Ra']
  vals=[]
  for item in fit['train']:
   c=dict(item['cube'],actual=item['actual'],factors=item['factors'][:12],fs_valid=item['fs_valid'])
   vals.append(run_filter(c,r,q,bias_state=bias_state)[1])
  return float(np.mean(vals))
 from scipy.optimize import minimize_scalar
 if dynamic:
  opt=minimize_scalar(objective,bounds=(0,.5),method='bounded',options={'xatol':.0005,'maxiter':22})
  choices=[(objective(0.),0.),(float(opt.fun),float(opt.x)),(objective(.5),.5)];loss,fraction=min(choices)
 else:loss=objective(0.);fraction=0.
 q=fraction*fit['Ra']
 return fit,q,dict(process_variance=q,process_fraction=fraction,training_loss=loss,noise_method='matched neutral-score/source-error moments; process variance by sequential likelihood')

def normal_crps(mu,sd,y):
 z=(y-mu)/sd;return sd*(z*(2*ndtr(z)-1)+2*np.exp(-.5*z*z)/np.sqrt(2*np.pi)-1/np.sqrt(np.pi))
