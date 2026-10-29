"""Same-week public submitted start counts across ADL and FAFL."""
import datetime as dt

def start_counts(feed,week):
    from collect_live_bonus import franchises,many
    if int(feed.get('week',-1))!=week:raise ValueError('Wrong week in pooled start-count feed')
    clubs=franchises(feed)
    if len(clubs)!=32:raise ValueError('Incomplete league feed for pooled starts')
    result={};seen=set()
    for fid,f in clubs.items():
        players=many(f.get('player')) or many(f.get('players',{}).get('player'))
        for p in players:
            key=(str(fid),str(p['id']))
            if str(p.get('status','')).lower()=='starter' and key not in seen:
                seen.add(key);result[key[1]]=result.get(key[1],0)+1
    return result

def with_start_counts(calibration,collector,week,local_feed=None,final=False):
    if not calibration.get('unifiedFSPositions'):return calibration
    feeds={};kind='weeklyResults' if final else 'liveScoring';extra=f'&W={week}'+('' if final else '&DETAILS=1')
    if not hasattr(collector,'start_count_peers'):collector.start_count_peers={}
    for lg in ['ADL','FAFL']:
        if lg==collector.league:source=collector;feed=local_feed if local_feed is not None else source.get(kind,extra,ttl=60)
        else:
            if lg not in collector.start_count_peers:collector.start_count_peers[lg]=collector.__class__(lg,collector.season)
            source=collector.start_count_peers[lg];feed=source.get(kind,extra,ttl=60)
        feeds[lg]=start_counts(feed,week)
    counts={pid:{lg:feeds[lg].get(pid,0) for lg in feeds} for pid in set(feeds['ADL'])|set(feeds['FAFL'])}
    return dict(calibration,_startCounts=counts,_startCountsContext=dict(season=collector.season,week=week,fetchedAt=dt.datetime.now(dt.timezone.utc).isoformat(),source=kind))
