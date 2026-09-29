"""Email the owner only after both leagues' GitHub runs and live sites are ready."""
import argparse
import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, getaddresses, parseaddr
from functools import lru_cache
import hashlib
import json
import os
import re
import smtplib
import ssl
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
    lines.append('ADL completion includes the Extension Calculator deployment. No report is sent for failed or unfinished refreshes.')
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
