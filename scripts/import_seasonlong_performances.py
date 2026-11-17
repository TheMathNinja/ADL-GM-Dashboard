"""Seasonlong records from the same MFL games and ADL26 overlay as weekly records.

Completed seasons are frozen with --history --overlay PATH. Ordinary authorized
refreshes merge that history with completed current-season weeks only.
"""
import argparse,copy,csv,hashlib,json
from collections import Counter,defaultdict
from pathlib import Path
from import_top_performances import (arr,export,fetch_json,PlayerReport,POSITIONS,OFFENSE,
    optimize,tenths,scoring_signature,current_playoff_field,rank_ten)

ROOT=Path(__file__).resolve().parents[1]
METRICS=['record','allplay','total','offense','defense','potential']
PHASES=['regular','playoffs','combined']

def result(a,b):return 'W' if a>b else 'L' if a<b else 'T'
def record(values):
    c=Counter(values);return dict(wins=c['W'],losses=c['L'],ties=c['T'])
def add_records(a,b):return {k:a[k]+b[k] for k in ['wins','losses','ties']}
def percentage(r):
    games=sum(r.values());return (r['wins']+.5*r['ties'])/games if games else None
def allplay(scores):
    return {fid:dict(wins=sum(v>other for oid,other in scores.items() if oid!=fid),
                     losses=sum(v<other for oid,other in scores.items() if oid!=fid),
                     ties=sum(v==other for oid,other in scores.items() if oid!=fid)) for fid,v in scores.items()}

def bonus_awards(weekly,year,through,league=None):
    """Historical standard awards: four quarters; full RS from 2021; 2025 cut changes."""
    events=[('Q1',1,3),('Q2',4,6),('Q3',7,9),('Q4',10,12)]
    if year>=2021:events.append(('Regular Season',1,12))
    output=defaultdict(list)
    for label,start,end in events:
        if through<end:continue
        frame=[weekly.get(w) for w in range(start,end+1)]
        if any(not week or len(week)!=32 or any(v['total'] is None or v['potential'] is None for v in week.values()) for week in frame):return None
        ap={fid:0 for fid in frame[0]};points=Counter();potential=Counter()
        for week in frame:
            played=allplay({fid:r['total'] for fid,r in week.items()})
            for fid,row in week.items():
                ap[fid]+=2*played[fid]['wins']+played[fid]['ties'];points[fid]+=tenths(row['total']);potential[fid]+=tenths(row['potential'])
        groups=[list(ap)] if year>=2025 else [[fid for fid in ap if (int(fid)<=16)==is_nfc] for is_nfc in [True,False]]
        for group in groups:
            cut=15 if year>=2025 else 7;tie_end=len(group)-cut
            ordered=sorted(group,key=lambda fid:(-ap[fid],-points[fid],-potential[fid],fid))
            for i,fid in enumerate(ordered):output[fid].append(dict(label=label,start=start,end=end,rank=i+1,result='W' if i<cut else 'T' if i<tie_end else 'L',allplayWins=ap[fid]/2,points=points[fid]/10,potential=potential[fid]/10))
    return output

def blank():return dict(teams={p:{c:{m:[] for m in METRICS} for c in ['NFC','AFC']} for p in PHASES},positions={p:{pos:[] for pos in POSITIONS} for p in PHASES})
def rank_seasons(rows,limit=10):
    return [{k:v for k,v in r.items() if k!='week'} for r in rank_ten([dict(r,week=0) for r in rows],limit)]
def compact(modes):
    for mode in modes.values():
        for phase in PHASES:
            for conf in ['NFC','AFC']:
                for metric,rows in mode['teams'][phase][conf].items():mode['teams'][phase][conf][metric]=rank_seasons(rows)
            for pos,rows in mode['positions'][phase].items():mode['positions'][phase][pos]=rank_seasons(rows,25)
def retained(modes):
    out=set()
    for mode in modes.values():
        for phase in PHASES:
            for conf in mode['teams'][phase].values():
                for rows in conf.values():out.update(r['detail'] for r in rows)
            for rows in mode['positions'][phase].values():out.update(r['detail'] for r in rows)
    return out
def merge(old,new):
    for mode in new:
        for phase in PHASES:
            for conf in ['NFC','AFC']:
                for metric in METRICS:new[mode]['teams'][phase][conf][metric]+=old[mode]['teams'][phase][conf][metric]
            for pos in POSITIONS:new[mode]['positions'][phase][pos]+=old[mode]['positions'][phase][pos]
    compact(new);return new

