"""Import Trophy Room results directly from MFL, never the retired Trophy Room.

Run from a dashboard: python scripts/import_trophy_results.py --league ADL
Use --cache DIR to retain the exact MFL responses for a reproducible audit.
Published payout records identify award recipients; MFL supplies their metrics.
"""
import argparse
import hashlib
import json
import time
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
LABELS = dict(HC='Head Coach', OC='Offensive Coordinator',
              DC='Defensive Coordinator', GM='General Manager')
OFFENSE = {'QB', 'RB', 'WR', 'TE', 'PK', 'K', 'PN', 'P'}
DEFENSE = {'DT', 'DE', 'DL', 'LB', 'CB', 'S', 'DB'}


def arr(value):
    return value if isinstance(value, list) else ([] if value is None else [value])


def normalized(value):
    return {'OAK': 'LVR', 'NOR': 'NOS', 'SDC': 'LAC', 'STL': 'LAR'}.get(value, value)


def codes_for(league, year):
    west = 'SFO SEA LAR' if league == 'FAFL' and year <= 2022 else 'LAR SFO SEA'
    return ('DAL NYG PHI WAS CHI DET GBP MIN ATL CAR NOS TBB ARI ' + west +
            ' BUF MIA NEP NYJ BAL CIN CLE PIT HOU IND JAC TEN DEN KCC LVR LAC').split()


def award_recipient(payout, conference, key, name_to_code):
    label = LABELS[key] + ' of the Year'
    if payout['prizes']:
        matches = [p for p in payout['prizes'] if p['prize'] == label]
        if not matches:
            return None
        assert len(matches) == 1, (conference, key, 'duplicate published award')
        value = matches[0][conference.lower()]
        return normalized(value) if value else None
    # Early local payout workbooks describe earned awards in prose.
    winners = []
    for team in payout['teams']:
        for item in team['earnedBreakdown']:
            text = item['label']
            if conference in text and (label in text or key + ' of the Year' in text):
                code = normalized(name_to_code.get(team['team'], team['team']))
                winners.append(code)
    assert len(set(winners)) <= 1, (conference, key, winners)
    return winners[0] if winners else None


