"""Score-coupled mathematical clinch certificates; never infer proof from odds.

Future scores are nonnegative, unbounded rationals; Potential >= PF.
Observed scores use exact rational thousandths; no future scoring-grid restriction.
No roster-strength/probability/NFL-score ceiling is imposed. This deliberately
admits a superset of physically plausible NFL performances: UNSAT is a sound
league-rule certificate; SAT only means no certificate in this score model.
Unresolved final tiebreaks can be decided either way, independently by contest.
"""
from pathlib import Path
import os,sys,json,time,hashlib,itertools
from decimal import Decimal
try:import z3
except ImportError:
 sys.path.insert(0,str(Path(__file__).resolve().parent/'pydeps'));import z3

VERSION='score-coupled-clinch-v1-real'
BONUSES=[(0,3),(3,6),(6,9),(9,12),(0,12)]
def tick(v,scale):
 x=Decimal(str(v))*scale
 if abs(x-x.to_integral_value())>Decimal('0.000001'):raise ValueError('Score is not on configured scoring grid')
 return int(x.to_integral_value())
def lexbetter(a,b):
 return z3.Or(*[z3.And(*[a[j]==b[j] for j in range(k)],a[k]>b[k]) for k in range(len(a))])
def exactly(v,n):return z3.PbEq([(x,1) for x in v],n)

def normalize(req):
 r=dict(req);teams=r['teams'];ids=[str(t.get('id',t.get('franchise_id'))).zfill(4) for t in teams];n=len(ids);w=int(r['week']);m=int(r.get('max_week',12));scale=int(r.get('score_scale',1000))
 if len(set(ids))!=n or not 0<=w<=m:raise ValueError('Invalid identities or week')
 r.update(ids=ids,week=w,max_week=m,score_scale=scale,wild_cards=int(r.get('wild_cards',3)),bonus_win_count=int(r.get('bonus_win_count',15)),bonus_tie_count=int(r.get('bonus_tie_count',2)),bonus_specs=r.get('bonus_specs',BONUSES))
 if 'observations' in r:
  observed={(int(x['week']),str(x.get('id',x.get('franchise_id'))).zfill(4)):x for x in r['observations']}
  r['scores']=[[observed[k+1,i].get('points',observed[k+1,i].get('points_for_week')) for i in ids] for k in range(w)]
  r['potential']=[[observed[k+1,i].get('potential',observed[k+1,i].get('potential_points_week')) for i in ids] for k in range(w)]
 if 'schedule' in r:
  index={v:i for i,v in enumerate(ids)};games={(int(g['week']),str(g['franchise_id']).zfill(4)):index[str(g['opponent_id']).zfill(4)] for g in r['schedule']};r['opp']=[[games[k+1,i] for i in ids] for k in range(m)]
 if len(r['scores'])!=w or len(r['potential'])!=w or len(r['opp'])!=m:raise ValueError('Incomplete weeks')
 for k in range(m):
  if len(r['opp'][k])!=n:raise ValueError('Incomplete schedule')
  for i,j in enumerate(r['opp'][k]):
   if not isinstance(j,int) or j<0 or j>=n or j==i or r['opp'][k][j]!=i:raise ValueError('Invalid reciprocal schedule')
 for frame in ['scores','potential']:
  if any(len(row)!=n for row in r[frame]):raise ValueError('Incomplete score field')
 r['scores']=[[tick(x,scale) for x in row] for row in r['scores']];r['potential']=[[tick(x,scale) for x in row] for row in r['potential']]
 raw_wins=[t.get('wins2',r.get('wins2',[0]*n)[i]) for i,t in enumerate(teams)]
 if any(Decimal(str(x))!=int(x) for x in raw_wins):raise ValueError('Observed wins2 must be integral')
 r['wins2']=[int(x) for x in raw_wins]
 if any(x<0 or x>2*(w+sum(b<=w for a,b in r['bonus_specs'])) for x in r['wins2']):raise ValueError('Invalid observed adjusted wins')
 r['conferences']={c:[i for i,t in enumerate(teams) if str(t['conference'])==c] for c in sorted({str(t['conference']) for t in teams})}
 r['divisions']={c:[i for i,t in enumerate(teams) if (str(t['conference']),str(t['division']))==c] for c in sorted({(str(t['conference']),str(t['division'])) for t in teams})}
 if r['bonus_win_count']+r['bonus_tie_count']>n:raise ValueError('Invalid bonus allocations')
 return r

