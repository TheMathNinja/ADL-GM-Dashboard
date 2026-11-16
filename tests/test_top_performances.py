import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_top_performances import rank_ten,optimize,playoff_game,current_playoff_field,scoring_signature


class TopPerformanceTests(unittest.TestCase):
    def test_ties_at_tenth_and_duplicate_copies(self):
        rows=[dict(key=str(i),score=20-i,year=2024,week=1) for i in range(9)]
        rows += [dict(key='a',score=11,year=2024,week=2),dict(key='b',score=11,year=2024,week=3),dict(key='c',score=10,year=2024,week=4)]
        result=rank_ten(rows+[rows[0]])
        self.assertEqual(len(result),11)
        self.assertEqual([r['rank'] for r in result[-2:]],[10,10])
        self.assertTrue(all(r['tied'] for r in result[-2:]))

    def test_optimal_lineup_obeys_position_and_group_counts(self):
        rules=dict(count='6',iop_starters='3',idp_starters='2',position=[dict(name=p,limit=l) for p,l in [('QB','1'),('RB','0-2'),('WR','1-2'),('PK','1'),('DT','0-1'),('DE','1-2')]])
        pool=[dict(id=str(i),position=p,score=s) for i,(p,s) in enumerate([('QB',10),('RB',30),('RB',29),('WR',5),('PK',2),('DT',12),('DE',8),('DE',7)])]
        chosen=optimize(pool,rules)
        self.assertEqual(sum(p['score'] for p in chosen),67)
        self.assertEqual(len(chosen),6)
        self.assertEqual(sum(p['position']=='WR' for p in chosen),1)
        self.assertEqual(sum(p['position']=='RB' for p in chosen),1)

    def test_playoff_classification_and_no_projected_qualification(self):
        self.assertTrue(playoff_game(15,14,7,'0001'))
        self.assertFalse(playoff_game(12,1,7,'0001'))
        self.assertFalse(playoff_game(15,15,7,'0001'))
        self.assertFalse(playoff_game(13,1,7,'BYE'))
        self.assertFalse(playoff_game(13,1,7,None))
        bracket=dict(season=2026,completedWeek=9,games=[])
        with self.assertRaises(AssertionError):current_playoff_field(bracket,2026)
        bracket['completedWeek']=12
        bracket['games']=[dict(week=13,conference=c,category='championship',teams=[dict(name=f'{c}-{n}') for n in range(7)]) for c in ['NFC','AFC']]
        self.assertEqual(len(current_playoff_field(bracket,2026)),14)

    def test_scoring_rule_signature_ignores_order_but_detects_changes(self):
        raw=dict(rules=dict(positionRules=[dict(positions='QB|RB',rule=[dict(event={'$t':'PY'},points={'$t':'*0.2'},range={'$t':'0-999'})])]))
        other=copy.deepcopy(raw);other['rules']['positionRules'][0]['positions']='RB|QB'
        self.assertEqual(scoring_signature(raw),scoring_signature(other))
        other['rules']['positionRules'][0]['rule'][0]['points']['$t']='*0.3'
        self.assertNotEqual(scoring_signature(raw),scoring_signature(other))

    def test_published_rankings_and_details(self):
        path=ROOT/'data/trophy_room/top-performances.json'
        self.assertEqual(path.read_bytes(),(ROOT/'docs/trophy-room/top-performances.json').read_bytes())
        d=json.loads(path.read_text());seen=set()
        for mode,boards in d['modes'].items():
            lists=[rows for phase in boards['teams'].values() for conf in phase.values() for rows in conf.values()]+list(boards['positions'].values())
            for rows in lists:
                self.assertEqual(len(rows),len({r['key'] for r in rows}))
                self.assertEqual([r['score'] for r in rows],sorted([r['score'] for r in rows],reverse=True))
                for r in rows:
                    self.assertLessEqual(r['rank'],10)
                    detail=d['details'][r['detail']];seen.add(r['detail'])
                    self.assertEqual(detail['mode'],mode)
                    self.assertEqual(detail['score'],r['score'])
                    self.assertIn('myfantasyleague.com',detail['url'])
                    if detail['kind']=='team':
                        self.assertTrue(detail['players'])
                        self.assertEqual(len(detail['players']),len({p['id'] for p in detail['players']}))
                        if detail['phase']=='playoffs':self.assertGreater(detail['week'],12)
                        if mode=='current' and detail['year']<d['meta']['scoringYear']:
                            self.assertAlmostEqual(detail['score'],sum(p['score'] for p in detail['players']),places=1)
        self.assertEqual(seen,set(d['details']))
        for cover in d['meta']['coverage'].values():self.assertLessEqual(cover['covered'],cover['eligible'])
        for source in d['meta']['sources']:self.assertIn('L=',source['players']['url'])
        if d['meta']['league']=='ADL':
            historical=json.loads((ROOT/'data/trophy_room/top_performances_history.json').read_text())
            n=historical['modes']['native']['teams']['regular']
            self.assertEqual(n['NFC']['total'][0]['score'],372.3)
            self.assertEqual(n['AFC']['total'][0]['score'],355.2)
        self.assertFalse(d['modes']['current']['positions']['KR'])
        if d['meta']['league']=='FAFL':self.assertTrue(d['modes']['native']['positions']['KR'])


if __name__=='__main__':unittest.main()
