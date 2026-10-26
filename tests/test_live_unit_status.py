import copy,gzip,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from live_unit_status import annotate_player,unit_summary,DEFINITION
from collect_live_bonus import player_projection,archive_record

class UnitOnFieldTests(unittest.TestCase):
 def player(self,pos,team='KCC',possession='KCC',status='3Q 10:00'):
  return annotate_player(dict(id='1',position=pos,nflTeam=team,seconds=1500,gameStatus=status,nflScoreboard=[dict(team='KCC',score=10,possession=possession=='KCC'),dict(team='SEA',score=7,possession=possession=='SEA')]))
 def test_own_possession_offense_and_opponent_defense_count(self):
  for pos in ['QB','RB','WR','TE']:self.assertIs(self.player(pos)['unitOnField'],True)
  for pos in ['DT','DE','LB','CB','S']:self.assertIs(self.player(pos,'SEA')['unitOnField'],True)
  self.assertEqual(unit_summary([self.player('QB'),self.player('LB','SEA')]),dict(unitOnFieldCount=2,unitOnFieldUnknownCount=0,unitOnFieldEligibleLiveCount=2))
 def test_change_of_possession_switches_both_units(self):
  self.assertIs(self.player('WR',possession='SEA')['unitOnField'],False)
  self.assertIs(self.player('LB',possession='SEA')['unitOnField'],True)
  self.assertIs(self.player('LB','SEA',possession='SEA')['unitOnField'],False)
 def test_special_teams_not_inferred_from_possession(self):
  for pos in ['PK','PN']:self.assertIsNone(self.player(pos)['unitOnField'])
  self.assertEqual(unit_summary([self.player('PK')])['unitOnFieldEligibleLiveCount'],0)
 def test_unknown_possession_is_null_not_off_field(self):
  for possession in [None,'unknown']:
   p=self.player('WR',possession=possession);self.assertIsNone(p['unitOnField']);self.assertEqual(unit_summary([p])['unitOnFieldUnknownCount'],1)
 def test_pregame_final_bye_not_counted(self):
  for status in ['Pregame','Final','Bye']:
   p=self.player('QB',status=status);self.assertIs(p['unitOnField'],False);self.assertEqual(unit_summary([p])['unitOnFieldCount'],0)
 def test_projection_carries_unit_status_without_mean_change(self):
  p=self.player('LB','SEA')
  game=dict(state='in',period=3,clock=600,scoreboard=p['nflScoreboard'])
  projected=player_projection(dict(id='1',score=4,gameSecondsRemaining=1500),{'1':dict(position='LB',team='SEA')},{'1':12},{'SEA':game})
  self.assertIs(projected['unitOnField'],True);self.assertEqual(projected['liveProjection'],9)
 def test_archive_round_trip_retains_status_unknown_and_definition(self):
  snapshot=dict(season=2026,week=7,fetchedAt='2026-10-25T23:59:00+00:00',teams=[dict(id='0001',starters=[self.player('QB'),self.player('LB',possession=None)])],unitOnFieldDefinition=DEFINITION)
  record=json.loads(gzip.decompress(archive_record(snapshot)[1]));self.assertEqual(record['snapshot'],snapshot)
  self.assertIsNone(record['snapshot']['teams'][0]['starters'][1]['unitOnField'])

if __name__=='__main__':unittest.main()
