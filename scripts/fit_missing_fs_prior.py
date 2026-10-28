"""Reproduce prior-only missing-FS coefficients from archived ADL player-seasons."""
from pathlib import Path
import argparse,json
import numpy as np,pandas as pd

def fit(root,season):
 d=Path(root)/'data/player_strength';data=pd.read_csv(d/'missing_fs_training.csv');tr=data[(data.season<season)&data.missing];positions={}
 if tr.empty:raise ValueError('Missing prior fallback training data')
 for pos,g in tr.groupby('pos'):
  x=g[['last_ppg','rostered']].to_numpy();mean=x.mean(0);sd=x.std(0);sd[sd<1e-10]=1.;z=np.c_[np.ones(len(g)),(x-mean)/sd];b=np.linalg.lstsq(z.T@z+np.diag([0.,10.,10.]),z.T@g.target.to_numpy(),rcond=None)[0];slope=b[1:]/sd
  positions[pos]=dict(intercept=float(b[0]-mean@slope),last_ppg=float(slope[0]),rostered=float(slope[1]),n=len(g))
 result=dict(version='missing-fs-last-ppg-adl-week1-rostered-v1',training_years=sorted(int(y) for y in tr.season.unique()),target='Weeks 2-12 active-game PPG',ridge=10.,positions=positions)
 path=d/'missing_fs_priors.json';saved=json.loads(path.read_text()) if path.exists() else {};saved[str(season)]=result;path.write_text(json.dumps(saved,indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--season',type=int,required=True);a=p.parse_args();fit(a.root,a.season)