def build(league,cache,history=False,overlay=None):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    careers=json.loads((ROOT/'data/gm_career_seasons.json').read_bytes());status=json.loads((ROOT/'docs/weekly-refresh-status.json').read_bytes())
    season,through=int(status['season']),int(status['week']);assert season==2026,'Audit reconstruction before changing current scoring year.'
    ownership=json.loads((ROOT/f'data/current_gms_{season}.json').read_bytes());assert ownership['season']==season
    profiles=ownership['profiles'];assert len(profiles)==32
    aliases={k.lower():v for k,v in json.loads((ROOT/'data/gm_name_aliases.json').read_bytes()).items()} if league=='ADL' else {}
    if league=='FAFL':
        from build_trophy_room import people
    def gm(text):return ' / '.join(dict.fromkeys(aliases.get(p.strip().lower(),p.strip()) for p in text.split(',') if p.strip())) if league=='ADL' else ' / '.join(people(text))
    points={}
    if history:
        assert overlay,'Historical Current Scoring needs the authoritative reconstructed overlay.'
        for r in csv.DictReader(Path(overlay).open(encoding='utf-8-sig')):
            if r['adl26_points'] not in ('','NA'):points[int(r['season']),int(r['week']),r['player_id']]=tenths(r['adl26_points'])/10
    current_lid=60206 if league=='ADL' else 22686
    rules=fetch_json(cache/f'{league}-{season}-rules.json',f'https://api.myfantasyleague.com/{season}/export?TYPE=rules&L={current_lid}&JSON=1')
    signature=scoring_signature(rules)
    weekly_reference=json.loads((ROOT/'docs/trophy-room/top-performances.json').read_bytes())
    assert weekly_reference['meta']['scoringRulesSignature']==signature,'Seasonlong and weekly scoring rules differ.'
    config_current=fetch_json(cache/f'{league}-{season}-league.json',f'https://api.myfantasyleague.com/{season}/export?TYPE=league&L={current_lid}&JSON=1')['league']
    supported={p['name'] for p in arr(config_current['starters']['position'])}
    modes={m:blank() for m in ['native','current']};details={};sources=[];coverage=Counter();adjustments=[]
    years=sorted({r['season'] for r in careers}) if history else [season]
    for year in years:
        end=min(16 if year<2021 else 17,through if year==season else 99)
        lid=60206 if league=='ADL' else {2014:37677,2015:27312}.get(year,22686)
        weekly,weekly_source=export(year,'allWeeklyResults',dict(L=lid,W='YTD',MISSING_AS_BYE=1),cache)
        schedule,schedule_source=export(year,'schedule',dict(L=lid),cache)
        schedule_weeks={int(w['week']):w for w in arr(schedule['weeklySchedule'])}
        metadata,players_source=export(year,'players',dict(L=lid),cache)
        players={p['id']:p for p in arr(metadata['player'])}
        config=fetch_json(cache/f'{league}-{year}-league.json',f'https://api.myfantasyleague.com/{year}/export?TYPE=league&L={lid}&JSON=1')['league']
        if year==season:
            franchises={str(p['franchise_id']).zfill(4):dict(name=name,gm=gm(p['gm']),finish=33) for name,p in profiles.items()}
            field=current_playoff_field(json.loads((ROOT/'docs/playoff-picture/bracket-data.json').read_bytes()),season) if end>12 else set()
            qualifiers={fid for fid,r in franchises.items() if r['name'] in field}
        else:
            franchises={r['franchise_id']:dict(r,gm=gm(r['gm'])) for r in careers if r['season']==year}
            brackets=fetch_json(cache/f'{league}-{year}-playoffBrackets.json',f'https://api.myfantasyleague.com/{year}/export?TYPE=playoffBrackets&L={lid}&JSON=1')['playoffBrackets']
            counts={int(b['teamsInvolved']) for b in arr(brackets.get('playoffBracket')) if b['name'] in ['NFC Playoffs','AFC Playoffs']};assert len(counts)==1
            qualifiers={fid for fid,r in franchises.items() if r['finish']<=2*next(iter(counts))}
        report_path=cache/f'{league}-{year}-player-report.html'
        if not report_path.exists():
            import urllib.request
            report_path.write_bytes(urllib.request.urlopen(f'https://api.myfantasyleague.com/{year}/top?L={lid}&SEARCHTYPE=ADVANCED&COUNT=9999&START_WEEK=1&END_WEEK={end}',timeout=90).read())
        report=PlayerReport(end);report.feed(report_path.read_bytes().decode('utf8','replace'));assert len(report.players)>500,(league,year,'Incomplete MFL player report')
        frames={m:{} for m in modes};games={};native_results={};eligible={};ap={m:{} for m in modes}
        for w in arr(weekly['weeklyResults']):
            week=int(w['week'])
            if week>end:continue
            all_teams=arr(w.get('franchise'))+[f for match in arr(w.get('matchup')) for f in arr(match['franchise'])]
            fs={f['id']:f for f in all_teams if f['id']!='BYE'};assert len(fs)==32,(year,week,'Incomplete week')
            opponents={};results={}
            for match in arr(schedule_weeks.get(week,{}).get('matchup')):
                pair=arr(match['franchise'])
                if len(pair)!=2 or any(f['id']=='BYE' for f in pair):continue
                for f in pair:
                    assert f['result'] in ['W','L','T'],(league,year,week,'Incomplete scheduled result')
                    other=next(x for x in pair if x['id']!=f['id'])
                    opponents.setdefault(f['id'],[]).append(other['id']);results.setdefault(f['id'],[]).append(f['result'])
            games[week]=opponents;native_results[week]=results
            eligible[week]={fid for fid in fs if week<=12 or fid in qualifiers and fid in opponents}
            for mode in modes:frames[mode][week]={}
            for fid,f in fs.items():
                pools={'native':[],'current':[]};starter_ids=[]
                for p in arr(f.get('player')):
                    pid=p['id'];meta=players.get(pid)
                    if not meta:
                        assert not float(p.get('score') or 0),(year,week,pid,'Unknown scored player');continue
                    pos={'K':'PK','P':'PN'}.get(meta.get('position'),meta.get('position'))
                    if pos not in POSITIONS:
                        assert not float(p.get('score') or 0),(year,week,pid,'Unsupported scored position');continue
                    native=float(p.get('score') or 0);played=report.players.get(pid,{}).get('weeks',{})
                    current=native if year==season else points.get((year,week,pid),0 if week not in played else None)
                    if pos not in supported:current=None
                    for mode,value in [('native',native),('current',current)]:pools[mode].append(dict(id=pid,position=pos,score=value))
                    if p.get('status')=='starter':starter_ids.append(pid)
                for mode,pool in pools.items():
                    starters=[p for p in pool if p['id'] in starter_ids]
                    values={}
                    for metric in ['total','offense','defense']:
                        chosen=[p for p in starters if metric=='total' or ((p['position'] in OFFENSE)==(metric=='offense'))]
                        values[metric]=None if any(p['score'] is None for p in chosen) else float(f['score']) if metric=='total' and (mode=='native' or year==season) else tenths(sum(p['score'] for p in chosen))/10
                    values['potential']=float(f['opt_pts']) if mode=='native' or year==season else None if any(p['score'] is None for p in pool) else tenths(sum(p['score'] for p in optimize(pool,config['starters'])))/10
                    frames[mode][week][fid]=values
            for mode in modes:
                totals={fid:r['total'] for fid,r in frames[mode][week].items()}
                ap[mode][week]=allplay(totals) if all(v is not None for v in totals.values()) else None
        bonus={m:bonus_awards(frames[m],year,end,league) for m in modes}
        official_bonus={}
        for fid,franchise in franchises.items():
            if year==season:official_bonus[fid]=record(e['result'] for e in (bonus['native'] or {}).get(fid,[]));continue
            basis=[outcome for w in native_results if fid in native_results[w] and (w<=12 if year<=2018 else True) for outcome in native_results[w][fid]]
            scheduled=record(basis)
            official_bonus[fid]={k:franchise['record_'+k]-scheduled[k] for k in scheduled}
            assert min(official_bonus[fid].values())>=0,(league,year,fid,'Invalid official bonus decomposition')
            modeled=record(e['result'] for e in (bonus['native'] or {}).get(fid,[]))
            if modeled!=official_bonus[fid]:adjustments.append(dict(year=year,franchise=franchise['name'],publishedBonus=official_bonus[fid],standardBonus=modeled))
        for mode in modes:
            for phase in PHASES:
                for fid,franchise in franchises.items():
                    weeks=[w for w in frames[mode] if fid in eligible[w] and (w<=12 if phase=='regular' else w>12 if phase=='playoffs' else True)]
                    if not weeks:continue
                    conf='NFC' if int(fid)<=16 else 'AFC';week_rows=[]
                    for w in weeks:
                        row=frames[mode][w][fid];opponents=games[w].get(fid,[])
                        outcomes=native_results[w].get(fid,[]) if mode=='native' or year==season else [result(row['total'],frames[mode][w][opponent]['total']) if row['total'] is not None and frames[mode][w][opponent]['total'] is not None else None for opponent in opponents]
                        week_rows.append(dict(week=w,**row,opponent=' / '.join(franchises[o]['name'] for o in opponents) or None,result=' / '.join(r or '—' for r in outcomes) or None,results=outcomes,allplay=ap[mode][w].get(fid) if ap[mode][w] else None,url=f'https://api.myfantasyleague.com/{year}/weekly?L={lid}&W={w}'))
                    scheduled_rows=[r for r in week_rows if r['opponent']]
                    h2h=record(outcome for r in scheduled_rows for outcome in r['results'])
                    bonus_events=[] if phase=='playoffs' else (bonus[mode] or {}).get(fid,[])
                    bonus_record=record(e['result'] for e in bonus_events)
                    adjustment={k:official_bonus[fid][k]-bonus_record[k] for k in bonus_record} if mode=='native' and phase!='playoffs' else dict(wins=0,losses=0,ties=0)
                    combined=add_records(add_records(h2h,bonus_record),adjustment)
                    ap_record={k:sum((r['allplay'] or {}).get(k,0) for r in week_rows) for k in ['wins','losses','ties']}
                    for metric in METRICS:
                        cover=f'{mode}:{phase}:{conf}:{metric}';coverage[cover+':eligible']+=1
                        if metric=='record':
                            if any(outcome is None for r in scheduled_rows for outcome in r['results']) or (phase!='playoffs' and mode=='current' and bonus[mode] is None):continue
                            value=percentage(combined)
                            if value is None:continue
                        elif metric=='allplay':
                            if any(r['allplay'] is None for r in week_rows):continue
                            value=percentage(ap_record)
                        else:
                            if any(r[metric] is None for r in week_rows):continue
                            value=sum(tenths(r[metric]) for r in week_rows)/10
                        coverage[cover+':covered']+=1;key=f'{mode}:season-team:{phase}:{year}:{fid}:{metric}'
                        row=dict(key=f'{year}:{fid}',detail=key,year=year,franchise=franchise['name'],gm=franchise['gm'],score=value,games=len(weeks),partial=year==season,throughWeek=end)
                        if metric=='record':row.update(record=combined,h2h=h2h,bonus=bonus_record,adjustment=adjustment)
                        modes[mode]['teams'][phase][conf][metric].append(row)
                        details[key]=dict(kind='season-team',mode=mode,phase=phase,metric=metric,**{k:v for k,v in row.items() if k not in ['key','detail','record','h2h','bonus','adjustment']},weeks=week_rows,record=combined,h2h=h2h,bonus=bonus_record,adjustment=adjustment,bonusEvents=bonus_events,bonusAdjustment=any(adjustment.values()),url=f'https://api.myfantasyleague.com/{year}/standings?L={lid}')
                for pid,recorded in report.players.items():
                    if pid not in players:continue
                    player=players[pid];pos={'K':'PK','P':'PN'}.get(player.get('position'),player.get('position'))
                    if pos not in POSITIONS or mode=='current' and pos not in supported:continue
                    scores=[];missing=False
                    for w,native in recorded['weeks'].items():
                        if w>end or not (w<=12 if phase=='regular' else w>12 if phase=='playoffs' else True):continue
                        value=float(native) if mode=='native' or year==season else points.get((year,w,pid))
                        if value is None:missing=True;break
                        scores.append(dict(week=w,score=tenths(value)/10,url=f'https://api.myfantasyleague.com/{year}/top?L={lid}&SEARCHTYPE=ADVANCED&START_WEEK={w}&END_WEEK={w}&POSITION={pos}&COUNT=100&SORT=TOT'))
                    if missing or not scores:continue
                    value=sum(tenths(r['score']) for r in scores)/10;key=f'{mode}:season-player:{phase}:{year}:{pid}'
                    row=dict(key=f'{year}:{pid}',detail=key,year=year,name=player['name'],position=pos,nflTeam=player.get('team',''),score=value,games=len(scores),partial=year==season,throughWeek=end)
                    modes[mode]['positions'][phase][pos].append(row)
                    details[key]=dict(kind='season-player',mode=mode,phase=phase,**{k:v for k,v in row.items() if k not in ['key','detail']},weeks=scores,url=f'https://api.myfantasyleague.com/{year}/top?L={lid}&SEARCHTYPE=ADVANCED&START_WEEK={1 if phase!="playoffs" else 13}&END_WEEK={12 if phase=="regular" else end}&POSITION={pos}&COUNT=100&SORT=TOT')
        sources.append(dict(year=year,weekly=weekly_source,schedule=schedule_source,players=players_source,playerReport=dict(file=report_path.name,sha256=hashlib.sha256(report_path.read_bytes()).hexdigest())))
        compact(modes);keep=retained(modes);details={k:details[k] for k in keep}
        print(league,year,'seasonlong scores built',flush=True)
    meta=dict(league=league,firstSeason=min(r['season'] for r in careers),scoringYear=season,throughSeason=season,throughWeek=through,
              teamRankingLimit=10,individualRankingLimit=25,regularSeasonWeeks=12,scoringRulesSignature=signature,coverage=dict(coverage),sources=sources,officialBonusDifferences=adjustments,
              method='Regular season Weeks 1–12. Team playoffs include scheduled games by the actual playoff field, including placement games and Super Bowl; byes and consolation teams excluded. All-play compares with all 31 league opponents. Combined sums regular season and eligible playoffs. Bonus ranking uses league-wide all-play wins then points and potential points; awards use conference cutoffs through 2024 and league-wide cutoffs from 2025. Four quarters through 2020, plus regular season from 2021, identically for both leagues. Native records preserve audited published standings; any residual is a separately displayed MFL record adjustment, never an invented bonus rule. Current Scoring recalculates standard bonus games without that adjustment. Individual seasons sum all NFL games in the selected week range. Incomplete reconstructed totals are excluded. Current season is partial and explicitly labeled.',
              bonusRuleSources=[dict(url='https://www46.myfantasyleague.com/2021/options?L=60206&O=28&THREAD=39',finding='Fifth bonus proposed as an all-season bonus alongside the 18-week NFL schedule.'),dict(url='https://www46.myfantasyleague.com/2023/options?L=60206&O=28&THREAD=25',finding='Contemporaneous discussion describes five bonus games and a Wild Card doubleheader, not a sixth bonus.')])
    meta['canonicalInputs']={name:dict(file='data/'+name,sha256=hashlib.sha256((ROOT/'data'/name).read_bytes()).hexdigest()) for name in ['gm_career_seasons.json',f'current_gms_{season}.json']}
    payload=dict(meta=meta,modes=modes,details=details);dest=ROOT/'data/trophy_room';dest.mkdir(parents=True,exist_ok=True)
    if history:
        payload['meta']['overlay']=dict(file=Path(overlay).name,sha256=hashlib.sha256(Path(overlay).read_bytes()).hexdigest())
        (dest/'seasonlong_performances_history.json').write_text(json.dumps(payload,separators=(',',':'))+'\n',encoding='utf8')
    else:
        old=json.loads((dest/'seasonlong_performances_history.json').read_bytes());assert old['meta']['scoringRulesSignature']==signature
        payload['modes']=merge(old['modes'],modes);combined_details={**old['details'],**details};payload['details']={k:combined_details[k] for k in retained(payload['modes'])}
        payload['meta']['sources']=old['meta']['sources']+sources;payload['meta']['overlay']=old['meta']['overlay'];payload['meta']['officialBonusDifferences']=old['meta']['officialBonusDifferences']+adjustments
        payload['meta']['coverage']=dict(Counter(old['meta']['coverage'])+coverage)
        for directory in ['data/trophy_room','docs/trophy-room']:
            path=ROOT/directory/'seasonlong-performances.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,separators=(',',':'))+'\n',encoding='utf8')
    return payload

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--league',choices=['ADL','FAFL'],required=True);parser.add_argument('--cache',type=Path,required=True);parser.add_argument('--history',action='store_true');parser.add_argument('--overlay',type=Path)
    args=parser.parse_args();build(args.league,args.cache,args.history,args.overlay)
