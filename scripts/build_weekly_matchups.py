"""Published-week matchup browser. Historical lineups are never today's rosters."""
import argparse,copy,csv,datetime as dt,json,time,urllib.error
from pathlib import Path
import numpy as np
from collect_live_bonus import Collector,many,franchises,weekly_opponents,player_projection
from player_availability import weekly_metadata
from lineup_submissions import get_submissions
from fs_pregame_calibration import load_calibration
from pooled_start_counts import with_start_counts
from live_win_probability import load_model,attach_h2h_probabilities

class MatchupCollector(Collector):
    """Space upstream reads and tolerate transient MFL rate limiting."""
    def get(self,kind,extra='',ttl=0):
        key=kind,extra
        if key in self.cache and time.time()-self.cache[key][0]<ttl:return self.cache[key][1]
        for attempt in range(5):
            time.sleep(3 if attempt==0 else min(30,5*2**(attempt-1)))
            try:return super().get(kind,extra,ttl)
            except (urllib.error.URLError,TimeoutError) as error:
                if isinstance(error,urllib.error.HTTPError) and error.code not in [429,500,502,503,504]:raise
                if attempt==4:raise
                print('Retrying MFL',kind,'after transient upstream error',flush=True)

def attach_probabilities(teams,model,week):
    return attach_h2h_probabilities(teams,model)


