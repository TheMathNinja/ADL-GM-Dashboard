"""Validated game-state mean/variance and continuous fitted-rate NIG marginal.

Parameters and numerical quantile interpolation match the 2026 held-out candidate.
The same NFL player shares one draw across fantasy franchises. NFL-game factors
couple different players through a Gaussian copula, preserving each NIG marginal.
"""
from functools import lru_cache
import math
import numpy as np
from scipy.special import expit,ndtr,ndtri
from scipy.stats import norminvgauss,qmc
from scipy.integrate import cumulative_trapezoid,trapezoid

TIME_GRID=np.geomspace(1/3600,1,151)
PROB_GRID=np.unique(np.r_[np.geomspace(1e-8,.001,80),np.linspace(.001,.999,1997),1-np.geomspace(1e-8,.001,80)])

def exposure(player):
    if player.get('gameStatus') in ('Final','Bye'):return 0.
    return float(np.clip(float(player.get('projectionSeconds',player.get('seconds',0)))/3600,0,1))

def lead(player):
    scores=player.get('nflScoreboard') or []
    own=[x for x in scores if x.get('team')==player.get('nflTeam')]
    other=[x for x in scores if x.get('team')!=player.get('nflTeam')]
    return float(own[0]['score'])-float(other[0]['score']) if len(own)==1 and len(other)==1 else 0.

def remaining_moments(player,model,level=None):
    f=exposure(player)
    if not f:return 0.,0.,False
    mu=float(player.get('calibratedPregameProjection',player.get('pregameProjection')) or 0)
    pos=player.get('position');status=str(player.get('gameStatus',''))
    fallback=status.startswith(('OT','Awaiting')) or pos not in model['conditionalPositions'] or player.get('pregameProjection') is None
    if fallback:
        level=model['referenceLevel'] if level is None else level
        v=model['positions'].get(pos,model['fallback'])
        return mu*f,level*math.sqrt((v['floorVariance']+v['projectionVariance']*(max(mu,0)/level)**2)*f),True
    current=float(player.get('score',0));scorelead=lead(player);a=1-f;margin=min(abs(scorelead)/7,5)
    ot=model['conditionalOT'];ox=np.array([a,a*a,margin,margin*margin,margin*a,margin*a*a,(margin==0)*a,(margin<=3/7)*a*a,(margin<=8/7)*a*a])
    pot=expit(math.log(ot['p0']/(1-ot['p0']))+ox@np.asarray(ot['coef']))
    knots=np.array([0,.0333333333,.0833333333,.1666666667,.3333333333,.5,.6666666667,.8333333333,1])
    tents=np.array([np.interp(f,knots,np.eye(9)[j]) for j in range(1,8)])
    spec=model['conditionalPositions'][pos];surprise=current-(1-f)*mu;ll=np.clip(scorelead/14,-3,3)
    x=np.r_[tents,tents*mu]
    if spec['full']:x=np.r_[x,f*surprise,f*(1-f)*ll*mu,f*(1-f)**3*ll*mu]
    mean=mu*(1-spec['rho'])*f+(x/np.asarray(spec['scale']))@np.asarray(spec['coef'])+spec['beta']*mu*pot
    ref=spec['ref'];xx=mu/ref;ss=surprise/ref
    vx=np.array([f,f*f,xx*xx*f,xx*xx*f*f,ss*ss*f*f,pot,pot*xx*xx])*ref**2
    return float(mean),float(np.sqrt(max(vx@np.asarray(spec['var']),.0025))),False

def projected_points(player,model):
    mean,_,_=remaining_moments(player,model)
    return float(player.get('score',0))+mean

@lru_cache(maxsize=4096)
def knot_quantiles(g0,skew,power,index):
    f=TIME_GRID[index];gamma=np.exp(g0+power*np.log(f));a=gamma*np.cosh(skew);b=gamma*np.sinh(skew)
    location=np.sinh(skew);scale=np.cosh(skew)/np.sqrt(gamma)
    x=np.unique(np.r_[-np.geomspace(12,5000,1400)[::-1],np.linspace(-12,12,12001),np.geomspace(12,5000,1400)])
    density=np.exp(norminvgauss.logpdf(x*scale+location,a,b))*scale
    mass=trapezoid(density,x)
    if not np.isfinite(mass) or mass<.999:raise ValueError('Continuous NIG quantile mass failed')
    cdf=cumulative_trapezoid(density/mass,x,initial=0)
    return np.interp(PROB_GRID,cdf,x)

def nig_quantiles(probability,f,spec):
    f=max(f,TIME_GRID[0]);index=int(np.clip(np.searchsorted(TIME_GRID,f)-1,0,len(TIME_GRID)-2))
    w=(np.log(f)-np.log(TIME_GRID[index]))/(np.log(TIME_GRID[index+1])-np.log(TIME_GRID[index]))
    args=(float(spec['g0']),float(spec['skew']),float(spec['power']))
    table=(1-w)*knot_quantiles(*args,index)+w*knot_quantiles(*args,index+1)
    return np.interp(probability,PROB_GRID,table)

def simulate(teams,model,draws=20000,seed=62813):
    samples={t['id']:np.full(draws,float(t['score'])) for t in teams}
    pending=[(t,p) for t in teams for p in t.get('starters',[]) if exposure(p)>0]
    if not pending:return samples
    def identity(p):return (str(p['id']),p.get('position',''),p.get('nflGame') or 'unknown:'+str(p['id']))
    keys=sorted({identity(p) for _,p in pending});games=sorted({k[2] for k in keys});ki={k:i for i,k in enumerate(keys)};gi={g:i for i,g in enumerate(games)}
    engine=qmc.Sobol(d=len(keys)+2*len(games),scramble=True,seed=seed)
    z=ndtri(np.clip(engine.random_base2(int(np.ceil(np.log2(draws))))[:draws],1e-9,1-1e-9)).T
    pace=model['paceVariance'];adv=model['advantageVariance'];ind=max(0,1-pace-adv)
    projections=[max(0,float(p.get('calibratedPregameProjection',p.get('pregameProjection')) or 0)) for t in teams for p in t.get('starters',[]) if p.get('pregameProjection') is not None]
    level=np.clip(np.mean(projections) if projections else model['referenceLevel'],model['referenceLevel']*.5,model['referenceLevel']*2)
    cached={}
    for t,p in pending:
        key=identity(p);f=exposure(p);m,sd,fallback=remaining_moments(p,model,float(level));game=gi[key[2]];side=float(p.get('gameSide',1))
        cachekey=(key,f,m,sd,fallback,side)
        if cachekey not in cached:
            latent=np.sqrt(ind)*z[ki[key]]+np.sqrt(pace)*z[len(keys)+game]+side*np.sqrt(adv)*z[len(keys)+len(games)+game]
            noise=latent if fallback else nig_quantiles(ndtr(latent),f,model['continuousShapes'][p['position']])
            cached[cachekey]=m+sd*noise
        samples[t['id']]+=cached[cachekey]
    return samples
