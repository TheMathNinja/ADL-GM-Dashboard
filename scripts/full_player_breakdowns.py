"""Complete player-game scoring/ownership banks shared by weekly and season views."""
import argparse,collections,copy,hashlib,json,re,urllib.request
from pathlib import Path
from performance_scoring import array,scalar,scoring_details,order_scoring_rows,POSITION_ORDER
from import_trophy_rosters import PlayerReport

def _numbers(value):
    values=value if isinstance(value,list) else str(value).split(',')
    return [float(v) for v in values if str(v).strip()]
def _number(value):
    number=float(value);return str(int(number)) if number.is_integer() else str(number)
def event_values(text,pid):
    line=next((line for line in text.splitlines() if line.split('|')[0]==pid),None)
    if line is None:return None
    return {m.group(1):m.group(2) for part in line.split('|')[1:] if (m:=re.match(r'^(\S+)\s+(.+)$',part.strip()))}
def relevant_codes(position):
    selected=POSITION_ORDER.get('QB' if position=='QB' else 'skill' if position in ['RB','WR','TE'] else 'defense' if position in ['DT','DE','LB','CB','S'] else '',[])
    return set(selected)|{'F','FY'}
def complete_scoring(values,rules,pid,position,labels,order):
    values=copy.deepcopy(values);codes={str(scalar(rule['event'])) for group in array(rules['positionRules']) if position in group['positions'].split('|') for rule in array(group.get('rule'))}
    for code in relevant_codes(position)&codes:
        if code not in values:values[code]=0
    # A zero-length field goal is not an attempted field goal.
    if values.get('FG') in [0,0.0,'0',[],None]:values.pop('FG',None)
    fields=[]
    for code,value in values.items():
        if code not in codes:continue
        try:numbers=_numbers(value)
        except (TypeError,ValueError):continue
        if numbers:fields.append(code+' '+','.join(_number(v) for v in numbers))
    return scoring_details(pid+'|'+'|'.join(fields),rules,pid,position,labels,order)
def empty_scoring(rules,position,labels,order):
    codes={str(scalar(rule['event'])) for group in array(rules['positionRules']) if position in group['positions'].split('|') for rule in array(group.get('rule'))}
    selected=(relevant_codes(position)&codes) or codes
    rows=[dict(eventCode=code,category=code,value=0,label=labels.get(code,code),event='0 '+labels.get(code,code),points=0) for code in selected if code!='FG']
    return dict(position=position,rows=order_scoring_rows(rows,position,order),total=0,noScoringEvents=True)
def franchise_names(root,league,year):
    history=json.loads((root/'data/gm_career_seasons.json').read_bytes());names={r['franchise_id']:r['name'] for r in history if r['season']==year}
    if not names:
        current=json.loads((root/f'data/current_gms_{year}.json').read_bytes());names={str(r['franchise_id']).zfill(4):name for name,r in current['profiles'].items()}
    assert len(names)==32;return names

def weekly_frames(cache,league,year):
    lid=60206 if league=='ADL' else {2014:37677,2015:27312}.get(year,22686)
    raw=json.loads((cache/f'{year}-allWeeklyResults-{lid}.json').read_bytes())['allWeeklyResults'];frames={}
    for week in array(raw['weeklyResults']):
        owners=collections.defaultdict(dict)
        for team in array(week.get('franchise'))+[t for match in array(week.get('matchup')) for t in array(match.get('franchise'))]:
            fid=team['id']
            if fid=='BYE':continue
            for p in array(team.get('player')):owners[p['id']][fid]=owners[p['id']].get(fid,False) or p.get('status')=='starter'
        frames[int(week['week'])]=owners
    return frames

def owners_for_game(active,fallback,names):
    active={str(fid).zfill(4):bool(started) for fid,started in active.items()};result=[]
    for nfc in [True,False]:
        in_conference=lambda fid:(int(fid)<=16)==nfc
        present={fid:started for fid,started in active.items() if in_conference(fid)}
        if not present:present={str(fid).zfill(4):False for fid in array(fallback) if in_conference(str(fid).zfill(4))}
        for fid,started in sorted(present.items()):result.append(dict(franchiseId=fid,franchise=names[fid],conference='NFC' if nfc else 'AFC',started=started))
    return result

