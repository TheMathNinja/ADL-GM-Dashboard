import math
"""Public MFL live-score relay; separate data branch, no forecast/result writes."""
import argparse,base64,datetime as dt,gzip,hashlib,json,os,time,urllib.request,urllib.error
from zoneinfo import ZoneInfo
from live_unit_status import annotate_player,unit_summary,DEFINITION as UNIT_ON_FIELD_DEFINITION
ET=ZoneInfo('America/New_York')
IDS={f'{i:04}' for i in range(1,33)}
BRANCH='live-bonus-watch'
def many(x):return [] if x is None else x if isinstance(x,list) else [x]
def window(now):
    local=now.astimezone(ET);minute=local.hour*60+local.minute
    return (local.weekday()==6 and minute>=780) or (local.weekday()==0 and minute>=1200) or (local.weekday() in [0,1] and minute<=30)
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

def weekly_opponents(node):
    result={fid:set() for fid in IDS}
    for matchup in many(node.get('matchup')):
        ids={str(f.get('id','')).zfill(4) for f in many(matchup.get('franchise'))}&IDS
        if len(ids)==2:
            for fid in ids:result[fid].update(ids-{fid})
    return {fid:sorted(opponents) for fid,opponents in result.items()}
def number(v):
    f=float(v)
    if not (-100000<f<100000):raise ValueError('Invalid score')
    return f

def nfl_scoreboard(competition,aliases):
    """Away/home NFL scores, with possession only when explicitly reported live."""
    teams=many(competition.get('competitors'))
    if len(teams)!=2:return []
    status=competition.get('status',{});kind=status.get('type',{})
    possession=str((competition.get('situation') or {}).get('possession') or '')
    active=kind.get('state')=='in' and not kind.get('completed') and kind.get('name')!='STATUS_HALFTIME' and float(status.get('clock',0))>0
    result=[]
    for t in sorted(teams,key=lambda t:0 if t.get('homeAway')=='away' else 1):
        raw=t.get('score');abbr=t.get('team',{}).get('abbreviation','')
        if raw in [None,''] or not abbr:return []
        try:score=float(raw)
        except (TypeError,ValueError):return []
        if not math.isfinite(score) or score<0 or not score.is_integer():return []
        team=aliases.get(abbr,abbr)
        has_ball=active and bool(possession) and (possession==str(t.get('id',t.get('team',{}).get('id',''))) or aliases.get(possession,possession)==team)
        result.append(dict(team=team,score=int(score),possession=has_ball))
    return result


