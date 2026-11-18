"""Complete individual season timelines using MFL player reports and weekly injury exports."""
import hashlib,json,re,urllib.request
from pathlib import Path
from import_trophy_rosters import PlayerReport

class SeasonPlayerReport(PlayerReport):
    def __init__(self,end):
        super().__init__(end);self.weekly_labels={}
    def handle_endtag(self,tag):
        if tag=='tr' and self.cells is not None and self.player_id:
            self.weekly_labels[self.player_id]={w:value for w,value in enumerate(self.cells[4:4+self.end],1)}
        super().handle_endtag(tag)

class StatusArchive:
    def __init__(self,cache):
        self.cache=Path(cache);self.loaded={};self.sources={}
    def get(self,year,week,pid):
        key=(year,week)
        if key not in self.loaded:
            path=self.cache/f'NFL-{year}-injuries-{week}.json'
            url=f'https://api.myfantasyleague.com/{year}/export?TYPE=injuries&W={week}&JSON=1'
            try:
                if not path.exists():path.write_bytes(urllib.request.urlopen(url,timeout=45).read())
                raw=path.read_bytes();data=json.loads(raw);injuries=data.get('injuries',{})
                entries=injuries.get('injury',[]);entries=[entries] if isinstance(entries,dict) else entries
                self.loaded[key]={r['id']:r for r in entries if isinstance(r,dict) and 'id' in r}
                self.sources[key]=dict(year=year,week=week,url=url,file=path.name,sha256=hashlib.sha256(raw).hexdigest(),timestamp=injuries.get('timestamp'),available=bool(entries))
            except (OSError,ValueError):
                self.loaded[key]={};self.sources[key]=dict(year=year,week=week,url=url,available=False)
        return self.loaded[key].get(pid,{})

def absence_status(label,injury):
    if label.strip().upper() in ('B','BYE'):return 'Bye'
    status=injury.get('status','').strip()
    if re.search(r'suspend',status,re.I):return 'Suspended'
    if status=='Out':return 'Out'
    if status.startswith('IR'):return f'Out ({status})'
    if status.lower()=='holdout':return 'Holdout'
    if status.upper()=='RETIRED':return 'Retired'
    return 'Did not play'

def complete_player_weeks(detail,labels,archive):
    year,phase=detail['year'],detail['phase'];end=16 if year<2021 else 17
    start,stop=(1,12) if phase=='regular' else (13,end) if phase=='playoffs' else (1,end)
    played={r['week']:r for r in detail['weeks'] if isinstance(r.get('score'),(int,float))}
    pid=detail['key'].split(':')[-1] if 'key' in detail else detail['playerId']
    total=0;games=0;rows=[]
    for week in range(start,stop+1):
        if week in played:
            row=dict(played[week],status='Played');total+=round(row['score']*10);games+=1
        else:
            label=labels.get(week,'');injury={} if label.strip().upper() in ('B','BYE') else archive.get(year,week,pid)
            row=dict(week=week,score=None,status=absence_status(label,injury),url=f'https://api.myfantasyleague.com/{year}/top?L={detail["leagueId"]}&SEARCHTYPE=ADVANCED&START_WEEK={week}&END_WEEK={week}&POSITION={detail["position"]}&COUNT=100&SORT=TOT')
        row['cumulativeAverage']=total/10/games if games else None;rows.append(row)
    assert games==detail['games'] and abs(total/10-detail['score'])<.051,(year,pid,phase,'Timeline total mismatch')
    return rows
