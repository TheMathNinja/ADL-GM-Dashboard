"""Possession-based offensive/defensive unit indicators, not snap participation."""
OFFENSE={'QB','RB','WR','TE'}
DEFENSE={'DT','DE','DL','EDGE','LB','CB','S','DB'}
DEFINITION=dict(version=1,basis='NFL possession and fantasy position',offense='NFL team has possession',defense='opponent has possession',specialTeams='excluded; possession does not identify kicking formations',unknown='null when a live unit cannot be determined')


def player_live(p):
    status=p.get('gameStatus','')
    return status not in ('Pregame','Final','Bye') and (float(p.get('seconds',0))>0 or status.startswith('Awaiting'))


def scoring_unit(position):
    return 'offense' if position in OFFENSE else 'defense' if position in DEFENSE else 'special_teams' if position in {'PK','K','PN','P'} else 'unknown'


def unit_on_field(p):
    if not player_live(p):return False
    unit=scoring_unit(p.get('position'))
    if unit not in ('offense','defense'):return None
    board=p.get('nflScoreboard') or []
    teams={t.get('team') for t in board};possession=[t.get('team') for t in board if t.get('possession') is True]
    if len(board)!=2 or len(teams)!=2 or p.get('nflTeam') not in teams or len(possession)!=1:return None
    return (p['nflTeam']==possession[0])==(unit=='offense')


def annotate_player(p):
    p['scoringUnit']=scoring_unit(p.get('position'))
    p['unitOnField']=unit_on_field(p)
    return p


def unit_summary(starters):
    eligible=[p for p in starters if player_live(p) and scoring_unit(p.get('position')) in ('offense','defense')]
    return dict(unitOnFieldCount=sum(p.get('unitOnField') is True for p in eligible),unitOnFieldUnknownCount=sum(p.get('unitOnField') is None for p in eligible),unitOnFieldEligibleLiveCount=len(eligible))