def build(root,league,cache,nfl_dir,ownership_file):
    root=Path(root);cache=Path(cache);wanted={};expected={};weekly_files=[root/'data/trophy_room/top_performances_history.json',root/'docs/trophy-room/top-performances.json']
    for path in weekly_files+[root/'docs/trophy-room/seasonlong-performances.json']:
        payload=json.loads(path.read_bytes())
        for key,d in payload['details'].items():
            if d['kind'] not in ['player','season-player']:continue
            pid=key.rsplit(':',1)[1]
            games=[dict(week=d['week'],score=d['score'])] if d['kind']=='player' else [w for w in d['weeks'] if w['score'] is not None]
            for w in games:
                k=f"{d['year']}:{w['week']}:{pid}";wanted[k]=dict(year=d['year'],week=w['week'],id=pid,position=d['position'])
                if (d['mode'],k) in expected:assert abs(expected[d['mode'],k]-w['score'])<.05
                expected[d['mode'],k]=w['score']
    labels=json.loads((root/'data/trophy_room/mfl-stat-labels.json').read_bytes());order=json.loads((root/'data/trophy_room/mfl-scoring-order.json').read_bytes())['order'];ownership_data=json.loads(Path(ownership_file).read_bytes());ownership=ownership_data['ownership'][league]
    nfl={}
    for path in Path(nfl_dir).glob('20*.json'):nfl.update(json.loads(path.read_bytes()))
    counts=collections.Counter();all_games={};rule_cache={};event_cache={};source_rows=[]
    for year in sorted({d['year'] for d in wanted.values()}):
        names=franchise_names(root,league,year);frames=weekly_frames(cache,league,year);games={}
        end=16 if year<2021 else 17
        report_path=cache/f'{league}-{year}-player-report.html';report=PlayerReport(min(int(json.loads((root/'docs/weekly-refresh-status.json').read_bytes())['week']),end) if year==2026 else end);report.feed(report_path.read_text(encoding='utf8'))
        for k,d in sorted(wanted.items()):
            if d['year']!=year:continue
            week,pid,pos=d['week'],d['id'],d['position'];stats=nfl.get(k);native_expected=expected.get(('native',k));native_expected=float(report.players.get(pid,{}).get('weeks',{}).get(week,native_expected or 0))
            source_week=18 if year==2022 and week==17 and stats and stats.get('team') in ['BUF','CIN'] else week
            event_path=cache/f'mfl-events-{year}-{source_week:02}.txt'
            if event_path not in event_cache:event_cache[event_path]=event_path.read_text(encoding='utf8') if event_path.exists() else ''
            values=event_values(event_cache[event_path],pid);captured=values is not None
            rule_path=cache/f'{league}-{year}-rules.json'
            if rule_path not in rule_cache:rule_cache[rule_path]=json.loads(rule_path.read_bytes())['rules']
            rules=rule_cache[rule_path]
            if values is None:
                values=stats.get('events') if stats else None
                if values is None:
                    assert abs(native_expected)<.05,(league,k,'No stat line for nonzero recorded game')
                    native=empty_scoring(rules,pos,labels,order)
                else:native=complete_scoring(values,rules,pid,pos,labels,order)
            else:native=complete_scoring(values,rules,pid,pos,labels,order)
            if captured and stats and abs(native['total']-native_expected)>.05:
                corrected=complete_scoring(stats['events'],rules,pid,pos,labels,order)
                if abs(corrected['total']-native_expected)<.05:
                    native=corrected;captured=False
            native.update(source='MFL recorded scoring events' if captured else 'NFL-stat reconstruction under the original season rules',reconstructed=not captured,scoringYear=year,recordedTotal=native_expected)
            owners=owners_for_game(frames.get(week,{}).get(pid,{}),ownership.get(k,[]),names)
            game=dict(id=pid,year=year,week=week,position=pos,team=stats.get('team') if stats else values.get('Team','') if values else '',owners=owners,native=native)
            if year<2026 and stats:
                current=copy.deepcopy(stats['current']);current['position']=pos;current['rows']=order_scoring_rows(current['rows'],pos,order);game['current']=current
            elif year==2026:
                current=copy.deepcopy(native);current['reconstructed']=False;current['source']='MFL recorded 2026 scoring events';game['current']=current
            elif expected.get(('current',k))==0:game['current']=empty_scoring(json.loads((cache/f'{league}-2026-rules.json').read_bytes())['rules'],pos,labels,order);game['current'].update(reconstructed=True,source='No scoring events recorded for this zero-point game')
            if ('current',k) in expected:
                assert 'current' in game,(league,k,'Current breakdown missing')
                assert abs(game['current']['total']-expected['current',k])<.05,(league,k,game['current']['total'],expected['current',k])
            if ('native',k) in expected:assert abs(native_expected-expected['native',k])<.05,(league,k,'Native player report differs')
            for mode in ['native','current']:
                if mode not in game:continue
                sc=game[mode];assert abs(sum(r['points'] for r in sc['rows'])-sc['total'])<.0001
                counts[mode+':captured' if not sc.get('reconstructed') else mode+':reconstructed']+=1
            if abs(native['total']-native_expected)>.05:counts['native:unreconciled']+=1
            if not owners:counts['unrostered']+=1
            games[f'{week}:{pid}']=game;all_games[k]=game
        payload=dict(meta=dict(league=league,year=year,scoringYear=2026,ownershipSource=ownership_data['sources'][league].get(str(year)),nflSource=json.loads((Path(nfl_dir)/'provenance.json').read_bytes()).get(str(year)),method='Original MFL events and rules for Native; cached nflfastR statistics and the audited ADL26 engine for historical Current Scoring. Missing archived MFL events are reconstructed under original rules and explicitly labeled. Recorded totals are retained independently. Ownership uses actual starters and weekly roster snapshots, NFC first. Zero-value relevant scoring categories remain visible.'),games=games)
        for folder in ['data/trophy_room/player_game_breakdowns','docs/trophy-room/player-game-breakdowns']:
            path=root/folder/f'{year}.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,separators=(',',':'))+'\n',encoding='utf8')
        print(league,year,len(games),'complete game breakdowns',flush=True)
    for path in weekly_files:
        payload=json.loads(path.read_bytes())
        for key,d in payload['details'].items():
            if d['kind']!='player':continue
            game=all_games[f"{d['year']}:{d['week']}:{key.rsplit(':',1)[1]}"];d['scoring']=game[d['mode']];d['ownership']=game['owners']
        payload['meta']['fullPlayerBreakdowns']=dict(method='Complete stat lines and point contributions, using CHI Team Tools display order. Ownership labels distinguish starters and nonstarters in NFC/AFC order.',referenceOnly=0)
        path.write_text(json.dumps(payload,separators=(',',':'))+'\n',encoding='utf8')
        if path.name=='top-performances.json':(root/'data/trophy_room/top-performances.json').write_bytes(path.read_bytes())
    print(league,'breakdown audit',dict(counts),flush=True)
    (root/'data/trophy_room/player_breakdown_audit.json').write_text(json.dumps(dict(counts),indent=2)+'\n',encoding='utf8')
    return all_games

