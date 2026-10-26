"""Shared public FS calibration; raw source values remain archived."""
import json,math
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=2)
def load_calibration(league):
    model=json.loads((Path(__file__).resolve().parents[1]/'data/live_win_probability.json').read_text())
    return model[league]['pregameCalibration']

def calibrated_projection(raw,position,source,calibration=None):
    if raw is None:return None
    value=float(raw)
    if not math.isfinite(value):raise ValueError('Nonfinite pregame projection')
    if source!='Fantasy Sharks' or not calibration:return value
    spec=calibration.get('positions',{}).get(position)
    if not spec:return value
    return max(0.,float(spec['intercept'])+float(spec['slope'])*max(0.,value))