def game_clock(seconds,game=None):
    game=game or {};seconds=max(0,min(3600,int(seconds)))
    period=int(game.get('period',0));state=game.get('state','')
    scores=game.get('scores',[])
    known=len(scores)==2 and all(x is not None for x in scores)
    # Only an authoritative completed game may become final. Final OT ties are legal.
    if game.get('completed') and state=='post' and float(game.get('clock',-1))==0 and known and (scores[0]!=scores[1] or period>4):return 0,'Final'
    if period>4 and state=='in':
        remaining=max(0,int(float(game['clock'])))
        if remaining==0:return 0,'Awaiting final status'
        return remaining,'OT '+str(remaining//60)+':'+str(remaining%60).zfill(2)
    if seconds==0:
        return 0,('Awaiting OT' if period==4 and known and scores[0]==scores[1] else 'Awaiting final status')
    if seconds==3600:return seconds,('1Q 15:00' if state=='in' else 'Pregame')
    if game.get('halftime'):return seconds,'Halftime'
    quarter=4-(seconds-1)//900;clock=seconds-(4-quarter)*900
    return seconds,str(quarter)+'Q '+str(clock//60)+':'+str(clock%60).zfill(2)

def starter_progress(starters):
    live=sum(p['gameStatus'] not in ['Pregame','Final','Bye'] for p in starters)
    yet=sum(p['seconds']>0 and p['gameStatus']=='Pregame' for p in starters)
    return dict(playing=live,yet=yet,seconds=sum(p['seconds'] for p in starters))

def injury_code(value):
    raw=str(value or '').strip().upper()
    return {'QUESTIONABLE':'Q','DOUBTFUL':'D','OUT':'O','PROBABLE':'P','INACTIVE':'I','SUSPENDED':'S','RETIRED':'RET'}.get(raw,raw if raw in {'Q','D','O','P','I','S','IR','PUP','NFI','IR-PUP','IR-NFI','IR-R'} else '')

def current_player_score(player,details,now=None):
    """Prefer fresh timestamped event totals; never choose a score by magnitude."""
    fallback=number(player.get('score',0))
    if not details:return fallback,'MFL liveScoring',None
    try:
        stamp=dt.datetime.fromisoformat(details['sourceUpdatedAt'].replace('Z','+00:00'))
        age=((now or dt.datetime.now(dt.timezone.utc))-stamp).total_seconds()
        total=float(details['total']);parts=[float(row['points']) for row in details['rows']]
        if not -30<=age<=120 or not math.isfinite(total) or any(not math.isfinite(v) for v in parts) or abs(sum(parts)-total)>.05:
            return fallback,'MFL liveScoring',None
        return total,'MFL live raw stats',details['sourceUpdatedAt']
    except (KeyError,TypeError,ValueError,OverflowError):return fallback,'MFL liveScoring',None

def player_projection(player,metadata,projections,games=None,ytd_ppg=None):
    pid=player['id'];meta=metadata.get(pid,{})
    score=number(player.get('score',0));seconds=max(0,min(3600,int(player.get('gameSecondsRemaining',0))))
    game=(games or {}).get(meta.get('team'),{})
    seconds,game_status=game_clock(seconds,game)
    if games and meta.get('team') not in games and seconds==0:game_status='Bye'
    raw=projections.get(pid);pregame=None if raw in [None,''] else number(raw)
    source='Fantasy Sharks' if pregame is not None else 'Unavailable'
    if pregame is None and (ytd_ppg or {}).get(pid) not in [None,'']:
        pregame=number(ytd_ppg[pid]);source='YTD PPG'
    # MFL omits players without a Sharks projection. Use league YTD PPG next;
    # zero additional points applies only when neither source is available.
    # Reserve the regular-season OT period while its start is pending. The
    # displayed clock remains zero; this is an explicit provisional exposure.
    projection_seconds=600 if game_status.startswith('Awaiting') else seconds
    projected=score+projection_seconds/3600*(pregame if pregame is not None else 0)
    result=dict(id=pid,name=meta.get('name',pid),position=meta.get('position',''),nflTeam=meta.get('team',''),injuryStatus=injury_code(meta.get('injuryStatus')),injuryDetails=meta.get('injuryDetails',''),score=score,seconds=seconds,projectionSeconds=projection_seconds,gameStatus=game_status,kickoff=game.get('kickoff'),nflGame=game.get('nflGame'),gameSide=game.get('gameSide',1),nflScoreboard=game.get('scoreboard',[]),pregameProjection=pregame,projectionSource=source,liveProjection=round(projected,6))
    return annotate_player(result,game)
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
        url=f'https://api.myfantasyleague.com/{self.season}/export?TYPE={kind}&JSON=1'+('' if kind in ['nflSchedule','injuries'] else '&L='+self.lid)+extra
        if not ttl:url+='&_='+str(int(now//60))
        req=urllib.request.Request(url,headers={'User-Agent':'GM-Dashboard-Live-Bonus-Watch/1.0'})
        with urllib.request.urlopen(req,timeout=25) as response:data=json.load(response)
        if data.get('error') or kind not in data:raise ValueError('MFL '+kind+' unavailable')
        self.cache[key]=(now,data[kind]);return data[kind]
    def scoring_details(self,week,players):
        from mfl_stat_details import fetch_raw_details
        key=('scoring-details',week,tuple(sorted(players.items())));now=time.time()
        if key in self.cache and now-self.cache[key][0]<50:return self.cache[key][1]
        try:
            rules=self.get('rules',ttl=3600);labels=json.loads((__import__('pathlib').Path(__file__).resolve().parents[1]/'data/mfl_stat_labels.json').read_text());data=fetch_raw_details(self.season,self.lid,week,players,rules,labels);self.cache[key]=(now,data);return data
        except Exception as error:
            print('Player scoring details unavailable; retaining last known details:',type(error).__name__,flush=True)
            return self.cache.get(key,(0,{}))[1]
    def game_states(self,week):
        # MFL exposes total game seconds but no explicit quarter/OT flag. The
        # public NFL scoreboard supplies that metadata for the same NFL games.
        games={}
        try:
            schedule=self.get('nflSchedule','&W='+str(week))
            matches=many(schedule.get('matchup'))
            games={}
            for m in matches:
                ids=sorted(t['id'] for t in many(m.get('team')))
                for tid in ids:games[tid]=dict(kickoff=int(m['kickoff']),nflGame='|'.join(ids),gameSide=1 if tid==ids[0] else -1)
            key=('nfl-game-states',week);now=time.time()
            if key in self.cache and now-self.cache[key][0]<45:return self.cache[key][1]
            url='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates='+str(self.season)+'&week='+str(week)+'&seasontype=2'
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'GM-Dashboard-Live-Bonus-Watch/1.0'}),timeout=12) as r:data=json.load(r)
            aliases={'JAX':'JAC','NE':'NEP','NO':'NOS','TB':'TBB','GB':'GBP','KC':'KCC','LV':'LVR','SF':'SFO','WSH':'WAS','LA':'LAR'}
            for event in data.get('events',[]):
                if int(event.get('season',{}).get('year',0))!=self.season:continue
                for competition in event.get('competitions',[]):
                    ids=[aliases.get(t['team']['abbreviation'],t['team']['abbreviation']) for t in competition.get('competitors',[])]
                    matching=next((m for m in matches if set(ids)=={t['id'] for t in many(m.get('team'))}),None)
                    if matching is None:continue
                    kickoff=dt.datetime.fromisoformat(competition['date'].replace('Z','+00:00')).timestamp()
                    if abs(kickoff-int(matching['kickoff']))>3600:continue
                    status=competition.get('status',event.get('status',{}));kind=status.get('type',{})
                    info=dict(period=int(status.get('period',0)),clock=float(status.get('clock',0)),state=kind.get('state',''),completed=kind.get('completed') is True,scores=[float(t['score']) if t.get('score') not in [None,''] else None for t in competition.get('competitors',[])],halftime=kind.get('name')=='STATUS_HALFTIME',kickoff=int(matching['kickoff']))
                    info['scoreboard']=nfl_scoreboard(competition,aliases)
                    for tid in ids:games[tid]={**games.get(tid,{}),**info}
            self.cache[key]=(now,games);return games
        except Exception as error:
            print('NFL period metadata unavailable; retaining MFL game clocks:',type(error).__name__,flush=True)
            return games
    def collect(self):
        live=self.get('liveScoring','&DETAILS=1');sourceweek=int(live['week']);week=min(sourceweek,12)
        if not 1<=week<=12:raise ValueError('No regular-season live week')
        previous=[]
        for w in range(1,week):
            result=franchises(self.get('weeklyResults','&W='+str(w),ttl=1200));previous.append(dict(week=w,teams=[dict(id=fid,score=number(f['score']),potential=number(f['opt_pts']) if f.get('opt_pts') not in [None,''] else None) for fid,f in sorted(result.items())]))
        details={}
        if sourceweek>12:
            result=franchises(self.get('weeklyResults','&W=12',ttl=1200));teams=[dict(id=fid,score=number(f['score']),potential=number(f['opt_pts']) if f.get('opt_pts') not in [None,''] else None,yet=0,playing=0,seconds=0) for fid,f in sorted(result.items())]
        else:
            result=franchises(live);opponents=weekly_opponents(live);rules=self.get('league',ttl=3600)['starters'];players=self.get('players','&DETAILS=1',ttl=21600);metadata={p['id']:p for p in many(players.get('player'))};positions={pid:p['position'] for pid,p in metadata.items()};rosters=self.get('rosters',ttl=300);status={(f['id'],p['id']):str(p.get('status','ROSTER')).upper() for f in many(rosters.get('franchise')) for p in many(f.get('player'))};teams=[]
            fs=self.get('projectedScores','&W='+str(week),ttl=300)
            if int(fs.get('week',week))!=week:raise ValueError('Wrong projection week')
            projections={p['id']:p.get('score') for p in many(fs.get('playerScore'))}
            averages=self.get('playerScores','&W=AVG&COUNT=10000',ttl=300)
            ytd_ppg={p['id']:p.get('score') for p in many(averages.get('playerScore'))}
            injury_key='&W='+str(week)
            try:injuries=self.get('injuries',injury_key,ttl=60)
            except Exception as error:
                print('Injury feed unavailable; retaining last known weekly statuses:',type(error).__name__,flush=True)
                injuries=self.cache.get(('injuries',injury_key),(0,{}))[1]
            for row in many(injuries.get('injury')):
                pid=row.get('id')
                if pid in metadata:metadata[pid]={**metadata[pid],'injuryStatus':row.get('status',''),'injuryDetails':row.get('details','')}
            detail_players={p['id']:positions[p['id']] for f in result.values() for p in many(f.get('players',{}).get('player')) if p['id'] in positions}
            details=self.scoring_details(week,detail_players)
            games=self.game_states(week)
            for fid,f in sorted(result.items()):
                candidates=[];projected_candidates=[];starters=[];unknown=False;potential_complete=True
                for p in many(f.get('players',{}).get('player')):
                    current,score_source,score_updated=current_player_score(p,details.get(p['id']))
                    projected=player_projection({**p,'score':current},metadata,projections,games,ytd_ppg)
                    projected.update(scoreSource=score_source,scoreUpdatedAt=score_updated,mflReportedScore=number(p.get('score',0)))
                    if str(p.get('status','')).lower()=='starter':starters.append(projected)
                    state=status.get((fid,p['id']))
                    if state not in ['ROSTER','ACTIVE','STARTER','NONSTARTER']:continue
                    if projected['gameStatus'] not in ['Final','Bye']:potential_complete=False
                    pos=positions.get(p['id']);score=projected['score']
                    if not pos:unknown=True
                    else:
                        candidates.append((pos,score));projected_candidates.append((pos,projected['liveProjection']))
                score=round(sum(p['score'] for p in starters),1);potential=None if unknown else max(score,legal_potential(candidates,rules))
                projected_score=round(sum(p['liveProjection'] for p in starters),6)
                projected_potential=None if unknown else max(projected_score,legal_potential(projected_candidates,rules,6))
                teams.append(dict(id=fid,score=score,mflReportedScore=number(f['score']),potential=potential,potentialComplete=potential_complete and not unknown,projectedScore=projected_score,projectedPotential=projected_potential,starters=starters,opponentIds=opponents[fid],**starter_progress(starters),**unit_summary(starters)))
        for t in teams:
            for p in t.get('starters',[]):p['scoringDetails']=details.get(p['id'])
        snapshot=dict(league=self.league,season=self.season,week=week,sourceWeek=sourceweek,complete=sourceweek>12,fetchedAt=dt.datetime.now(dt.timezone.utc).isoformat(),source='MFL fresh live raw stats with liveScoring fallback',teams=teams,completed=previous,provisional=True,unitOnFieldDefinition=UNIT_ON_FIELD_DEFINITION)
        try:
            from live_win_probability import add_probabilities,load_model
            return add_probabilities(snapshot,load_model(self.league))
        except Exception as error:
            print('Live probability unavailable; retaining live scores:',type(error).__name__,flush=True)
            snapshot['liveProbabilityUnavailable']=True
            return snapshot

def github(path,token,method='GET',data=None):
    headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'GM-Dashboard-Live-Bonus-Watch'}
    payload=None if data is None else json.dumps(data).encode();req=urllib.request.Request('https://api.github.com/repos/'+path,data=payload,headers=headers,method=method)
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def archive_record(snapshot):
    record=dict(schemaVersion=1,collectorCommit=os.environ.get('GITHUB_SHA'),snapshot=snapshot)
    raw=json.dumps(record,separators=(',',':'),allow_nan=False,sort_keys=True).encode()
    digest=hashlib.sha256(raw).hexdigest()
    stamp=dt.datetime.fromisoformat(snapshot['fetchedAt'].replace('Z','+00:00')).astimezone(dt.timezone.utc)
    path=f"archive/{snapshot['season']}/week-{snapshot['week']:02d}/{stamp:%Y-%m-%d}/{stamp:%H%M%S.%f}Z-{digest[:12]}.json.gz"
    return path,gzip.compress(raw,mtime=0),raw

