"""Bind MFL verification to the exact validated scores from the parent refresh."""
import argparse, hashlib, json, math, os, re
from pathlib import Path


def reports_digest(reports):
    return hashlib.sha256(json.dumps(reports, sort_keys=True).encode()).hexdigest()


def validate_snapshot(snapshot, league, season, week, run_id):
    if not isinstance(snapshot, dict) or (snapshot.get('version'), snapshot.get('league'), snapshot.get('season'), snapshot.get('week'), str(snapshot.get('run_id'))) != (1, league, season, week, str(run_id)):
        raise ValueError('Bonus Games source snapshot belongs to another refresh')
    if not re.fullmatch(r'\d+', str(run_id)) or not 1 <= week <= 17:
        raise ValueError('Invalid Bonus Games source context')
    reports = snapshot.get('reports', {})
    if not isinstance(reports, dict) or set(reports) != {'TPF', 'PPF'}:
        raise ValueError('Bonus Games source must contain actual and potential scores')
    ids = {f'{i:04}' for i in range(1, 33)}
    for field in reports.values():
        if not isinstance(field, dict) or set(field) != ids:
            raise ValueError('Bonus Games source must include all 32 teams')
        for values in field.values():
            if not isinstance(values, list) or len(values) != week or any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
                raise ValueError('Bonus Games source must cover every completed week exactly')
    if snapshot.get('reports_sha256') != reports_digest(reports):
        raise ValueError('Bonus Games source snapshot checksum mismatch')
    return reports


def request_body(snapshot, mode='official'):
    validate_snapshot(snapshot, snapshot['league'], snapshot['season'], snapshot['week'], snapshot['run_id'])
    if mode not in ('official', 'preview'):
        raise ValueError('Invalid Bonus Games request mode')
    body = {k: snapshot[k] for k in ('version', 'league', 'season', 'week', 'run_id', 'reports')}
    body['mode'] = mode
    body['source_sha256'] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return body


def main():
    p = argparse.ArgumentParser(); p.add_argument('--league', required=True, choices=['ADL', 'FAFL']); p.add_argument('--out', required=True, type=Path); a = p.parse_args()
    from sync_bonus_mfl import reports, ROOT
    season = int(os.environ['CURRENT_SEASON']); week = int(os.environ['READY_WEEK'])
    data = reports(ROOT, a.league, season, week)
    snapshot = dict(version=1, league=a.league, season=season, week=week, run_id=os.environ['GITHUB_RUN_ID'], reports=data, reports_sha256=reports_digest(data))
    validate_snapshot(snapshot, a.league, season, week, os.environ['GITHUB_RUN_ID'])
    a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(json.dumps(snapshot, indent=2)+'\n')
    print(f'{a.league}: captured exact Week {week} Bonus Games source for parent {snapshot["run_id"]}')


if __name__ == '__main__': main()