def build(league,root,payload=None):
    out=root/'docs/bonus-games/matchups';out.mkdir(parents=True,exist_ok=True)
    payload=payload or json.loads((root/'docs/bonus-games/snapshots.json').read_text())
    season=int(payload['season']);through=int(payload['through_week']);current=min(17,through+1)
    # Bonus standings stop at 12; source publication can continue through week 17.
    source=root/('data/score_metadata.csv' if league=='ADL' else 'data/weekly_source_context.json')
    if source.exists():
        raw=next(csv.DictReader(source.open(encoding='utf-8-sig'))) if source.suffix=='.csv' else json.loads(source.read_text())
        through=max(through,int(raw.get('week',through)));current=min(17,through+1)
    collector=MatchupCollector(league,season);cal=load_calibration(league);model=load_model(league)
    meta={p['id']:p for p in many(collector.get('players','&DETAILS=1',ttl=21600).get('player'))}
    names={t['id']:t for t in payload['weeks'][str(payload['through_week'])]}
    elo={}
    with (root/'data/elo_ratings.csv').open(encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            if int(row['season'])==season:elo[int(row['week']),row['franchise_name']]=float(row['elo'])
    total={};count={};manifest=dict(league=league,season=season,currentWeek=current,publishedThroughWeek=through,weeks=list(range(1,current+1)),generatedAt=dt.datetime.now(dt.timezone.utc).isoformat())
    for week in range(1,current+1):
        final=week<=through
        saved=out/f'week-{week:02}.json'
        existing=json.loads(saved.read_text(encoding='utf8')) if saved.exists() else {}
        if week<through and existing.get('final') and existing.get('season')==season and existing.get('modelId')==model['id'] and existing.get('lineupSchema')==4:
            # Older published results are stable; always refresh the latest
            # completed week for Thursday corrections and the upcoming week.
            scores=collector.get('playerScores',f'&W={week}&COUNT=10000',ttl=300)
            for p in many(scores.get('playerScore')):
                if p.get('score') not in [None,'']:
                    pid=p['id'];total[pid]=total.get(pid,0)+float(p['score']);count[pid]=count.get(pid,0)+1
            print(league,'Weekly Matchups',week,'preserved',flush=True)
            continue
        if not final:
            live=collector.collect(requested_week=week,include_bonus=False)
            if live.get('liveProbabilityUnavailable'):raise ValueError('Current matchup probability build failed')
            previous={t['id']:t for t in payload['weeks'].get(str(week-1),[])}
            teams=[{**t,'name':names[t['id']]['name'],'logo':names[t['id']].get('logo',''),
                'record':previous.get(t['id'],{}).get('record','0-0-0' if week==1 else '—'),
                'elo':elo.get((week-1,names[t['id']]['name'])),'scoreAdjustment':0} for t in live['teams']]
            data=dict(**manifest,lineupSchema=4,week=week,final=False,teams=teams,modelId=model['id'],
                liveProbabilityModel=live['liveProbabilityModel'],fetchedAt=live['fetchedAt'],
                estimateBasis='Current MFL starting lineups and the shared live scoring model.')
            saved.write_text(json.dumps(data,separators=(',',':'),allow_nan=False),encoding='utf8')
            print(league,'Weekly Matchups',week,len(teams),'teams (shared live collector)',flush=True)
            continue
        feed=collector.get('weeklyResults' if final else 'liveScoring',f'&W={week}'+('' if final else '&DETAILS=1'),ttl=300)
        if int(feed.get('week',-1))!=week:raise ValueError('Wrong weekly matchup feed')
        week_cal=with_start_counts(cal,collector,week,feed,final)
        clubs=franchises(feed);opponents=weekly_opponents(feed)
        if any(len(v)!=1 for v in opponents.values()):raise ValueError('Expected one H2H opponent for every team')
        fs=collector.get('projectedScores',f'&W={week}',ttl=300)
        if int(fs.get('week',week))!=week:raise ValueError('Wrong projection week')
        projections={p['id']:p.get('score') for p in many(fs.get('playerScore'))};available=sum(v not in [None,''] for v in projections.values())>=100
        ytd={pid:total[pid]/count[pid] for pid in count if count[pid]}
        submitted=get_submissions(collector,week)
        games=collector.game_states(week);teams=[]
        detail_players={p['id']:meta[p['id']]['position'] for f in clubs.values() for p in many(f.get('player')) if p['id'] in meta}
        details=collector.scoring_details(week,detail_players)
        week_meta=weekly_metadata(collector,meta,week)
        previous={t['id']:t for t in payload['weeks'].get(str(week-1),[])}
        for fid,f in sorted(clubs.items()):
            players=many(f.get('player')) if final else many(f.get('players',{}).get('player'))
            starters=[];bench=[]
            for p in players:
                row=player_projection({**p,'score':p.get('score',0),'gameSecondsRemaining':0 if final else p.get('gameSecondsRemaining',3600)},week_meta,projections,games,ytd,week_cal,available)
                row['scoringDetails']=details.get(p['id'])
                if final:row.update(gameStatus='Bye' if row['gameStatus']=='Bye' else 'Final',seconds=0,projectionSeconds=0,liveProjection=row['score'])
                (starters if p.get("status")=="starter" else bench).append(row)
            t=dict(id=fid,name=names[fid]['name'],logo=names[fid].get('logo',''),record=previous.get(fid,{}).get('record','0-0-0' if week==1 else '—'),elo=elo.get((week-1,names[fid]['name'])),score=float(f.get('score',0)),starters=starters,bench=bench,opponentIds=opponents[fid],lineupCount=len(starters),lineupSubmittedAt=submitted.get(fid))
            t['projectedScore']=t['score'] if final else sum(p['liveProjection'] for p in starters)
            t['scoreAdjustment']=round(t['score']-sum(p['score'] for p in starters),6) if final else 0
            teams.append(t)
        attach_probabilities(teams,model,week)
        if final:
            pre=copy.deepcopy(teams)
            for t in pre:
                t['score']=0
                for p in t['starters']:
                    bye=p.get('nflTeam') not in games
                    p.update(score=0,seconds=0 if bye else 3600,projectionSeconds=0 if bye else 3600,gameStatus='Bye' if bye else 'Pregame',nflScoreboard=[])
                from live_continuous_nig import projected_points
                t['projectedScore']=sum(projected_points(p,model) for p in t['starters'])
            attach_probabilities(pre,model,week)
            for t,p in zip(teams,pre):
                t['pregameProjectedScore']=p['projectedScore'];t['pregameMatchups']=p['liveMatchups']
        data=dict(**manifest,lineupSchema=4,week=week,final=final,teams=teams,modelId=model['id'],estimateBasis='Rebuilt pregame estimates use the current calibration and historical submitted starters; these are not archived pregame forecasts.' if final else 'Current MFL starting lineups and the shared live scoring model.',fetchedAt=dt.datetime.now(dt.timezone.utc).isoformat())
        (out/f'week-{week:02}.json').write_text(json.dumps(data,separators=(',',':'),allow_nan=False),encoding='utf8')
        # Only earlier games contribute to fallback PPG for the next week.
        scores=collector.get('playerScores',f'&W={week}&COUNT=10000',ttl=300)
        for p in many(scores.get('playerScore')):
            if p.get('score') not in [None,'']:
                pid=p['id'];total[pid]=total.get(pid,0)+float(p['score']);count[pid]=count.get(pid,0)+1
        print(league,'Weekly Matchups',week,len(teams),'teams',flush=True)
    (out/'index.json').write_text(json.dumps(manifest,indent=2),encoding='utf8')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--league',required=True);p.add_argument('--root',type=Path,default=Path('.'));a=p.parse_args();build(a.league,a.root)
