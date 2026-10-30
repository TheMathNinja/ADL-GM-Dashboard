"""Week-specific availability gates shared by live and pregame forecasts.
Keep earned points; never infer absence from a missing Sharks projection.
"""
UNAVAILABLE = frozenset({'H','S','O','I','IR','IR-R','PUP','NFI','IR-PUP','IR-NFI'})
ALIASES = {'HOLDOUT':'H','HOLD OUT':'H','SUSPENDED':'S','OUT':'O','INACTIVE':'I',
 'INJURED RESERVE':'IR','INJURED RESERVE - DESIGNATED FOR RETURN':'IR-R',
 'HEALTHY':'','ACTIVE':'','QUESTIONABLE':'Q','DOUBTFUL':'D','PROBABLE':'P','BYE WEEK':'BYE'}

def status_code(value):
    raw=str(value or '').strip().upper().replace('(', '').replace(')', '')
    return ALIASES.get(raw,raw)

def unavailable_status(value):
    return status_code(value) in UNAVAILABLE

def unavailable(player):
    return player.get('gameStatus')=='Bye' or unavailable_status(player.get('injuryStatus'))

def remaining_exposure(player):
    if player.get('gameStatus')=='Final' or unavailable(player):return 0.
    return max(0.,min(1.,float(player.get('projectionSeconds',player.get('seconds',0)))/3600))

def weekly_metadata(collector,metadata,week):
    """Use only this week's report; a missing report must not silently erase flags."""
    report=collector.get('injuries',f'&W={week}',ttl=0)
    if str(report.get('week',week))!=str(week):raise ValueError('Wrong injury report week')
    result={pid:{**p,'injuryStatus':'','injuryDetails':''} for pid,p in metadata.items()}
    rows=report.get('injury',[]);rows=rows if isinstance(rows,list) else [rows]
    for row in rows:
        pid=row.get('id')
        if pid in result:result[pid].update(injuryStatus=status_code(row.get('status')),injuryDetails=row.get('details',''))
    return result
