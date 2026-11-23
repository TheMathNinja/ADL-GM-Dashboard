"""Write and verify one finalized postseason slate using MFL's schedule editor."""
import collections
import http.cookiejar
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HOSTS = {'ADL': ('www46', '60206'), 'FAFL': ('www43', '22686')}


def sync(plan):
    host, league_id = HOSTS[plan['league']]
    if str(plan['leagueId']) != league_id or plan['season'] != 2026:
        raise ValueError('Wrong league or season')
    week = plan['week']
    if not 13 <= week <= 17 or plan['officialThroughWeek'] != week - 1:
        raise ValueError('Wrong postseason week')
    base = f'https://{host}.myfantasyleague.com/2026/'
    body = urllib.parse.urlencode({
        'USERNAME': os.environ['MFL_USERNAME'],
        'PASSWORD': os.environ['MFL_PASSWORD'], 'XML': '1',
    }).encode()
    with urllib.request.urlopen('https://api.myfantasyleague.com/2026/login', body, timeout=30) as response:
        token = ET.fromstring(response.read()).get('MFL_USER_ID')
    if not token:
        raise RuntimeError('MFL commissioner login failed')
    jar = http.cookiejar.CookieJar()
    jar.set_cookie(http.cookiejar.Cookie(
        0, 'MFL_USER_ID', urllib.parse.quote(token, safe=''), None, False,
        '.myfantasyleague.com', True, True, '/', True, True, None,
        True, None, None, {}, False))
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def get(path, fields=None):
        data = None if fields is None else urllib.parse.urlencode(fields).encode()
        request = urllib.request.Request(base + path, data=data, headers={
            'Cache-Control': 'no-cache',
        })
        with opener.open(request, timeout=30) as response:
            return response.read().decode(errors='replace')

    get(f'logout?L={league_id}&BECOME=0000')

    def snapshot():
        schedule = json.loads(get(f'export?TYPE=schedule&L={league_id}&W={week}&JSON=1'))
        data = schedule['schedule']['weeklySchedule']
        if int(data['week']) != week:
            raise RuntimeError('MFL returned the wrong schedule week')
        pairs = []
        for game in data.get('matchup', []):
            sides = game['franchise']
            if len(sides) != 2:
                raise RuntimeError('Unexpected MFL matchup shape')
            if any(side['id'] == 'BYE' for side in sides):
                pairs.append(tuple(sorted(side['id'] for side in sides)))
            else:
                if {side.get('isHome') for side in sides} != {'0', '1'}:
                    raise RuntimeError('Missing MFL home/away flags')
                pairs.append(tuple(side['id'] for side in sorted(sides, key=lambda s: s['isHome'])))
        return collections.Counter(pairs)

    rows = [(g['away'], g['home']) for g in plan['games']]
    rows += [(team, 'BYE') for team in plan['byes']]
    rows += [(g['third'], 'BYE') for g in plan['games'] if g['third']]
    if sorted(t for row in rows for t in row if t != 'BYE') != [f'{n:04}' for n in range(1, 33)]:
        raise ValueError('Slate must account for each franchise once')
    expected = collections.Counter(rows)
    existing = snapshot()
    if existing == expected:
        print(f'Week {week} already matches and was verified')
        return
    if existing:
        raise RuntimeError(f'MFL Week {week} already contains a different slate')

    document = get(f'csetup?L={league_id}&C=WEEKSCHED&W={week}')
    match = re.search(r'<form action="csetup" method="post" name="sched">(.*?)</form>', document, re.S)
    if not match:
        raise RuntimeError('MFL commissioner schedule editor unavailable')
    form = match[1]
    fields = dict(re.findall(r'<input type="hidden" name="([^"]+)"(?: id="[^"]+")? value="([^"]*)"', form))
    if (fields.get('LEAGUE_ID'), fields.get('W'), fields.get('C')) != (league_id, str(week), 'WEEKSCHED'):
        raise RuntimeError('MFL form target differs from plan')
    row_count = max(int(fields['ROWS']), len(rows))
    fields.update(ROWS=str(row_count), SUBMIT='Save Matchups', ADD_GAMES='0')
    for i, (away, home) in enumerate(rows + [('BYE', 'BYE')] * (row_count - len(rows))):
        fields[f'AWAY_{i}'] = away
        fields[f'HOME_{i}'] = home
    if snapshot():
        raise RuntimeError('MFL slate populated during preparation')
    response = get('csetup', fields)
    if f'Week {week} Schedule Saved' not in response or snapshot() != expected:
        raise RuntimeError(f'MFL Week {week} save/readback was not verified')
    print(f'Verified Week {week} schedule in MFL: {len(rows)} rows')


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    from preview import plan as build_plan

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--league', required=True, choices=HOSTS)
    parser.add_argument('--official-week', required=True, type=int)
    args = parser.parse_args()
    host, league_id = HOSTS[args.league]
    bracket = json.loads(Path('docs/playoff-picture/bracket-data.json').read_text(encoding='utf-8'))
    if bracket['league'] != args.league:
        raise ValueError('Wrong bracket league')
    with urllib.request.urlopen(
        f'https://{host}.myfantasyleague.com/2026/export?TYPE=league&L={league_id}&JSON=1',
        timeout=30,
    ) as response:
        directory = json.load(response)
    sync(build_plan(bracket, directory, args.official_week))
