"""Point-by-point MFL event scoring, using CHI Team Tools' scoring algorithm."""
import concurrent.futures,hashlib,json,math,re,urllib.request
from decimal import Decimal,ROUND_FLOOR,ROUND_DOWN
from pathlib import Path

def array(value):return value if isinstance(value,list) else [value] if value is not None else []
def scalar(value):return value.get('$t') if isinstance(value,dict) else value
def rounded(value):return float((value*10+Decimal('0.500000001')).to_integral_value(rounding=ROUND_FLOOR)/10)

def scoring_details(text,rules,pid,position,labels,order):
    line=next((l for l in text.splitlines() if l.split('|')[0]==str(pid)),None)
    if line is None:raise ValueError('Player event line unavailable')
    values={}
    for field in line.split('|')[1:]:
        match=re.match(r'^(\S+)\s+(.+)$',field.strip())
        if match:values[match[1]]=match[2]
    rows=[]
    for group in array(rules['positionRules']):
        if position not in group['positions'].split('|'):continue
        for rule in array(group.get('rule')):
            code=str(scalar(rule['event']));raw=values.get(code)
            if raw is None:continue
            match=re.fullmatch(r'(-?\d+(?:\.\d+)?)-(-?\d+(?:\.\d+)?)',str(scalar(rule['range'])))
            if not match:raise ValueError('Unsupported event range')
            lower,upper=map(Decimal,match.groups())
            for val in raw.split(','):
                value=Decimal(val)
                if not lower<=value<=upper:continue
                form=str(scalar(rule['points']));bonus=str(scalar(rule.get('thresholdPoints')) or '')
                if form.startswith('*'):points=value*Decimal(form[1:])
                elif '/' in form:
                    ppu,unit=form.split('/');unit=unit or '1'
                    base=(value-lower if bonus else value)/Decimal(unit)
                    if '.' not in unit:base=base.to_integral_value(rounding=ROUND_DOWN)
                    points=base*Decimal(ppu or '1')+Decimal(bonus or '0')
                else:points=Decimal(form)
                if code not in labels:raise ValueError('Unknown event label: '+code)
                rows.append(dict(eventCode=code,event=val+' '+labels[code],points=rounded(points)))
    if not rows:raise ValueError('No scoring events supplied')
    preferred={'QB':['PC','PA','PY','#P','P2','IN','TSK','TSY','RA','RY','#R','R2','FD','FUO','FL','FUS','OFC','OFCY','#FR','FR'],
               'skill':['RA','RY','#R','R2','CC','TGT','CY','#C','C2','FD','FUO','FL','FUS','FUD','OFC','OFCY','#FR','FR','FC','FCY','#D','#DR','TK','AS','TKL'],
               'defense':['TK','AS','TKL','QH','SK','SKY','PD','FF','FC','FCY','#D','#DR','IC','ICY','#IR','F','FY']}
    selected=preferred.get('QB' if position=='QB' else 'skill' if position in ['RB','WR','TE'] else 'defense' if position in ['DT','DE','LB','CB','S'] else '',[])
    ranks={code:i for i,code in enumerate(selected)};general={code:i for i,code in enumerate(order)}
    rows.sort(key=lambda row:ranks.get(row['eventCode'],1000+general.get(row['eventCode'],1000)))
    return dict(position=position,rows=rows,total=round(sum(row['points'] for row in rows),1))