def adjudicate(r,p,v):
 """Independent, ordinary-Python completion of every league decision.

 Exact ties choose the first team here only to construct one valid witness;
 the proof model permits every tied choice instead.
 """
 n=len(r['ids']);m=r['max_week'];w=r['week'];opp=r['opp']
 ap=[[sum(2*(row[i]>row[j])+(row[i]==row[j]) for j in range(n) if i!=j) for i in range(n)] for row in p]
 h=[[2*(p[k][i]>p[k][opp[k][i]])+(p[k][i]==p[k][opp[k][i]]) for i in range(n)] for k in range(m)]
 totals=lambda frame,a=0,b=m:[sum(frame[k][i] for k in range(a,b)) for i in range(n)]
 aps,pf,pot=totals(ap),totals(p),totals(v);wins=[r['wins2'][i]+sum(h[k][i] for k in range(w,m)) for i in range(n)];bonus={}
 for event,(a,b) in enumerate(r['bonus_specs']):
  if b<=w:continue
  aa,pp,vv=totals(ap,a,b),totals(p,a,b),totals(v,a,b);order=sorted(range(n),key=lambda i:(aa[i],pp[i],vv[i]),reverse=True);award=[0]*n
  for rank,i in enumerate(order):award[i]=2 if rank<r['bonus_win_count'] else 1 if rank<r['bonus_win_count']+r['bonus_tie_count'] else 0
  bonus[str(event)]=award;wins=[a+b for a,b in zip(wins,award)]
 dw=[False]*n;wc=[False]*n;bye=[False]*n
 from fractions import Fraction
 for ix in r['divisions'].values():
  tied=[i for i in ix if wins[i]==max(wins[j] for j in ix)]
  def key(i):
   games=[k for k in range(m) if opp[k][i] in tied]
   mini=Fraction(sum(h[k][i] for k in games),len(games)) if games else Fraction(-1)
   return mini,aps[i],pf[i],pot[i]
  dw[max(tied,key=key)]=True
 for ix in r['conferences'].values():
  order=sorted([i for i in ix if not dw[i]],key=lambda i:(wins[i],aps[i],pf[i],pot[i]),reverse=True)
  for i in order[:r['wild_cards']]:wc[i]=True
  bye[max([i for i in ix if dw[i] or wc[i]],key=lambda i:(aps[i],pf[i],pot[i]))]=True
 return dict(points=p,potential=v,bonus=bonus,division=dw,wildcard=wc,bye=bye)

