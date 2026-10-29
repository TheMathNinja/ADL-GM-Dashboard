"""Shared mean-one scoring environment for the seasonal joint PF/Potential world."""
import numpy as np

def apply_environment(future,potential,season,week,fit):
    if fit.get('mean_adjustment',False):raise ValueError('Mean adjustments are not enabled by this uncertainty-only model')
    if max(fit['training_years'])>=season:raise ValueError('League environment training leakage')
    if not 1<=week<12:raise ValueError('League environment needs 1-11 completed weeks')
    future=np.asarray(future,dtype=float);potential=np.asarray(potential,dtype=float)
    if future.ndim!=3 or future.shape!=potential.shape or future.shape[1:]!=(12-week,32):raise ValueError('Invalid shared score trajectory dimensions')
    n=len(future)
    if n<2 or n%2:raise ValueError('Shared environment needs even simulation count')
    if not np.isfinite(future).all() or not np.isfinite(potential).all() or (potential<future).any():raise ValueError('Invalid PF/Potential pairs')
    v=np.asarray(fit['coef'],dtype=float)
    if not np.isfinite(v).all() or (v<0).any():raise ValueError('Invalid shared factor SD')
    family=fit['family'];sigma=float(v[0])
    if family=='shared_linear' and len(v)==3:tau=float(v[1]+v[2]*(11-week)/10)
    elif family=='shared_sqrt' and len(v)==2:tau=float(v[1]/np.sqrt(week))
    elif family=='shared_weekly' and len(v)==1:tau=0.
    else:raise ValueError('Unknown shared environment family')
    rng=np.random.default_rng(111903+season*100+week)
    z=rng.normal(size=(n//2,1));e=rng.normal(size=(n//2,12-week))
    z=np.concatenate([z,-z]);e=np.concatenate([e,-e])
    factor=np.exp(tau*z+sigma*e-.5*(tau*tau+sigma*sigma))
    # Scale both sides of the same PF/Potential pair, then retain the score grid.
    scores=np.round(future*factor[:,:,None],1)
    pots=np.maximum(potential*factor[:,:,None],scores)
    return scores,pots,dict(**fit,weekly_log_sd=sigma,persistent_log_sd=tau,scope='one factor per simulation/week shared by all 32 teams',expected_factor=1.,factor_mean_by_week=factor.mean(0).tolist())
