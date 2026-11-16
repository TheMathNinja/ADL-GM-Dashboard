"""Build Trophy Room performance rankings from MFL and a labeled scoring overlay.

--history rebuilds completed seasons using cached MFL responses and the explicit
2026 reconstructed player-score CSV. The default refresh merges the frozen
historical top ranks with the current season's completed MFL weeks.
"""
import argparse
import csv
import hashlib
import json
import re
import time
import urllib.request
import urllib.error
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from performance_scoring import add_scoring_details
from import_trophy_results import arr, export
from import_trophy_rosters import PlayerReport

ROOT=Path(__file__).resolve().parents[1]
POSITIONS=['QB','RB','WR','TE','PK','PN','KR','DT','DE','LB','CB','S']
OFFENSE=set(POSITIONS[:7])
METRICS=['total','offense','defense','potential']
STAT_LABELS={'completions':'Completions','attempts':'Pass attempts','passing_yards':'Pass yards','passing_tds':'Pass TDs','passing_interceptions':'Interceptions thrown','sacks_suffered':'Sacks taken','carries':'Carries','rushing_yards':'Rush yards','rushing_tds':'Rush TDs','receptions':'Receptions','targets':'Targets','receiving_yards':'Rec yards','receiving_tds':'Rec TDs','def_tackles_solo':'Solo tackles','def_tackle_assists':'Assists','def_tackles_for_loss':'Tackles for loss','def_sacks':'Sacks','def_qb_hits':'QB hits','def_interceptions':'Interceptions','def_pass_defended':'Passes defended','def_fumbles_forced':'Forced fumbles','fumble_recovery_opp':'Fumbles recovered','def_tds':'Def TDs','fg_made':'FG made','fg_missed':'FG missed','pat_made':'XP made','pat_missed':'XP missed','pt_att':'Punts','pt_yards':'Punt yards','pt_inside_20':'Punts inside 20','pt_net_yards':'Net punt yards','kickoff_return_yards':'Kick return yards','punt_return_yards':'Punt return yards','penalties':'Penalties','penalty_yards':'Penalty yards'}


def tenths(n):
    return int((Decimal(str(n))*10).quantize(Decimal('1'),rounding=ROUND_HALF_UP))


def rank_ten(rows):
    unique={r['key']:r for r in rows}
    ordered=sorted(unique.values(),key=lambda r:(-r['score'],r['year'],r['week'],r['key']))
    out=[]
    for i,row in enumerate(ordered):
        rank=1+sum(r['score']>row['score'] for r in ordered)
        if rank>10:break
        out.append(dict(row,rank=rank,tied=sum(r['score']==row['score'] for r in ordered)>1))
    return out


def playoff_game(week,finish,field_per_conference,opponent):
    return week>12 and finish<=2*field_per_conference and opponent not in (None,'BYE')


def started_in_week(teams,franchises):
    result=defaultdict(set)
    for fid,team in teams.items():
        for player in arr(team.get('player')):
            if player.get('status')=='starter':result[player['id']].add(franchises[fid]['name'])
    return result


def current_playoff_field(bracket,season):
    assert bracket['season']==season and bracket['completedWeek']>=12,'Published regular-season qualification must be final before classifying playoff performances.'
    fields={conf:{t['name'] for game in bracket['games'] if game['week']==13 and game['category']=='championship' and game['conference']==conf for t in game['teams']} for conf in ['NFC','AFC']}
    assert len(fields['NFC'])==len(fields['AFC']) and len(fields['NFC']) in (6,7),'Missing frozen playoff field.'
    return fields['NFC']|fields['AFC']


def optimize(pool,rules):
    """Maximize legal historical positional/group counts, with no hindsight starts."""
    limits={}
    for p in arr(rules['position']):
        values=list(map(int,p['limit'].split('-')))
        limits[p['name']]=(values[0],values[-1])
    fixed_special=sum(low for pos,(low,high) in limits.items() if pos in {'PK','PN','KR'})
    totals={'off':int(rules.get('iop_starters',int(rules['count'])-int(rules['idp_starters'])-fixed_special)),'def':int(rules['idp_starters'])}
    totals['st']=int(rules['count'])-totals['off']-totals['def']
    group=lambda p:'st' if p in {'PK','PN','KR'} else 'off' if p in OFFENSE else 'def'
    selected=[]
    for g,count in totals.items():
        states={0:(0,[])}
        for pos,(minimum,maximum) in limits.items():
            if group(pos)!=g:continue
            players=sorted([p for p in pool if p['position']==pos],key=lambda p:(-p['score'],p['id']))
            # Empty eligible slots score zero only after real players are exhausted.
            choices=[]
            for k in range(minimum,maximum+1):
                chosen=players[:k]
                choices.append((k,sum(tenths(p['score']) for p in chosen),chosen))
            next_states={}
            for used,(score,chosen) in states.items():
                for k,points,rows in choices:
                    size=used+k
                    if size<=count and (size not in next_states or score+points>next_states[size][0]):
                        next_states[size]=(score+points,chosen+rows)
            states=next_states
        if count not in states:raise ValueError(('Impossible lineup rules',g,count))
        selected+=states[count][1]
    assert len({p['id'] for p in selected})==len(selected)
    return selected


