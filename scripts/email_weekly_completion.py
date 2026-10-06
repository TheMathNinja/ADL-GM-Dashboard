"""Email the owner only after both leagues' GitHub runs and live sites are ready."""
import argparse
import base64
import csv
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, getaddresses, parseaddr
from functools import lru_cache
import hashlib
import io
import json
import os
import re
import smtplib
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from score_readiness import ET, mfl
from score_corrections import snapshot

LEAGUES = {
    'ADL': ('TheMathNinja/ADL-GM-Dashboard', '60206', 'refresh_extension_calculator.yml'),
    'FAFL': ('TheMathNinja/FAFL-GM-Dashboard', '22686', 'refresh.yml'),
}
STATE_PATH = 'data/weekly_email_state.json'


def get_json(url, payload=None, method=None):
    headers = {'User-Agent': 'Analytics-Fantasy-Labs-completion-report', 'Accept': 'application/json'}
    if url.startswith('https://api.github.com/'):
        headers['Authorization'] = 'Bearer ' + os.environ['GH_TOKEN']
    data = None if payload is None else json.dumps(payload).encode()
    if data is not None:
        headers['Content-Type'] = 'application/json'
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


@lru_cache(maxsize=None)
def document(repo, path):
    item = get_json(f'https://api.github.com/repos/{repo}/contents/{path}?ref=main')
    return json.loads(base64.b64decode(item['content'])) if item else None


@lru_cache(maxsize=None)
def text_document(repo, path):
    item = get_json(f'https://api.github.com/repos/{repo}/contents/{path}?ref=main')
    return base64.b64decode(item['content']).decode('utf-8') if item else None


def csv_document(repo, path):
    value = text_document(repo, path)
    return list(csv.DictReader(io.StringIO(value))) if value else []


def orchestration_json(url, payload=None, method=None):
    token = os.environ.get('WEEKLY_ORCHESTRATION_TOKEN', '').strip()
    if not token:
        raise RuntimeError('WEEKLY_ORCHESTRATION_TOKEN is not configured')
    headers = {
        'User-Agent': 'Analytics-Fantasy-Labs-weekly-orchestrator',
        'Accept': 'application/vnd.github+json',
        'Authorization': 'Bearer ' + token,
        'X-GitHub-Api-Version': '2022-11-28',
    }
    data = None if payload is None else json.dumps(payload).encode()
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=45) as response:
        if response.status == 204:
            return None
        return json.load(response)


def ensure_swing_refresh(league, through_week):
    repo, _, workflow = LEAGUES[league]
    runs = orchestration_json(
        f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?event=workflow_dispatch&per_page=20'
    ) or {}
    preview_title = f'{league} manual preview'
    active = any(
        run.get('status') in ('queued', 'in_progress', 'waiting', 'pending') and
        run.get('display_title') == preview_title
        for run in runs.get('workflow_runs', [])
    )
    if active:
        print(f'{league} Game of the Week: repair refresh already active')
        return False
    common = {
        'ready_week': str(through_week),
        'score_status': 'official',
        'authorize_official_writes': 'false',
    }
    if league == 'ADL':
        common.update(force='true', capture_cap_snapshot='false')
    orchestration_json(
        f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches',
        {'ref': 'main', 'inputs': common},
        method='POST',
    )
    print(f'{league} Game of the Week: dispatched calculation-only repair through Week {through_week}')
    return True


def choose_receipts(process, receipts):
    preferred = {league: files.get(process) for league, files in receipts.items()}
    available = [r for r in preferred.values() if r]
    if not available:
        return None
    season, week = max((r['season'], r['week']) for r in available)
    chosen = {}
    for league, files in receipts.items():
        value = files.get(process)
        if not value or (value['season'], value['week']) != (season, week):
            return None  # Both leagues must finish the official Thursday run.
        if not value or (value['season'], value['week']) != (season, week):
            return None
        if value.get('status') != 'success':
            return None
        if process == 'corrections' and not value.get('bonus_mfl_verified'):
            return None
        chosen[league] = value
    return chosen


