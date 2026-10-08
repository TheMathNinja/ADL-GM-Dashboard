"""Capture and report user-visible effects of an official score correction."""
import argparse
import csv
import json
import os
from pathlib import Path

ROOT = Path(__file__).parents[1]
BEFORE = ROOT / '.correction_impact_before.json'
BASELINE = ROOT / 'data/official_score_output_baseline.json'
OUTPUT = ROOT / 'data/correction_impact.json'


def read_csv(path):
    return list(csv.DictReader(path.open(encoding='utf-8-sig'))) if path.exists() else []


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def score_map(path, week):
    value = json.loads(path.read_text()) if path.exists() else {}
    if 'scores' in value and int(value.get('week', -1)) == week:
        return {str(k): number(v) for k, v in value['scores'].items()}
    item = value.get('weeks', {}).get(str(week), {})
    return {str(k): number(v) for k, v in item.get('scores', {}).items()}


def all_play(rows, week, score_column):
    selected = [r for r in rows if int(r['week']) == week]
    scores = {r['franchise_id'].zfill(4): number(r[score_column]) for r in selected}
    names = {r['franchise_id'].zfill(4): r.get('franchise_name') or r['franchise_id'] for r in selected}
    return {fid: {'name': names[fid], 'wins': sum(
        1 if value > other else .5 if value == other else 0
        for other_id, other in scores.items() if other_id != fid)} for fid, value in scores.items()}


def bonus_results(rows, week, score_column, potential_column):
    results = {}
    names = {}
    for r in rows:
        names[r['franchise_id'].zfill(4)] = r.get('franchise_name') or r['franchise_id']
    due = [w for w in (3, 6, 9, 12) if w <= week]
    for end in due:
        for event, first in [(f'Q{end // 3}', end - 2)] + ([('Season', 1)] if end == 12 else []):
            block = [r for r in rows if first <= int(r['week']) <= end]
            ids = sorted({r['franchise_id'].zfill(4) for r in block})
            ranked = []
            for fid in ids:
                team = [r for r in block if r['franchise_id'].zfill(4) == fid]
                ap = sum(all_play([r for r in block if int(r['week']) == w], w, score_column)[fid]['wins']
                         for w in range(first, end + 1))
                ranked.append((fid, ap, sum(number(r[score_column]) for r in team),
                               sum(number(r[potential_column]) for r in team)))
            ranked.sort(key=lambda x: (-x[1], -x[2], -x[3], x[0]))
            for index, (fid, _, _, _) in enumerate(ranked):
                results[event + ':' + fid] = {'name': names[fid], 'event': event,
                                              'result': 'W' if index < 15 else 'T' if index < 17 else 'L'}
    return results


def ext_state(root):
    summary = read_csv(root / 'data/ext_pr_summary.csv')
    rosters = read_csv(root / 'data/current_rosters.csv')
    rostered = {r['player_id']: r for r in rosters}
    result = {}
    for row in summary:
        pid = row['player_id']
        rank = number(row.get('pr_current_final'))
        if pid in rostered and rank is not None:
            info = rostered[pid]
            result[pid] = {'name': info.get('player_name') or info.get('player') or pid,
                           'position': row.get('pr_current_pos') or info.get('player_pos'), 'rank': rank}
    return result


def state(root, league, week, current=False):
    if league == 'ADL':
        rows, score, potential = read_csv(root / 'data/weekly_team_metrics.csv'), 'total_points', 'potential_points'
    else:
        rows, score, potential = read_csv(root / 'data/current_weekly.csv'), 'points', 'potential'
        names = {r['franchise_id'].zfill(4): r['franchise_name'] for r in read_csv(root / 'data/bonus_games.csv')}
        for row in rows:
            row['franchise_name'] = names.get(row['franchise_id'].zfill(4), row['franchise_id'])
    score_path = ROOT / '.refresh_player_scores.json' if current else root / 'data/processed_player_scores.json'
    return {'season': int(os.environ.get('CURRENT_SEASON', '2026')), 'week': week,
            'player_scores': score_map(score_path, week),
            'ext': ext_state(root) if league == 'ADL' else {},
            'all_play': all_play(rows, week, score),
            'bonus': bonus_results(rows, week, score, potential)}


def changed(before, after, league):
    impact = {'league': league, 'season': after['season'], 'week': after['week'],
              'run_id': os.environ.get('GITHUB_RUN_ID', ''), 'ext_pr': [], 'all_play': [], 'bonus_games': []}
    for pid in sorted(set(before['ext']) | set(after['ext'])):
        old, new = before['ext'].get(pid), after['ext'].get(pid)
        if old and new and old['rank'] != new['rank']:
            impact['ext_pr'].append({'player_id': pid, 'player': new['name'], 'position': new['position'],
                'old_score': before['player_scores'].get(pid), 'new_score': after['player_scores'].get(pid),
                'old_rank': old['rank'], 'new_rank': new['rank']})
    for fid in sorted(set(before['all_play']) & set(after['all_play'])):
        old, new = before['all_play'][fid], after['all_play'][fid]
        if old['wins'] != new['wins']:
            impact['all_play'].append({'franchise_id': fid, 'franchise': new['name'],
                                       'old_wins': old['wins'], 'new_wins': new['wins']})
    for key in sorted(set(before['bonus']) & set(after['bonus'])):
        old, new = before['bonus'][key], after['bonus'][key]
        if old['result'] != new['result']:
            impact['bonus_games'].append({'franchise': new['name'], 'event': new['event'],
                                          'old_result': old['result'], 'new_result': new['result']})
    return impact


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('capture', 'compare', 'promote'))
    parser.add_argument('--league', choices=('ADL', 'FAFL'), required=True)
    parser.add_argument('--week', type=int, required=True)
    args = parser.parse_args()
    if args.action == 'capture':
        value = json.loads(BASELINE.read_text()) if BASELINE.exists() else None
        if not value or value.get('week') != args.week:
            value = state(ROOT, args.league, args.week)
        BEFORE.write_text(json.dumps(value, indent=2) + '\n')
    elif args.action == 'compare':
        before = json.loads(BEFORE.read_text())
        OUTPUT.write_text(json.dumps(changed(before, state(ROOT, args.league, args.week, True), args.league), indent=2) + '\n')
    else:
        BASELINE.write_text(json.dumps(state(ROOT, args.league, args.week, True), indent=2) + '\n')


if __name__ == '__main__':
    main()
