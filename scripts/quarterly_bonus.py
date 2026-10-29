"""Single quarterly model entry point shared by Bonus Games and Playoffs."""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
import bonus_predictor as e
from weekly_pairs import future_pairs
from league_environment import apply_environment
DEFAULT_SIMULATIONS=12000

def forecast(root,current,league,season,week,n=DEFAULT_SIMULATIONS,primary=None):
 current=current[current.week<=week].copy();current.franchise_id=current.franchise_id.astype(str).str.zfill(4)
 ids=sorted(current.franchise_id.unique());s=current.pivot(index='week',columns='franchise_id',values='points').reindex(index=range(1,week+1),columns=ids).to_numpy();p=current.pivot(index='week',columns='franchise_id',values='potential').reindex(index=range(1,week+1),columns=ids).to_numpy()
 if len(ids)!=32 or not np.isfinite(s).all() or not np.isfinite(p).all():raise ValueError('Incomplete shared quarterly source')
 if week<12:
  if league=='ADL':
   data=e.load_adl(root,season);data[season]=(ids,np.vstack([s,np.full((12-week,32),np.nan)]),np.vstack([p,np.full((12-week,32),np.nan)]));mu,sigma,tau,gap,model=e.adl_parameters(data,season,week,e.adl_availability_credit(root,season,week,ids),root=root)
  else:mu,sigma,tau,gap,model=e.fafl_parameters(root,current,season,week)
  if league=='ADL':
   future=e.draw_future(mu,sigma,tau,league,season,week,n,shape=model['weekly_shape'])
  else:future=e.draw_future(mu,sigma,tau,league,season,week,n)
  pairs,pair_metadata=future_pairs(root,current,league,season,week,future)
  future_potential=pairs[...,1]
  environment=model.get('league_environment') if league=='ADL' else None
  if environment:
   future,future_potential,metadata=apply_environment(future,future_potential,season,week,environment)
   model={**model,'league_environment':metadata}
  model={**model,"potential_points":pair_metadata}
 else:mu=s.mean(0);sigma=tau=0.;gap=np.zeros(32);model={'model':'completed','training_years':[]};future=np.zeros((n,0,32));future_potential=future.copy()
 events=e.event_forecasts(s,p,week,future,gap,league,future_potential)

 credits=np.stack([e.segment_samples(s,p,week,future,gap,league,a,b,future_potential)[1]/2 for _,a,b in e.EVENTS[:4]],axis=1)
 if not np.allclose(credits.sum(2),16):raise ValueError('Invalid shared quarterly totals')
 reg_season_credits=e.segment_samples(s,p,week,future,gap,league,0,12,future_potential)[1]/2
 if not np.allclose(reg_season_credits.sum(1),16):raise ValueError('Invalid shared Reg Season totals')
 native=future
 return dict(ids=ids,s=s,p=p,mu=mu,sigma=sigma,tau=tau,gap=gap,model=model,future=future,future_potential=future_potential,native_future=native,events=events,quarterly_credits=credits,reg_season_credits=reg_season_credits)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--current',type=Path,required=True);parser.add_argument('--primary',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--season',type=int,required=True);parser.add_argument('--week',type=int,required=True);parser.add_argument('--simulations',type=int,default=DEFAULT_SIMULATIONS);a=parser.parse_args()
 current=pd.read_csv(a.current,dtype={'franchise_id':str}).rename(columns={'points_for_week':'points','potential_points_week':'potential'});primary=json.loads(a.primary.read_text(encoding='utf8'));f=forecast(a.root,current,'ADL',a.season,a.week,a.simulations,primary)
 order=[f['ids'].index(t) for t in primary['ids']];a.out.mkdir(parents=True,exist_ok=True)
 f['native_future'][:,:,order].astype('<f8').tofile(a.out/'native.bin');f['quarterly_credits'][:,:,order].astype('<f8').tofile(a.out/'quarters.bin')
 f['reg_season_credits'][:,order].astype('<f8').tofile(a.out/'reg-season.bin')
 f['future_potential'][:,:,order].astype('<f8').tofile(a.out/'potential.bin')
 means={q:f['events'][q]['probabilities'][:,2]+.5*f['events'][q]['probabilities'][:,1] for q,_,_ in e.EVENTS[:4]}
 (a.out/'metadata.json').write_text(json.dumps(dict(ids=primary['ids'],simulations=a.simulations,model=f['model'],mu=(f['mu'].mean(0) if np.ndim(f['mu'])==2 else f['mu'])[order].tolist(),weekly_sd=float(f['sigma']),strength_sd=float(f['tau']),quarterly_means={q:v[order].tolist() for q,v in means.items()})),encoding='utf8')
if __name__=='__main__':main()