def publish(repo,token,snapshot):
    # Latest display and immutable calibration evidence advance in one commit.
    try:head=github(repo+'/git/ref/heads/'+BRANCH,token)['object']['sha']
    except urllib.error.HTTPError as e:
        if e.code!=404:raise
        tree=github(repo+'/git/trees',token,'POST',{'tree':[{'path':'README.md','mode':'100644','type':'blob','content':'Generated public MFL live scores and timestamped calibration snapshots. Official forecasts and results are maintained on main.\n'}]});commit=github(repo+'/git/commits',token,'POST',{'message':'Initialize public live Bonus Game data','tree':tree['sha'],'parents':[]});github(repo+'/git/refs',token,'POST',{'ref':'refs/heads/'+BRANCH,'sha':commit['sha']});head=commit['sha']
    path,compressed,_=archive_record(snapshot)
    blob=github(repo+'/git/blobs',token,'POST',dict(encoding='base64',content=base64.b64encode(compressed).decode()))
    for attempt in range(3):
        parent=github(repo+'/git/commits/'+head,token)
        entries=[dict(path='live.json',mode='100644',type='blob',content=json.dumps(snapshot,separators=(',',':'),allow_nan=False)),dict(path=path,mode='100644',type='blob',sha=blob['sha'])]
        tree=github(repo+'/git/trees',token,'POST',dict(base_tree=parent['tree']['sha'],tree=entries))
        commit=github(repo+'/git/commits',token,'POST',dict(message='Archive live probabilities and refresh live standings',tree=tree['sha'],parents=[head]))
        try:
            github(repo+'/git/refs/heads/'+BRANCH,token,'PATCH',dict(sha=commit['sha'],force=False))
            print('Archived calibration snapshot:',path,flush=True)
            return
        except urllib.error.HTTPError as error:
            if error.code not in [409,422] or attempt==2:raise
            head=github(repo+'/git/ref/heads/'+BRANCH,token)['object']['sha']

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
