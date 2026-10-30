"""Constrained recorded-score appearance probabilities, not medical clearance.

Uses only origin-available MFL status/return-date history. Player scoring
ability, scheduled-game gates and confirmed next-game absences stay separate.
"""
from datetime import date
import numpy as np

ABSENT=frozenset({'OUT','O','SUSPENDED','S','IR','IR-R','IR-PUP','IR-NFI','PUP','NFI'})

def matrix(model,c,pos,week,target,scheduled):
 if week<1:raise ValueError('Constrained availability requires a completed week')
 active=np.isfinite(c['active_score']);status=np.char.upper(np.asarray(c['injury_status'],str))
 absent=np.isin(status,list(ABSENT))&~(active&(np.nan_to_num(c['points'])!=0))
 labs=np.where(active,1.,np.where((c['inactive']==1)|absent,0.,np.nan));labs=np.where(scheduled,labs,np.nan)
 n=len(c['ids']);state=np.zeros(n,int);duration=np.zeros(n);returned=np.zeros(n)
 for j in range(n):
  ix=np.flatnonzero(np.isfinite(labs[:week,j]));last=ix[-1] if len(ix) else None
  if last is None:state[j]=5;continue
  if labs[last,j]==1:returned[j]=absent[max(0,last-3):last,j].any()
  else:
   st=status[last,j];state[j]=1 if st in {'IR','IR-PUP','IR-NFI','PUP','NFI'} else 2 if st=='IR-R' else 3 if st in {'S','SUSPENDED'} else 4
   for k in ix[::-1]:
    if labs[k,j]==1:break
    duration[j]+=1
 weights=2.**(-np.arange(week-1,-1,-1)/float(model['half']))
 known=scheduled[:week];hist=((active[:week]*known*weights[:,None]).sum(0)+1.7)/((known*weights[:,None]).sum(0)+2)
 lead=(target-week-1)/10;one=np.eye(6)[state]
 x=np.c_[np.ones(n),one[:,1:],one*lead,one*lead**2,one*np.log1p(duration[:,None]),returned,hist,hist*one[:,0]]
 position=np.tile(np.eye(len(model['positions']))[model['positions'].index(pos),1:],(n,1));x=np.c_[x,position]
 count=active[:week].sum(0);mean=np.divide(np.nansum(c['active_score'][:week],0),count,out=np.zeros(n),where=count>0)
 previous=np.nan_to_num(np.asarray(c.get('previous_ppg',np.zeros(n)),float))
 if 'previous_ppg' not in c and abs(model['coef'][38])>1e-12:raise ValueError('Missing prior-season PPG input')
 x=np.c_[x,np.log1p(np.maximum(0,mean)),np.log1p(np.maximum(0,previous))]
 if 'mfl_return_date' not in c or 'availability_calendar' not in c:raise ValueError('Missing weekly MFL return-date inputs')
 calendar=c['availability_calendar'];end=date.fromisoformat(calendar['season_end']);within=np.zeros(n);timing=np.zeros(n);beyond=np.zeros(n)
 for j in range(n):
  text=str(c['mfl_return_date'][week-1,j] or '');gd=calendar['games'].get(str(target),{}).get(str(c['team'][week-1,j]))
  if not text or text=='nan' or not gd:continue
  try:rd=date.fromisoformat(text);game=date.fromisoformat(gd)
  except ValueError:continue
  if rd>end:beyond[j]=1.
  else:
   within[j]=1.;z=np.clip((game-rd).days/7/float(model['tau']),-35,35);timing[j]=1/(1+np.exp(-z))
 return np.c_[x,within,within*timing,beyond]

def predict(model,c,pos,week,target,scheduled):
 coef=np.asarray(model['coef'],float)
 if len(coef)!=42:raise ValueError('Unexpected constrained appearance schema')
 if not (coef[25]>=0 and coef[26]>=0 and coef[37]>=0 and coef[38]>=0 and coef[40]>=0 and coef[41]<=coef[39]<=0):raise ValueError('Invalid appearance monotonicity constraints')
 eta=matrix(model,c,pos,week,target,scheduled)@coef
 return 1/(1+np.exp(-np.clip(eta,-40,40)))
