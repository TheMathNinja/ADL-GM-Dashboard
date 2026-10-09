"""Refuse publication when Playoffs and Bonus Games use different quarters."""
import argparse,json,re
from pathlib import Path

def verify_snapshot(root,league,bonus,week,page):
 rows=bonus['weeks'][str(week)]
 raw=(root/'docs/playoff-picture'/page).read_text(encoding='utf8')
 match=re.search(r'const data\s*=\s*',raw)
 if not match:raise ValueError('Missing playoff forecast')
 data=json.JSONDecoder().raw_decode(raw[match.end():])[0]
 teams={str(t.get('franchise_id',t.get('id'))).zfill(4):t for c,v in data.items() if c in ['NFC','AFC'] for t in v}
 if set(teams)!={r['id'] for r in rows}:raise ValueError('Different teams in quarterly consumers')
 count=0
 for row in rows:
  team=teams[row['id']]
  remaining={('All-Season' if b['label'].startswith('Regular Season') else b['label'].split()[0]):float(b['probability']) for b in team['winDetails']['bonusGames']}
  actual={('All-Season' if b['label'].startswith('Regular Season') else b['label'].split()[0]):{'W':1.,'T':.5,'L':0.}[b['result']] for b in team['actualDetails']['bonusGames']}
  for event in row['events'][:5 if league=='ADL' else 4]:
   value=(actual if event['completed'] else remaining).get(event['event'])
   if value is None or abs(value-event['credit'])>1e-8:
    raise ValueError(f"Quarterly mismatch: {league} week {week} {row['id']} {event['event']}: {value} vs {event['credit']}")
   count+=1
 return count

def verify(root,league):
 bonus=json.loads((root/'docs/bonus-games/snapshots.json').read_text(encoding='utf8'))
 last=bonus['through_week'];count=0
 for week in range(1,last+1):
  page='index.html' if week==last else (f"ADL_{bonus['season']}_W{week+1:02}_playoff_and_draft_forecast.html" if league=='ADL' else f'week-{week+1:02}.html')
  count+=verify_snapshot(root,league,bonus,week,page)
 print(f'{league}: {count} quarterly team forecasts match across {last} weekly outlooks; ADL Reg Season also shares the selected Bonus predictor.')
 return count

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--league',required=True);a=p.parse_args();verify(a.root,a.league)
