"""Reuse only an independently verified, equivalent daily delivery."""
import json
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

REQUIRED={'Refresh SalAdj and Commissioner data','Apply waiver cap corrections',
          'Refresh rosters, EXT and Salary Cap Manager / refresh','Run Commissioner alerts',
          'Verify daily maintenance package'}

def eastern_time(stamp):
    return datetime.fromisoformat(stamp.replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York'))

def prior_delivery(current,history,intent,read_jobs):
    for run in history:
        if (run['id']==current['id'] or run.get('head_branch')!='main' or run.get('conclusion')!='success'
            or run.get('workflow_id')!=current['workflow_id'] or run['created_at']>=current['created_at']
            or eastern_time(run['created_at']).hour<5
            or eastern_time(run['created_at']).date()!=eastern_time(current['created_at']).date()):continue
        jobs=read_jobs(run['id'])
        passed={j['name'] for j in jobs if j['conclusion']=='success'}
        if REQUIRED|{intent} <= passed:return str(run['id'])
    return ''

def main():
    def api(path):
        return json.loads(subprocess.check_output(['gh','api','repos/'+os.environ['GITHUB_REPOSITORY']+'/'+path],timeout=30))
    current=api('actions/runs/'+os.environ['GITHUB_RUN_ID'])
    prior=''
    if os.environ.get('FORCE')!='true':
        history=api(f"actions/workflows/{current['workflow_id']}/runs?branch=main&status=success&per_page=100")['workflow_runs']
        prior=prior_delivery(current,history,os.environ['INTENT'],lambda i:api(f'actions/runs/{i}/jobs?per_page=100')['jobs'])
    with open(os.environ['GITHUB_OUTPUT'],'a') as f:print('prior='+prior,file=f)
    print('Verified prior package '+prior if prior else 'Fresh daily package required')

if __name__=='__main__':main()
