"""Build the public Payouts module from completed scores and season rules."""

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from nfl_teams import MFL_TEAMS, mfl_team, provider_team
from sync_payouts import ROOT, PERIODS, expected_awards, input_matrix, load_scores, mapping, postseason_prizes


CONFERENCES = ('NFC', 'AFC')
DISPLAY_PERIODS = [
    *(period for q in range(1, 5) for period in (
        *(f'Week {week}' for week in range(3*q-2, 3*q+1)), f'Q{q} Cumulative')),
    'Regular Season ($)', *(f'Week {week}' for week in range(13, 18)),
    'Postseason Cumulative',
]


def winners(value):
    return [mfl_team(token, strict=True) for token in value.split(',')] if value else []


def cents(value):
    amount = Fraction(str(value)) * 100
    if amount.denominator != 1:
        raise ValueError(f'Expected a currency amount in whole cents: {value}')
    return int(amount)


def build_snapshot(root, league, season, ready_week=None):
    config = json.loads((root / 'config/payouts.json').read_text(encoding='utf-8'))
    if (config['league'], config['season']) != (league, season):
        raise ValueError('Payout rules do not match the requested league and season')
    scores, week = load_scores(root, league, season, ready_week)
    teams = mapping([[]] + config['teams'], scores)
    teams = [(name, mfl_team(code, strict=True), conf) for name, code, conf in teams]
    by_code = {code: conf for _, code, conf in teams}
    if set(by_code) != MFL_TEAMS:
        raise ValueError('Payouts requires all 32 canonical NFL teams')

    awards = expected_awards(teams, scores, week)
    bracket = dict(completedWeek=week, season=season, games=[])
    if week >= 12:
        bracket = json.loads((root / 'docs/playoff-picture/bracket-data.json').read_text(encoding='utf-8'))
        if bracket['league'] != league:
            raise ValueError('Wrong league bracket')
    postseason = postseason_prizes(bracket, teams, week, season)
    season_awards = awards['Regular Season ($)']
    recipients = (
        postseason
        + [[season_awards[i], season_awards[i+4]] for i in range(4)]
        + [[awards[f'Week {w}'][i] for i in (0, 4)] for w in range(1, 18)]
    )
    due_weeks = [17, 17, 16, 16, 16, 16, 16] + [12]*7 + [17] + [12]*4 + list(range(1, 18))
    earnings = dict.fromkeys(by_code, Fraction(0))
    if len(config['prizes']) != len(recipients):
        raise ValueError('Payout rules must contain all 36 prize rows in workbook order')
    prizes = []
    for index, ((label, amount), row, due) in enumerate(zip(config['prizes'], recipients, due_weeks)):
        total_cents = cents(amount)
        league_wide = index < 2
        if total_cents < 0:
            raise ValueError(f'Negative prize amount: {label}')
        by_conference = {conf: winners(value) for conf, value in zip(CONFERENCES, row)}
        count = sum(bool(codes) for codes in by_conference.values())
        if count != (1 if league_wide else 2) * (week >= due):
            raise ValueError(f'Unexpected number of completed prize slots: {label}')
        for conf, codes in by_conference.items():
            if len(set(codes)) != len(codes) or any(by_code.get(code) != conf for code in codes):
                raise ValueError(f'Invalid recipients: {label}, {conf}')
            for code in codes:
                earnings[code] += Fraction(total_cents, len(codes))
        group = 'Weekly' if index >= 19 else 'Regular Season' if index >= 15 else 'Postseason'
        prizes.append(dict(label=label, amount=amount, scope='league' if league_wide else 'conference',
                           group=group, recipients=by_conference, settled=week >= due))

    adjustments = {}
    for code, value in config['adjustments'].items():
        canonical = mfl_team(code, strict=True)
        if canonical not in by_code or canonical in adjustments:
            raise ValueError(f'Invalid or duplicate payout adjustment: {code}')
        adjustments[canonical] = cents(value)
    adjustment_notes = {}
    for code, note in config.get('adjustmentNotes', {}).items():
        canonical = mfl_team(code, strict=True)
        if canonical not in by_code or canonical in adjustment_notes:
            raise ValueError(f'Invalid or duplicate payout adjustment note: {code}')
        if not isinstance(note, str) or not note.strip():
            raise ValueError(f'Expected a nonempty payout adjustment note: {code}')
        adjustment_notes[canonical] = note
    awarded = sum(cents(p['amount']) * sum(bool(c) for c in p['recipients'].values()) for p in prizes)
    pool = sum(cents(p['amount']) * (1 if p['scope'] == 'league' else 2) for p in prizes)
    if sum(earnings.values()) != awarded:
        raise ValueError('Prize awards do not reconcile to team earnings')
    dollars = lambda value: float(value / 100)
    balances = []
    for name, code, conf in teams:
        adjustment = adjustments.get(code, 0)
        balances.append(dict(code=code, name=name, conference=conf,
                             logo=f'https://a.espncdn.com/i/teamlogos/nfl/500/{provider_team(code, "espn").lower()}.png',
                             earned=dollars(earnings[code]), adjustment=dollars(adjustment),
                             payout=dollars(earnings[code] + adjustment),
                             adjustmentNote=adjustment_notes.get(code)))
    end_weeks = {label: max(weeks) for label, weeks in PERIODS}
    snapshot = dict(
        league=league, season=season, throughWeek=week,
        awards=[dict(period=label, settled=end_weeks[label] <= week,
                     winners=[winners(value) for value in awards[label]]) for label in DISPLAY_PERIODS],
        prizes=prizes, teams=balances,
        totals=dict(payIn=dollars(cents(config['payIn'])), pool=dollars(pool),
                    hostingFee=dollars(cents(config['hostingFee'])),
                    earned=dollars(awarded), adjustments=dollars(sum(adjustments.values())),
                    payout=dollars(awarded+sum(adjustments.values())), remaining=dollars(pool-awarded)),
    )
    source = dict(scores=input_matrix(teams, scores, week, league, season), bracket=bracket, rules=config)
    return snapshot, awards, hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as output:
        temporary = Path(output.name)
        json.dump(payload, output, indent=2, allow_nan=False)
        output.write('\n')
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--league', choices=['ADL', 'FAFL'], required=True)
    parser.add_argument('--check', action='store_true', help='Validate and report without writing publication files')
    args = parser.parse_args()
    season = int(os.environ.get('CURRENT_SEASON', '2026'))
    snapshot, awards, digest = build_snapshot(ROOT, args.league, season, int(os.environ.get('READY_WEEK') or 0))
    week = snapshot['throughWeek']
    if not args.check:
        url = f'https://themathninja.github.io/{args.league}-GM-Dashboard/payouts/'
        receipt = dict(league=args.league, season=season, through_week=week, run_id=os.environ['GITHUB_RUN_ID'],
                       status='success', verified_at=datetime.now(timezone.utc).isoformat(),
                       source_sha256=digest, awards=awards, published_url=url, mode='dashboard')
        write_json(ROOT / 'docs/payouts/payouts-data.json', snapshot)
        write_json(ROOT / 'data/payouts_sync_metadata.json', receipt)
    print(f'{args.league} Payouts reconciled through Week {week}: 32 teams, 36 prizes.')


if __name__ == '__main__':
    main()
