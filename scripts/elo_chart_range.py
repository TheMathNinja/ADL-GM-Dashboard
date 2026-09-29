"""Keep each league's two Readout charts on the smallest 1500 +/- 50k scale.

Uses the latest 32 unrounded workbook ratings, not the shadow model or historical
trajectory. Only chart viewWindowOptions are changed; cells and positions are
never written. Both conference specs are submitted in one atomic Sheets batch.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import time

BOOKS = {
    'ADL': ('1iu7oJUQ8IEhHDTp5RiArK7oTD4-DmjTbI1xtOwuwRBI', 'Data', '26'),
    'FAFL': ('1yWEzFx8hKhhlTQ47gacHSQXmZtPsX9k7hB2s6D6-g3k', '2026', ''),
}


def bounds(ratings):
    if len(ratings) != 32 or any(type(v) not in (int, float) or not math.isfinite(v) for v in ratings):
        raise ValueError('Range check requires exactly 32 finite numeric Elo ratings')
    # A zero-width axis cannot render; use the smallest positive window if tied.
    x = max(50, 50 * math.ceil(max(abs(v - 1500) for v in ratings) / 50))
    return 1500 - x, 1500 + x


def column(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def scalar_column(rows):
    return [r[0] if len(r) == 1 else None for r in rows]


def read_current(book, league, expected_week=None):
    _, tab, prefix = BOOKS[league]
    data = book.worksheet(tab)
    headers = data.row_values(36)
    start = headers.index(prefix + 'W1OPF') + 1
    if headers[start-1:start+16] != [f'{prefix}W{w}OPF' for w in range(1, 18)]:
        raise ValueError('Unexpected current-season OPF headers')
    scores = data.get(f'{column(start)}37:{column(start+16)}68', value_render_option='UNFORMATTED_VALUE')
    if len(scores) != 32:
        raise ValueError('Incomplete current-season score inputs')
    week = 0
    gap = False
    for w in range(17):
        values = [r[w] if w < len(r) else '' for r in scores]
        if all(v == '' for v in values):
            gap = True
            continue
        if gap or any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
            raise ValueError('Incomplete or noncontiguous scoring week')
        week = w + 1
    if expected_week is not None and week != expected_week:
        raise ValueError(f'Workbook week {week} differs from expected week {expected_week}')
    names = scalar_column(data.get('A2:A33'))
    if len(names) != 32 or len(set(names)) != 32 or not all(isinstance(n, str) and n for n in names):
        raise ValueError('Expected 32 unique workbook team names')
    elo_col = data.row_values(1).index(f'{prefix}W{week}Elo') + 1
    ratings = scalar_column(data.get(f'{column(elo_col)}2:{column(elo_col)}33', value_render_option='UNFORMATTED_VALUE'))
    bounds(ratings)
    expected = dict(zip(names, ratings))
    output = book.worksheet('Readout').get('C2:E33', value_render_option='UNFORMATTED_VALUE')
    if len(output) != 32 or {r[0] for r in output if r} != set(names):
        raise ValueError('Readout team mapping differs from source')
    if any(len(r) != 3 or type(r[2]) not in (int, float) or not math.isfinite(r[2]) or abs(r[2]-expected[r[0]]) > 0.001 for r in output):
        raise ValueError('Readout does not match latest unrounded workbook Elo')
    return week, expected


def read_charts(book, league):
    metadata = book.fetch_sheet_metadata(params={'fields': 'sheets(properties(title),charts)'})
    sheets = [s for s in metadata['sheets'] if s['properties']['title'] == 'Readout']
    if len(sheets) != 1:
        raise ValueError('Missing Readout sheet')
    titles = {f'{league} {conf} Elo Ratings' for conf in ('NFC', 'AFC')}
    charts = [c for c in sheets[0].get('charts', []) if c['spec'].get('title') in titles]
    if len(charts) != 2 or {c['spec']['title'] for c in charts} != titles:
        raise ValueError('Expected one NFC and one AFC Elo chart')
    return charts


def plan(charts, lower, upper):
    desired = deepcopy(charts)
    requests = []
    for chart in desired:
        basic = chart['spec'].get('basicChart', {})
        if basic.get('chartType') != 'LINE' or len(basic.get('series', [])) != 16:
            raise ValueError('Unexpected conference chart type or series count')
        axes = [a for a in basic.get('axis', []) if a.get('position') == 'LEFT_AXIS']
        if len(axes) != 1 or any(s.get('targetAxis', 'LEFT_AXIS') != 'LEFT_AXIS' for s in basic['series']):
            raise ValueError('Unexpected Elo axis assignment')
        window = {'viewWindowMin': lower, 'viewWindowMax': upper, 'viewWindowMode': 'EXPLICIT'}
        if axes[0].get('viewWindowOptions') == window:
            continue
        axes[0]['viewWindowOptions'] = window
        requests.append({'updateChartSpec': {'chartId': chart['chartId'], 'spec': chart['spec']}})
    return desired, requests


def sync_ranges(book, league, expected_week=None, apply=False, output_dir=None):
    week, teams = read_current(book, league, expected_week)
    lower, upper = bounds(list(teams.values()))
    before = read_charts(book, league)
    desired, requests = plan(before, lower, upper)
    report = dict(league=league, week=week, minimum_rating=min(teams.values()),
                  maximum_rating=max(teams.values()), axis_min=lower, axis_max=upper,
                  x=upper-1500, changed_charts=len(requests), applied=False,
                  checked_at=datetime.now(timezone.utc).isoformat(), before=before, desired=desired)
    path = Path(output_dir or 'artifacts/elo-range')
    path.mkdir(parents=True, exist_ok=True)
    backup = path / f'{league.lower()}-range-check.json'
    backup.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    if apply:
        if requests:
            # Don't overwrite a chart someone changed while the range was read.
            if read_charts(book, league) != before:
                raise ValueError('Charts changed during range check; retry')
            book.batch_update({'requests': requests})
        actual = read_charts(book, league)
        if sorted(actual, key=lambda c: c['chartId']) != sorted(desired, key=lambda c: c['chartId']):
            raise ValueError('Saved chart settings differ from the requested specs; inspect range-check backup')
        check_week, check_teams = read_current(book, league, week)
        if check_teams != teams:
            raise ValueError('Elo ratings changed during range check; retry')
        report.update(applied=True, verified=True, after=actual)
        backup.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(f'{league} Week {week}: {min(teams.values()):.6f}–{max(teams.values()):.6f}; '
          f'both charts {lower}–{upper} (1500 +/- {upper-1500}); '
          f'{len(requests)} chart changes; {"verified" if apply else "preview only"}')
    return report


def main():
    import gspread
    parser = argparse.ArgumentParser()
    parser.add_argument('--league', choices=BOOKS, required=True)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--expected-week', type=int)
    args = parser.parse_args()
    client = gspread.service_account_from_dict(json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON']),
                                               http_client=gspread.BackOffHTTPClient)
    book = client.open_by_key(BOOKS[args.league][0])
    # Readout may lag formula recalculation briefly after a weekly write.
    for attempt in range(6):
        try:
            read_current(book, args.league, args.expected_week)
            break
        except ValueError:
            if attempt == 5:
                raise
            time.sleep(5)
    sync_ranges(book, args.league, args.expected_week, args.apply)


if __name__ == '__main__':
    main()