def add_scoring_details(payload,cache,league,root):
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    labels=json.loads((Path(root)/'data/trophy_room/mfl-stat-labels.json').read_bytes())
    order=json.loads((Path(root)/'data/trophy_room/mfl-scoring-order.json').read_bytes())['order']
    details={k:d for k,d in payload['details'].items() if d['kind']=='player'}
    bank_path=Path(root)/'data/trophy_room/top_performances_reconstructed_breakdowns.json'
    reconstructed=json.loads(bank_path.read_bytes()) if bank_path.exists() else {}
    needed={}
    for d in details.values():
        if d.get('scoring') and d['year']<payload['meta']['scoringYear']:continue
        year,week=d['year'],d['week']
        needed[f'mfl-events-{year}-{week:02}.txt']=f'https://api.myfantasyleague.com/fflnetdynamic{year}/live_stats_idp_{week:02}.txt'
        rule_year=payload['meta']['scoringYear'] if d['mode']=='current' else year
        lid=60206 if league=='ADL' else 37677 if rule_year==2014 else 27312 if rule_year==2015 else 22686
        needed[f'{league}-{rule_year}-rules.json']=f'https://api.myfantasyleague.com/{rule_year}/export?TYPE=rules&L={lid}&JSON=1'
    sources={};failures={}
    def fetch(item):
        name,url=item;path=cache/name
        if path.exists():body=path.read_bytes()
        else:
            with urllib.request.urlopen(url,timeout=35) as response:body=response.read()
            path.write_bytes(body)
        if name.endswith('.json'):
            value=json.loads(body)['rules']
        else:
            value=body.decode('utf8')
            if '<html' in value.lower():raise ValueError('HTML instead of scoring events')
        return name,value,dict(url=url,sha256=hashlib.sha256(body).hexdigest())
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        jobs={pool.submit(fetch,item):item[0] for item in needed.items()}
        for job in concurrent.futures.as_completed(jobs):
            name=jobs[job]
            try:name,value,source=job.result();sources[name]=(value,source)
            except Exception as error:failures[name]=type(error).__name__
    counts=dict(eventBreakdowns=0,referenceOnly=0,differentTotals=0)
    for key,d in details.items():
        if d.get('scoring') and d['year']<payload['meta']['scoringYear']:
            existing=d['scoring'];counts['referenceOnly' if existing.get('referenceOnly') else 'eventBreakdowns']+=1
            if abs(existing['total']-d['score'])>.05:counts['differentTotals']+=1
            continue
        reconstructed_key=':'.join(key.split(':')[2:])
        if d['mode']=='current' and d['year']<payload['meta']['scoringYear'] and reconstructed_key in reconstructed:
            result=reconstructed[reconstructed_key]
            if abs(result['total']-d['score'])>.05:raise ValueError('Reconstructed contribution total differs from ranking estimate: '+key)
            # Reuse CHI's event ordering even though contributions came from the overlay engine.
            preferred=['PC','PA','PY','#P','P2','IN','TSK','TSY','RA','RY','#R','R2','CC','TGT','CY','#C','C2','FD','FUO','OFC','OFCY'] if d['position']=='QB' else ['RA','RY','#R','R2','CC','TGT','CY','#C','C2','FD','FUO','OFC','OFCY'] if d['position'] in ['RB','WR','TE'] else ['TK','AS','TKL','QH','SK','SKY','PD','FF','FC','FCY','#D','#DR','IC','ICY','#IR','F','FY']
            rank={code:i for i,code in enumerate(preferred)};general={code:i for i,code in enumerate(order)}
            result['rows'].sort(key=lambda row:rank.get(row['eventCode'],1000+general.get(row['eventCode'],1000)))
            d['scoring']=result;counts['eventBreakdowns']+=1
            continue
        rule_year=payload['meta']['scoringYear'] if d['mode']=='current' else d['year']
        rawname=f"mfl-events-{d['year']}-{d['week']:02}.txt";rulename=f'{league}-{rule_year}-rules.json'
        try:
            raw,raw_source=sources[rawname];rules,rule_source=sources[rulename]
            result=scoring_details(raw,rules,key.rsplit(':',1)[1],d['position'],labels,order)
            result.update(source='MFL captured scoring events and season-specific rules',eventsSource=raw_source,rulesSource=rule_source,scoringYear=rule_year)
            counts['eventBreakdowns']+=1
            if abs(result['total']-d['score'])>.05:counts['differentTotals']+=1
        except (KeyError,ValueError,ArithmeticError):
            result=dict(position=d['position'],rows=[dict(eventCode='MFL_TOTAL',event='Published MFL total (event details not supplied)' if d['mode']=='native' else 'Reconstructed estimate (event details unavailable)',points=d['score'])],total=d['score'],referenceOnly=True)
            counts['referenceOnly']+=1
        d['scoring']=result
    payload['meta']['scoringBreakdowns']=dict(**counts,method='Same event rules, per-event rounding and display order as CHI Team Tools; captured MFL events are distinct from the NFL-stat reconstructed ranking estimates.',sourceFailures=failures)
    print(league,'scoring breakdowns',counts,flush=True)
    return payload
