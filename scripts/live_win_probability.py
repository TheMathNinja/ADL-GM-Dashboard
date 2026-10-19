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
            f=np.clip(float(p.get('seconds',0))/3600,0,1)
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

def add_probabilities(snapshot,model,draws=20000):
    # Identical score/clock/lineup snapshots yield identical odds across refreshes.
    evidence=[(t['id'],t['score'],t.get('opponentIds',[]),[(p['id'],p['seconds'],p.get('pregameProjection'),p.get('nflGame'),p.get('gameSide')) for p in t.get('starters',[])]) for t in snapshot['teams']]
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
    return snapshot

def load_model(league):
    return json.loads((Path(__file__).resolve().parents[1]/'data/live_win_probability.json').read_text())[league]
