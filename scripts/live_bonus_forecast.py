"""Cache unchanged deployed Bonus/Playoffs trajectories for later NFL weeks."""
from functools import lru_cache
from pathlib import Path
import hashlib,os
import numpy as np

@lru_cache(maxsize=2)
def remaining_forecast(league,season,live_week,draws):
    root=Path(__file__).resolve().parents[1]
    if live_week>=12:
        return dict(ids=[f'{i:04}' for i in range(1,33)],future=np.empty((draws,0,32)),potential=np.empty((draws,0,32)),metadata=dict(observedWeek=11,sourceCommit=os.environ.get('GITHUB_SHA'),laterWeeks=[]))
    import pandas as pd
    from quarterly_bonus import forecast
    path=root/('data/weekly_team_metrics.csv' if league=='ADL' else 'data/current_weekly.csv')
    current=pd.read_csv(path,dtype={'franchise_id':str}).rename(columns={'franchise_score':'points','potential_points':'potential'})
    observed=live_week-1
    current=current[(current.season==season)&(current.week<=observed)]
    if observed<1 or current.empty or int(current.week.max())!=observed:
        raise ValueError('Final Bonus odds need a deployed forecast through the preceding week')
    result=forecast(root,current,league,season,observed,draws)
    # The shared forecast includes the live week. Replace that week with the
    # player-clock simulation, retaining the exact later-week PF/Potential pairs.
    first=live_week-observed
    future=result['future'][:,first:];potential=result['future_potential'][:,first:]
    digest=hashlib.sha256(future.astype('<f8').tobytes()+potential.astype('<f8').tobytes()).hexdigest()
    metadata=dict(observedWeek=observed,laterWeeks=list(range(live_week+1,13)),sourceCommit=os.environ.get('GITHUB_SHA'),draws=draws,trajectoryHash=digest,model=result['model'])
    return dict(ids=result['ids'],future=future,potential=potential,metadata=metadata)
