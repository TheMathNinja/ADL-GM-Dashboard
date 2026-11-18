import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class FullPlayerBreakdownsTests(unittest.TestCase):
 def test_all_banks_and_season_weeks(self):
  banks={}
  for path in (ROOT/'data/trophy_room/player_game_breakdowns').glob('*.json'):
   self.assertEqual(path.read_bytes(),(ROOT/'docs/trophy-room/player-game-breakdowns'/path.name).read_bytes())
   banks[int(path.stem)]=json.loads(path.read_bytes())['games']
   for game in banks[int(path.stem)].values():
    self.assertEqual(game['owners'],sorted(game['owners'],key=lambda o:int(o['franchiseId'])))
    for mode in ['native','current']:
     if mode not in game:continue
     s=game[mode];self.assertFalse(s.get('referenceOnly'));self.assertAlmostEqual(sum(r['points'] for r in s['rows']),s['total'],places=6)
     self.assertNotIn('MFL_TOTAL',[r['eventCode'] for r in s['rows']])
  payload=json.loads((ROOT/'docs/trophy-room/seasonlong-performances.json').read_bytes())
  for d in payload['details'].values():
   if d['kind']!='season-player':continue
   for w in d['weeks']:
    if w['score'] is None:continue
    g=banks[d['year']][str(w['week'])+':'+d['playerId']]
    s=g[d['mode']]
    self.assertAlmostEqual(s['total'] if d['mode']=='current' else s['recordedTotal'],w['score'],places=5)
 def test_watson_native_and_current_details(self):
  g=json.loads((ROOT/'data/trophy_room/player_game_breakdowns/2019.json').read_bytes())['games']['5:13113']
  self.assertEqual(g['native']['total'],105.1 if ROOT.name=='FAFL' else 99.4)
  stats={r['eventCode']:r for r in g['native']['rows']}
  self.assertEqual(stats['FD']['value'],23);self.assertEqual(stats['FUO']['value'],2);self.assertEqual(stats['OFC']['value'],2)
  self.assertEqual([r['eventCode'] for r in g['native']['rows'][:4]],['PC','PA','PY','#P'])
  current={r['eventCode'] for r in g['current']['rows']};self.assertTrue({'FD','F','FY'}<=current)
 def test_legacy_fallback_is_replaced_from_shared_bank(self):
  import sys,tempfile
  sys.path.insert(0,str(ROOT/'scripts'))
  from performance_scoring import add_scoring_details
  raw=json.loads((ROOT/'docs/trophy-room/top-performances.json').read_bytes())
  key=next(k for k,d in raw['details'].items() if d['kind']=='player' and d['year']==2019 and d['mode']=='native')
  d=raw['details'][key];d['scoring']={'referenceOnly':True,'total':d['score'],'rows':[]};d.pop('ownership',None)
  with tempfile.TemporaryDirectory() as cache:
   result=add_scoring_details({'meta':{'scoringYear':2026},'details':{key:d}},cache,ROOT.name,ROOT)
  self.assertFalse(result['details'][key]['scoring'].get('referenceOnly'));self.assertIn('ownership',d)
 def test_weekly_payload_has_ownership_and_no_reference_fallback(self):
  payload=json.loads((ROOT/'docs/trophy-room/top-performances.json').read_bytes())
  for d in payload['details'].values():
   if d['kind']=='player':self.assertIn('ownership',d);self.assertFalse(d['scoring'].get('referenceOnly'))
if __name__=='__main__':unittest.main()
