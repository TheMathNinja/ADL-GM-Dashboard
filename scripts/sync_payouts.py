"""Publish the shared score snapshot; reconcile existing Payouts formulas before success.

Only Reference!E2:V102 (formerly an asynchronous IMPORTRANGE spill) and
Money!B2:C16 (earned postseason prizes) are written. Prize amounts, formulas,
manual money corrections, and formatting remain owned by the workbook.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
BOOKS = {'ADL': '1oh7P9TRUj356U7xjC26X5a6lunYI73zpSPjT11t1Vok',
         'FAFL': '1E-N1YK-udh88c7LFbB57itbMIEAzt6z1N4M5s_J1XBA'}
PUBLISHED = {'ADL': '2PACX-1vRcxPf_UXq0eR0eBHe0X64BgCyK_qZgu10Stx2x9Ae580IfK3TMz2Wgn9no3NJ-LWm3C1INPPkBtbl6',
             'FAFL': '2PACX-1vRzJ6YMO_7eh-G8x4vk-DC9aLsjPJUI2qoe1yRwpj8W6mh2vxtSc5z6gATMl8Ef6AkRaQg1BcNl1-TD'}
PERIODS = [(f'Week {w}', [w]) for w in range(1, 18)] + [
    (f'Q{q} Cumulative', list(range(3*q-2, 3*q+1))) for q in range(1, 5)] + [
    ('Regular Season ($)', list(range(1, 13))), ('Postseason Cumulative', list(range(13, 18)))]


def cell(rows, r, c, default=''):
    value = rows[r][c] if r < len(rows) and c < len(rows[r]) else default
    return default if value is None else value


def load_scores(root, league, season, ready_week=None):
    filename = 'weekly_team_metrics.csv' if league == 'ADL' else 'current_weekly.csv'
    rows = list(csv.DictReader((root/'data'/filename).open(encoding='utf-8-sig')))
    names = {}
    if league == 'FAFL':
        context = json.loads((root/'data/weekly_source_context.json').read_text())
        names = {str(f['id']).zfill(4): f['name'] for f in context['meta']}
    keys = ['offense_points', 'defense_points', 'potential_points', 'total_points'] if league == 'ADL' else ['off', 'deff', 'potential', 'points']
    scores = {}
    for row in rows:
        if int(row['season']) != season:
            raise ValueError('Payouts source season does not match workflow')
        name = row['franchise_name'] if league == 'ADL' else names[row['franchise_id'].zfill(4)]
        key = (name, int(row['week']))
        values = [float(row[k]) for k in keys]
        if key in scores or not all(math.isfinite(v) for v in values):
            raise ValueError('Duplicate or nonfinite payout source')
        if not math.isclose(values[0]+values[1], values[3], abs_tol=1e-5):
            raise ValueError('Offense plus defense does not reconcile to total points')
        scores[key] = values
    week = max(w for _, w in scores)
    teams = {n for n, _ in scores}
    if not 1 <= week <= 17 or len(teams) != 32 or set(scores) != {(n, w) for n in teams for w in range(1, week+1)}:
        raise ValueError('Payouts requires all 32 teams for every completed week')
    if ready_week and week != ready_week:
        raise ValueError('Payouts source week does not match requested week')
    return scores, week


def mapping(reference, scores):
    teams = [(cell(reference, i, 0), cell(reference, i, 1), cell(reference, i, 2)) for i in range(1, 33)]
    if len({t[0] for t in teams}) != 32 or len({t[1] for t in teams}) != 32 or {t[0] for t in teams} != {n for n, _ in scores}:
        raise ValueError('Payouts team mapping differs from source')
    if any(sum(t[2] == c for t in teams) != 16 for c in ['NFC', 'AFC']):
        raise ValueError('Payouts conference mapping is incomplete')
    return teams


def input_matrix(teams, scores, week, league, season):
    rows = [['']*18 for _ in range(101)]
    for metric, label in enumerate(['OP', 'DP', 'PP']):
        start = metric*34
        prefix = str(season)[-2:] if league == 'ADL' else ''
        rows[start] = [f'FRANCHISE/WEEK ({label})'] + [f'{prefix}W{w}{label}F' for w in range(1, 18)]
        for i, (name, _, _) in enumerate(teams, 1):
            rows[start+i] = [name] + [scores[name, w][metric] if w <= week else '' for w in range(1, 18)]
    return rows


def expected_awards(teams, scores, week):
    ap = {(n, w): sum(round(scores[m, w][3], 6) < round(scores[n, w][3], 6) for m, _, _ in teams)
          + (sum(round(scores[m, w][3], 6) == round(scores[n, w][3], 6) for m, _, _ in teams)-1)/2
          for n, _, _ in teams for w in range(1, week+1)}
    result = {}
    for label, weeks in PERIODS:
        winners = []
        for conf in ['NFC', 'AFC']:
            for metric in [3, 0, 1, 2]:
                if max(weeks) > week:
                    winners.append('')
                    continue
                values = [(abbr, round(sum(ap[n, w] if metric == 3 else scores[n, w][metric] for w in weeks), 6))
                          for n, abbr, c in teams if c == conf]
                best = max(v for _, v in values)
                winners.append(', '.join(a for a, v in values if v == best))
        result[label] = winners
    return result


def postseason_prizes(bracket, teams, week, season):
    if bracket['completedWeek'] != week or bracket['season'] != season:
        raise ValueError('Bracket is stale; cannot publish postseason payouts')
    lookup = {n: (abbr, conf) for n, abbr, conf in teams}
    prizes = [['', ''] for _ in range(15)]  # Money rows 2:16
    def put(row, name):
        abbr, conf = lookup[name]
        prizes[row-2][0 if conf == 'NFC' else 1] = abbr
    def ordered(game, aggregate=False):
        field = 'aggregate' if aggregate else 'points'
        if any(t.get(field) is None for t in game['teams']):
            raise ValueError('Missing completed postseason result')
        return sorted(game['teams'], key=lambda t: (-t[field], t['seed']))
    games = bracket['games']
    if week >= 12:
        for conf in ['NFC', 'AFC']:
            entrants = {t['name']: t for g in games if g['week'] == 13 and g['conference'] == conf and g['category'] == 'championship' for t in g['teams']}
            if len(entrants) != 7:
                raise ValueError('Missing final qualifying field')
            for row, t in enumerate(sorted(entrants.values(), key=lambda t: t['seed']), 9):
                put(row, t['name'])
    for g in games:
        if g['week'] > week:
            continue
        if g['week'] == 16 and g['title'].endswith(' Championship'):
            put(4, ordered(g)[1]['name'])
        if g['week'] == 16 and g['title'] == '3rd Place Game':
            for row, t in zip([5, 6], ordered(g)): put(row, t['name'])
        if g['week'] == 16 and g['title'] == '5th Place Game':
            for row, t in zip([7, 8], ordered(g, True)): put(row, t['name'])
        if g['week'] == 17 and g['title'] == 'Super Bowl':
            for row, t in zip([2, 3], ordered(g)): put(row, t['name'])
        if g['week'] == 17 and g['title'] == 'Consolation Game 1':
            put(16, g.get('seriesWinner') or ordered(g)[0]['name'])
    if week >= 16 and any(not all(prizes[r-2]) for r in range(4, 9)):
        raise ValueError('Incomplete conference placement results')
    if week == 17 and (not all(prizes[14]) or any(sum(bool(v) for v in prizes[r-2]) != 1 for r in [2, 3])):
        raise ValueError('Incomplete championship or ladder results')
    return prizes


def winner_set(value):
    return set(str(value).split(', ')) if value else set()


def verify_outputs(display, money, awards, prizes, teams):
    if {cell(display, r, 0) for r in range(2, 25)} != set(awards):
        raise ValueError('Unexpected Payouts Display layout')
    for row in display[2:25]:
        for col, expected in enumerate(awards[row[0]], 1):
            if winner_set(cell([row], 0, col)) != winner_set(expected):
                raise ValueError(f'Payouts has not recalculated: {row[0]}, column {col+1}')
    for r in range(15):
        if [cell(money, r+1, c) for c in [1, 2]] != prizes[r]:
            raise ValueError('Postseason payouts have not recalculated')
    for conf_index in [0, 1]:
        for offset, metric in enumerate(range(4)):
            if winner_set(cell(money, 16+offset, conf_index+1)) != winner_set(awards['Regular Season ($)'][4*conf_index+metric]):
                raise ValueError('Season award payout link is stale')
        for w in range(1, 18):
            if winner_set(cell(money, 19+w, conf_index+1)) != winner_set(awards[f'Week {w}'][4*conf_index]):
                raise ValueError('Weekly payout link is stale')
    by_abbr = {a: c for _, a, c in teams}
    expected_cash = dict.fromkeys(by_abbr, 0.0)
    for row in money[1:37]:
        for c, conf in [(1, 'NFC'), (2, 'AFC')]:
            winners = winner_set(cell([row], 0, c))
            if any(by_abbr.get(a) != conf for a in winners):
                raise ValueError('Unrecognized payout winner or wrong conference')
            for a in winners: expected_cash[a] += float(row[3])/len(winners)
    seen = set()
    for row in money:
        a = cell([row], 0, 5)
        if a not in by_abbr: continue
        if a in seen: raise ValueError('Duplicate payout balance')
        seen.add(a)
        raw, correction, final = [cell([row], 0, c) for c in [6, 7, 8]]
        if not math.isclose(float(raw), expected_cash[a], abs_tol=1e-6) or not math.isclose(float(final), float(raw)+float(correction or 0), abs_tol=1e-6):
            raise ValueError('Payout balance has not recalculated: '+a)
    if seen != set(by_abbr): raise ValueError('Missing team payout balances')


def main():
    import gspread
    p = argparse.ArgumentParser(); p.add_argument('--league', choices=BOOKS, required=True); a = p.parse_args()
    season = int(os.environ.get('CURRENT_SEASON', '2026'))
    scores, week = load_scores(ROOT, a.league, season, int(os.environ.get('READY_WEEK') or 0))
    book = gspread.service_account_from_dict(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])).open_by_key(BOOKS[a.league])
    ref, display, money = [book.worksheet(n) for n in ['Reference', 'Display', 'Money']]
    if int(display.acell('A1').value) != season: raise ValueError('Payouts workbook season mismatch')
    teams = mapping(ref.get('A1:C33'), scores)
    matrix = input_matrix(teams, scores, week, a.league, season)
    awards = expected_awards(teams, scores, week)
    bracket = json.loads((ROOT/'docs/playoff-picture/bracket-data.json').read_text())
    if bracket['league'] != a.league: raise ValueError('Wrong league bracket')
    prizes = postseason_prizes(bracket, teams, week, season)
    backup_path = ROOT/'data/payouts_source_backup.json'
    if not backup_path.exists():
        backup_path.write_text(json.dumps(dict(reference_anchor=ref.get('E2', value_render_option='FORMULA'),
                                               postseason=money.get('B2:C16', value_render_option='FORMULA')), indent=2)+'\n')
    # Removing the spill anchor and replacing its rectangle are one atomic batch.
    def update(sheet_id, row, col, values):
        def entry(v):
            return {'userEnteredValue': {'numberValue': v} if isinstance(v, (int, float)) else {'stringValue': v}} if v != '' else {}
        return {'updateCells': {'range': {'sheetId': sheet_id, 'startRowIndex': row, 'endRowIndex': row+len(values),
                                         'startColumnIndex': col, 'endColumnIndex': col+len(values[0])},
                                'rows': [{'values': [entry(v) for v in r]} for r in values], 'fields': 'userEnteredValue'}}
    book.batch_update({'requests': [update(ref.id, 1, 4, [['']]), update(ref.id, 1, 4, matrix), update(money.id, 1, 1, prizes)]})
    for attempt in range(24):
        try:
            # Validate values after Sheets calculates; never trust a write response alone.
            actual = ref.get('E2:V102', value_render_option='UNFORMATTED_VALUE')
            for r, row in enumerate(matrix):
                for c, v in enumerate(row):
                    got = cell(actual, r, c)
                    if isinstance(v, (int, float)):
                        if not isinstance(got, (int, float)) or not math.isclose(v, got, abs_tol=1e-6): raise ValueError('Payout input readback mismatch')
                    elif got != v: raise ValueError('Payout input readback mismatch')
            verify_outputs(display.get('A1:I25', value_render_option='UNFORMATTED_VALUE'),
                           money.get('A1:J37', value_render_option='UNFORMATTED_VALUE'), awards, prizes, teams)
            break
        except ValueError:
            if attempt == 23: raise
            time.sleep(10)
    digest = hashlib.sha256(json.dumps(matrix).encode()).hexdigest()
    request = dict(version=1, league=a.league, season=season, week=week, run_id=os.environ['GITHUB_RUN_ID'],
                   source_sha256=digest, inputs=matrix, awards=awards)
    # Existing over-cell logos require Apps Script. The bridge does no scraping;
    # it acknowledges this exact run only after checking inputs, winners and images.
    ref.update([[json.dumps(request)]], range_name='Z10', value_input_option='RAW')
    for attempt in range(90):
        raw = ref.acell('Z11').value
        ack = json.loads(raw) if raw else {}
        if ack.get('run_id') == request['run_id'] and ack.get('source_sha256') == digest and ack.get('status') == 'success':
            break
        if attempt == 89:
            raise ValueError('Payout logo bridge did not acknowledge this run: '+str(ack.get('error', 'waiting for Apps Script')))
        time.sleep(10)
    public_url = f'https://docs.google.com/spreadsheets/d/e/{PUBLISHED[a.league]}/pubhtml/sheet?headers=false&gid={display.id}'
    for attempt in range(60):
        with urllib.request.urlopen(public_url+'&run='+request['run_id'], timeout=45) as response:
            page = response.read().decode('utf8')
        if len(re.findall(r'<img\b', page)) == ack['images']:
            break
        if attempt == 59: raise ValueError('Published Payouts embed still has an outdated logo count')
        time.sleep(10)
    receipt = dict(league=a.league, season=season, through_week=week, run_id=os.environ['GITHUB_RUN_ID'],
                   status='success', verified_at=datetime.now(timezone.utc).isoformat(), spreadsheet_id=BOOKS[a.league],
                   source_sha256=digest, awards=awards, logos=ack, published_url=public_url, published_images_verified=True)
    (ROOT/'data/payouts_sync_metadata.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'{a.league} Payouts verified through Week {week}: score inputs, award winners, and all 32 balances reconcile.')


if __name__ == '__main__': main()
