import sys,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from bracket import make_games
class BracketReplay(unittest.TestCase):
 def test_every_round_against_2025_archive(self):
  old=json.loads((Path(__file__).parent/'fixtures/adl_2025_bracket.json').read_text());field={'NFC':[],'AFC':[]};scores={w:{} for w in range(13,18)};elo={w:{} for w in range(12,18)}
  for g in old['games']:
   for t in g['teams']:
    scores[g['week']][t['name']]={'points':t['points'],'potential':t['points']};elo[g['week']-1][t['name']]=t['elo']
    if g['week']==13:field[g['conference']].append(dict(t,apPct=t['allPlayPct']/100,ppg=t['totalPoints']/12,pot=t['totalPoints']/12))
  elo[17]=elo[16]
  for completed in range(12,18):
   games=make_games(field,completed,scores,elo,30.625025877938)
   for w in range(13,min(completed+1,17)+1):self.assertEqual(len({t['name'] for g in games if g['week']==w for t in g['teams']}),32)
   for g in games:
    self.assertAlmostEqual(sum(t['odds'] for t in g['teams']),100)
    if g['week']>completed:self.assertTrue(all(t['points'] is None for t in g['teams']))
    self.assertTrue(any(x['week']==g['week'] and x['category']==g['category'] and {t['name'] for t in x['teams']}=={t['name'] for t in g['teams']} for x in old['games']))
if __name__=='__main__':unittest.main()
