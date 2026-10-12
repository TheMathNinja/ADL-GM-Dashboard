import unittest
from collections import namedtuple
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from adjusted_lineup_selection import choose,replacement_rating
Player=namedtuple('Player','player_id pos rating actual')
class SelectionTests(unittest.TestCase):
 def test_missing_projection_uses_ytd(self):
  self.assertEqual(replacement_rating(None,9.5),(9.5,'YTD PPG'))
  self.assertEqual(replacement_rating(float('nan'),9.5),(9.5,'YTD PPG'))
  self.assertEqual(replacement_rating(0,9.5),(0.,'Fantasy Sharks'))
 def test_selection_does_not_use_realized_score(self):
  limits={'RB':(0,1,'off')};totals={'off':1}
  a=Player('A','RB',5,100);b=Player('B','RB',10,-5)
  self.assertEqual(choose([], [a,b],limits,totals),[b])
 def test_partial_lineup_is_counted(self):
  limits={'QB':(1,1,'off'),'RB':(1,1,'off')};totals={'off':2}
  a=Player('A','RB',10,7)
  self.assertEqual(choose([], [a],limits,totals),[a])
  self.assertEqual(choose([], [],limits,totals),[])
 def test_healthy_zero_starter_is_preserved(self):
  limits={'RB':(1,1,'off')};totals={'off':1}
  fixed=Player('A','RB',0,0);bench=Player('B','RB',100,100)
  self.assertEqual(choose([fixed],[bench],limits,totals),[])
 def test_fill_maximum_players_even_when_rating_negative(self):
  limits={'RB':(0,2,'off')};totals={'off':2}
  a=Player('A','RB',-1,-2);b=Player('B','RB',-2,-3)
  self.assertEqual(set(choose([],[a,b],limits,totals)),{a,b})
if __name__=='__main__':unittest.main()