class ClinchModel:
 def __init__(self,request,timeout_ms=10000):
  self.r=r=normalize(request);self.n=n=len(r['ids']);self.w=w=r['week'];self.m=m=r['max_week'];self.timeout_ms=timeout_ms;self.solver=z3.Solver();self.solver.set(timeout=timeout_ms)
  self.p=[[z3.IntVal(r['scores'][k][i]) if k<w else z3.Real(f'pf_{k}_{i}') for i in range(n)] for k in range(m)]
  self.v=[[z3.IntVal(r['potential'][k][i]) if k<w else z3.Real(f'pot_{k}_{i}') for i in range(n)] for k in range(m)]
  for k in range(w,m):
   for i in range(n):self.solver.add(self.p[k][i]>=0,self.v[k][i]>=self.p[k][i])
  self.ap=[[z3.Sum([z3.If(self.p[k][i]>self.p[k][j],2,z3.If(self.p[k][i]==self.p[k][j],1,0)) for j in range(n) if i!=j]) for i in range(n)] for k in range(m)]
  self.h=[[z3.If(self.p[k][i]>self.p[k][r['opp'][k][i]],2,z3.If(self.p[k][i]==self.p[k][r['opp'][k][i]],1,0)) for i in range(n)] for k in range(m)]
  self.bonuses={}
  for event,(a,b) in enumerate(r['bonus_specs']):
   if b<=w:continue
   awards=[z3.Int(f'bonus_{event}_{i}') for i in range(n)];self.bonuses[event]=awards
   keys=[[z3.Sum([self.ap[k][i] for k in range(a,b)]),z3.Sum([self.p[k][i] for k in range(a,b)]),z3.Sum([self.v[k][i] for k in range(a,b)])] for i in range(n)]
   for award in awards:self.solver.add(z3.Or(award==0,award==1,award==2))
   self.solver.add(exactly([x==2 for x in awards],r['bonus_win_count']),exactly([x==1 for x in awards],r['bonus_tie_count']))
   for i in range(n):
    for j in range(i):
     self.solver.add(z3.Implies(awards[i]>awards[j],z3.Not(lexbetter(keys[j],keys[i]))),z3.Implies(awards[j]>awards[i],z3.Not(lexbetter(keys[i],keys[j]))))
  self.wins=[r['wins2'][i]+z3.Sum([self.h[k][i] for k in range(w,m)])+z3.Sum([v[i] for v in self.bonuses.values()]) for i in range(n)]
  self.ap_total=[z3.Sum([self.ap[k][i] for k in range(m)]) for i in range(n)];self.points=[z3.Sum([self.p[k][i] for k in range(m)]) for i in range(n)];self.potential=[z3.Sum([self.v[k][i] for k in range(m)]) for i in range(n)]
  self.dw=[z3.Bool(f'division_{i}') for i in range(n)];self.wc=[z3.Bool(f'wildcard_{i}') for i in range(n)];self.q=[z3.Or(self.dw[i],self.wc[i]) for i in range(n)];self.bye=[z3.Bool(f'seed1_{i}') for i in range(n)]
  for ix in r['divisions'].values():
   self.solver.add(exactly([self.dw[i] for i in ix],1))
   for size in range(1,len(ix)+1):
    for tied in itertools.combinations(ix,size):
     tied=set(tied);first=min(tied);condition=z3.And(*[self.wins[j]==self.wins[first] if j in tied else self.wins[j]<self.wins[first] for j in ix]);mini={};den={}
     for i in tied:
      games=[k for k in range(m) if r['opp'][k][i] in tied];mini[i]=z3.Sum([self.h[k][i] for k in games]);den[i]=len(games)
     for i in ix:
      if i not in tied:self.solver.add(z3.Implies(condition,z3.Not(self.dw[i])));continue
      for j in tied-{i}:
       # Undefined mini-league records sort below played mini-leagues, matching
       # the existing rule implementation; equal undefined records skip H2H.
       if den[i] and den[j]:mi,mj=mini[i]*den[j],mini[j]*den[i]
       else:mi,mj=z3.IntVal(int(bool(den[i]))),z3.IntVal(int(bool(den[j])))
       better=lexbetter([mj,self.ap_total[j],self.points[j],self.potential[j]],[mi,self.ap_total[i],self.points[i],self.potential[i]])
       self.solver.add(z3.Implies(z3.And(condition,self.dw[i]),z3.Not(better)))
  for ix in r['conferences'].values():
   if len(ix)<r['wild_cards']+sum(1 for v in r['divisions'].values() if v[0] in ix):raise ValueError('Too few conference teams')
   self.solver.add(exactly([self.wc[i] for i in ix],r['wild_cards']),exactly([self.bye[i] for i in ix],1))
   for i in ix:
    self.solver.add(z3.Implies(self.wc[i],z3.Not(self.dw[i])),z3.Implies(self.bye[i],self.q[i]))
    for j in ix:
     if i==j:continue
     wildbetter=lexbetter([self.wins[j],self.ap_total[j],self.points[j],self.potential[j]],[self.wins[i],self.ap_total[i],self.points[i],self.potential[i]])
     self.solver.add(z3.Implies(z3.And(self.wc[i],z3.Not(self.dw[j]),z3.Not(self.wc[j])),z3.Not(wildbetter)))
     seedbetter=lexbetter([self.ap_total[j],self.points[j],self.potential[j]],[self.ap_total[i],self.points[i],self.potential[i]])
     self.solver.add(z3.Implies(z3.And(self.bye[i],self.q[j]),z3.Not(seedbetter)))
  assertions=z3.simplify(z3.And(*self.solver.assertions()))
  self.solver=z3.Solver();self.solver.set(timeout=timeout_ms);self.solver.add(assertions)
  self.input_hash=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest();self.feasible=False

 def contradiction(self,claim,i):
  return {'bye':z3.Not(self.bye[i]),'division':z3.Not(self.dw[i]),'playoffs':z3.Not(self.q[i]),'eliminated':self.q[i],'eliminated_division':self.dw[i],'eliminated_bye':self.bye[i]}[claim]

 def fix_world(self,mode=0,target=None,high=False):
  for k in range(self.w,self.m):
   for i in range(self.n):
    value=2000+100*((i+k*mode)%self.n)
    if i==target:value=100000 if high else 0
    self.solver.add(self.p[k][i]==value,self.v[k][i]==value+500)

 def feasibility(self):
  result,witness=self.concrete_world()
  if result!=z3.sat:raise RuntimeError('Could not establish a feasible rules model: '+str(result))
  replacements=[]
  for k in range(self.w,self.m):
   for i in range(self.n):replacements.extend([(self.p[k][i],z3.RealVal(witness['points'][k][i])),(self.v[k][i],z3.RealVal(witness['potential'][k][i]))])
  for event,awards in self.bonuses.items():
   replacements.extend((variable,z3.IntVal(witness['bonus'][str(event)][i])) for i,variable in enumerate(awards))
  for field,variables in [('division',self.dw),('wildcard',self.wc),('bye',self.bye)]:replacements.extend((variable,z3.BoolVal(witness[field][i])) for i,variable in enumerate(variables))
  if not z3.is_true(z3.simplify(z3.substitute(z3.And(*self.solver.assertions()),*replacements))):raise AssertionError('Independent completion does not satisfy solver model')
  self.feasible=True

 def concrete_world(self,claim=None,mode=0,target=None,high=False):
  p=[list(row) for row in self.r['scores']];v=[list(row) for row in self.r['potential']]
  cumulative=[sum(2*(row[i]>row[j])+(row[i]==row[j]) for row in p for j in range(self.n) if i!=j) for i in range(self.n)]
  target_conf=next((ix for ix in self.r['conferences'].values() if target in ix),[])
  leaders={max(ix,key=lambda i:self.r['wins2'][i]) for ix in self.r['divisions'].values()}
  for k in range(self.w,self.m):
   row=[(200+10*((i+k*mode)%self.n))*self.r['score_scale'] for i in range(self.n)]
   if mode>=32:
    order=sorted(range(self.n),key=lambda i:((i in target_conf) if mode==33 else (i not in leaders) if mode==34 else False,cumulative[i]),reverse=True)
    for rank,i in enumerate(order):row[i]=(200+10*rank)*self.r['score_scale']
   if target is not None:row[target]=10000*self.r['score_scale'] if high else 0
   p.append(row);v.append([x+50*self.r['score_scale'] for x in row])
   cumulative=[cumulative[i]+sum(2*(row[i]>row[j])+(row[i]==row[j]) for j in range(self.n) if i!=j) for i in range(self.n)]
  witness=adjudicate(self.r,p,v)
  truth={'bye':witness['bye'],'division':witness['division'],'playoffs':[d or c for d,c in zip(witness['division'],witness['wildcard'])],'eliminated':[not(d or c) for d,c in zip(witness['division'],witness['wildcard'])],'eliminated_division':[not d for d in witness['division']],'eliminated_bye':[not b for b in witness['bye']]}
  return (z3.sat,witness) if claim is None or not truth[claim][target] else (z3.unsat,None)

 def witness(self,model):
  integer=lambda x:str(model.eval(x,model_completion=True))
  return dict(points=[[integer(v) for v in row] for row in self.p],potential=[[integer(v) for v in row] for row in self.v],bonus={str(k):[integer(v) for v in row] for k,row in self.bonuses.items()},division=[bool(z3.is_true(model.eval(v))) for v in self.dw],wildcard=[bool(z3.is_true(model.eval(v))) for v in self.wc],bye=[bool(z3.is_true(model.eval(v))) for v in self.bye])

 def check(self,claim,i):
  if not self.feasible:self.feasibility()
  begin=time.monotonic();predicate=self.contradiction(claim,i)
  remaining=self.m-self.w;extra=2*(remaining+len(self.bonuses));low=self.r['wins2'];high=[x+extra for x in low]
  division=next(ix for ix in self.r['divisions'].values() if i in ix);conference=next(ix for ix in self.r['conferences'].values() if i in ix)
  div_yes=lambda t:all(low[t]>high[j] for j in next(ix for ix in self.r['divisions'].values() if t in ix) if j!=t)
  div_no=any(low[j]>high[i] for j in division if j!=i)
  qualified=div_yes(i) or sum(high[j]>=low[i] for j in conference if j!=i)<self.r['wild_cards']
  ap_low=[sum(2*(self.r['scores'][k][t]>self.r['scores'][k][j])+(self.r['scores'][k][t]==self.r['scores'][k][j]) for k in range(self.w) for j in range(self.n) if t!=j) for t in range(self.n)]
  ap_high=[x+2*(self.n-1)*remaining for x in ap_low]
  ndiv=sum(ix[0] in conference for ix in self.r['divisions'].values())
  bound=(claim=='division' and div_yes(i)) or (claim=='eliminated_division' and div_no) or (claim=='playoffs' and qualified) or (claim=='bye' and qualified and all(ap_low[i]>ap_high[j] for j in conference if i!=j)) or (claim=='eliminated_bye' and any(div_yes(j) and ap_low[j]>ap_high[i] for j in conference if j!=i)) or (claim=='eliminated' and div_no and sum(low[j]>high[i] for j in conference if j!=i)-ndiv>=self.r['wild_cards'])
  if bound:return dict(status='proved',certified=True,proof='Conservative win/AP bounds; no probability or score ceiling',seconds=time.monotonic()-begin)
  # Concrete completions disprove a claim; they never prove one. This speeds up
  # rare-event simulation false positives without weakening UNSAT certification.
  for mode in [0,7,11,17,23,29,32,33,34]:
   r,witness=self.concrete_world(claim,mode,i,claim.startswith('eliminated'))
   if witness is not None:
    self.solver.set(timeout=self.timeout_ms)
    witness_hash=hashlib.sha256(json.dumps(witness,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(status='counterexample',certified=False,completion=dict(mode=mode,target=i,high=claim.startswith('eliminated')),witness_hash=witness_hash,seconds=time.monotonic()-begin)
  self.solver.set(timeout=self.timeout_ms)
  self.solver.push();self.solver.add(predicate);r=self.solver.check();reason=self.solver.reason_unknown() if r==z3.unknown else None;witness=self.witness(self.solver.model()) if r==z3.sat else None;self.solver.pop()
  return dict(status='proved' if r==z3.unsat else 'counterexample' if r==z3.sat else 'unknown',certified=r==z3.unsat,reason=reason,witness=witness,seconds=time.monotonic()-begin)

def certify(request,timeout_ms=10000):
 model=ClinchModel(request,timeout_ms);model.feasibility();ids=model.r['ids'];candidates=request.get('candidates');out={i:dict(bye=False,division=False,playoffs=False,eliminated=False,eliminated_division=False,eliminated_bye=False,clinch='') for i in ids};queries=[]
 for claim in ['bye','division','playoffs','eliminated','eliminated_division','eliminated_bye']:
  selected=ids if candidates is None else [str(i).zfill(4) for i in candidates.get(claim,[])]
  for team in selected:
   i=ids.index(team)
   if claim=='playoffs' and (out[team]['bye'] or out[team]['division']):out[team]['playoffs']=True;continue
   result=model.check(claim,i);out[team][claim]=result['certified'];queries.append(dict(team=team,claim=claim,**result))
 for team in ids:
  r=out[team];r['playoffs']=r['playoffs'] or r['bye'] or r['division'];r['clinch']='b' if r['bye'] else 'd' if r['division'] else 'p' if r['playoffs'] else 'e' if r['eliminated'] else ''
  if r['playoffs'] and r['eliminated']:raise AssertionError('Conflicting certificate')
 return dict(method=VERSION,solver='Z3 '+z3.get_version_string(),input_hash=model.input_hash,season=request.get('season'),week=model.w,teams=out,queries=queries,complete=all(q['status']!='unknown' for q in queries),score_scale=model.r['score_scale'],unresolved_ties='All choices permitted; no franchise-ID fallback',domain='Unbounded rational score completions; future Potential >= PF; no roster-strength or NFL scoring ceiling')

def certify_cached(request,directory,timeout_ms=None):
 """Persist reproducible inputs and certificates; never reuse across engine/data changes."""
 if timeout_ms is None:timeout_ms=int(os.environ.get("CLINCH_TIMEOUT_MS","10000"))
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
 engine_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 key=hashlib.sha256(json.dumps(dict(input=request,engine=engine_hash,solver=z3.get_version_string(),timeout_ms=timeout_ms),sort_keys=True,separators=(',',':')).encode()).hexdigest()
 path=directory/f"week-{int(request['week']):02}.json"
 if path.exists():
  saved=json.loads(path.read_text())
  if saved.get('cache_key')==key:return saved
 result=certify(request,timeout_ms);result.update(cache_key=key,engine_hash=engine_hash,input=request)
 temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(result,indent=2),encoding='utf8');temporary.replace(path)
 return result

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--output',required=True);p.add_argument('--cache-dir');p.add_argument('--timeout-ms',type=int,default=int(os.environ.get('CLINCH_TIMEOUT_MS','10000')));a=p.parse_args()
 request=json.loads(Path(a.input).read_text(encoding='utf-8-sig'));result=certify_cached(request,a.cache_dir,a.timeout_ms) if a.cache_dir else certify(request,a.timeout_ms);dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2),encoding='utf8');print('Clinch certificates:',sum(bool(t['clinch']) for t in result['teams'].values()),'proved;',sum(q['status']=='unknown' for q in result['queries']),'unresolved queries',flush=True)
