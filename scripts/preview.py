"""Build a read-only MFL schedule preview from an official postseason bracket."""
import argparse
import html
import json
from pathlib import Path


def plan(bracket, league_export, official_week):
    league = bracket['league']
    week = official_week + 1
    if league not in ('ADL', 'FAFL') or week not in range(13, 18):
        raise ValueError('Expected an ADL or FAFL target in Weeks 13–17')
    if bracket['completedWeek'] != official_week:
        raise ValueError('Bracket does not match the finalized scoring week')
    directory = league_export['league']
    expected = {'ADL': '60206', 'FAFL': '22686'}[league]
    if str(directory['id']) != expected:
        raise ValueError('MFL league ID does not match the bracket')
    identities = {html.unescape(t['name']): t['id']
                  for t in directory['franchises']['franchise']}
    if len(identities) != 32 or len(set(identities.values())) != 32:
        raise ValueError('Incomplete MFL franchise directory')

    used = set()
    games = []
    byes = []
    for game in bracket['games']:
        if game['week'] != week:
            continue
        teams = game['teams']
        if not 1 <= len(teams) <= 3:
            raise ValueError('Invalid game size')
        ids = [identities[t['name']] for t in teams]
        if len(set(ids)) != len(ids) or used.intersection(ids):
            raise ValueError('Franchise appears twice in the target week')
        used.update(ids)
        if len(teams) == 1:
            if game['title'] != 'Bye':
                raise ValueError('Unexpected one-team game')
            byes.append(ids[0])
            continue

        ranked = sorted(teams, key=lambda t: (-t['allPlayPct'], t['seed']))
        if (ranked[0]['allPlayPct'], ranked[0]['seed']) == (ranked[1]['allPlayPct'], ranked[1]['seed']):
            raise ValueError(f"Unresolved home-field tie in {game['title']}")
        if len(ranked) == 3 and (ranked[1]['allPlayPct'], ranked[1]['seed']) == (ranked[2]['allPlayPct'], ranked[2]['seed']):
            raise ValueError(f"Unresolved display-pair tie in {game['title']}")
        games.append({
            'title': game['title'],
            'home': identities[ranked[0]['name']],
            'away': identities[ranked[1]['name']],
            'third': identities[ranked[2]['name']] if len(ranked) == 3 else None,
        })
    expected_byes = 2 if week in (13, 14) else 0
    if len(used) != 32 or len(byes) != expected_byes:
        raise ValueError('Incomplete postseason slate')
    return {'league': league, 'leagueId': expected, 'season': bracket['season'],
            'officialThroughWeek': official_week, 'week': week,
            'games': games, 'byes': byes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bracket', type=Path)
    parser.add_argument('league_export', type=Path)
    parser.add_argument('--official-week', type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(plan(json.loads(args.bracket.read_text(encoding='utf-8-sig')),
                          json.loads(args.league_export.read_text(encoding='utf-8-sig')),
                          args.official_week), indent=2))
