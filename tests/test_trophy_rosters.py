import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_trophy_rosters import PlayerReport,starter_weeks,stats_for,unique_roster


class RosterStatsTests(unittest.TestCase):
    def test_zero_point_games_and_absences(self):
        report=PlayerReport(3)
        report.feed("""<table><tr><td>1</td><td><a href="javascript:launch_player_modal('60206','1');">Player</a></td><td>5.0</td><td>2.50</td><td>0.0</td><td>B</td><td>5.0</td></tr></table>""")
        self.assertEqual(report.players['1']['weeks'],{1:Decimal('0.0'),3:Decimal('5.0')})
        result=stats_for('1',report.players,{'1':{1,3}})
        self.assertEqual((result['gp'],result['points'],result['ppg']),(2,5,2.5))
        self.assertEqual((result['starts'],result['starterPoints'],result['starterPpg']),(2,5,2.5))

    def test_starts_follow_player_across_teams_without_counting_copies_twice(self):
        scores={'1':dict(weeks={1:Decimal('10'),2:Decimal('20'),3:Decimal('30')},points=Decimal('60'))}
        player=lambda points:dict(id='1',status='starter',score=str(points))
        weekly=dict(weeklyResults=[dict(week='1',matchup=[dict(franchise=[dict(id='0001',player=[player(10)]),dict(id='0002',player=[player(10)])])]),dict(week='2',franchise=[dict(id='0003',player=[player(20)])])])
        starts=starter_weeks(weekly,scores,3)
        self.assertEqual(starts['1'],{1,2})
        result=stats_for('1',scores,starts)
        self.assertEqual((result['gp'],result['points'],result['ppg']),(3,60,20))
        self.assertEqual((result['starts'],result['starterPoints'],result['starterPpg']),(2,30,15))

    def test_no_starts_and_reserve_duplicates(self):
        result=stats_for('1',{'1':dict(weeks={1:Decimal('-2')},points=Decimal('-2'))},{})
        self.assertEqual(result['ppg'],-2)
        self.assertEqual(result['starterPoints'],0)
        self.assertIsNone(result['starterPpg'])
        self.assertEqual(unique_roster([dict(id='1',status='ROSTER'),dict(id='1',status='TAXI_SQUAD')]),[dict(id='1',status='TAXI_SQUAD')])

    def test_complete_archive(self):
        years={r['season'] for r in json.loads((ROOT/'data/gm_career_seasons.json').read_text())}
        root=ROOT/'data/trophy_room/rosters'
        self.assertEqual({int(p.stem) for p in root.glob('*.json')},years)
        for year in years:
            source=root/f'{year}.json'
            self.assertEqual(source.read_bytes(),(ROOT/f'docs/trophy-room/rosters/{year}.json').read_bytes())
            season=json.loads(source.read_text())
            self.assertEqual(len(season['franchises']),32)
            for team in season['franchises'].values():
                self.assertTrue(team['players'])
                self.assertEqual(len(team['players']),len({p['id'] for p in team['players']}))
                for row in team['players']:
                    player=season['players'][row['id']]
                    self.assertLessEqual(player['starts'],player['gp'])
                    self.assertLessEqual(player['gp'],season['throughWeek'])
                    if player['gp']:
                        self.assertAlmostEqual(player['ppg'],player['points']/player['gp'])
                    else:self.assertIsNone(player['ppg'])
                    if player['starts']:
                        self.assertAlmostEqual(player['starterPpg'],player['starterPoints']/player['starts'])
                    else:self.assertIsNone(player['starterPpg'])


if __name__=='__main__':unittest.main()
