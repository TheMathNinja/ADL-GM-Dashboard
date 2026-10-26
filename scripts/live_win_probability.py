"""Conditional matchup simulations. Only unplayed NFL-game time is random.

Full-game variance is learned separately by league/position. Two shared Gaussian
NFL-game processes represent common production and opposite-team advantage;
independent centered Normal increments (or the tested NIG alternative) supply
the remaining player variance.
Both increment families have variance proportional to time, not time squared. This is a
stationary-increments assumption, not a fit to archived in-game observations.
"""
import hashlib,json
from pathlib import Path
import numpy as np

def nig_increment(rng,a,b,f,n):
    gamma=np.sqrt(a*a-b*b)
    # IG(delta/gamma, delta^2) is the mixing subordinator at exposure delta=f.
    v=rng.wald(f/gamma,f*f,n)
    return (b*(v-f/gamma)+np.sqrt(v)*rng.standard_normal(n))/np.sqrt(a*a/gamma**3)

def simulate(teams,model,draws=20000,seed=62813):
    """One joint simulation for all clubs; reciprocal odds share the same draws."""
    rng=np.random.default_rng(seed);samples={t['id']:np.full(draws,float(t['score'])) for t in teams}
    pending=[]
    for t in teams:
        for p in t.get('starters',[]):
            f=np.clip(float(p.get('projectionSeconds',p.get('seconds',0)))/3600,0,1)
            if not f:continue
            pending.append((t,p,f))
    projections=[max(0,float(p['pregameProjection'])) for t in teams for p in t.get('starters',[]) if p.get('pregameProjection') is not None]
    level=float(np.mean(projections)) if projections else model['referenceLevel']
    # Stabilize season scale for unusual/incomplete lineups, without changing means.
    level=max(model['referenceLevel']*.5,min(model['referenceLevel']*2,level))
    shared={}
    for game in sorted({p.get('nflGame') or 'unknown:'+p['id'] for _,p,_ in pending}):
        fractions=sorted({f for _,p,f in pending if (p.get('nflGame') or 'unknown:'+p['id'])==game})
        pace=np.zeros(draws);adv=np.zeros(draws);last=0
        for f in fractions:
            pace=pace+rng.standard_normal(draws)*np.sqrt(f-last)
            adv=adv+rng.standard_normal(draws)*np.sqrt(f-last)
            shared[game,f]=(pace.copy(),adv.copy());last=f
    pace_var=model['paceVariance'];adv_var=model['advantageVariance'];independent=max(0,1-pace_var-adv_var)
    for t,p,f in pending:
        mu=float(p.get('pregameProjection') or 0)
        spec=model['positions'].get(p.get('position'),model['fallback'])
        sd=level*np.sqrt(spec['floorVariance']+spec['projectionVariance']*(max(mu,0)/level)**2)
        game=p.get('nflGame') or 'unknown:'+p['id'];pace,adv=shared[game,f]
        side=float(p.get('gameSide',1))
        z=rng.standard_normal(draws)*np.sqrt(f) if model['shape']=='Normal' else nig_increment(rng,model['a'],model['b'],f,draws)
        samples[t['id']]+=f*mu+sd*(np.sqrt(independent)*z+np.sqrt(pace_var)*pace+side*np.sqrt(adv_var)*adv)
    return samples

def bonus_outcomes(ap,points,potential,potential_complete):
    """Rank APW, then PF, then known Potential; split unresolved boundary ties.

    Return team x [win,tie,loss]. Fractional allocation avoids inventing IDs or
    deterministic simulated Potential for an unfinished NFL roster.
    """
    ap=np.asarray(ap);points=np.asarray(points);potential=np.broadcast_to(potential,ap.shape)
    complete=np.asarray(potential_complete,dtype=bool);result=[]
    for i in range(ap.shape[1]):
        same=(ap==ap[:,i,None])&(points==points[:,i,None])
        unresolved=(same&~complete[None,:]).any(1)
        better=(ap>ap[:,i,None])|((ap==ap[:,i,None])&(points>points[:,i,None]))|((~unresolved[:,None])&same&(potential>potential[:,i,None]))
        equal=same&(unresolved[:,None]|(potential==potential[:,i,None]))
        rank=better.sum(1);size=equal.sum(1)
        win=np.clip(15-rank,0,size)/size
        tie=np.clip(17-rank,0,size)/size-win
        result.append([float(win.mean()),float(tie.mean()),float((1-win-tie).mean())])
    return np.array(result)

