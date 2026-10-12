"""Fill eligible roster slots by projection, falling back to prior YTD PPG."""
import math

def replacement_rating(projection, ytd_ppg):
 if projection is not None and math.isfinite(float(projection)):
  return float(projection), 'Fantasy Sharks'
 return (float(ytd_ppg) if ytd_ppg is not None and math.isfinite(float(ytd_ppg)) else 0.), 'YTD PPG'

def choose(fixed,candidates,limits,totals):
 # Vacancies satisfy reserved position/group slots but contribute no player/score.
 # Maximize real-player count first, then rating; never replace an active starter.
 selected=[]
 for group,total in totals.items():
  k=sum(limits[r.pos][2]==group for r in fixed)
  if k>=total:continue
  states={0:(0,0.,[])}
  for pos,(lo,hi,g) in limits.items():
   if g!=group:continue
   count=sum(r.pos==pos for r in fixed)
   hi=max(hi,count)
   a=sorted([r for r in candidates if r.pos==pos],key=lambda r:(-r.rating,r.player_id));new={}
   for used,(real,value,chosen) in states.items():
    for n in range(0,min(hi-count,len(a),total-k-used)+1):
     for vacancies in range(max(0,lo-count-n),min(hi-count-n,total-k-used-n)+1):
      j=used+n+vacancies;candidate=(real+n,value+sum(r.rating for r in a[:n]),chosen+a[:n])
      if j not in new or candidate[:2]>new[j][:2]:new[j]=candidate
   states=new
  if total-k not in states:
   # Historical position labels can make already-submitted active players
   # incompatible with minima. Preserve them and fill only remaining capacity.
   relaxed={p:(0 if g==group else lo,hi,g) for p,(lo,hi,g) in limits.items()}
   selected.extend(choose(fixed,candidates,relaxed,{group:total}));continue
  selected.extend(states[total-k][2])
 return selected
