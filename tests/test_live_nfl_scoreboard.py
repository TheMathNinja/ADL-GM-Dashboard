import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_live_bonus import nfl_scoreboard,player_projection
class NflScoreboardTests(unittest.TestCase):
 def game(self):
  return dict(status=dict(type=dict(state='in',completed=False),clock=400),situation=dict(possession='12'),competitors=[dict(id='26',homeAway='home',team=dict(abbreviation='SEA'),score='14'),dict(id='12',homeAway='away',team=dict(abbreviation='KC'),score='17')])
 def test_away_home_order_scores_and_explicit_possession(self):
  self.assertEqual(nfl_scoreboard(self.game(),{'KC':'KCC'}),[dict(team='KCC',score=17,possession=True),dict(team='SEA',score=14,possession=False)])
 def test_unknown_missing_halftime_final_and_awaiting_do_not_invent_possession(self):
  for mode in ['missing','unknown','halftime','final','awaiting']:
   c=self.game()
   if mode=='missing':c.pop('situation')
   if mode=='unknown':c['situation']['possession']='999'
   if mode=='halftime':c['status']['type']['name']='STATUS_HALFTIME'
   if mode=='final':c['status']['type'].update(state='post',completed=True)
   if mode=='awaiting':c['status']['clock']=0
   self.assertFalse(any(t['possession'] for t in nfl_scoreboard(c,{'KC':'KCC'})),mode)
 def test_score_unavailable_is_not_zero(self):
  for bad in [None,'','NaN','invalid',-1]:
   c=self.game();c['competitors'][0]['score']=bad
   self.assertEqual(nfl_scoreboard(c,{}),[])
 def test_player_carries_scoreboard_without_changing_points(self):
  board=nfl_scoreboard(self.game(),{'KC':'KCC'})
  p=player_projection(dict(id='1',score=8,gameSecondsRemaining=900),{'1':dict(team='KCC')},{'1':20},{'KCC':dict(state='in',period=4,clock=400,scoreboard=board)})
  self.assertEqual(p['nflScoreboard'],board);self.assertEqual(p['score'],8);self.assertEqual(p['liveProjection'],13)
if __name__=='__main__':unittest.main()
