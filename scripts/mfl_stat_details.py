"""Read MFL's public detailed scoring table as inert data, never embed its HTML."""
from html.parser import HTMLParser
import datetime as dt,re,urllib.request
from concurrent.futures import ThreadPoolExecutor

def clean(s):return ' '.join(s.split())

class ScoringParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.depth=0;self.cells=None;self.cell=None;self.player=None;self.result={};self.report_seen=False
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='table':
            if self.depth:self.depth+=1
            elif 'report' in a.get('class','').split():self.depth=1;self.report_seen=True
        if not self.depth:return
        if tag=='tr':self.cells=[]
        if tag=='td' and self.cells is not None:self.cell=dict(text=[],classes=a.get('class','').split(),playerId=None)
        if tag=='br' and self.cell is not None:self.cell['text'].append('\n')
        if tag=='a' and self.cell is not None:
            m=re.search(r"launch_player_modal\(['\"]\d+['\"],\s*['\"](\d+)['\"]\)",a.get('href',''))
            if m:self.cell['playerId']=m.group(1)
    def handle_data(self,text):
        if self.depth and self.cell is not None:self.cell['text'].append(text)
    def handle_endtag(self,tag):
        if tag=='td' and self.cell is not None:
            self.cells.append(self.cell);self.cell=None
        if tag=='tr' and self.cells is not None and self.depth:
            cells=self.cells;self.cells=None
            if not cells:return
            if cells[0]['playerId']:
                self.player=cells[0]['playerId'];lines=[clean(s) for s in ''.join(cells[0]['text']).split('\n') if clean(s)]
                self.result[self.player]=dict(player=lines[0] if lines else '',context=lines[1:],rows=[],total=None)
                cells=cells[1:]
            if self.player and len(cells)==2 and 'points' in cells[0]['classes']:
                try:points=float(clean(''.join(cells[0]['text'])))
                except ValueError:return
                if not -100000<points<100000:raise ValueError('Invalid detail points')
                event=clean(''.join(cells[1]['text']))
                if 'subtotal' in cells[0]['classes'] or event.lower()=='subtotal':self.result[self.player]['total']=points
                else:self.result[self.player]['rows'].append(dict(points=points,event=event))
        if tag=='table' and self.depth:self.depth-=1;self.player=None

def parse_details(html,season,league_id,week,players,fetched_at=None):
    if not re.search(r'Week\s+'+str(week)+r'\s+Detailed Results',html,re.I):raise ValueError('Wrong detailed scoring week')
    parser=ScoringParser();parser.feed(html)
    if not parser.report_seen:raise ValueError('Detailed scoring table unavailable')
    stamp=fetched_at or dt.datetime.now(dt.timezone.utc).isoformat();result={}
    for pid in players:
        row=parser.result.get(pid)
        if row and row['total'] is not None:
            result[pid]={**row,'fetchedAt':stamp,'week':week,'sourceUrl':f'https://api.myfantasyleague.com/{season}/detailed?L={league_id}&W={week}&P={pid}&YEAR={season}'}
    return result

def fetch_details(season,league_id,week,players):
    ids=sorted(set(str(p) for p in players))
    if not ids:return {}
    if any(not p.isdigit() for p in ids):raise ValueError('Invalid MFL player identifier')
    # MFL's report limits PLAYERS to fewer than 750 characters. Bounded batches
    # require about six reports per league, rather than 672 individual requests.
    batches=[];batch=[]
    for pid in ids:
        if len(','.join(batch+[pid]))>=700:batches.append(batch);batch=[]
        batch.append(pid)
    if batch:batches.append(batch)
    def one(batch):
        url=f'https://api.myfantasyleague.com/{season}/detailed?L={league_id}&W={week}&P='+','.join(batch)+f'&YEAR={season}'
        req=urllib.request.Request(url,headers={'User-Agent':'GM-Dashboard-Live-Scoring-Details/1.0'})
        with urllib.request.urlopen(req,timeout=20) as r:html=r.read().decode('utf8',errors='replace')
        return parse_details(html,season,league_id,week,batch)
    result={}
    with ThreadPoolExecutor(max_workers=3) as pool:
        for parsed in pool.map(one,batches):result.update(parsed)
    return result
