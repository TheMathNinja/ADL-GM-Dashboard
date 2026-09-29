import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]/'scripts'))
import sync_payouts as p


class PayoutTests(unittest.TestCase):
    def setUp(self):
        self.teams = [(f'Team {i}', f'T{i}', 'NFC' if i < 16 else 'AFC') for i in range(32)]
        self.scores = {(n, w): [float(i), float(i+1), float(i+5), float(2*i+1)] for i, (n, _, _) in enumerate(self.teams) for w in range(1, 4)}

    def test_future_blank_quarter_complete_and_ties(self):
        for w in range(1, 4): self.scores['Team 14', w] = self.scores['Team 15', w][:]
        awards = p.expected_awards(self.teams, self.scores, 3)
        self.assertEqual(awards['Week 3'][:4], ['T14, T15']*4)
        self.assertEqual(awards['Q1 Cumulative'][:4], ['T14, T15']*4)
        self.assertEqual(awards['Week 4'], ['']*8)
        self.assertEqual(awards['Regular Season ($)'], ['']*8)
        matrix = p.input_matrix(self.teams, self.scores, 3, 'ADL', 2026)
        self.assertEqual(matrix[0][1:3], ['26W1OPF', '26W2OPF'])
        self.assertEqual(matrix[69][1:4], [5.0]*3)
        self.assertEqual(matrix[1][4:], ['']*14)

    def test_team_order_is_keyed_and_wrong_mapping_rejected(self):
        ref = [['Name', 'Abbr', 'Conference']] + [list(t) for t in reversed(self.teams)]
        teams = p.mapping(ref, self.scores)
        self.assertEqual(p.input_matrix(teams, self.scores, 3, 'FAFL', 2026)[1][:2], ['Team 31', 31.0])
        ref[1][0] = 'Unknown'
        with self.assertRaises(ValueError): p.mapping(ref, self.scores)

    def bracket(self, week):
        games = []
        for conf, base in [('NFC', 0), ('AFC', 16)]:
            def game(w, title, ids, points, aggregate=None):
                ts = [dict(name=f'Team {base+i}', seed=i+1, points=v, aggregate=(aggregate or points)[j]) for j, (i, v) in enumerate(zip(ids, points))]
                return dict(week=w, conference=conf, title=title, category='championship', teams=ts)
            games += [game(13, 'Bye', [0], [10]), game(13, 'Wild Card Round', list(range(1, 7)), [10]*6),
                      game(16, conf+' Championship', [0, 1], [10, 20]), game(16, '3rd Place Game', [2, 3], [10, 20]),
                      game(16, '5th Place Game', [4, 5, 6], [100, 20, 30], [110, 200, 130])]
            ladder = game(17, 'Consolation Game 1', [7, 8], [10, 20]); ladder['seriesWinner'] = f'Team {base+7}'; games.append(ladder)
        games.append(dict(week=17, title='Super Bowl', teams=[dict(name='Team 1', seed=1, points=100), dict(name='Team 17', seed=2, points=100)]))
        return dict(season=2026, completedWeek=week, games=games)

    def test_no_projected_prizes_or_early_postseason_awards(self):
        self.assertEqual(p.postseason_prizes(self.bracket(3), self.teams, 3, 2026), [['', '']]*15)
        prizes = p.postseason_prizes(self.bracket(12), self.teams, 12, 2026)
        self.assertEqual(prizes[7], ['T0', 'T16'])
        self.assertEqual(prizes[:7], [['', '']]*7)

    def test_fifth_place_uses_total_ladder_uses_series_and_sb_seed_tie(self):
        prizes = p.postseason_prizes(self.bracket(17), self.teams, 17, 2026)
        self.assertEqual(prizes[0], ['T1', ''])
        self.assertEqual(prizes[1], ['', 'T17'])
        self.assertEqual(prizes[5:7], [['T5', 'T21'], ['T6', 'T22']])
        self.assertEqual(prizes[14], ['T7', 'T23'])
        with self.assertRaises(ValueError): p.postseason_prizes(self.bracket(16), self.teams, 17, 2026)

    def test_recalculation_and_cash_reconciliation(self):
        awards = p.expected_awards(self.teams, self.scores, 3)
        display = [[2026], []] + [[k]+v for k, v in awards.items()]
        money = [['']*10 for _ in range(37)]
        for row in money: row[3] = 20
        for w in range(1, 18):
            money[19+w][1:3] = [awards[f'Week {w}'][i] for i in [0, 4]]
        for i, (_, abbr, _) in enumerate(self.teams):
            money[i+1][5:9] = [abbr, 60 if abbr in ['T15', 'T31'] else 0, 2, 62 if abbr in ['T15', 'T31'] else 2]
        prizes = [['', '']]*15
        p.verify_outputs(display, money, awards, prizes, self.teams)
        stale = copy.deepcopy(display); stale[4][1] = ''
        with self.assertRaises(ValueError): p.verify_outputs(stale, money, awards, prizes, self.teams)
        money[1][8] = 5
        with self.assertRaises(ValueError): p.verify_outputs(display, money, awards, prizes, self.teams)


if __name__ == '__main__': unittest.main()
