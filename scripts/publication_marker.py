"""A public build marker lets the email reporter verify the deployed Pages build."""
import json
import os
from pathlib import Path

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    marker = dict(run_id=os.environ['GITHUB_RUN_ID'],
                  season=int(os.environ['CURRENT_SEASON']),
                  week=int(os.environ.get('READY_WEEK') or 0),
                  process=os.environ.get('REFRESH_PROCESS', 'manual'))
    (root / 'docs/weekly-refresh-status.json').write_text(json.dumps(marker, indent=2) + '\n')
