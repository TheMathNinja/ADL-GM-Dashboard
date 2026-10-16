import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SuperBowlLineupTests(unittest.TestCase):
 def test_complete_archive_and_scores(self):
  source=ROOT/'data/trophy_room/super_bowl_lineups.json'
  published=ROOT/'docs/trophy-room/lineups.json'
  self.assertEqual(source.read_bytes(),published.read_bytes())
  games=json.loads(source.read_text())
  champions=json.loads((ROOT/'docs/trophy-room/data.json').read_text())['champions']
  self.assertEqual(set(games),{str(c['year']) for c in champions})
  for c in champions:
   game=games[str(c['year'])]
   self.assertEqual(game['week'],16 if c['year']<2021 else 17)
   self.assertEqual([t['franchise'] for t in game['teams']],[c['champion'],c['runner']])
   self.assertEqual([t['publishedTotal'] for t in game['teams']],list(map(float,c['score'].split(' - '))))
   for team in game['teams']:
    players=team['players']
    self.assertTrue(players)
    self.assertEqual(len(players),len({p['id'] for p in players}))
    self.assertAlmostEqual(sum(p['points'] for p in players),team['starterTotal'],places=1)
    self.assertTrue(all(p['name'] and p['position'] for p in players))
    if abs(team['starterTotal']-team['total'])>.11:
     self.assertEqual(c['year'],2022)
     self.assertIn(team['franchise'],['Kansas City Chiefs','Detroit Lions'])
if __name__=='__main__':unittest.main()
