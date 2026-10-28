import csv,json,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from weekly_matchup_stakes import add_rows

class WeeklyMatchupsTests(unittest.TestCase):
    def test_published_weeks_and_lineup_results(self):
        folder=ROOT/'docs/bonus-games/matchups';index=json.loads((folder/'index.json').read_text())
        self.assertEqual(index['currentWeek'],min(17,index['publishedThroughWeek']+1))
        self.assertEqual(index['weeks'],list(range(1,index['currentWeek']+1)))
        for week in index['weeks']:
            d=json.loads((folder/f'week-{week:02}.json').read_text());teams={t['id']:t for t in d['teams']}
            self.assertEqual(len(teams),32);self.assertEqual(d['week'],week)
            pairs=set()
            for t in teams.values():
                self.assertIsInstance(t['elo'],(int,float));self.assertNotEqual(t['record'],'—')
                self.assertEqual(len(t['opponentIds']),1)
                other=t['opponentIds'][0];self.assertIn(t['id'],teams[other]['opponentIds']);pairs.add(tuple(sorted([t['id'],other])))
                self.assertEqual(len({p['id'] for p in t['starters']}),len(t['starters']))
                if d['final']:
                    self.assertAlmostEqual(t['score'],sum(p['score'] for p in t['starters'])+t['scoreAdjustment'],places=4)
                    self.assertTrue(all(p['gameStatus'] in ['Final','Bye'] for p in t['starters']))
                else:self.assertAlmostEqual(t['projectedScore'],sum(p['liveProjection'] for p in t['starters']),places=4)
                for field in ['liveMatchups','pregameMatchups']:
                    if other in t.get(field,{}):
                        p=t[field][other];q=teams[other][field][t['id']]
                        self.assertAlmostEqual(sum(p.values()),1);self.assertTrue(all(0<=v<=1 for v in p.values()))
                        self.assertEqual(p['win'],q['loss']);self.assertEqual(p['tie'],q['tie'])
            self.assertEqual(len(pairs),16)

    def test_stakes_use_email_metric_and_competition_rank(self):
        with (ROOT/'data/playoff_swing.csv').open() as f:rows=list(csv.DictReader(f))
        if not rows:return
        data={};add_rows(data,rows,int(rows[0]['season']));values=data['weeks'][str(rows[0]['target_week'])]
        for original,row in zip(rows,values):
            self.assertAlmostEqual(row['combinedSwing'],float(original['team_a_swing'])+float(original['team_b_swing']))
            self.assertEqual(row['rank'],1+sum(round(x['combinedSwing'],6)>round(row['combinedSwing'],6) for x in values))

if __name__=='__main__':unittest.main()