def export(year, kind, params, cache=None):
    url = f'https://api.myfantasyleague.com/{year}/export?' + urlencode(
        dict(TYPE='weeklyResults' if kind == 'allWeeklyResults' else kind, JSON=1, **params))
    filename = f'{year}-{kind}-{params.get("L", "all")}.json'
    path = cache / filename if cache else None
    if path and path.exists():
        body = path.read_bytes()
    else:
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={'User-Agent': 'GM-Dashboard-Trophy-Results/2.0'})
                with urllib.request.urlopen(request, timeout=90) as response:
                    body = response.read()
                break
            except (OSError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep(2)
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
    result = json.loads(body)
    assert kind in result, (url, list(result))
    return result[kind], dict(url=url, sha256=hashlib.sha256(body).hexdigest())


def build(league, cache=None):
    history = json.loads((ROOT / 'data/gm_career_seasons.json').read_text())
    payouts = json.loads((ROOT / 'data/trophy_room/payouts.json').read_text())
    champions, games, provenance = [], {}, []
    for year in sorted({r['season'] for r in history}):
        end = 16 if year < 2021 else 17
        league_id = 60206 if league == 'ADL' else {2014: 37677, 2015: 27312}.get(year, 22686)
        raw, source = export(year, 'allWeeklyResults', dict(L=league_id, W='YTD', MISSING_AS_BYE=1), cache)
        # MFL's export TYPE is weeklyResults even when its YTD response is allWeeklyResults.
        metadata, player_source = export(year, 'players', {}, cache)
        players = {p['id']: p for p in arr(metadata['player'])}
        weeks = {}
        for week in arr(raw['weeklyResults']):
            number = int(week['week'])
            if number > end:
                continue
            fs = arr(week.get('franchise')) + [f for m in arr(week.get('matchup')) for f in arr(m['franchise'])]
            weeks[number] = {f['id']: f for f in fs if f['id'] != 'BYE'}
        assert set(weeks) == set(range(1, end + 1)), (year, 'missing weeks')
        assert all(len(fs) == 32 for fs in weeks.values()), (year, 'missing franchises')
        rows = [r for r in history if r['season'] == year]
        # Reconcile to the shared GM history before publishing another module.
        for row in rows:
            wins = ties = rs_wins = rs_ties = 0
            for number, fs in weeks.items():
                own = Decimal(fs[row['franchise_id']]['score'])
                for other, team in fs.items():
                    if other == row['franchise_id']:
                        continue
                    win = own > Decimal(team['score'])
                    tie = own == Decimal(team['score'])
                    wins += win
                    ties += tie
                    if number <= 12:
                        rs_wins += win
                        rs_ties += tie
            assert (wins, ties, rs_wins, rs_ties) == (row['wins'], row['ties'], row['rs_wins'], row['rs_ties']), (year, row['name'], 'MFL and canonical GM history disagree')
        codes = codes_for(league, year)
        by_code = {codes[int(r['franchise_id']) - 1]: r for r in rows}
        name_to_code = {r['name']: code for code, r in by_code.items()}
        champion = next(r for r in rows if r['finish'] == 1)
        runner = next(r for r in rows if r['finish'] == 2)
        final_week = next(w for w in arr(raw['weeklyResults']) if int(w['week']) == end)
        matches = [m for m in arr(final_week.get('matchup')) if
                   {f['id'] for f in arr(m['franchise'])} == {champion['franchise_id'], runner['franchise_id']}]
        assert len(matches) == 1, (year, 'championship matchup disagrees with canonical finishes')
        teams = []
        for row in [champion, runner]:
            team = weeks[end][row['franchise_id']]
            lineup = [dict(id=p['id'], name=players[p['id']]['name'],
                           position=players[p['id']]['position'], nflTeam=players[p['id']].get('team', ''),
                           points=float(p.get('score') or 0)) for p in arr(team.get('player')) if p.get('status') == 'starter']
            assert lineup and len({p['id'] for p in lineup}) == len(lineup)
            total = float(team['score'])
            teams.append(dict(franchise=row['name'], franchiseId=row['franchise_id'], total=total,
                              starterTotal=float(sum((Decimal(str(p['points'])) for p in lineup), Decimal(0))), players=lineup))
        assert teams[0]['total'] >= teams[1]['total'], (year, 'MFL result conflicts with champion')
        awards, award_sources = {}, {}
        for conference in ['NFC', 'AFC']:
            for key in LABELS:
                code = award_recipient(payouts[str(year)], conference, key, name_to_code)
                if not code:
                    assert league == 'FAFL' and year == 2014 and key == 'GM', (year, conference, key, 'missing award')
                    awards[conference + ' ' + key] = 'Not awarded'
                    continue
                assert code in by_code, (year, code)
                fid = by_code[code]['franchise_id']
                if key == 'HC':
                    wins = ties = 0
                    for w in range(1, 13):
                        own = Decimal(weeks[w][fid]['score'])
                        for other, team in weeks[w].items():
                            if other != fid:
                                wins += own > Decimal(team['score'])
                                ties += own == Decimal(team['score'])
                    value = (Decimal(wins) + Decimal(ties) / 2) / 372
                elif key == 'GM':
                    # Match the shared weekly dashboard calculation: MFL's optimal starters.
                    value = sum((Decimal(p.get('score') or '0') for w in range(1, 13)
                                 for p in arr(weeks[w][fid].get('player'))
                                 if str(p.get('shouldStart')) == '1'), Decimal(0)) / 12
                else:
                    positions = OFFENSE if key == 'OC' else DEFENSE
                    value = sum((Decimal(p.get('score') or '0') for w in range(1, 13)
                                 for p in arr(weeks[w][fid].get('player'))
                                 if p.get('status') == 'starter' and players[p['id']]['position'] in positions), Decimal(0)) / 12
                rounded = value.quantize(Decimal('.001') if key == 'HC' else Decimal('.1'), rounding=ROUND_HALF_UP)
                awards[conference + ' ' + key] = f'{code} ({rounded})'
                award_sources[conference + ' ' + key] = dict(franchiseId=fid, value=float(value), weeks=list(range(1, 13)))
        def record(row):
            return '-'.join(str(row['record_' + k]) for k in ['wins', 'losses', 'ties'])
        report = f'https://www{46 if league == "ADL" else 43}.myfantasyleague.com/{year}/weekly?L={league_id}&W={end}'
        champions.append(dict(year=year, champion=champion['name'], runner=runner['name'],
                              championRecord=record(champion), runnerRecord=record(runner), gm=champion['gm'],
                              score=f'{teams[0]["total"]:.1f} - {teams[1]["total"]:.1f}', awards=awards, source=report))
        games[str(year)] = dict(year=year, week=end, teams=teams, source=report)
        provenance.append(dict(year=year, weeklyResults=source, players=player_source, report=report,
                               awards=award_sources, awardRecipients=payouts[str(year)].get('source') or payouts[str(year)].get('sourceLabel')))
        print(f'{league} {year}: {champions[-1]["score"]}; eight award slots sourced', flush=True)
    dest = ROOT / 'data/trophy_room'
    for filename, value in [('champions.json', champions), ('super_bowl_lineups.json', games), ('results_provenance.json', provenance)]:
        (dest / filename).write_text(json.dumps(value, indent=2) + '\n')
    return champions, games


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--league', choices=['ADL', 'FAFL'], required=True)
    parser.add_argument('--cache', type=Path)
    args = parser.parse_args()
    build(args.league, args.cache)
