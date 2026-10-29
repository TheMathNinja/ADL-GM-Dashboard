"""Shared source-specific public pregame calibration; raw source values remain archived."""
import json,math
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=2)
def load_calibration(league):
    model=json.loads((Path(__file__).resolve().parents[1]/'data/live_win_probability.json').read_text())
    calibration=dict(model[league]['pregameCalibration'])
    if model[league].get('shape')=='ContinuousNIG':
        calibration['conditionalLiveModel']={k:v for k,v in model[league].items() if k!='pregameCalibration'}
    return calibration

def calibrated_projection(raw,position,source,calibration=None,fs_feed_available=True,submitted_starter=True,start_counts=None):
    if raw is None:return None
    value=float(raw)
    if not math.isfinite(value):raise ValueError('Nonfinite pregame projection')
    if not calibration:return value
    if source=='Fantasy Sharks' and calibration.get('unifiedFSPositions'):
        spec=calibration['unifiedFSPositions'].get(position)
        if not spec:return value
        if start_counts is None:raise ValueError('Unified FS calibration requires same-week ADL and FAFL start counts')
        result=float(spec['intercept'])+float(spec['slope'])*max(0.,value)
        for league,key in [('ADL','adlIncrements'),('FAFL','faflIncrements')]:
            count=int(start_counts.get(league,0))
            if count<0:raise ValueError('Negative submitted start count')
            result+=sum(spec[key][:count])
        return max(0.,result)
    key=('positions' if submitted_starter else 'fsBenchPositions') if source=='Fantasy Sharks' else (('ytdPositions' if submitted_starter else 'ytdRosteredPositions') if fs_feed_available else 'ytdGeneralPositions') if source=='YTD PPG' else None
    if submitted_starter and source=='YTD PPG' and calibration.get('continuousNIGStarterCalibration'):key='ytdPositions'
    spec=calibration.get(key,{}).get(position) if key else None
    if not spec:return value
    return max(0.,float(spec['intercept'])+float(spec['slope'])*max(0.,value))