def fetch_json(path,url):
    if path.exists():return json.loads(path.read_bytes())
    path.parent.mkdir(parents=True,exist_ok=True)
    for attempt in range(4):
        try:
            time.sleep(2)
            with urllib.request.urlopen(url,timeout=90) as r:raw=r.read()
            value=json.loads(raw)
            assert 'error' not in value,(url,value)
            path.write_bytes(raw)
            return value
        except urllib.error.HTTPError as e:
            if e.code!=429 or attempt==3:raise
            time.sleep(min(60,int(e.headers.get('Retry-After','30'))))


def scoring_signature(raw):
    expanded=[]
    for position in arr(raw['rules']['positionRules']):
        for pos in position['positions'].split('|'):
            for rule in arr(position['rule']):
                expanded.append((pos,tuple(sorted((key,value['$t']) for key,value in rule.items()))))
    return hashlib.sha256(json.dumps(sorted(expanded)).encode()).hexdigest()


def current_stat_lines(season,through,players,cache):
    files=[('nfl-stats-'+str(season)+'.csv',f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv'),
           ('nfl-mfl-player-ids.csv','https://github.com/DynastyProcess/data/raw/master/files/db_playerids.csv')]
    try:
        for name,url in files:
            path=cache/name
            if not path.exists():
                with urllib.request.urlopen(url,timeout=90) as response:path.write_bytes(response.read())
        ids={}
        for row in csv.DictReader((cache/'nfl-mfl-player-ids.csv').open(encoding='utf8')):
            if row['gsis_id'] and row['mfl_id'] in players:ids[row['gsis_id']]=row['mfl_id']
        out={}
        for row in csv.DictReader((cache/files[0][0]).open(encoding='utf8')):
            if row['season_type']!='REG' or int(row['week'])>through or row['player_id'] not in ids:continue
            values={label:float(row[field]) for field,label in STAT_LABELS.items() if row.get(field) not in (None,'','0','0.0') and float(row[field])!=0}
            out[f'{season}:{row["week"]}:{ids[row["player_id"]]}']=dict(team=row['team'],opponent=row['opponent_team'],**values)
        return out,[dict(url=url,sha256=hashlib.sha256((cache/name).read_bytes()).hexdigest()) for name,url in files]
    except (OSError,ValueError,KeyError) as error:
        print('Supplemental current-season stat lines unavailable:',type(error).__name__,flush=True)
        return {},[]


def blank():
    return dict(teams={phase:{conf:{metric:[] for metric in METRICS} for conf in ['NFC','AFC']} for phase in ['regular','playoffs']},positions={pos:[] for pos in POSITIONS})


def compact(mode):
    for phase in mode['teams'].values():
        for conf in phase.values():
            for metric,rows in conf.items():conf[metric]=rank_ten(rows)
    for pos,rows in mode['positions'].items():mode['positions'][pos]=rank_ten(rows)


def merge(old,new):
    for phase in new['teams']:
        for conf in new['teams'][phase]:
            for metric in METRICS:new['teams'][phase][conf][metric]=old['teams'][phase][conf][metric]+new['teams'][phase][conf][metric]
    for pos in POSITIONS:new['positions'][pos]=old['positions'][pos]+new['positions'][pos]
    compact(new)
    return new


def keys(modes):
    result=set()
    for mode in modes.values():
        for phase in mode['teams'].values():
            for conf in phase.values():
                for rows in conf.values():result.update(r['detail'] for r in rows)
        for rows in mode['positions'].values():result.update(r['detail'] for r in rows)
    return result


def build(league,cache,history=False,overlay=None,stats_path=None):
    careers=json.loads((ROOT/'data/gm_career_seasons.json').read_text())
    status=json.loads((ROOT/'docs/weekly-refresh-status.json').read_text())
    season=int(status['season']);through=int(status['week'])
    assert season==2026,'Refresh the scoring overlay and rules audit before advancing Current Scoring to a new year.'
    current=json.loads((ROOT/f'data/current_gms_{season}.json').read_text())['profiles']
    if league=='ADL':
        aliases={k.lower():v for k,v in json.loads((ROOT/'data/gm_name_aliases.json').read_text()).items()}
        def gm_name(value):return ' / '.join(dict.fromkeys(aliases.get(p.strip().lower(),p.strip()) for p in value.split(',') if p.strip()))
    else:
        from build_trophy_room import people
        def gm_name(value):return ' / '.join(people(value))
    current_points={}
    if history:
        assert overlay,'Historical Current Scoring requires an explicitly sourced overlay.'
        for r in csv.DictReader(Path(overlay).open()):
            if r['adl26_points'] not in ('','NA'):
                current_points[int(r['season']),int(r['week']),r['player_id']]=tenths(r['adl26_points'])/10
    raw_stats=json.loads(Path(stats_path).read_text()) if stats_path else {}
    current_config=fetch_json(cache/f'{league}-{season}-league.json',f'https://api.myfantasyleague.com/{season}/export?TYPE=league&L={60206 if league=="ADL" else 22686}&JSON=1')['league']
    current_positions={p['name'] for p in arr(current_config['starters']['position'])}
    scoring_rules=fetch_json(cache/f'{league}-{season}-rules.json',f'https://api.myfantasyleague.com/{season}/export?TYPE=rules&L={60206 if league=="ADL" else 22686}&JSON=1')
    rules_signature=scoring_signature(scoring_rules)
    modes={m:blank() for m in ['native','current']};details={};coverage=defaultdict(lambda:dict(eligible=0,covered=0));sources=[]
    years=sorted({r['season'] for r in careers}) if history else [season]
    for year in years:
        end=16 if year<2021 else 17
        if year==season:end=min(end,through)
        lid=60206 if league=='ADL' else {2014:37677,2015:27312}.get(year,22686)
        weekly,weekly_source=export(year,'allWeeklyResults',dict(L=lid,W='YTD',MISSING_AS_BYE=1),cache)
        # League-specific overrides (notably FAFL's historical KR role) matter.
        if not (cache/f'{year}-players-{lid}.json').exists():time.sleep(3)
        metadata,metadata_source=export(year,'players',dict(L=lid),cache)
        players={p['id']:p for p in arr(metadata['player'])}
        stat_sources=[]
        if year==season:
            season_stats,stat_sources=current_stat_lines(season,end,players,cache);raw_stats.update(season_stats)
        config=fetch_json(cache/f'{league}-{year}-league.json',f'https://api.myfantasyleague.com/{year}/export?TYPE=league&L={lid}&JSON=1')['league']
        if year==season:
            franchises={str(p['franchise_id']).zfill(4):dict(name=name,gm=gm_name(p['gm']),finish=33) for name,p in current.items()}
            assert len(franchises)==32
            playoff_count=0
            if end>12:
                field=current_playoff_field(json.loads((ROOT/'docs/playoff-picture/bracket-data.json').read_text()),season)
                playoff_count=len(field)//2
                for team in franchises.values():team['finish']=1 if team['name'] in field else 33
        else:
            franchises={r['franchise_id']:dict(r,gm=gm_name(r['gm'])) for r in careers if r['season']==year}
            brackets=fetch_json(cache/f'{league}-{year}-playoffBrackets.json',f'https://api.myfantasyleague.com/{year}/export?TYPE=playoffBrackets&L={lid}&JSON=1')['playoffBrackets']
            counts={int(b['teamsInvolved']) for b in arr(brackets.get('playoffBracket')) if b['name'] in ['NFC Playoffs','AFC Playoffs']}
            assert len(counts)==1,(year,'Unknown playoff field',counts)
            playoff_count=counts.pop()
            assert all(sum(r['finish']<=2*playoff_count for fid,r in franchises.items() if (int(fid)<=16)==(conf=='NFC'))==playoff_count for conf in ['NFC','AFC'])
        report_path=cache/f'{league}-{year}-player-report.html'
        report_url=f'https://api.myfantasyleague.com/{year}/top?L={lid}&SEARCHTYPE=ADVANCED&COUNT=9999&START_WEEK=1&END_WEEK={end}'
        if not report_path.exists():
            time.sleep(2)
            with urllib.request.urlopen(report_url,timeout=90) as response:report_path.write_bytes(response.read())
        report=PlayerReport(end);report.feed(report_path.read_bytes().decode('utf8','replace'))
        assert len(report.players)>500
        source_report=dict(url=report_url,sha256=hashlib.sha256(report_path.read_bytes()).hexdigest())
        sources.append(dict(year=year,weekly=weekly_source,players=metadata_source,playerReport=source_report,supplementalStats=stat_sources))
        started=defaultdict(set)
        for w in arr(weekly['weeklyResults']):
            week=int(w['week'])
            if week>end:continue
            fs=arr(w.get('franchise'))+[f for m in arr(w.get('matchup')) for f in arr(m['franchise'])]
            fs={f['id']:f for f in fs if f['id']!='BYE'}
            assert len(fs)==32,(year,week,'Missing team')
            opponents={}
            for match in arr(w.get('matchup')):
                pair=arr(match['franchise'])
                for f in pair:opponents[f['id']]=next((x['id'] for x in pair if x['id']!=f['id']),'BYE')
            for pid,names in started_in_week(fs,franchises).items():started[week,pid].update(names)
            for fid,f in fs.items():
                franchise=franchises[fid];conf='NFC' if int(fid)<=16 else 'AFC'
                phase='regular' if week<=12 else 'playoffs'
                if phase=='playoffs' and not playoff_game(week,franchise['finish'],playoff_count,opponents.get(fid)):continue
                native=[];rescored=[];actual=[];optimal=[];complete=True
                for p in arr(f.get('player')):
                    pid=p['id']
                    if pid not in players:
                        assert not float(p.get('score') or 0) and p.get('status')!='starter' and str(p.get('shouldStart'))!='1',(year,week,pid,'Unknown scored player')
                        continue
                    meta=players[pid];pos={'K':'PK','P':'PN'}.get(meta.get('position'),meta.get('position'))
                    if pos not in POSITIONS:
                        assert p.get('status')!='starter' or not float(p.get('score') or 0),(year,week,pid,pos,'Unsupported scored starting position')
                        continue
                    score=float(p.get('score') or 0)
                    game_team=raw_stats.get(f'{year}:{week}:{pid}',{}).get('team') or meta.get('team','')
                    row=dict(id=pid,name=meta['name'],position=pos,nflTeam=game_team,score=score)
                    native.append(row)
                    played=report.players.get(pid,{}).get('weeks',{})
                    cur=score if year==season else current_points.get((year,week,pid),0 if week not in played else None)
                    if pos not in current_positions:cur=None
                    rescored.append(dict(row,score=cur))
                    if p.get('status')=='starter':
                        actual.append(pid)
                    if str(p.get('shouldStart'))=='1':optimal.append(pid)
                for mode,pool in [('native',native),('current',rescored)]:
                    starters=[p for p in pool if p['id'] in actual]
                    for metric in METRICS:
                        cover=coverage[f'{mode}:{phase}:{conf}:{metric}'];cover['eligible']+=1
                        if metric=='potential':
                            if any(p['score'] is None for p in pool):continue
                            chosen=[p for p in pool if p['id'] in optimal] if mode=='native' or year==season else optimize(pool,config['starters'])
                            score=float(f['opt_pts']) if mode=='native' or year==season else sum(p['score'] for p in chosen)
                        else:
                            chosen=[p for p in starters if metric=='total' or ((p['position'] in OFFENSE)==(metric=='offense'))]
                            if any(p['score'] is None for p in chosen):continue
                            score=float(f['score']) if metric=='total' and (mode=='native' or year==season) else sum(p['score'] for p in chosen)
                        score=tenths(score)/10;cover['covered']+=1
                        key=f'{mode}:team:{year}:{week}:{fid}:{metric}'
                        modes[mode]['teams'][phase][conf][metric].append(dict(key=f'{year}:{week}:{fid}',detail=key,year=year,week=week,franchise=franchise['name'],gm=franchise['gm'],score=score))
                        details[key]=dict(kind='team',mode=mode,year=year,week=week,franchise=franchise['name'],gm=franchise['gm'],conference=conf,phase=phase,metric=metric,score=score,players=chosen,url=f'https://api.myfantasyleague.com/{year}/weekly?L={lid}&W={week}',opponent=franchises.get(opponents.get(fid),{}).get('name'),playerSum=tenths(sum(p['score'] for p in chosen))/10)
        for pid,record in report.players.items():
            if pid not in players:continue
            meta=players[pid];pos={'K':'PK','P':'PN'}.get(meta.get('position'),meta.get('position'))
            if pos not in POSITIONS:continue
            for week,score in record['weeks'].items():
                for mode in ['native','current']:
                    cover=coverage[f'{mode}:player:{pos}'];cover['eligible']+=1
                    value=float(score) if mode=='native' or year==season else current_points.get((year,week,pid))
                    if mode=='current' and pos not in current_positions:value=None
                    if value is None:continue
                    cover['covered']+=1;value=tenths(value)/10
                    key=f'{mode}:player:{year}:{week}:{pid}'
                    modes[mode]['positions'][pos].append(dict(key=f'{year}:{week}:{pid}',detail=key,year=year,week=week,name=meta['name'],position=pos,score=value))
                    details[key]=dict(kind='player',mode=mode,year=year,week=week,name=meta['name'],position=pos,score=value,startedBy=sorted(started[week,pid]),nativeScore=float(score),url=f'https://api.myfantasyleague.com/{year}/top?L={lid}&SEARCHTYPE=ADVANCED&START_WEEK={week}&END_WEEK={week}&POSITION={pos}&COUNT=100&SORT=TOT',stats=raw_stats.get(f'{year}:{week}:{pid}',{}))
        for mode in modes.values():compact(mode)
        keep=keys(modes);details={key:details[key] for key in keep}
        print(f'{league} {year}: rankings built through Week {end}',flush=True)
    for mode in modes.values():compact(mode)
    keep=keys(modes);details={key:details[key] for key in keep}
    meta=dict(league=league,scoringYear=season,firstSeason=min(r['season'] for r in careers),throughSeason=season,throughWeek=through,regularSeasonWeeks=12,
              scoringRulesSignature=rules_signature,
              playoffDefinition='Scheduled games by the playoff field, including placement games; byes and consolation teams excluded.',
              currentDefinition='2026 rules applied to reconstructed historical NFL statistics, using original starters and positional eligibility. Potential Points reselects the highest-scoring legal lineup. The current season uses recorded MFL scores. Historical positions absent from 2026 rules, including KR, are unsupported and omitted.',
              coverage=dict(coverage),sources=sources)
    payload=dict(meta=meta,modes=modes,details=details)
    dest=ROOT/'data/trophy_room';dest.mkdir(parents=True,exist_ok=True)
    if history:
        meta['overlay']=dict(file=Path(overlay).name,sha256=hashlib.sha256(Path(overlay).read_bytes()).hexdigest(),label='Existing ADL26 historical reconstructed scoring overlay; estimates, not original MFL results')
        if stats_path:meta['statLines']=dict(file=Path(stats_path).name,sha256=hashlib.sha256(Path(stats_path).read_bytes()).hexdigest(),source='Cached nflverse player-week statistics joined using the audited season-specific GSIS/MFL ID maps; 2022 BUF/CIN replacement statistics use Week 18.')
        add_scoring_details(payload,cache,league,ROOT)
        (dest/'top_performances_history.json').write_text(json.dumps(payload,separators=(',',':'))+'\n')
    else:
        old=json.loads((dest/'top_performances_history.json').read_text())
        assert old['meta']['scoringYear']==season
        assert old['meta']['scoringRulesSignature']==rules_signature,'Current rules changed: rebuild the reconstructed historical overlay and performance history.'
        payload['modes']={m:merge(old['modes'][m],modes[m]) for m in modes}
        all_details={**old['details'],**details};payload['details']={k:all_details[k] for k in keys(payload['modes'])}
        payload['meta']['sources']=old['meta']['sources']+sources
        payload['meta']['overlay']=old['meta']['overlay']
        if 'statLines' in old['meta']:payload['meta']['statLines']=old['meta']['statLines']
        for key,row in old['meta']['coverage'].items():
            target=payload['meta']['coverage'].setdefault(key,dict(eligible=0,covered=0))
            for field in ['eligible','covered']:target[field]+=row[field]
        add_scoring_details(payload,cache,league,ROOT)
        for directory in ['data/trophy_room','docs/trophy-room']:
            path=ROOT/directory/'top-performances.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,separators=(',',':'))+'\n')
    return payload


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--league',choices=['ADL','FAFL'],required=True)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--history',action='store_true')
    parser.add_argument('--overlay',type=Path)
    parser.add_argument('--stats',type=Path)
    args=parser.parse_args();build(args.league,args.cache,args.history,args.overlay,args.stats)