def published(league, receipt):
    if not receipt.get('payouts_verified'):
        return None
    repo, league_id, workflow = LEAGUES[league]
    if receipt.get('league_id') != league_id or not str(receipt.get('run_id', '')).isdigit():
        raise ValueError('Invalid completion receipt')
    run_id = str(receipt['run_id'])
    api = f'https://api.github.com/repos/{repo}'
    runs = get_json(f'{api}/actions/workflows/{workflow}/runs?per_page=100')['workflow_runs']
    if any(r['status'] != 'completed' for r in runs):
        return None
    run = get_json(f'{api}/actions/runs/{run_id}')
    if not run or run['status'] != 'completed' or run['conclusion'] != 'success':
        return None
    site = f'https://themathninja.github.io/{repo.split("/")[1]}/'
    marker = get_json(site + 'weekly-refresh-status.json?run=' + run_id)
    if not marker or str(marker.get('run_id')) != run_id:
        return None
    if (marker.get('season'), marker.get('week')) != (receipt['season'], receipt['week']):
        return None
    payout = document(repo, 'data/payouts_sync_metadata.json')
    if not payout or payout.get('status') != 'success' or str(payout.get('run_id')) != run_id or payout.get('through_week') != receipt['week'] or payout.get('season') != receipt['season'] or payout.get('league') != league:
        return None
    if payout.get('logos', {}).get('status') != 'success' or str(payout['logos'].get('run_id')) != run_id:
        return None
    if receipt.get('process') == 'corrections':
        bonus = document(repo, 'data/bonus_mfl_sync_metadata.json')
        if not receipt.get('bonus_mfl_verified') or not bonus or (bonus.get('status'), bonus.get('mode'), str(bonus.get('run_id')), bonus.get('season'), bonus.get('week'), bonus.get('league')) != ('success', 'official', run_id, receipt['season'], receipt['week'], league):
            return None
    baseline = document(repo, 'data/processed_player_scores.json')
    if not baseline or baseline.get('season') != receipt['season'] or baseline.get('league_id') != league_id:
        return None
    processed = baseline['weeks'].get(str(receipt['week']))
    live = snapshot(mfl('playerScores', receipt['season'], league_id, receipt['week']),
                    receipt['season'], league_id, receipt['week'])
    if not processed or processed['digest'] != live['digest']:
        return None
    jobs = get_json(f'{api}/actions/runs/{run_id}/jobs?per_page=100')['jobs']
    if not jobs or any(j['status'] != 'completed' or j['conclusion'] not in ('success', 'skipped') for j in jobs):
        return None
    started = min(j['started_at'] for j in jobs if j.get('started_at'))
    finished = max(j['completed_at'] for j in jobs if j.get('completed_at'))
    return dict(league=league, receipt=receipt, started=started, finished=finished,
                created=run['created_at'], url=run['html_url'], site=site,
                verified=datetime.now(timezone.utc).isoformat())


def local_time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(ET).strftime('%a %b %d, %Y %I:%M:%S %p %Z')


def report_key(process, checked):
    return process + ':' + ':'.join(f'{r["league"]}-{r["receipt"]["run_id"]}' for r in checked)


def competition_rank(values, value, reverse=False):
    rounded = [round(float(v), 6) for v in values]
    target = round(float(value), 6)
    return 1 + sum(v > target if reverse else v < target for v in rounded)


