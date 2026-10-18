"""Public MFL live-score relay; separate data branch, no forecast/result writes."""
import argparse,base64,datetime as dt,json,os,time,urllib.request,urllib.error
from zoneinfo import ZoneInfo
ET=ZoneInfo('America/New_York')
IDS={f'{i:04}' for i in range(1,33)}
BRANCH='live-bonus-watch'
def many(x):return [] if x is None else x if isinstance(x,list) else [x]
def window(now):
    local=now.astimezone(ET);minute=local.hour*60+local.minute
    return (local.weekday()==6 and 780<=minute<=1425) or (local.weekday()==0 and 1200<=minute<=1425)
def near_window(now):
    return any(window(now+dt.timedelta(minutes=n)) for n in range(21))
def franchises(node):
    result={}
    for match in many(node.get('matchup')):
        for f in many(match.get('franchise')):
            fid=str(f['id']).zfill(4)
            if fid in result and float(result[fid]['score'])!=float(f['score']):raise ValueError('Conflicting franchise scores')
            result[fid]=f
    for f in many(node.get('franchise')):result[str(f['id']).zfill(4)]=f
    if set(result)!=IDS:raise ValueError('Live scoring must contain all 32 teams')
    return result
def number(v):
    f=float(v)
    if not (-100000<f<100000):raise ValueError('Invalid score')
    return f

def player_projection(player,metadata,projections):
    pid=player['id'];meta=metadata.get(pid,{})
    score=number(player.get('score',0));seconds=max(0,min(3600,int(player.get('gameSecondsRemaining',0))))
    raw=projections.get(pid);pregame=None if raw in [None,''] else number(raw)
    # MFL omits players without a Sharks projection. Keep that absence explicit;
    # zero additional points is the fallback, rather than inventing a projection.
    projected=score+seconds/3600*(pregame if pregame is not None else 0)
    return dict(id=pid,name=meta.get('name',pid),position=meta.get('position',''),nflTeam=meta.get('team',''),score=score,seconds=seconds,pregameProjection=pregame,liveProjection=round(projected,6))
def legal_potential(candidates,rules,decimals=1):
    limits={}
    for p in many(rules['position']):
        lohi=list(map(int,p['limit'].split('-')));pos=p['name'];limits[pos]=(lohi[0],lohi[-1],'off' if pos in ['QB','RB','WR','TE'] else 'st' if pos in ['PK','PN'] else 'def')
    totals={'off':int(rules.get('iop_starters',7)),'def':int(rules['idp_starters'])};totals['st']=int(rules['count'])-sum(totals.values());total=0.
    for group,count in totals.items():
        states={0:(0,0.)}
        for pos,(lo,hi,g) in limits.items():
            if g!=group:continue
            values=sorted([value for p,value in candidates if p==pos],reverse=True);prefix=[0.]
            for v in values:prefix.append(prefix[-1]+v)
            new={}
            for used,(real,score) in states.items():
                for n in range(min(hi,len(values),count-used)+1):
                    for vacancy in range(max(0,lo-n),min(hi-n,count-used-n)+1):
                        key=used+n+vacancy;value=(real+n,score+prefix[n])
                        if key not in new or value>new[key]:new[key]=value
            states=new
        if count not in states:raise ValueError('Invalid lineup constraints')
        total+=states[count][1]
    return round(total,decimals)
