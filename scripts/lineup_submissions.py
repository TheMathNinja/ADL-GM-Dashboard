"""Authoritative MFL lineup submission times, independent of score refresh times."""
import datetime as dt
from html import unescape
from pathlib import Path
import argparse,json,re,time,urllib.request
from urllib.parse import parse_qs,urlparse
from zoneinfo import ZoneInfo
from types import SimpleNamespace
ET=ZoneInfo('America/New_York')
HOSTS={'ADL':'www46.myfantasyleague.com','FAFL':'www43.myfantasyleague.com'}
IDS={'ADL':'60206','FAFL':'22686'}

def parse_submissions(html,season,week):
    result={}
    pattern=r'<b>\s*Lineup submitted at\s*</b>\s*(.*?)\s*-\s*<a\b([^>]+)>'
    for stamp,attrs in re.findall(pattern,html,re.I|re.S):
        href=re.search(r'href\s*=\s*[\"\x27]([^\"\x27]+)',attrs,re.I)
        if not href:continue
        query=parse_qs(urlparse(unescape(href.group(1))).query)
        if query.get('W')!=[str(week)]:continue
        fid=query.get('FRANCHISE',[''])[0]
        if not re.fullmatch(r'\d{4}',fid):continue
        text=unescape(re.sub('<[^>]+>',' ',stamp));text=re.sub(r'\s+',' ',text).strip()
        text=re.sub(r'a\.m\.', 'AM',text,flags=re.I);text=re.sub(r'p\.m\.', 'PM',text,flags=re.I)
        match=re.fullmatch(r'([A-Za-z]{3} [A-Za-z]{3} \d{1,2} \d{1,2}:\d{2}(?::\d{2})? [AP]M) (?:ET|EST|EDT) (\d{4})',text)
        if not match or int(match[2])!=int(season):continue
        fmt='%a %b %d %I:%M:%S %p %Y' if match[1].count(':')==2 else '%a %b %d %I:%M %p %Y'
        moment=dt.datetime.strptime(match[1]+' '+match[2],fmt).replace(tzinfo=ET)
        result[fid]=moment.isoformat()
    return result

def get_submissions(collector,week):
    key=('lineup-submissions',int(week));now=time.time()
    if key in collector.cache and now-collector.cache[key][0]<60:return collector.cache[key][1]
    url=f'https://{HOSTS[collector.league]}/{collector.season}/options?L={IDS[collector.league]}&O=06&W={week}'
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'GM-Dashboard-Lineup-Submission-Times/1.0'})
        with urllib.request.urlopen(req,timeout=25) as response:html=response.read().decode('utf8')
        rows=parse_submissions(html,collector.season,week)
        if not rows:raise ValueError('No lineup submission timestamps in MFL report')
        collector.cache[key]=(now,rows)
        return rows
    except Exception as error:
        print('Lineup submission times unavailable:',type(error).__name__,flush=True)
        return collector.cache.get(key,(0,{}))[1]

def backfill(root,league):
    root=Path(root);folder=root/'docs/bonus-games/matchups';manifest=json.loads((folder/'index.json').read_text(encoding='utf8'));collector=SimpleNamespace(league=league,season=int(manifest['season']),cache={})
    for week in manifest['weeks']:
        path=folder/f'week-{week:02}.json'
        if not path.exists():continue
        data=json.loads(path.read_text(encoding='utf8'))
        if week!=manifest['currentWeek'] and all('lineupSubmittedAt' in t for t in data['teams']):continue
        rows=get_submissions(collector,week)
        for t in data['teams']:t['lineupSubmittedAt']=rows.get(t['id'])
        path.write_text(json.dumps(data,separators=(',',':'),allow_nan=False),encoding='utf8');print(league,week,len(rows),'submission timestamps',flush=True);time.sleep(3)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--league',required=True,choices=HOSTS);p.add_argument('--root',type=Path,default=Path('.'));a=p.parse_args();backfill(a.root,a.league)