def gotw_candidates(league, swing, elo, standings):
    if len(swing) != 16:
        raise ValueError(f'{league} playoff swing must contain 16 matchups')
    weeks = {int(r['through_week']) for r in swing}
    targets = {int(r['target_week']) for r in swing}
    if len(weeks) != 1 or len(targets) != 1 or next(iter(targets)) != next(iter(weeks)) + 1:
        raise ValueError(f'{league} playoff swing has inconsistent weeks')
    through = next(iter(weeks)); target = next(iter(targets))
    latest = [r for r in elo if int(r['week']) == through]
    ratings = {r['franchise_name']: float(r['elo']) for r in latest}
    if len(ratings) != 32:
        raise ValueError(f'{league} Elo must contain 32 teams for Week {through}')
    franchises = standings.get('franchise', [])
    if isinstance(franchises, dict): franchises = [franchises]
    records = {f['id']: f"{f.get('h2hw','0')}-{f.get('h2hl','0')}-{f.get('h2ht','0')}" for f in franchises}
    enriched = []
    for row in swing:
        a, b = row['team_a'], row['team_b']
        if a not in ratings or b not in ratings:
            raise ValueError(f'{league} swing team missing from Elo: {a} or {b}')
        item = dict(row)
        item.update(a_elo=ratings[a], b_elo=ratings[b], combined_elo=ratings[a]+ratings[b],
                    elo_difference=abs(ratings[a]-ratings[b]),
                    a_record=records.get(row['team_a_id'], 'record unavailable'),
                    b_record=records.get(row['team_b_id'], 'record unavailable'))
        enriched.append(item)
    combined = [r['combined_elo'] for r in enriched]
    differences = [r['elo_difference'] for r in enriched]
    impacts = [float(r['combined_swing']) for r in enriched]
    for row in enriched:
        row['combined_rank'] = competition_rank(combined, row['combined_elo'], reverse=True)
        row['difference_rank'] = competition_rank(differences, row['elo_difference'])
        row['impact_rank'] = competition_rank(impacts, row['combined_swing'], reverse=True)
        row['selection_score'] = .5*(17-row['impact_rank']) + .3*(17-row['combined_rank']) + .2*(17-row['difference_rank'])
    return target, sorted(enriched, key=lambda r:(-r['selection_score'], r['impact_rank'], r['difference_rank']))[:4]


def gotw_message(season, target_week, candidates):
    subject = f'{season} Week {target_week}: ADL & FAFL Game of the Week suggestions'
    lines = [subject, '', 'Four ranked candidates per league, using newly published records, Elo, and playoff simulations.',
             "Playoff Percentage Points Up For Grabs is the combined change in both teams' playoff odds between win and loss scenarios.", '']
    for league in ('ADL', 'FAFL'):
        lines += [league, '---']
        for rank, r in enumerate(candidates[league], 1):
            lines += [
                f'{rank}. {r["team_a"]} ({r["a_record"]}) vs. {r["team_b"]} ({r["b_record"]})',
                f'Playoff Percentage Points Up For Grabs: {float(r["combined_swing"]):.1f} (#{r["impact_rank"]} of 16)',
                f'{r["team_a"]}: {float(r["team_a_playoff_if_win"]):.1f}% with win / {float(r["team_a_playoff_if_loss"]):.1f}% with loss ({float(r["team_a_swing"]):.1f}-point swing)',
                f'{r["team_b"]}: {float(r["team_b_playoff_if_win"]):.1f}% with win / {float(r["team_b_playoff_if_loss"]):.1f}% with loss ({float(r["team_b_swing"]):.1f}-point swing)',
                f'Combined Elo: {r["combined_elo"]:.1f} (#{r["combined_rank"]} of 16); Elo Difference: {r["elo_difference"]:.1f} (#{r["difference_rank"]} closest of 16)',
                f'Rationale: A high-leverage Week {target_week} matchup pairing playoff impact with proven team strength and competitiveness.',
                f'Blurb: {r["team_a"]} and {r["team_b"]} meet with {float(r["combined_swing"]):.1f} combined playoff percentage points hanging in the balance.',
                ''
            ]
    lines.append('Reply with the selected matchup and final blurb for each league. This email does not publish or modify MFL.')
    return subject, '\n'.join(lines)


