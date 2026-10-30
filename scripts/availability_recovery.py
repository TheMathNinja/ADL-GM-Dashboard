from player_availability import unavailable_status
"""Status-aware availability learned from past-only weekly MFL histories.
Ability estimates are not modified. Scheduled byes and known next-game
absences remain handled by the caller.
"""
import numpy as np

def design(c,w,target,scheduled):
 sched=scheduled;active=np.isfinite(c['active_score']);status=np.char.upper(np.asarray(c['injury_status'],str));absent=np.vectorize(unavailable_status)(status)&~(active&(np.nan_to_num(c['points'])!=0));labs=np.where(active,1.,np.where((c['inactive']==1)|absent,0.,np.nan));labs=np.where(sched,labs,np.nan)
 n=len(c['ids']);state=np.zeros(n,int);duration=np.zeros(n);returned=np.zeros(n)
 for j in range(n):
  ix=np.flatnonzero(np.isfinite(labs[:w,j]));last=ix[-1] if len(ix) else None
  if last is None:state[j]=5;continue
  if labs[last,j]==1:
   state[j]=0;returned[j]=absent[max(0,last-3):last,j].any()
  else:
   st=status[last,j];state[j]=1 if st in ['IR','IR-PUP','IR-NFI','PUP','NFI'] else 2 if st=='IR-R' else 3 if st in ['S','SUSPENDED'] else 4
   for k in ix[::-1]:
    if labs[k,j]==1:break
    duration[j]+=1
 hist=(np.nansum(labs[:w],0)+2*.85)/(np.isfinite(labs[:w]).sum(0)+2);lead=(target-w-1)/10
 # Fixed schema: intercept, position dummies elsewhere; state, horizon interactions,
 # duration interactions, healthy return flag and season appearance history.
 one=np.eye(6)[state];x=np.c_[np.ones(n),one[:,1:],one*lead,one*lead**2,one*np.log1p(duration[:,None]),returned,hist, hist*one[:,0]]
 return x


def predict(model,c,pos,week,target,scheduled):
 if model.get('family')=='simple_constrained_v1':
  if week>0:
   from simple_availability import predict as constrained_predict
   return constrained_predict(model,c,pos,week,target,scheduled)
  model=model['legacy']
 x=design(c,week,target,scheduled)
 position=np.tile(np.eye(len(model['positions']))[model['positions'].index(pos),1:],(len(x),1))
 eta=np.c_[x,position]@np.asarray(model['coef'])
 return 1/(1+np.exp(-np.clip(eta,-40,40)))
