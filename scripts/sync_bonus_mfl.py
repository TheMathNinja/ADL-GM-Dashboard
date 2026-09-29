"""Require verified MFL standings entries for official weekly refreshes.

The existing Apps Script owns commissioner credentials and form reconciliation.
Reference!Z12:Z13 is the authenticated request/ack channel, using the same
service account and five-minute bridge as Payouts. No second score scrape.
"""
import argparse
import csv
import hashlib
import json
import math
import os
import time
from pathlib import Path
from sync_payouts import BOOKS, ROOT, load_scores


def reports(root, league, season, week):
    load_scores(root, league, season, week)  # complete, finite, reconciled source
    path = root/'data'/('weekly_team_metrics.csv' if league == 'ADL' else 'current_weekly.csv')
    result = {'TPF': {}, 'PPF': {}}
    for row in csv.DictReader(path.open(encoding='utf-8-sig')):
        fid, w = row['franchise_id'].zfill(4), int(row['week'])
        for field, key in [('TPF', 'total_points' if league == 'ADL' else 'points'),
                           ('PPF', 'potential_points' if league == 'ADL' else 'potential')]:
            values = result[field].setdefault(fid, [None]*week)
            if not 1 <= w <= week or values[w-1] is not None:
                raise ValueError('Duplicate or invalid Bonus Games source week')
            values[w-1] = round(float(row[key]), 4)
    ids = {f'{i:04}' for i in range(1, 33)}
    for field in result.values():
        if set(field) != ids or any(v is None or not math.isfinite(v) for team in field.values() for v in team):
            raise ValueError('Incomplete Bonus Games franchise source')
    return result


def main():
    import gspread
    p = argparse.ArgumentParser()
    p.add_argument('--league', choices=BOOKS, required=True)
    p.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    season = int(os.environ.get('CURRENT_SEASON', '2026'))
    week = int(os.environ['READY_WEEK'])
    data = reports(ROOT, args.league, season, week)
    body = dict(version=1, league=args.league, season=season, week=week,
                run_id=os.environ['GITHUB_RUN_ID'], attempt=os.environ.get('GITHUB_RUN_ATTEMPT', '1'), mode='preview' if args.dry_run else 'official', reports=data)
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    body['source_sha256'] = digest
    ref = gspread.service_account_from_dict(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
        http_client=gspread.BackOffHTTPClient).open_by_key(BOOKS[args.league]).worksheet('Reference')
    ref.update([[json.dumps(body)]], range_name='Z12', value_input_option='RAW')
    for attempt in range(90):
        raw = ref.acell('Z13').value
        ack = json.loads(raw) if raw else {}
        if ack.get('run_id') == body['run_id'] and ack.get('source_sha256') == digest:
            if ack.get('status') == 'success':
                if ack.get('mode') != body['mode']: raise ValueError('Wrong Bonus Games acknowledgement mode')
                break
            if ack.get('status') == 'failure':
                raise ValueError('MFL Bonus Games verification failed: '+str(ack.get('error')))
        if attempt == 89: raise TimeoutError('MFL Bonus Games bridge acknowledgement timed out')
        time.sleep(10)
    (ROOT/'data/bonus_mfl_sync_metadata.json').write_text(json.dumps(ack, indent=2)+'\n')
    print(f"{args.league}: MFL Bonus Games {body['mode']} verified through week {week}; due weeks {ack['due_weeks']}")


if __name__ == '__main__': main()
