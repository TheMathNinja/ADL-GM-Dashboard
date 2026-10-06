"""Poll MFL cheaply; dispatch one successful preliminary refresh per league/week."""
import argparse, csv, json, math, os, urllib.request, urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo('America/New_York')

def target_week(now, season):
    local = now.astimezone(ET)
    # Poll Monday 23:30 through Tuesday 23:59; never guess readiness from the clock.
    if not (local.weekday() == 1 or (local.weekday() == 0 and (local.hour, local.minute) >= (23, 30))):
        return None
    sept = date(season, 9, 1)
    first_monday = sept + timedelta(days=(-sept.weekday()) % 7 + 7)
    week = (local.date() - first_monday).days // 7 + 1
    return week if 1 <= week <= 17 else None

def rows(value):
    return value if isinstance(value, list) else [value] if isinstance(value, dict) else []

def number(value):
    result = float(value)
    if not math.isfinite(result): raise ValueError('Non-finite score')
    return result

def validate(standings, results, players, nfl, week, now):
    fs = rows(standings.get('franchise'))
    ids = {f'{i:04}' for i in range(1, 33)}
    if len(fs) != 32 or {f.get('id') for f in fs} != ids:
        return False, 'Standings must include all 32 teams exactly once'
    records = [[int(f[k]) for k in ('h2hw','h2hl','h2ht')] for f in fs]
    # MFL h2hw/l/t includes commissioner Bonus Games adjustments. All-play
    # below pins the actual completed week; permit earned bonus entries here.
    bonus_limit = week // 3 + (1 if week == 12 else 0)
    if week <= 12 and any(min(r) < 0 or not week <= sum(r) <= week + bonus_limit for r in records):
        return False, 'Head-to-head records do not match the target week plus earned Bonus Games'
    if week <= 12 and (sum(r[0] for r in records) != sum(r[1] for r in records) or sum(r[2] for r in records) % 2):
        return False, 'Head-to-head standings do not balance'
    ap = [[int(x) for x in f['all_play_wlt'].split('-')] for f in fs]
    if any(len(r) != 3 or min(r) < 0 or sum(r) != 31 * week for r in ap):
        return False, 'All-play standings have not reached the target week'
    if sum(r[0] for r in ap) != sum(r[1] for r in ap) or sum(r[2] for r in ap) % 2:
        return False, 'All-play standings do not balance'
    games = rows(nfl.get('matchup'))
    if str(nfl.get('week')) != str(week) or not games:
        return False, 'NFL schedule has the wrong week or is empty'
    if any(str(g.get('gameSecondsRemaining')) != '0' or number(g.get('kickoff', float('inf'))) > now.timestamp() for g in games):
        return False, 'NFL games are still pending or in progress'
    if str(results.get('week')) != str(week) or str(players.get('week')) != str(week):
        return False, 'Score feeds have the wrong week'
    teams = rows(results.get('franchise')) + [f for m in rows(results.get('matchup')) for f in rows(m.get('franchise'))]
    # Postseason and doubleheaders can repeat franchises. Require consistent scores.
    scores = {}
    player_scores = {p['id']: number(p['score']) for p in rows(players.get('playerScore')) if 'score' in p}
    if not player_scores: return False, 'Player scores are missing'
    for team in teams:
        if team.get('id') not in ids: continue
        score = number(team['score'])
        if team['id'] in scores and scores[team['id']] != score:
            return False, 'Conflicting scores for a repeated franchise'
        scores[team['id']] = score
        starters = [p for p in rows(team.get('player')) if p.get('status') == 'starter']
        if not starters or not team.get('starters') or 'opt_pts' not in team:
            return False, 'Starting lineup or potential points are missing'
        number(team['opt_pts'])
        for p in starters:
            if 'score' in p and abs(number(p['score']) - player_scores.get(p['id'], 0.0)) > .11:
                return False, 'Weekly results and player scores disagree'
    if set(scores) != ids: return False, 'Weekly results do not cover all 32 teams'
    return True, 'Standings, completed NFL schedule, weekly results and player scores agree'

