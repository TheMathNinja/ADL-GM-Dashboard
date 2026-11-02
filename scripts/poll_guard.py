"""Throttle a known poll transport outage without claiming that publication succeeded."""
import argparse
import hashlib
import http.client
import json
import os
import sys
import time
import urllib.error
from pathlib import Path


def guarded(check, path, cycle, now=time.time):
    try:
        state=json.loads(path.read_text())
    except (OSError,ValueError):
        state={}
    # The workflow saves an immutable cache only when this invocation changes state.
    path.unlink(missing_ok=True)
    stamp=now()
    if state.get('cycle')==cycle and stamp < state.get('probe_at',0) <= stamp+3600:
        print('Known transport outage; next probe deferred. Publication is NOT verified.')
        return
    try:
        check()
    except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as error:
        code=getattr(error,'code',None)
        if code is not None and code not in (429,500,502,503,504):raise
        # Include the failing call site so a second dependency gets its own incident.
        import traceback
        frames=[f for f in traceback.extract_tb(error.__traceback__) if Path(f.filename).parent==Path(__file__).parent]
        key=hashlib.sha256(str(([(f.name,f.lineno) for f in frames],type(error).__name__,str(error))).encode()).hexdigest()
        repeat=state.get('cycle')==cycle and state.get('key')==key
        count=state.get('count',0)+1 if repeat else 1
        path.write_text(json.dumps(dict(cycle=cycle,key=key,count=count,probe_at=now()+min(3600,300*2**min(count-1,4)))))
        if not repeat:raise
        print('Existing transport incident persists. Publication is NOT verified; another probe is scheduled.')
        return
    if state.get('key'):path.write_text('{}')


if __name__=='__main__':
    process=sys.argv.pop(1)
    import score_corrections,score_readiness
    module={'corrections':score_corrections,'preliminary':score_readiness}[process]
    if '--dry-run' in sys.argv:module.main()
    else:
        parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--week',type=int)
        args,_=parser.parse_known_args()
        season=int(os.environ['CURRENT_SEASON'])
        week=args.week or module.target_week(module.datetime.now(module.timezone.utc),season)
        guarded(module.main,Path('.poll_transport.json'),f'{process}:{season}:{week}:{os.environ["LEAGUE_ID"]}')