def maybe_send_gotw(state, dry_run=False):
    started = time.perf_counter()
    candidates = {}; season = target = None; inputs = {}
    for league, (repo, league_id, _) in LEAGUES.items():
        swing = csv_document(repo, 'data/playoff_swing.csv')
        elo = csv_document(repo, 'data/elo_ratings.csv')
        inputs[league] = (swing, elo)
    ready = {
        league: (int(swing[0]['season']), int(swing[0]['through_week']), int(swing[0]['target_week']))
        for league, (swing, elo) in inputs.items() if swing and elo
    }
    if len(ready) < len(LEAGUES):
        if ready and not dry_run:
            through = max(value[1] for value in ready.values())
            for league in LEAGUES:
                if league not in ready:
                    ensure_swing_refresh(league, through)
        missing = ', '.join(league for league in LEAGUES if league not in ready)
        print(f'Game of the Week: waiting for swing or Elo data from {missing}')
        return False
    newest = max(ready.values())
    lagging = [league for league, value in ready.items() if value != newest]
    if lagging:
        if not dry_run:
            for league in lagging:
                ensure_swing_refresh(league, newest[1])
        print('Game of the Week: leagues are not aligned; repair requested for ' + ', '.join(lagging))
        return False
    for league, (repo, league_id, _) in LEAGUES.items():
        swing, elo = inputs[league]
        league_season = int(swing[0]['season']); through = int(swing[0]['through_week'])
        standings = mfl('leagueStandings', league_season, league_id, through)
        league_target, candidates[league] = gotw_candidates(league, swing, elo, standings)
        if season is None: season, target = league_season, league_target
        elif (season, target) != (league_season, league_target):
            print('Game of the Week: leagues are not aligned'); return False
    key = f'gotw:{season}:{target}'
    if key in state['sent']:
        print('Game of the Week: suggestions already sent'); return False
    prepared = time.perf_counter()
    subject, body = gotw_message(season, target, candidates)
    rendered = time.perf_counter()
    if dry_run:
        print(body)
        print(f'Game of the Week timings: inputs/ranking={prepared-started:.3f}s, email preparation={rendered-prepared:.3f}s, total={rendered-started:.3f}s')
        return False
    send_email(subject, body, key)
    emailed = time.perf_counter()
    state['sent'][key] = dict(sent_at=datetime.now(timezone.utc).isoformat(), subject=subject)
    save_state(state)
    print('Game of the Week: suggestions submitted to the configured sole recipient')
    print(f'Game of the Week timings: inputs/ranking={prepared-started:.3f}s, email preparation={rendered-prepared:.3f}s, SMTP={emailed-rendered:.3f}s, total={emailed-started:.3f}s')
    return True


def message(process, checked):
    receipt = checked[0]['receipt']
    label = 'Preliminary scores' if process == 'preliminary' else 'Thursday score corrections'
    subject = f'{receipt["season"]} Week {receipt["week"]}: {label} - updates complete'
    lines = [subject, '', 'All times are Eastern. GitHub runs succeeded and both live dashboard builds were verified.', '']
    for result in checked:
        r = result['receipt']
        lines.append(result['league'])
        if process == 'corrections' and r['process'] != 'corrections':
            lines.append('No player-score changes requiring a new refresh; the existing published scores match MFL.')
            lines.append('Most recent completed refresh: ' + local_time(result['finished']))
        else:
            if r.get('triggered_at'):
                lines.append('MFL check triggered GitHub: ' + local_time(r['triggered_at']))
            else:
                lines.append('Manual refresh created in GitHub: ' + local_time(result['created']) + ' (no MFL-check trigger)')
            lines += ['GitHub job started: ' + local_time(result['started']),
                      'GitHub job completed: ' + local_time(result['finished'])]
            begin = datetime.fromisoformat(result['started'].replace('Z', '+00:00'))
            end = datetime.fromisoformat(result['finished'].replace('Z', '+00:00'))
            lines.append(f'Run duration: {(end-begin).total_seconds()/60:.1f} minutes')
        if process == 'corrections': lines.append('Due Bonus Games entries in MFL verified.')
        lines += ['Payouts winners, balances and team logos verified.', 'Live site verified: ' + local_time(result['verified']),
                  'GitHub run: ' + result['url'],
                  'Dashboard: ' + result['site'], '']
    lines.append('The ADL Extension Calculator deployment runs independently after authoritative weekly data is recorded; Shiny hosting delays cannot block this report.')
    return subject, '\n'.join(lines)


