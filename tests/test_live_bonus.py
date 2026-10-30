import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import datetime as dt,unittest
from collect_live_bonus import window,near_window,legal_potential,franchises,player_projection,game_clock,weekly_opponents,injury_code,starter_progress,starter_progress,starter_progress
class LiveBonusTests(unittest.TestCase):
 def test_startup_lead_bridges_delayed_thursday_schedule(self):
  for stamp in ['2026-10-29T23:00:00+00:00','2026-10-29T23:39:09+00:00','2026-11-06T00:00:00+00:00','2026-10-25T12:00:00+00:00','2026-10-26T23:00:00+00:00']:
   now=dt.datetime.fromisoformat(stamp)
   self.assertTrue(near_window(now),stamp)
   self.assertFalse(window(now),stamp)
  for stamp in ['2026-10-29T22:59:00+00:00','2026-10-25T11:59:00+00:00','2026-10-28T23:30:00+00:00','2026-10-30T04:31:00+00:00']:
   self.assertFalse(near_window(dt.datetime.fromisoformat(stamp)),stamp)

 def test_counts_use_normalized_starter_clocks(self):
  starters=[dict(seconds=0,gameStatus='Final') for _ in range(2)]+[dict(seconds=3600,gameStatus='Pregame') for _ in range(4)]
  self.assertEqual(starter_progress(starters),dict(playing=0,yet=4,seconds=14400))
  starters.append(dict(seconds=118,gameStatus='OT 1:58'))
  self.assertEqual(starter_progress(starters),dict(playing=1,yet=4,seconds=14518))
 def test_kickoff_is_live_at_full_clock(self):
  seconds,status=game_clock(3600,dict(state='in',period=1,clock=900))
  self.assertEqual(status,'1Q 15:00')
  self.assertEqual(starter_progress([dict(seconds=seconds,gameStatus=status)]),dict(playing=1,yet=0,seconds=3600))

 def test_counts_use_normalized_starter_clocks(self):
  starters=[dict(seconds=0,gameStatus='Final') for _ in range(2)]+[dict(seconds=3600,gameStatus='Pregame') for _ in range(4)]
  self.assertEqual(starter_progress(starters),dict(playing=0,yet=4,seconds=14400))
  starters.append(dict(seconds=118,gameStatus='OT 1:58'))
  self.assertEqual(starter_progress(starters),dict(playing=1,yet=4,seconds=14518))
 def test_kickoff_is_live_at_full_clock(self):
  seconds,status=game_clock(3600,dict(state='in',period=1,clock=900))
  self.assertEqual(status,'1Q 15:00')
  self.assertEqual(starter_progress([dict(seconds=seconds,gameStatus=status)]),dict(playing=1,yet=0,seconds=3600))

 def test_counts_use_normalized_starter_clocks(self):
  starters=[dict(seconds=0,gameStatus='Final') for _ in range(2)]+[dict(seconds=3600,gameStatus='Pregame') for _ in range(4)]
  self.assertEqual(starter_progress(starters),dict(playing=0,yet=4,seconds=14400))
  starters.append(dict(seconds=118,gameStatus='OT 1:58'))
  self.assertEqual(starter_progress(starters),dict(playing=1,yet=4,seconds=14518))
 def test_kickoff_is_live_at_full_clock(self):
  seconds,status=game_clock(3600,dict(state='in',period=1,clock=900))
  self.assertEqual(status,'1Q 15:00')
  self.assertEqual(starter_progress([dict(seconds=seconds,gameStatus=status)]),dict(playing=1,yet=0,seconds=3600))

 def test_confirmed_final_and_pending_ot(self):
  for league_team in ['DEN','CHI']:
   game=dict(period=4,state='in',clock=0,completed=False,scores=[20,20])
   p=player_projection(dict(id='1',score=10,gameSecondsRemaining=0),{'1':dict(team=league_team)},{'1':36},{league_team:game})
   self.assertEqual((p['seconds'],p['gameStatus'],p['projectionSeconds']),(0,'Awaiting OT',600))
   self.assertEqual(p['liveProjection'],16)
   self.assertEqual(starter_progress([p]),dict(playing=1,yet=0,seconds=0))
   self.assertEqual(game_clock(0,{**game,'scores':[20,17]}),(0,'Awaiting final status'))
   self.assertEqual(game_clock(0,{**game,'state':'post','completed':True,'scores':[20,17]}),(0,'Final'))
   self.assertNotEqual(game_clock(0,{**game,'state':'post','completed':True})[1],'Final')
   self.assertEqual(game_clock(0,{**game,'period':5,'state':'post','completed':True}),(0,'Final'))
   self.assertNotEqual(game_clock(0,dict(state='post',clock=0,completed=True))[1],'Final')
   self.assertEqual(game_clock(0,{**game,'period':5,'clock':600}),(600,'OT 10:00'))

 def test_injury_labels_preserve_scoring(self):
  for raw,expected in [('Questionable','Q'),('Out','O'),('Doubtful','D'),('IR','IR'),('',''),('Healthy','')]:
   self.assertEqual(injury_code(raw),expected)
  p=player_projection(dict(id='1',score=4,gameSecondsRemaining=1800),{'1':dict(injuryStatus='Questionable',injuryDetails='Knee')},{'1':10})
  self.assertEqual(p['injuryStatus'],'Q');self.assertEqual(p['injuryDetails'],'Knee');self.assertEqual(p['liveProjection'],9)

 def test_weekly_opponents_and_byes(self):
  pairs=weekly_opponents({'matchup':[{'franchise':[{'id':'1'},{'id':'2'}]},{'franchise':[{'id':'1'},{'id':'3'}]},{'franchise':[{'id':'4'},{'id':'BYE'}]}]})
  self.assertEqual(pairs['0001'],['0002','0003'])
  self.assertEqual(pairs['0002'],['0001'])
  self.assertEqual(pairs['0003'],['0001'])
  self.assertEqual(pairs['0004'],[])
 def test_player_kickoff_metadata(self):
  p=player_projection(dict(id='1',score=0,gameSecondsRemaining=3600),{'1':dict(team='DEN')},{'1':12},{'DEN':dict(kickoff=1792455300)})
  self.assertEqual(p['kickoff'],1792455300)
  self.assertEqual(p['seconds'],3600)
  self.assertEqual(p['liveProjection'],12)
 def test_ytd_ppg_projection_fallback(self):
  p=dict(id='1',score=5,gameSecondsRemaining=1800)
  fallback=player_projection(p,{}, {},ytd_ppg={'1':12})
  self.assertEqual(fallback['pregameProjection'],12)
  self.assertEqual(fallback['liveProjection'],11)
  self.assertEqual(fallback['projectionSource'],'YTD PPG')
  sharks=player_projection(p,{}, {'1':0},ytd_ppg={'1':12})
  self.assertEqual(sharks['projectionSource'],'Fantasy Sharks')
  self.assertEqual(sharks['liveProjection'],5)
  missing=player_projection(p,{}, {},ytd_ppg={})
  self.assertIsNone(missing['pregameProjection'])
  self.assertEqual(missing['projectionSource'],'Unavailable')
 def test_regulation_and_overtime_clocks(self):
  self.assertEqual(game_clock(118),(118,'4Q 1:58'))
  self.assertEqual(game_clock(978),(978,'3Q 1:18'))
  self.assertEqual(game_clock(1800,dict(halftime=True)),(1800,'Halftime'))
  self.assertEqual(game_clock(3600),(3600,'Pregame'))
  self.assertEqual(game_clock(0),(0,'Awaiting final status'))
  overtime=dict(period=5,state='in',clock=118)
  self.assertEqual(game_clock(0,overtime),(118,'OT 1:58'))
  p=player_projection(dict(id='1',score=10,gameSecondsRemaining=0),{'1':dict(team='DEN')},{'1':36},{'DEN':overtime})
  self.assertEqual(p['seconds'],118)
  self.assertEqual(p['liveProjection'],11.18)
  self.assertEqual(p['gameStatus'],'OT 1:58')
  self.assertEqual(game_clock(118,dict(period=5,state='post',clock=0,completed=True,scores=[20,17])),(0,'Final'))
 def test_starter_live_projection(self):
  def project(seconds,projection=20):
   return player_projection(dict(id='1',score='7',gameSecondsRemaining=str(seconds)),{'1':dict(name='Player',position='LB')},{'1':projection})
  self.assertEqual(project(3600)['liveProjection'],27)
  self.assertEqual(project(1800)['liveProjection'],17)
  self.assertAlmostEqual(project(0)['liveProjection'],10.333333)
  self.assertEqual(project(900)['liveProjection'],12)
  self.assertEqual(project(1800,None)['liveProjection'],7)
  self.assertIsNone(project(1800,None)['pregameProjection'])
  self.assertEqual(project(1800,-2)['liveProjection'],6)
 def test_eastern_windows_and_dst(self):
  for date,expected in [('2026-10-18T12:59:00+00:00',False),('2026-10-18T13:00:00+00:00',True),('2026-10-19T03:45:00+00:00',True),('2026-10-19T03:46:00+00:00',True),('2026-10-20T00:00:00+00:00',True),('2026-10-20T03:46:00+00:00',True),('2026-11-01T13:59:00+00:00',False),('2026-11-01T14:00:00+00:00',True),('2026-11-03T01:00:00+00:00',True)]:
   self.assertEqual(window(dt.datetime.fromisoformat(date)),expected,date)
  for date,expected in [('2026-10-19T04:30:00+00:00',True),('2026-10-19T04:31:00+00:00',False),('2026-10-20T04:30:00+00:00',True),('2026-10-20T04:31:00+00:00',False),('2026-11-02T05:30:00+00:00',True),('2026-11-02T05:31:00+00:00',False),('2026-11-03T05:30:00+00:00',True),('2026-11-03T05:31:00+00:00',False),('2026-10-18T04:15:00+00:00',False)]:
   self.assertEqual(window(dt.datetime.fromisoformat(date)),expected,date)
  self.assertTrue(near_window(dt.datetime.fromisoformat('2026-10-18T12:50:00+00:00')))
 def test_legal_potential_and_partial_lineup(self):
  r=dict(count='2',iop_starters='2',idp_starters='0',position=[dict(name='QB',limit='1'),dict(name='RB',limit='1')])
  self.assertEqual(legal_potential([('QB',-2),('QB',12),('RB',5)],r),17)
  self.assertEqual(legal_potential([('QB',-2)],r),-2)
 def test_incomplete_feed_rejected(self):
  with self.assertRaises(ValueError):franchises({'franchise':[dict(id='0001',score='0')]})
  rows=[dict(id=f'{i:04}',score='1') for i in range(1,33)]
  self.assertEqual(len(franchises({'matchup':[{'franchise':rows}]})),32)
if __name__=='__main__':unittest.main()
