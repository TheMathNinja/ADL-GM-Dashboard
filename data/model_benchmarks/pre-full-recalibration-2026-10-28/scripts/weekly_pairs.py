"""Conditional empirical PF/Potential weekly pairs for Bonus Games."""
import numpy as np
import pandas as pd

def draw_pairs(future_pf,history,observed_pf,observed_potential,kind='team',k=200,seed=6123,calibrated=False,future_byes=None):
    """Return (..., PF/Potential) pairs without changing any supplied PF draw.

    history must contain only earlier seasons from the same league; fields are
    season, week, franchise_id, points, potential. Current observations must
    stop at the forecast checkpoint. Conditional draws preserve the supplied PF distribution exactly.
    """
    pf=np.asarray(future_pf,dtype=float)
    observed_pf=np.asarray(observed_pf,dtype=float)
    observed_potential=np.asarray(observed_potential,dtype=float)
    if pf.ndim!=3 or observed_pf.shape!=observed_potential.shape or observed_pf.shape[1]!=pf.shape[2]:
        raise ValueError('Expected simulation x week x team arrays and matching observations')
    if not np.isfinite(pf).all() or not np.isfinite(observed_pf).all() or not np.isfinite(observed_potential).all():
        raise ValueError('Nonfinite paired-score inputs')
    if (pf<0).any() or (observed_potential<observed_pf-1e-6).any():
        raise ValueError('Invalid PF/Potential observations')
    if kind.endswith('_bye') and ('byes' not in history or future_byes is None or len(future_byes)!=pf.shape[1]):
        raise ValueError('Bye-aware pairs require historical and future weekly bye counts')
    history=history[(history.week<=12)&(history.potential>=history.points)].copy()
    train=rows(history)
    scale=observed_pf.mean() if observed_pf.size else history.points.mean()
    if scale<=0 or train.empty:raise ValueError('Insufficient scoring history')
    prior=(observed_potential-observed_pf).mean(0)/scale if len(observed_pf) else np.full(pf.shape[2],(history.potential-history.points).mean()/scale)
    correction=calibration(train,kind,k) if calibrated else 0.
    rng=np.random.default_rng(seed);pot=np.empty_like(pf)
    for team in range(pf.shape[2]):
        for week in range(pf.shape[1]):
            values,inverse=np.unique(pf[:,week,team],return_inverse=True)
            # Chunk conditional distributions to keep 12,000-draw forecasts small.
            candidates=[]
            for start in range(0,len(values),256):
                v=values[start:start+256]
                target=pd.DataFrame(dict(x=v/scale,prior=prior[team],half=int(len(observed_pf)+week+1>6),scale=scale,byes=future_byes[week] if future_byes is not None else 0))
                candidates.append(np.maximum(0,predict(train,target,kind,k)+correction*scale))
            distributions=np.vstack(candidates)
            selected=rng.integers(distributions.shape[1],size=len(pf))
            pot[:,week,team]=pf[:,week,team]+distributions[inverse,selected]
    return np.stack([pf,pot],axis=-1)

def rows(d):
    out=[]
    for year,g in d.groupby('season'):
        for week in sorted(g.week.unique()):
            if week<2 or week>12: continue
            prior=g[g.week<week]
            if prior.empty: continue
            scale=prior.points.mean()
            means=prior.assign(gap=prior.potential-prior.points).groupby('franchise_id').gap.mean()
            for r in g[g.week==week].itertuples():
                if r.franchise_id not in means.index:continue
                out.append(dict(year=int(year),week=int(week),team=r.franchise_id,scale=scale,pf=r.points,pot=r.potential,gap=r.potential-r.points,x=r.points/scale,prior=means[r.franchise_id]/scale,half=int(week>6),byes=getattr(r,'byes',0)))
    return pd.DataFrame(out)

def predict(train,test,kind,k=150):
    # Empirical neighbors retain skew, zeros and tails; no Gaussian gap assumption.
    distance=((test.x.to_numpy()[:,None]-train.x.to_numpy()[None,:])/.35)**2
    if kind in ('team','half','team_bye'):
        distance+=((test.prior.to_numpy()[:,None]-train.prior.to_numpy()[None,:])/.18)**2
    if kind=='half':distance+=4*(test.half.to_numpy()[:,None]!=train.half.to_numpy()[None,:])
    if kind.endswith('_bye'):distance+=((test.byes.to_numpy()[:,None]-train.byes.to_numpy()[None,:])/2)**2
    k=min(k,len(train));ix=np.argpartition(distance,k-1,axis=1)[:,:k]
    return train.gap.to_numpy()[ix]/train.scale.to_numpy()[ix]*test.scale.to_numpy()[:,None]


def calibration(train,kind,k):
    # Fit correction using earlier-season predictions, never in-sample residuals.
    predicted=[];actual=[]
    for year in sorted(train.year.unique())[2:]:
        past=train[train.year<year];target=train[train.year==year]
        predicted.append(predict(past,target,kind,k)/target.scale.to_numpy()[:,None])
        actual.extend(target.gap/target.scale)
    if not predicted:return 0.
    z=np.vstack(predicted);target=np.mean(actual)
    lo,hi=-1.,1.
    for _ in range(50):
        mid=(lo+hi)/2
        if np.maximum(0,z+mid).mean()<target:lo=mid
        else:hi=mid
    return (lo+hi)/2



def future_pairs(root,current,league,season,week,future_pf):
    from pathlib import Path
    root=Path(root)
    if league=='ADL':
        history=pd.read_csv(root/'data/bonus_history.csv',dtype={'franchise_id':str}).rename(columns={'points_for_week':'points','potential_points_week':'potential'})
    else:
        history=pd.read_csv(root/'data/historical_weekly.csv',dtype={'franchise_id':str})
    history=history[(history.season>= (2018 if league=='ADL' else 2020)) & (history.season<season) & (history.week<=12)].copy()
    excluded=int((history.potential<history.points-1e-6).sum())
    counts=pd.read_csv(root/'data/bonus_nfl_byes.csv')
    history=history.merge(counts,on=['season','week'],how='left',validate='many_to_one')
    if history.byes.isna().any():raise ValueError('Missing historical NFL bye counts')
    future_counts=counts[counts.season==season].set_index('week').byes.reindex(range(week+1,13))
    if future_counts.isna().any():raise ValueError('Missing future NFL bye counts')
    ids=sorted(current.franchise_id.unique())
    observed_pf=current.pivot(index='week',columns='franchise_id',values='points').reindex(index=range(1,week+1),columns=ids).to_numpy()
    observed_potential=current.pivot(index='week',columns='franchise_id',values='potential').reindex(index=range(1,week+1),columns=ids).to_numpy()
    k=200 if league=='ADL' else 100
    calibrated=league=='FAFL'
    pairs=draw_pairs(future_pf,history,observed_pf,observed_potential,kind='team_bye',k=k,seed=281239+season*100+week,calibrated=calibrated,future_byes=future_counts.to_numpy())
    metadata=dict(method='conditional_empirical_gap',conditioned_on=['simulated PF','observed team PF/Potential gap','NFL bye count'],neighbors=k,calibrated_on_past_only=calibrated,training_years=sorted(map(int,history.season.unique())),excluded_invalid_pairs=excluded,validation='2023 selection; rolling 2024-2025 holdout; residual downward bias remains',tiebreak_order=['All-Play wins','Points For','Potential Points'])
    return pairs,metadata
