import json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ArchiveStandingsTests(unittest.TestCase):
 def test_every_completed_season_division_and_record(self):
  p=ROOT/'data/trophy_room/season-standings.json';self.assertEqual(p.read_bytes(),(ROOT/'docs/trophy-room/season-standings.json').read_bytes());d=json.loads(p.read_bytes());h=json.loads((ROOT/'data/gm_career_seasons.json').read_bytes());canonical={(r['season'],r['franchise_id']):r for r in h}
  self.assertEqual(set(map(int,d['seasons'])),{r['season'] for r in h})
  for year,season in d['seasons'].items():
   year=int(year);self.assertEqual(len(season['divisions']),8);self.assertEqual([g['conference'] for g in season['divisions']],['NFC']*4+['AFC']*4)
   rows=[r for group in season['divisions'] for r in group['rows']];self.assertEqual(len(rows),32);self.assertEqual(len({r['franchiseId'] for r in rows}),32)
   for group in season['divisions']:self.assertEqual(len(group['rows']),4)
   for row in rows:
    r=canonical[year,row['franchiseId']];self.assertEqual(row['franchise'],r['name']);self.assertEqual(row['gm'],r['gm']);self.assertEqual(row['record'],{k:r['record_'+k] for k in ['wins','losses','ties']});self.assertEqual(row['allPlayRecord'],{k:r[k] for k in ['wins','losses','ties']})
    self.assertEqual(sum(row['allPlayRecord'].values()),31*(16 if year<2021 else 17));self.assertLessEqual(abs(float(row['percentage'])-(row['record']['wins']+.5*row['record']['ties'])/sum(row['record'].values())),.001)
    self.assertNotIn(row['abbreviation'],['SF','GB','KC','NO','NE','TB','JAX','OAK','NOR'])
    self.assertGreaterEqual(row['averagePointsFor'],0);self.assertGreaterEqual(row['averagePointsAgainst'],0)
   self.assertTrue(season['source']['url'].startswith('https://api.myfantasyleague.com/'))
 def test_runner_up_gm_available_from_selected_season(self):
  data=json.loads((ROOT/'docs/trophy-room/data.json').read_bytes())
  for c in data['champions']:
   p=next(p for p in data['payouts'] if p['year']==c['year']);t=next(t for t in p['teams'] if t['franchise']==c['runner']);self.assertTrue(t['gm'])
if __name__=='__main__':unittest.main()