def request(url, payload=None, token=None):
    headers = {'User-Agent':'Analytics-Fantasy-Labs-readiness/1.0','Accept':'application/json'}
    if token: headers['Authorization'] = 'Bearer ' + token
    data = None if payload is None else json.dumps(payload).encode()
    if data is not None: headers['Content-Type'] = 'application/json'
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=45) as response:
        body = response.read()
        return json.loads(body) if body else None

def mfl(kind, season, league, week):
    params = {'TYPE':kind,'JSON':'1'}
    if kind != 'nflSchedule': params['L'] = league
    if kind != 'leagueStandings': params['W'] = week
    response = request(f'https://api.myfantasyleague.com/{season}/export?' + urllib.parse.urlencode(params))
    if kind not in response: raise ValueError(f'MFL {kind} unavailable')
    return response[kind]

def duplicate(runs, key):
    if any(r.get('status') != 'completed' for r in runs):
        return 'worker workflow already queued or running'
    matches = [r for r in runs if r.get('display_title') == key]
    if any(r.get('conclusion') == 'success' for r in matches): return 'already succeeded'
    return None

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--week',type=int);parser.add_argument('--dry-run',action='store_true');parser.add_argument('--complete',action='store_true');args=parser.parse_args()
    season=int(os.environ.get('CURRENT_SEASON','2026'));league=os.environ['LEAGUE_ID'];repo=os.environ.get('GITHUB_REPOSITORY','');workflow=os.environ.get('WORKER_WORKFLOW','');now=datetime.now(timezone.utc)
    if args.complete:
        week=int(os.environ['READY_WEEK'])
        if not 1<=week<=17:raise ValueError('Invalid ready week')
        receipt=dict(season=season,week=week,league_id=league,status='success',run_id=os.environ['GITHUB_RUN_ID'],completed_at=now.isoformat())
        (ROOT/'data/preliminary_refresh_complete.json').write_text(json.dumps(receipt,indent=2)+'\n')
        receipt.update(bonus_mfl_verified=os.environ.get('SCORE_STATUS') == 'official', payouts_verified=True, process=os.environ.get('REFRESH_PROCESS', 'preliminary'),
                       triggered_at=os.environ.get('TRIGGERED_AT', ''),
                       trigger_run_id=os.environ.get('TRIGGER_RUN_ID', ''))
        directory = ROOT/'data/refresh_receipts'
        directory.mkdir(exist_ok=True)
        (directory/(receipt['process']+'.json')).write_text(json.dumps(receipt,indent=2)+'\n')
        print(receipt);return
    week=args.week if args.week is not None else target_week(now,season)
    if week is None:print('Outside Monday-night/Tuesday polling window');return
    if not 1<=week<=17:raise ValueError('Invalid target week')
    key=f'Preliminary {league} {season} week {week}'
    token=os.environ.get('GH_TOKEN')
    if not args.dry_run:
        receipt=ROOT/'data/preliminary_refresh_complete.json'
        if receipt.exists():
            done=json.loads(receipt.read_text())
            if done.get('season')==season and done.get('week')==week and done.get('league_id')==league and done.get('status')=='success':
                print('Already published successfully for this league/week');return
        runs=request(f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/runs?per_page=100',token=token)['workflow_runs']
        reason=duplicate(runs,key)
        if reason:print(reason);return
    try:
        ready,reason=validate(*(mfl(k,season,league,week) for k in ['leagueStandings','weeklyResults','playerScores','nflSchedule']),week,now)
    except (KeyError,ValueError,TypeError) as exc:
        ready,reason=False,f'Incomplete MFL response: {exc}'
    print(json.dumps(dict(league=league,season=season,week=week,ready=ready,reason=reason,dry_run=args.dry_run)))
    if ready and not args.dry_run:
        request(f'https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches',{'ref':'main','inputs':{'score_status':'official','ready_week':str(week),'triggered_at':datetime.now(timezone.utc).isoformat(),'trigger_run_id':os.environ.get('GITHUB_RUN_ID',''),'capture_cap_snapshot':'true','authorize_official_writes':'true'}},token)
        print('Dispatched '+key)

if __name__=='__main__':main()
