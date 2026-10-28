"""Prior-only starting ability for players without a Week 1 Sharks projection."""
from pathlib import Path
import json
import numpy as np,pandas as pd

def missing_fs_initial_mean(root,season,pos,ids,initial,missing,membership):
 result=np.asarray(initial,dtype=float).copy();missing=np.asarray(missing,dtype=bool)
 if not missing.any():return result
 d=Path(root)/'data/player_strength';saved=json.loads((d/'missing_fs_priors.json').read_text());fit=saved[str(season)]
 if not fit['training_years'] or max(fit['training_years'])>=season:raise ValueError('Missing-FS prior training leakage')
 coef=fit['positions'][pos];previous=pd.read_csv(d/'fallback_previous_ppg.csv',dtype={'player_id':str});previous=previous[previous.season.eq(season-1)]
 if previous.empty or previous.player_id.duplicated().any():raise ValueError('Missing or duplicate previous-season PPG for fallback prior')
 ppg=previous.set_index('player_id').ppg.to_dict();owned=set(membership.loc[membership.week.eq(1),'player_id'].astype(str))
 for i,pid in enumerate(ids):
  if missing[i]:result[i]=max(0.,coef['intercept']+coef['last_ppg']*float(ppg.get(str(pid),0.))+coef['rostered']*int(str(pid) in owned))
 if result.shape!=missing.shape or not np.isfinite(result).all() or (result<0).any():raise ValueError('Invalid missing-FS starting ability')
 return result