def enrich_payload(payload,cache,league,root):
    """Reuse audited history; refresh complete present-season MFL events and ownership."""
    root=Path(root);cache=Path(cache);year=int(payload['meta']['scoringYear']);banks={}
    for path in (root/'data/trophy_room/player_game_breakdowns').glob('*.json'):banks[int(path.stem)]=json.loads(path.read_bytes())
    labels=json.loads((root/'data/trophy_room/mfl-stat-labels.json').read_bytes());order=json.loads((root/'data/trophy_room/mfl-scoring-order.json').read_bytes())['order']
    frames=None;names=None
    for key,d in payload['details'].items():
        if d['kind']!='player':continue
        y,w,pid=d['year'],d['week'],key.rsplit(':',1)[1];game=banks.get(y,{}).get('games',{}).get(f'{w}:{pid}')
        if y==year:
            if frames is None:frames=weekly_frames(cache,league,year);names=franchise_names(root,league,year)
            lid=60206 if league=='ADL' else 22686
            rp=cache/f'{league}-{year}-week-{w}-rosters.json'
            if not rp.exists():
                with urllib.request.urlopen(f'https://api.myfantasyleague.com/{year}/export?TYPE=rosters&L={lid}&W={w}&JSON=1',timeout=35) as response:rp.write_bytes(response.read())
            fallback=[f['id'] for f in array(json.loads(rp.read_bytes())['rosters']['franchise']) if any(p['id']==pid for p in array(f.get('player'))) ]
            vals=event_values((cache/f'mfl-events-{year}-{w:02}.txt').read_text(),pid)
            if vals is None:raise ValueError(f'No complete current MFL stat line: {key}')
            rules=json.loads((cache/f'{league}-{year}-rules.json').read_bytes())['rules']
            scoring=complete_scoring(vals,rules,pid,d['position'],labels,order);scoring.update(source='MFL recorded scoring events',reconstructed=False,recordedTotal=d['score'])
            game=dict(id=pid,year=y,week=w,position=d['position'],owners=owners_for_game(frames.get(w,{}).get(pid,{}),fallback,names),native=scoring,current=scoring)
            banks.setdefault(year,dict(meta=dict(league=league,year=year,scoringYear=year,method='Recorded MFL scoring events and weekly roster ownership'),games={}))['games'][f'{w}:{pid}']=game
        if game and d['mode'] in game:d['scoring']=copy.deepcopy(game[d['mode']]);d['ownership']=game['owners']
    if year in banks:
        for folder in ['data/trophy_room/player_game_breakdowns','docs/trophy-room/player-game-breakdowns']:
            p=root/folder/f'{year}.json';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(banks[year],separators=(',',':'))+'\n',encoding='utf8')
    return payload

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--league',choices=['ADL','FAFL'],required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--nfl-bank',type=Path,required=True);p.add_argument('--ownership',type=Path,required=True);a=p.parse_args();build(Path(__file__).resolve().parents[1],a.league,a.cache,a.nfl_bank,a.ownership)