class Collector:
    def __init__(self,league,season=2026):self.league=league;self.season=season;self.lid={'ADL':'60206','FAFL':'22686'}[league];self.cache={}
    def get(self,kind,extra='',ttl=0):
        key=kind,extra;now=time.time()
        if key in self.cache and now-self.cache[key][0]<ttl:return self.cache[key][1]
        url=f'https://api.myfantasyleague.com/{self.season}/export?TYPE={kind}&L={self.lid}&JSON=1'+extra
        if not ttl:url+='&_='+str(int(now//60))
        req=urllib.request.Request(url,headers={'User-Agent':'GM-Dashboard-Live-Bonus-Watch/1.0'})
        with urllib.request.urlopen(req,timeout=25) as response:data=json.load(response)
        if data.get('error') or kind not in data:raise ValueError('MFL '+kind+' unavailable')
        self.cache[key]=(now,data[kind]);return data[kind]
    def collect(self):
        live=self.get('liveScoring','&DETAILS=1');sourceweek=int(live['week']);week=min(sourceweek,12)
        if not 1<=week<=12:raise ValueError('No regular-season live week')
        previous=[]
        for w in range(1,week):
            result=franchises(self.get('weeklyResults','&W='+str(w),ttl=1200));previous.append(dict(week=w,teams=[dict(id=fid,score=number(f['score']),potential=number(f['opt_pts']) if f.get('opt_pts') not in [None,''] else None) for fid,f in sorted(result.items())]))
        if sourceweek>12:
            result=franchises(self.get('weeklyResults','&W=12',ttl=1200));teams=[dict(id=fid,score=number(f['score']),potential=number(f['opt_pts']) if f.get('opt_pts') not in [None,''] else None,yet=0,playing=0,seconds=0) for fid,f in sorted(result.items())]
        else:
            result=franchises(live);rules=self.get('league',ttl=3600)['starters'];players=self.get('players','&DETAILS=1',ttl=21600);metadata={p['id']:p for p in many(players.get('player'))};positions={pid:p['position'] for pid,p in metadata.items()};rosters=self.get('rosters',ttl=300);status={(f['id'],p['id']):str(p.get('status','ROSTER')).upper() for f in many(rosters.get('franchise')) for p in many(f.get('player'))};teams=[]
            fs=self.get('projectedScores','&W='+str(week),ttl=300)
            if int(fs.get('week',week))!=week:raise ValueError('Wrong projection week')
            projections={p['id']:p.get('score') for p in many(fs.get('playerScore'))}
            for fid,f in sorted(result.items()):
                candidates=[];projected_candidates=[];starters=[];unknown=False
                for p in many(f.get('players',{}).get('player')):
                    projected=player_projection(p,metadata,projections)
                    if str(p.get('status','')).lower()=='starter':starters.append(projected)
                    state=status.get((fid,p['id']))
                    if state not in ['ROSTER','ACTIVE','STARTER','NONSTARTER']:continue
                    pos=positions.get(p['id']);score=number(p.get('score',0))
                    if not pos:unknown=True
                    else:
                        candidates.append((pos,score));projected_candidates.append((pos,projected['liveProjection']))
                score=number(f['score']);potential=None if unknown else max(score,legal_potential(candidates,rules))
                projected_score=round(sum(p['liveProjection'] for p in starters),6)
                projected_potential=None if unknown else max(projected_score,legal_potential(projected_candidates,rules,6))
                teams.append(dict(id=fid,score=score,potential=potential,projectedScore=projected_score,projectedPotential=projected_potential,starters=starters,yet=int(f.get('playersYetToPlay',0)),playing=int(f.get('playersCurrentlyPlaying',0)),seconds=int(f.get('gameSecondsRemaining',0))))
        return dict(league=self.league,season=self.season,week=week,sourceWeek=sourceweek,complete=sourceweek>12,fetchedAt=dt.datetime.now(dt.timezone.utc).isoformat(),source='MFL liveScoring',teams=teams,completed=previous,provisional=True)

def github(path,token,method='GET',data=None):
    headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'GM-Dashboard-Live-Bonus-Watch'}
    payload=None if data is None else json.dumps(data).encode();req=urllib.request.Request('https://api.github.com/repos/'+path,data=payload,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def publish(repo,token,snapshot):
    try:github(repo+'/git/ref/heads/'+BRANCH,token)
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        tree=github(repo+'/git/trees',token,'POST',{'tree':[{'path':'README.md','mode':'100644','type':'blob','content':'Generated public MFL live Bonus Game scores. Official forecasts and results are maintained on main.\n'}]});commit=github(repo+'/git/commits',token,'POST',{'message':'Initialize public live Bonus Game data','tree':tree['sha'],'parents':[]});github(repo+'/git/refs',token,'POST',{'ref':'refs/heads/'+BRANCH,'sha':commit['sha']})
    path=repo+'/contents/live.json';sha=None
    try:sha=github(path+'?ref='+BRANCH,token)['sha']
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
    body=dict(message='Refresh public live Bonus Game standings',branch=BRANCH,content=base64.b64encode(json.dumps(snapshot,separators=(',',':'),allow_nan=False).encode()).decode())
    if sha:body['sha']=sha
    github(path,token,'PUT',body)
def main():
    p=argparse.ArgumentParser();p.add_argument('--league',choices=['ADL','FAFL'],required=True);p.add_argument('--once',action='store_true');a=p.parse_args();collector=Collector(a.league);now=dt.datetime.now(dt.timezone.utc)
    if not a.once and not near_window(now):print('Outside live-watch hours; no upstream requests.');return
    stop=time.monotonic()+345*60
    while time.monotonic()<stop:
        now=dt.datetime.now(dt.timezone.utc)
        if window(now) or a.once:
            try:
                data=collector.collect();publish(os.environ['GITHUB_REPOSITORY'],os.environ['GH_TOKEN'],data);print('Updated',a.league,'Week',data['week'],data['fetchedAt'],flush=True)
                if data['complete']:return
            except Exception as error:
                print('Live refresh failed; retaining last valid snapshot:',type(error).__name__,flush=True)
                if a.once:raise SystemExit(1)
            if a.once:return
        elif not near_window(now):return
        time.sleep(max(1,60-time.time()%60))
if __name__=='__main__':main()
