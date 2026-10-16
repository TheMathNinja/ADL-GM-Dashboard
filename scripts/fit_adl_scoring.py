"""Validate the versioned, prior-season-only selected ADL model artifacts.

The annual fit is produced from the archived R05/L17 player forecasts and
prior normalized team seasons. Weekly runs update player posteriors and current
ownership, never refit against current-season future outcomes.
"""
from pathlib import Path
import json,argparse
from player_blend_scoring import parameters,VERSION
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--season',type=int,default=2026);a=p.parse_args();saved=json.loads((a.root/'data/adl_scoring_model.json').read_text());f=saved.get(str(a.season),{})
 if f.get('version')!=VERSION:raise ValueError('Missing selected annual player-blend fit; refusing to use an old model')
 if max(f['training_years']+f['innovation_training_years'])>=a.season:raise ValueError('Training leakage')
 print('Selected ADL prior fit available for',a.season,VERSION)
