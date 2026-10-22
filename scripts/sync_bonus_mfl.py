"""Require verified MFL standings entries for official weekly refreshes.

The existing Apps Script owns commissioner credentials and form reconciliation.
Reference!Z12:Z13 is the authenticated request/ack channel, using the same
service account and five-minute bridge as Payouts. No second score scrape.
"""
import argparse
import csv
import json
import math
import os
import time
from pathlib import Path
from sync_payouts import BOOKS, ROOT, load_scores
from apps_script_bridge import request_bridge
from verify_bonus_receipt import validate_bonus_receipt
from bonus_source_snapshot import validate_snapshot, request_body, reports_digest


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



def dispatch_bonus_request(bridge, timeout_seconds=60):
    try:
        return request_bridge(attempts=1, timeout_seconds=timeout_seconds, **bridge)
    except RuntimeError:
        # A transport failure can occur after MFL accepted the request. Never
        # equate it with completion or resubmit blindly: poll the bound receipt.
        print('Bonus Games dispatch was uncertain; waiting for authoritative readback', flush=True)
        return {'status':'uncertain'}


def main():
    import gspread
    p = argparse.ArgumentParser()
    p.add_argument('--league', choices=BOOKS, required=True)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--source-snapshot', type=Path)
    p.add_argument('--allow-queued', action='store_true',
                   help='Deprecated compatibility option; authoritative verification is always required')
    args = p.parse_args()
    season = int(os.environ.get('CURRENT_SEASON', '2026'))
    week = int(os.environ['READY_WEEK'])
    run_id = os.environ.get('SOURCE_RUN_ID') or os.environ['GITHUB_RUN_ID']
    if os.environ.get('SOURCE_RUN_ID') and not args.source_snapshot:
        raise ValueError('Parent refresh requires its exact Bonus Games source artifact')
    if args.source_snapshot:
        snapshot = json.loads(args.source_snapshot.read_text(encoding='utf8'))
        validate_snapshot(snapshot, args.league, season, week, run_id)
    else:
        data = reports(ROOT, args.league, season, week)
        snapshot = dict(version=1,league=args.league,season=season,week=week,run_id=run_id,reports=data,reports_sha256=reports_digest(data))
    body = request_body(snapshot, 'preview' if args.dry_run else 'official')
    digest = body['source_sha256']
    receipt_path = ROOT/'data/bonus_mfl_sync_metadata.json'
    ref = gspread.service_account_from_dict(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
        http_client=gspread.BackOffHTTPClient).open_by_key(BOOKS[args.league]).worksheet('Reference')
    ref.update([[json.dumps(body)]], range_name='Z12', value_input_option='RAW')
    bridge=dict(league=args.league,operation='bonus_mfl',run_id=body['run_id'])
    dispatch_bonus_request(bridge)
    # At most 60s dispatch + 290s polling + two 30s re-triggers: below
    # the 8-minute step timeout even when every web response is lost.
    for attempt in range(30):
        raw = ref.acell('Z13').value
        ack = json.loads(raw) if raw else {}
        if ack.get('run_id') == body['run_id'] and ack.get('source_sha256') == digest:
            if ack.get('status') == 'success':
                if ack.get('mode') != body['mode']: raise ValueError('Wrong Bonus Games acknowledgement mode')
                break
            if ack.get('status') == 'failure':
                raise ValueError('MFL Bonus Games verification failed: '+str(ack.get('error')))
        if attempt == 29:
            raise TimeoutError('MFL Bonus Games readback timed out; completion is blocked')
        # A busy Apps Script lock in an older bridge deployment can return before
        # processing the request. Re-trigger periodically; requests are idempotent.
        if attempt in (6,18):
            dispatch_bonus_request(bridge,timeout_seconds=30)
        time.sleep(10)
    validate_bonus_receipt(ack,args.league,season,week,body['run_id'],digest,body['mode'])
    receipt_path.write_text(json.dumps(ack, indent=2)+'\n')
    if ack.get('status') == 'success':
        print(f"{args.league}: MFL Bonus Games {body['mode']} verified through week {week}; due weeks {ack['due_weeks']}")


if __name__ == '__main__': main()
