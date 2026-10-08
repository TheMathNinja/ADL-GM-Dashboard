"""Refresh on Thursday player-score changes, independently of standings changes."""
import argparse
import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from score_readiness import ET, ROOT, mfl, request, rows, validate

BASELINE = ROOT / 'data/processed_player_scores.json'
CAPTURE = ROOT / '.refresh_player_scores.json'
OFFICIAL = ROOT / 'data/refresh_receipts/corrections.json'
FAILED_REVISION_BACKOFF = timedelta(hours=6)


def official_complete(season, league, week):
    receipt = json.loads(OFFICIAL.read_text()) if OFFICIAL.exists() else {}
    return (receipt.get('season'), receipt.get('league_id'), receipt.get('week'), receipt.get('status'), receipt.get('bonus_mfl_verified')) == (season, league, week, 'success', True)


def target_week(now, season):
    local = now.astimezone(ET)
    if local.weekday() != 3 or (local.hour, local.minute) < (3, 45):
        return None
    sept = date(season, 9, 1)
    first_monday = sept + timedelta(days=(-sept.weekday()) % 7 + 7)
    week = (local.date() - first_monday).days // 7 + 1
    return week if 1 <= week <= 17 else None


def snapshot(feed, season, league, week):
    if str(feed.get('week')) != str(week):
        raise ValueError('Player-score feed has the wrong week')
    scores = {}
    for player in rows(feed.get('playerScore')):
        pid = str(player['id'])
        value = Decimal(str(player['score']))
        if not pid or not value.is_finite() or pid in scores:
            raise ValueError('Invalid or duplicate player score')
        scores[pid] = '0' if value == 0 else format(value.normalize(), 'f')
    if not scores:
        raise ValueError('Player-score feed is empty')
    digest = hashlib.sha256(json.dumps(scores, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return dict(season=season, league_id=league, week=week, digest=digest, scores=scores)


def changed_players(before, after):
    if not before:
        return None
    a, b = before['scores'], after['scores']
    return sorted(p for p in a.keys() | b.keys() if a.get(p) != b.get(p))


def recent_failed_revision(runs, digest, now):
    """Return the newest failed worker for this exact score revision in backoff."""
    candidates = []
    for run in runs:
        if (run.get('status') != 'completed' or run.get('conclusion') not in
                {'failure', 'timed_out', 'cancelled'} or digest not in run.get('display_title', '')):
            continue
        stamp = run.get('updated_at') or run.get('created_at')
        if not stamp:
            continue
        finished = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
        if now - finished < FAILED_REVISION_BACKOFF:
            candidates.append((finished, run))
    return max(candidates, default=(None, None), key=lambda item: item[0])[1]


def load_baseline(season, league):
    data = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    if data.get('season') != season or data.get('league_id') != league:
        return dict(season=season, league_id=league, weeks={})
    return data


def capture(season, league, week):
    current = snapshot(mfl('playerScores', season, league, week), season, league, week)
    CAPTURE.write_text(json.dumps(current, indent=2) + '\n')
    print(f'Captured {len(current["scores"])} player scores before the refresh')


def complete(season, league, week):
    # Never label an unprocessed correction as published. A score change during
    # the build prevents acknowledgement, and the next poll retries the worker.
    before = json.loads(CAPTURE.read_text())
    current = snapshot(mfl('playerScores', season, league, week), season, league, week)
    if before != current:
        raise ValueError('Player scores changed during the refresh; retry required')
    data = load_baseline(season, league)
    data['weeks'][str(week)] = current
    BASELINE.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')
    print(f'Recorded successfully processed player scores for week {week}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--week', type=int)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--complete', action='store_true')
    args = parser.parse_args()
    season = int(os.environ.get('CURRENT_SEASON', '2026'))
    league = os.environ['LEAGUE_ID']
    now = datetime.now(timezone.utc)
    week = args.week if args.week is not None else target_week(now, season)
    if week is None:
        print('Outside Thursday 03:45–23:59 Eastern correction window')
        return
    if not 1 <= week <= 17:
        raise ValueError('Invalid target week')
    if args.capture:
        capture(season, league, week)
        return
    if args.complete:
        complete(season, league, week)
        return
    players = mfl('playerScores', season, league, week)
    current = snapshot(players, season, league, week)
    baseline = load_baseline(season, league)['weeks'].get(str(week))
    changes = changed_players(baseline, current)
    if changes == [] and official_complete(season, league, week):
        print('No player scores changed and official refresh/MFL Bonus Games already verified')
        return
    # Standings need only reflect the SAME completed week, not a new week or
    # different W-L results. Reconcile feeds before publishing a correction.
    ready, reason = validate(mfl('leagueStandings', season, league, week),
                             mfl('weeklyResults', season, league, week), players,
                             mfl('nflSchedule', season, league, week), week, now)
    print(json.dumps(dict(week=week, league=league, changed_players=changes,
                         baseline_missing=baseline is None, ready=ready, reason=reason,
                         dry_run=args.dry_run)))
    if not ready or args.dry_run:
        return
    repo, workflow = os.environ['GITHUB_REPOSITORY'], os.environ['WORKER_WORKFLOW']
    token = os.environ['GH_TOKEN']
    runs = request(f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?per_page=100', token=token)['workflow_runs']
    if any(r.get('status') != 'completed' for r in runs):
        print('Weekly refresh already active; check again next poll')
        return
    failed = recent_failed_revision(runs, current['digest'], now)
    if failed:
        retry_at = datetime.fromisoformat((failed.get('updated_at') or failed['created_at']).replace('Z', '+00:00')) + FAILED_REVISION_BACKOFF
        print(f'Identical correction revision failed recently; retry deferred until {retry_at.isoformat()}')
        return
    # A missing baseline requires one actual refresh, never silent adoption.
    # Completed runs are deduplicated by the processed snapshot, not a week key:
    # subsequent corrections (including reversions) must trigger another run.
    request(f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches',
            {'ref': 'main', 'inputs': {'score_status': 'official', 'ready_week': str(week),
                                      'score_revision': current['digest'],
                                      'triggered_at': datetime.now(timezone.utc).isoformat(),
                                      'trigger_run_id': os.environ.get('GITHUB_RUN_ID', ''),
                                      'authorize_official_writes': 'true'}}, token)
    print('Dispatched official correction refresh')


if __name__ == '__main__':
    main()
