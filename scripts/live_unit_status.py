"""Possession-based unit indicators with explicit pauses and missing-data states."""
from collections import Counter
OFFENSE={'QB','RB','WR','TE'}
DEFENSE={'DT','DE','DL','EDGE','LB','CB','S','DB'}
PAUSED={'halftime','between_periods','awaiting_overtime','awaiting_final'}
DEFINITION=dict(version=2,basis='NFL possession and fantasy position',offense='NFL team has possession',defense='opponent has possession',specialTeams='excluded; possession does not identify kicking formations',paused='false during halftime, between periods, awaiting overtime or awaiting final confirmation',unknown='null only when live unit state is unavailable',display='known on-field count; zero shown even when paused or possession is unavailable; reason flags retained')


def player_live(p):
    status=p.get('gameStatus','')
    return status not in ('Pregame','Final','Bye') and (float(p.get('seconds',0))>0 or status.startswith('Awaiting'))


def scoring_unit(position):
    return 'offense' if position in OFFENSE else 'defense' if position in DEFENSE else 'special_teams' if position in {'PK','K','PN','P'} else 'unknown'


def game_phase(p,game=None):
    game=game or {};status=p.get('gameStatus','')
    if status in ('Pregame','Final','Bye'):return status.lower()
    if status=='Halftime' or game.get('halftime'):return 'halftime'
    if status.startswith('Awaiting OT'):return 'awaiting_overtime'
    if status.startswith('Awaiting'):return 'awaiting_final'
    if game.get('state')=='in' and game.get('period') in (1,2,3) and game.get('clock')==0:return 'between_periods'
    if status.startswith('OT '):return 'overtime'
    if player_live(p):return 'live'
    return 'unknown'


def unit_observation(p):
    phase=p.get('nflGamePhase') or game_phase(p)
    if phase in PAUSED or phase in ('pregame','final','bye'):return False,phase
    if phase=='unknown':return None,'unknown_game_phase'
    unit=scoring_unit(p.get('position'))
    if unit=='special_teams':return None,'special_teams_excluded'
    if unit=='unknown':return None,'unknown_position'
    board=p.get('nflScoreboard') or []
    teams={t.get('team') for t in board};possession=[t.get('team') for t in board if t.get('possession') is True]
    if len(board)!=2 or len(teams)!=2 or p.get('nflTeam') not in teams or len(possession)!=1:return None,'missing_possession'
    on=(p['nflTeam']==possession[0])==(unit=='offense')
    return on,'unit_on_field' if on else 'other_unit_on_field'


def unit_on_field(p):return unit_observation(p)[0]


def annotate_player(p,game=None):
    p['scoringUnit']=scoring_unit(p.get('position'))
    p['nflGamePhase']=game_phase(p,game)
    p['unitOnField'],p['unitOnFieldReason']=unit_observation(p)
    return p


def unit_summary(starters):
    eligible=[p for p in starters if player_live(p) and scoring_unit(p.get('position')) in ('offense','defense')]
    return dict(unitOnFieldCount=sum(p.get('unitOnField') is True for p in eligible),unitOnFieldUnknownCount=sum(p.get('unitOnField') is None for p in eligible),unitOnFieldEligibleLiveCount=len(eligible),unitOnFieldReasonCounts=dict(Counter(p.get('unitOnFieldReason','unrecorded') for p in starters)),starterGamePhaseCounts=dict(Counter(p.get('nflGamePhase','unknown') for p in starters)))