def add_bonus_probabilities(snapshot,samples,remaining=None):
    teams=snapshot['teams'];ids=[t['id'] for t in teams];week=int(snapshot['week'])
    if len(ids)!=32:raise ValueError('Bonus probabilities require all 32 teams')
    current=np.rint(np.column_stack([samples[i] for i in ids])*10)
    def ap2(x):return 2*(x[:,:,None]>x[:,None,:]).sum(2)+(x[:,:,None]==x[:,None,:]).sum(2)-1
    weekly_ap=ap2(current);history={int(w['week']):{t['id']:t for t in w['teams']} for w in snapshot['completed']}
    later_ap=[];later_pf=[];later_pot=[]
    if remaining is not None:
        order=[remaining['ids'].index(i) for i in ids]
        future=remaining['future'][:,:,order];future_potential=remaining['potential'][:,:,order]
        if future.shape!=(len(current),12-week,32):raise ValueError('Later-week trajectory dimensions disagree')
        for j in range(12-week):
            scores=np.rint(future[:,j]*10);later_ap.append(ap2(scores));later_pf.append(scores);later_pot.append(future_potential[:,j])
    for race,start,end in [('quarter',3*((week-1)//3)+1,3*((week-1)//3)+3),('season',1,12)]:
        ap=weekly_ap.copy();points=current.copy();pot=np.array([float(t.get('potential') or 0) for t in teams]);complete=np.array([bool(t.get('potentialComplete',False)) and t.get('potential') is not None for t in teams])
        for w in range(start,week):
            if w not in history or any(i not in history[w] for i in ids):raise ValueError('Completed-week carry-forward is incomplete')
            past=[history[w][i] for i in ids];scores=np.rint([[float(t['score'])*10 for t in past]])
            ap+=ap2(scores);points+=scores
            pot+=np.array([float(t.get('potential') or 0) for t in past]);complete&=np.array([t.get('potential') is not None for t in past])
        if remaining is not None:
            pot=np.broadcast_to(pot,ap.shape).copy()
            for j in range(end-week):ap+=later_ap[j];points+=later_pf[j];pot+=later_pot[j]
        probs=bonus_outcomes(ap,points,pot,complete)
        for t,p in zip(teams,probs):t.setdefault('liveBonusProbabilities',{})[race]=dict(zip(['win','tie','loss'],map(float,p)))
    snapshot['liveBonusProbabilityBasis']='final_event_outcome' if remaining is not None else 'end_of_current_week'
    if remaining is not None:snapshot['liveBonusForecast']=remaining.get('metadata',{})
    return snapshot

def add_probabilities(snapshot,model,draws=20000):
    # Identical score/clock/lineup snapshots yield identical odds across refreshes.
    evidence=[(t['id'],t['score'],t.get('opponentIds',[]),[(p['id'],p['seconds'],p.get('projectionSeconds',p['seconds']),p.get('gameStatus'),p.get('pregameProjection'),p.get('nflGame'),p.get('gameSide')) for p in t.get('starters',[])]) for t in snapshot['teams']]
    seed=int.from_bytes(hashlib.sha256(json.dumps(evidence,sort_keys=True).encode()).digest()[:8],'big')
    samples=simulate(snapshot['teams'],model,draws,seed)
    teams={t['id']:t for t in snapshot['teams']}
    for t in snapshot['teams']:
        t['liveMatchups']={}
        for other in t.get('opponentIds',[]):
            if other not in samples:continue
            # League scoring precision is 0.1 points. Compare rounded final totals.
            diff=np.rint(samples[t['id']]*10)-np.rint(samples[other]*10)
            t['liveMatchups'][other]=dict(win=float(np.mean(diff>0)),tie=float(np.mean(diff==0)),loss=float(np.mean(diff<0)))
    snapshot['liveProbabilityModel']=dict(id=model['id'],draws=draws,trainingYears=model['trainingYears'],method='Player '+model['shape']+' increments with shared NFL-game effects',inGameValidation=False,seed=str(seed),numpyVersion=np.__version__,parameters=model)
    # Archive the candidate next to the exact odds it will later be calibrated
    # against. No fitted possession effect exists yet, so it does not alter draws.
    starters=[p for t in snapshot['teams'] for p in t.get('starters',[])]
    snapshot['liveProbabilityModel']['candidateFeatures']={'unitOnField':dict(recorded=any('unitOnField' in p for p in starters),knownPlayers=sum(p.get('unitOnField') is not None for p in starters),usedForOdds=False,definitionVersion=1)}
    if len(teams)==32:
        try:
            from live_bonus_forecast import remaining_forecast
            remaining=remaining_forecast(snapshot['league'],snapshot['season'],snapshot['week'],draws)
            add_bonus_probabilities(snapshot,samples,remaining)
        except Exception as error:
            snapshot['liveBonusProbabilityUnavailable']=True
            print('Final Bonus probabilities unavailable:',type(error).__name__,str(error)[:180],flush=True)
    return snapshot

def load_model(league):
    return json.loads((Path(__file__).resolve().parents[1]/'data/live_win_probability.json').read_text())[league]
