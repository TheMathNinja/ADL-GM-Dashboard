"""Refuse publication when Playoffs and Bonus Games use different quarters."""
import argparse,json,re
from pathlib import Path

def verify(root,league):
 bonus=json.loads((root/'docs/bonus-games/snapshots.json').read_text(encoding='utf8'))
 week=bonus['through_week']; rows=bonus['weeks'][str(week)]
 raw=(root/'docs/playoff-picture/index.html').read_text(encoding='utf8')
 match=re.search(r'const data\s*=\s*',raw)
 if not match:raise ValueError('Missing playoff forecast')
 data=json.JSONDecoder().raw_decode(raw[match.end():])[0]
 teams={str(t.get('franchise_id',t.get('id'))).zfill(4):t for c,v in data.items() if c in ['NFC','AFC'] for t in v}
 if set(teams)!={r['id'] for r in rows}:raise ValueError('Different teams in quarterly consumers')
 count=0
 for row in rows:
  team=teams[row['id']]
  remaining={b['label'].split()[0]:float(b['probability']) for b in team['winDetails']['bonusGames']}
  actual={b['label'].split()[0]:{'W':1.,'T':.5,'L':0.}[b['result']] for b in team['actualDetails']['bonusGames']}
  for event in row['events'][:4]:
   value=(actual if event['completed'] else remaining).get(event['event'])
   if value is None or abs(value-event['credit'])>1e-8:
    raise ValueError(f"Quarterly mismatch: {league} week {week} {row['id']} {event['event']}: {value} vs {event['credit']}")
   count+=1
 print(f'{league}: {count} quarterly team forecasts match at week {week}; Reg Season model remains independent.')
 return count

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--league',required=True);a=p.parse_args();verify(a.root,a.league)
