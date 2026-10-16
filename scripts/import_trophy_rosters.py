"""Import championship-week rosters and full-season MFL player performance.

python scripts/import_trophy_rosters.py --league ADL --cache /path/to/cache
GP counts numeric weekly scores in MFL's player report, including zero scores.
Starter statistics count each played week once if any league team started him.
"""
import argparse
import hashlib
import json
import re
import urllib.request
from collections import defaultdict
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from import_trophy_results import arr, export

ROOT = Path(__file__).resolve().parents[1]


class PlayerReport(HTMLParser):
    def __init__(self, end):
        super().__init__(convert_charrefs=True)
        self.end, self.players = end, {}
        self.cells = self.cell = None
        self.player_id = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr':
            self.cells, self.player_id = [], None
        elif tag == 'td' and self.cells is not None:
            self.cell = ''
        elif tag == 'a' and self.cells is not None:
            match = re.search(r"launch_player_modal\('[^']+','(\d+)'\)", attrs.get('href', ''))
            if match:
                self.player_id = match[1]

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag == 'td' and self.cell is not None:
            self.cells.append(self.cell.strip())
            self.cell = None
        elif tag == 'tr' and self.cells is not None:
            if self.player_id:
                assert len(self.cells) >= 4 + self.end, (self.player_id, 'missing weekly columns')
                weeks = {week: Decimal(value) for week, value in enumerate(self.cells[4:4 + self.end], 1)
                         if re.fullmatch(r'-?\d+(?:\.\d+)?', value)}
                points = sum(weeks.values(), Decimal(0))
                assert points == Decimal(self.cells[2]), (self.player_id, points, self.cells[2])
                assert self.player_id not in self.players, ('duplicate report row', self.player_id)
                self.players[self.player_id] = dict(weeks=weeks, points=points)
            self.cells, self.cell = None, None


def starter_weeks(weekly, player_stats, end):
    starts = defaultdict(set)
    for week in arr(weekly['weeklyResults']):
        number = int(week['week'])
        if number > end:
            continue
        teams = arr(week.get('franchise')) + [f for m in arr(week.get('matchup')) for f in arr(m['franchise'])]
        for team in teams:
            for player in arr(team.get('player')):
                if player.get('status') != 'starter':
                    continue
                pid = player['id']
                if pid not in player_stats:
                    assert Decimal(player.get('score') or '0') == 0, ('missing scored starter', number, pid)
                    continue
                played = player_stats[pid]['weeks']
                if number in played:
                    assert played[number] == Decimal(player.get('score') or '0'), ('MFL report/lineup conflict', number, pid)
                    starts[pid].add(number)
                else:
                    assert Decimal(player.get('score') or '0') == 0, ('points without a played game', number, pid)
    return starts


def stats_for(pid, report, starts):
    record = report.get(pid, dict(weeks={}, points=Decimal(0)))
    gp = len(record['weeks'])
    weeks_started = starts.get(pid, set())
    starter_points = sum((record['weeks'][w] for w in weeks_started), Decimal(0))
    return dict(gp=gp, points=float(record['points']), ppg=float(record['points'] / gp) if gp else None,
                starts=len(weeks_started), starterPoints=float(starter_points),
                starterPpg=float(starter_points / len(weeks_started)) if weeks_started else None)


def unique_roster(raw):
    # Older MFL exports repeat a reserve player in both ROSTER and TAXI_SQUAD/IR.
    # Keep one player, preserving the specific reserve designation when present.
    found = {}
    for player in arr(raw):
        pid = player['id']
        if pid not in found or player.get('status', 'ROSTER') != 'ROSTER':
            found[pid] = player
    return list(found.values())


def build(league, cache=None):
    history = json.loads((ROOT / 'data/gm_career_seasons.json').read_text())
    provenance = []
    for year in sorted({r['season'] for r in history}):
        end = 16 if year < 2021 else 17
        lid = 60206 if league == 'ADL' else {2014: 37677, 2015: 27312}.get(year, 22686)
        rosters, roster_source = export(year, 'rosters', dict(L=lid, W=end), cache)
        weekly, weekly_source = export(year, 'allWeeklyResults', dict(L=lid, W='YTD', MISSING_AS_BYE=1), cache)
        metadata, metadata_source = export(year, 'players', {}, cache)
        metadata = {p['id']: p for p in arr(metadata['player'])}
        url = f'https://api.myfantasyleague.com/{year}/top?' + urlencode(
            dict(L=lid, SEARCHTYPE='ADVANCED', COUNT=9999, START_WEEK=1, END_WEEK=end))
        report_path = cache / f'{league}-{year}-player-report.html' if cache else None
        if report_path and report_path.exists():
            raw = report_path.read_bytes()
        else:
            with urllib.request.urlopen(url, timeout=90) as response:
                raw = response.read()
            if report_path:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_bytes(raw)
        report = PlayerReport(end)
        report.feed(raw.decode('utf8', errors='replace'))
        assert len(report.players) > 500, (year, 'incomplete MFL player report')
        starts = starter_weeks(weekly, report.players, end)
        franchises, players = {}, {}
        rows = {r['franchise_id']: r for r in history if r['season'] == year}
        for team in arr(rosters['franchise']):
            fid = team['id']
            assert fid in rows
            roster = []
            for player in unique_roster(team.get('player')):
                pid = player['id']
                assert pid in metadata, (year, fid, 'unknown rostered player', pid)
                # A rostered player absent from MFL's full report did not play/scored no points.
                # Check the league's weekly lineups above before allowing that zero record.
                meta = metadata[pid]
                players[pid] = dict(id=pid, name=meta['name'], position=meta['position'],
                                    nflTeam=meta.get('team', ''), **stats_for(pid, report.players, starts))
                roster.append(dict(id=pid, status=player.get('status', 'ROSTER')))
            assert roster and len({p['id'] for p in roster}) == len(roster), (year, fid, 'invalid roster')
            franchises[fid] = dict(franchise=rows[fid]['name'], players=roster)
        assert set(franchises) == set(rows) and len(franchises) == 32
        payload = dict(year=year, throughWeek=end, franchises=franchises, players=players)
        for directory in ['data/trophy_room/rosters', 'docs/trophy-room/rosters']:
            dest = ROOT / directory
            dest.mkdir(parents=True, exist_ok=True)
            (dest / f'{year}.json').write_text(json.dumps(payload, separators=(',', ':')) + '\n')
        provenance.append(dict(year=year, rosters=roster_source, lineups=weekly_source, players=metadata_source,
                               playerReport=dict(url=url, sha256=hashlib.sha256(raw).hexdigest()),
                               teams=32, rosteredPlayers=len(players)))
        print(f'{league} {year}: 32 ending rosters, {len(players)} distinct players', flush=True)
    (ROOT / 'data/trophy_room/rosters_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--league', choices=['ADL', 'FAFL'], required=True)
    parser.add_argument('--cache', type=Path)
    args = parser.parse_args()
    build(args.league, args.cache)
