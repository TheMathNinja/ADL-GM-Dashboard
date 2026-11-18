import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from import_seasonlong_performances import allplay,bonus_awards,record,percentage,rank_seasons,retained,PHASES,METRICS,season_is_complete

from seasonlong_player_weeks import absence_status,complete_player_weeks

class SeasonlongTests(unittest.TestCase):
 def test_absence_reasons_are_sourced_not_guessed(self):
  self.assertEqual(absence_status('B',{'status':'Out'}),'Bye')
  self.assertEqual(absence_status('',{'status':'Suspended'}),'Suspended')
  self.assertEqual(absence_status('',{'status':'Out'}),'Out')
  self.assertEqual(absence_status('',{'status':'IR'}),'Out (IR)')
  self.assertEqual(absence_status('',{'status':'Questionable'}),'Did not play')
  self.assertEqual(absence_status('',{}),'Did not play')

 def test_cumulative_average_counts_zero_games_and_preserves_absences(self):
  class Archive:
   def get(self,year,week,pid):return {'status':{4:'Out',5:'Suspended'}.get(week,'')}
  d=dict(year=2025,phase='regular',games=2,score=10,playerId='1',leagueId=60206,position='QB',weeks=[dict(week=1,score=0,url='one'),dict(week=3,score=10,url='three')])
  labels={w:'B' for w in range(1,13)};labels[4]=labels[5]=''
  rows=complete_player_weeks(d,labels,Archive())
  self.assertEqual(len(rows),12);self.assertEqual([r['status'] for r in rows[:5]],['Played','Bye','Played','Out','Suspended'])
  self.assertEqual([r['cumulativeAverage'] for r in rows[:5]],[0,0,5,5,5])
  self.assertIsNone(rows[1]['score'])

 def test_only_final_official_season_is_eligible(self):
  self.assertFalse(season_is_complete(2026,10,'official'))
  self.assertFalse(season_is_complete(2026,16,'official'))
  self.assertFalse(season_is_complete(2026,17,'preliminary'))
  self.assertTrue(season_is_complete(2026,17,'official'))
  self.assertTrue(season_is_complete(2020,16,'official'))

 def test_winning_percentage_ties_and_rank_cutoff(self):
  self.assertEqual(percentage(record(['W','L','T','T'])),.5)
  self.assertIsNone(percentage(record([])))
  rows=[dict(key=str(i),score=30-i,year=2020) for i in range(11)];rows[-1]['score']=rows[-2]['score']
  ranked=rank_seasons(rows)
  self.assertEqual(len(ranked),11);self.assertEqual([r['rank'] for r in ranked[-2:]],[10,10])
  self.assertTrue(all(r['tied'] for r in ranked[-2:]));self.assertNotIn('week',ranked[0])

 def test_allplay_counts_ties_against_all_opponents(self):
  ap=allplay({'0001':100,'0002':100,'0003':90})
  self.assertEqual(ap['0001'],dict(wins=1,losses=0,ties=1));self.assertEqual(percentage(ap['0001']),.75)
  self.assertEqual(sum(r['wins'] for r in ap.values()),sum(r['losses'] for r in ap.values()))

 def test_bonus_formats_and_only_completed_awards(self):
  weekly={w:{str(i+1).zfill(4):dict(total=32-i,potential=40-i) for i in range(32)} for w in range(1,13)}
  self.assertFalse(bonus_awards(weekly,2024,2))
  old=bonus_awards(weekly,2024,3)
  self.assertEqual([old[str(i).zfill(4)][0]['result'] for i in [7,8,9,10,23,24,25,26]],['W','T','T','L','W','T','T','L'])
  modern=bonus_awards(weekly,2025,3)
  self.assertEqual([modern[str(i).zfill(4)][0]['result'] for i in [15,16,17,18]],['W','T','T','L'])
  self.assertEqual(len(bonus_awards(weekly,2020,12)['0001']),4)
  self.assertEqual(len(bonus_awards(weekly,2025,12)['0001']),5)
  self.assertEqual(len(bonus_awards(weekly,2023,12,'FAFL')['0001']),5)
  incomplete=copy.deepcopy(weekly);incomplete[2]['0001']['total']=None
  self.assertIsNone(bonus_awards(incomplete,2025,3))

 def test_saved_board_limits_details_totals_and_completed_seasons_only(self):
  source=ROOT/'data/trophy_room/seasonlong-performances.json'
  self.assertEqual(source.read_bytes(),(ROOT/'docs/trophy-room/seasonlong-performances.json').read_bytes())
  d=json.loads(source.read_bytes());self.assertEqual(retained(d['modes']),set(d['details']))
  for mode,boards in d['modes'].items():
   for phase in PHASES:
    lists=[(rows,metric,False) for conf in boards['teams'][phase].values() for metric,rows in conf.items()]+[(rows,'total',True) for rows in boards['positions'][phase].values()]
    for rows,metric,player in lists:
     self.assertEqual([r['score'] for r in rows],sorted([r['score'] for r in rows],reverse=True))
     self.assertEqual(len({r['key'] for r in rows}),len(rows))
     for row in rows:
      self.assertLessEqual(row['rank'],25 if player else 10)
      detail=d['details'][row['detail']];self.assertEqual(detail['phase'],phase);self.assertEqual(detail['mode'],mode)
      self.assertEqual(detail['score'],row['score']);self.assertFalse(detail['partial']);self.assertFalse(row['partial']);self.assertLessEqual(row['year'],d['meta']['completedThroughSeason'])
      weeks=[w['week'] for w in detail['weeks']];self.assertEqual(len(weeks),len(set(weeks)))
      self.assertTrue(all(w<=12 for w in weeks) if phase=='regular' else all(w>12 for w in weeks) if phase=='playoffs' else True)
      self.assertLessEqual(max(weeks),d['meta']['throughWeek'] if row['partial'] else 16 if row['year']<2021 else 17)
      if player:
       self.assertAlmostEqual(sum(r['score'] for r in detail['weeks'] if r['score'] is not None),row['score'],places=6)
       end=16 if row['year']<2021 else 17
       self.assertEqual(weeks,list(range(1,13)) if phase=='regular' else list(range(13,end+1)) if phase=='playoffs' else list(range(1,end+1)))
       total=0;gp=0
       for week in detail['weeks']:
        if week['score'] is not None:total+=round(week['score']*10);gp+=1;self.assertEqual(week['status'],'Played')
        else:self.assertIn(week['status'],['Bye','Out','Out (IR)','Out (IR-PUP)','Out (IR-NFI)','Out (IR-R)','Suspended','Holdout','Retired','Did not play'])
        self.assertEqual(week['cumulativeAverage'],total/10/gp if gp else None)
       self.assertEqual(gp,row['games']);self.assertAlmostEqual(row['average'],row['score']/gp)
       self.assertAlmostEqual(detail['average'],row['average'])
      elif metric in ['total','offense','defense','potential']:self.assertAlmostEqual(sum(r[metric] for r in detail['weeks']),row['score'],places=6)
      elif metric=='record':
       self.assertAlmostEqual(percentage(row['record']),row['score'])
       self.assertEqual(row['record'],{k:row['h2h'][k]+row['bonus'][k]+row['adjustment'][k] for k in row['record']})
       if phase=='playoffs':self.assertEqual(row['bonus'],dict(wins=0,losses=0,ties=0))
      else:self.assertTrue(0<=row['score']<=1)
  self.assertFalse(any(d['modes']['current']['positions'][p]['KR'] for p in PHASES))

 def test_native_records_use_canonical_published_bonus(self):
  d=json.loads((ROOT/'data/trophy_room/seasonlong-performances.json').read_bytes())
  careers={(r['season'],r['franchise_id']):r for r in json.loads((ROOT/'data/gm_career_seasons.json').read_bytes())}
  for key,detail in d['details'].items():
   if detail['kind']!='season-team' or detail['mode']!='native' or detail['metric']!='record' or detail['partial']:continue
   year,fid=detail['year'],key.split(':')[-2];official=careers[year,fid]
   if detail['phase']=='regular' and year<=2018:self.assertEqual(detail['record'],{k:official['record_'+k] for k in ['wins','losses','ties']})
   if detail['phase']=='combined' and year>=2019 and any(w['week']>12 for w in detail['weeks']):self.assertEqual(detail['record'],{k:official['record_'+k] for k in ['wins','losses','ties']})
  self.assertTrue(all(r['year']==2023 for r in d['meta']['officialBonusDifferences']))
  if d['meta']['league']=='ADL':self.assertFalse(d['meta']['officialBonusDifferences'])

if __name__=='__main__':unittest.main()
