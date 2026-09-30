"""Exact legal-lineup availability credits shared with the validated research.

Caller supplies point-in-time player estimates and NFL status labels. Missing
status is NOT inferred from a zero score or fantasy injured-reserve designation.
"""
from math import isfinite


def status_code(value):
    value = (value or '').strip().upper().replace('(', '').replace(')', '')
    return {'SUSPENDED':'S', 'OUT':'O', 'BYE WEEK':'BYE',
            'INJURED RESERVE - DESIGNATED FOR RETURN':'IR-R'}.get(value, value)


def player_credit(player, multipliers):
    status = status_code(player.get('nfl_status'))
    if status not in {'S','O','BYE','IR-R'} or float(player['points']) != 0:
        return 0.0
    estimate = player.get('estimated_ppg')
    if estimate is None or not isfinite(float(estimate)):
        raise ValueError('Eligible player lacks a point-in-time PPG estimate')
    weight = float(multipliers[status])
    if not isfinite(weight) or not 0 <= weight <= 1: raise ValueError('Invalid multiplier')
    return weight * max(0, float(estimate))


def best_lineup(players, limits, totals, adjusted=False, multipliers=None):
    """Exact position-count optimization, independently within each lineup group.

    limits: position -> (minimum, maximum, group). totals: group -> starter count.
    Includes every supplied roster player; caller must apply historical roster
    eligibility rules (e.g. taxi/IR) before calling.
    """
    if len({p['id'] for p in players}) != len(players): raise ValueError('Duplicate player')
    if any(p['pos'] not in limits for p in players): raise ValueError('Unknown position')
    result = 0.0
    for group, count in totals.items():
        states = {0:0.0}
        for pos, (lo,hi,g) in limits.items():
            if g != group: continue
            values = sorted((float(p['points']) + (player_credit(p,multipliers) if adjusted else 0)
                             for p in players if p['pos']==pos), reverse=True)
            choices = {n:sum(values[:n]) for n in range(lo,min(hi,len(values))+1)}
            next_states = {}
            for used,score in states.items():
                for n,points in choices.items():
                    if used+n <= count:
                        next_states[used+n] = max(next_states.get(used+n,float('-inf')),score+points)
            states = next_states
        if count not in states: raise ValueError('Roster cannot fill a legal lineup')
        result += states[count]
    return result


def credits(players, multipliers, limits, totals):
    direct = sum(player_credit(p,multipliers) for p in players)
    baseline = best_lineup(players,limits,totals)
    adjusted = best_lineup(players,limits,totals,True,multipliers)
    return {'direct_credit':direct,'lineup_credit':adjusted-baseline,
            'reconstructed_potential':baseline,'adjusted_potential':adjusted}