def send_email(subject, body, key):
    to = os.environ['WEEKLY_REPORT_EMAIL_TO']
    addresses = getaddresses([to])
    if len(addresses) != 1 or addresses[0][1] != to or '\n' in to or '\r' in to:
        raise ValueError('Exactly one report recipient is required')
    sender = os.environ['ADL_ALERT_EMAIL_FROM']
    msg = EmailMessage()
    msg['From'], msg['To'], msg['Subject'] = sender, to, subject
    msg['Date'] = format_datetime(datetime.now(timezone.utc))
    msg['Message-ID'] = '<' + hashlib.sha256(key.encode()).hexdigest() + '@analyticsfantasylabs.github.io>'
    msg.set_content(body)
    server = os.environ['ADL_SMTP_SERVER']
    parsed = urllib.parse.urlsplit(server if '://' in server else 'smtp://' + server)
    secure = parsed.scheme == 'smtps' or parsed.port == 465
    context = ssl.create_default_context()
    username = os.environ['ADL_SMTP_USERNAME'].strip()
    password = os.environ['ADL_SMTP_PASSWORD'].strip()
    # Gmail displays app passwords in four spaced groups; spaces are cosmetic.
    if re.fullmatch(r'(?:[a-z]{4} ){3}[a-z]{4}', password):
        password = password.replace(' ', '')
    factory = smtplib.SMTP_SSL if secure else smtplib.SMTP
    kwargs = {'context': context} if secure else {}
    with factory(parsed.hostname, parsed.port or (465 if secure else 587), timeout=45, **kwargs) as smtp:
        if not secure:
            smtp.starttls(context=context)
        # Some submission servers close the connection on an inline AUTH PLAIN
        # response. Prefer the challenge/response LOGIN flow when advertised.
        smtp.ehlo()
        if 'LOGIN' in smtp.esmtp_features.get('auth', '').upper().split():
            smtp.user = username
            smtp.password = password
            smtp.auth('LOGIN', smtp.auth_login, initial_response_ok=False)
        else:
            smtp.login(username, password, initial_response_ok=False)
        smtp.send_message(msg, from_addr=parseaddr(sender)[1], to_addrs=[to])


def save_state(state):
    repo = os.environ['GITHUB_REPOSITORY']
    url = f'https://api.github.com/repos/{repo}/contents/{STATE_PATH}'
    current = get_json(url)
    payload = dict(message='Record delivered weekly refresh email',
                   content=base64.b64encode((json.dumps(state, indent=2)+'\n').encode()).decode(),
                   branch='main')
    if current:
        payload['sha'] = current['sha']
    get_json(url, payload, method='PUT')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    receipts = {league: {process: document(repo, f'data/refresh_receipts/{process}.json')
                        for process in ('preliminary', 'corrections')}
                for league, (repo, _, _) in LEAGUES.items()}
    state = document(os.environ['GITHUB_REPOSITORY'], STATE_PATH) or {'sent': {}}
    maybe_send_gotw(state, args.dry_run)
    for process in ('preliminary', 'corrections'):
        chosen = choose_receipts(process, receipts)
        if not chosen:
            print(f'{process}: waiting for completion receipts')
            continue
        # Skip already-reported pairs before making live MFL/site checks.
        key = report_key(process, [dict(league=l, receipt=r) for l, r in chosen.items()])
        if key in state['sent']:
            print(f'{process}: report already sent')
            continue
        checked = [published(league, r) for league, r in chosen.items()]
        if not all(checked):
            print(f'{process}: waiting for successful jobs, live sites, or score corrections')
            continue
        subject, body = message(process, checked)
        if args.dry_run:
            print(body)
            continue
        send_email(subject, body, key)
        state['sent'][key] = dict(sent_at=datetime.now(timezone.utc).isoformat(), subject=subject)
        save_state(state)
        print(f'{process}: report submitted to the configured sole recipient')


if __name__ == '__main__':
    main()
