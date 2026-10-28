"""Regenerate the shared initial active-game ability for status-credit tapering."""
from pathlib import Path
import argparse,json
import numpy as np,pandas as pd
from player_team_strength import RuntimeStudy
from player_strength_core import mapped
from missing_fs_prior import missing_fs_initial_mean

def build(root,season):
 root=Path(root);d=root/'data/player_strength';study=RuntimeStudy(root,season);fits=json.loads((d/f'fits_{season}.json').read_text());members=pd.read_csv(d/'fantasy_rosters.csv',dtype={'player_id':str});rows=[]
 for rec in fits:
  if max(rec['training_years'])>=season:raise ValueError('Initial ability training leakage')
  pos=rec['pos'];c=study.cubes[season,pos];missing=(~np.isfinite(c['first_fs']))|(~np.isfinite(c['projection'][0]))|c['known_out'][0]|(c['scheduled_bye'][0]==1)
  initial=missing_fs_initial_mean(root,season,pos,c['ids'],mapped(rec['prior']['prior'],c['first_fs']),missing,members)
  rows.extend(dict(player_id=pid,pos=pos,preseason_ppg=float(value),source='missing_or_unavailable_week1_fallback' if bad else 'calibrated_week1_FS',fit_year=season) for pid,value,bad in zip(c['ids'],initial,missing))
 result=pd.DataFrame(rows)
 if result.player_id.duplicated().any() or not np.isfinite(result.preseason_ppg).all():raise ValueError('Invalid shared initial ability')
 result.to_csv(root/f'data/lineup_preseason_{season}.csv',index=False)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--season',type=int,required=True);a=p.parse_args();x=build(a.root,a.season);print('Rebuilt shared initial ability',a.season,len(x),'players')
