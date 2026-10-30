import json,sys,unittest,tempfile,shutil
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from bonus_predictor import load_adl,adl_availability_credit
from player_blend_scoring import parameters
from player_team_strength import build,historical_roster_rating,RATING_HISTORY_START
from refresh_player_strength_inputs import refresh

class PlayerStrengthTests(unittest.TestCase):
 def test_rating_is_a_historical_week_scale_with_league_rank(self):
  d=pd.read_csv(ROOT/'data/player_team_outlooks_2026.csv')
  for w,g in d.groupby('week'):
   self.assertEqual(len(g),32);self.assertTrue(g.roster_strength.between(0,10).all())
   np.testing.assert_array_equal(pd.Series(np.round(g.roster_strength.to_numpy(),6)).rank(ascending=False,method='min').astype(int),g.roster_strength_rank.to_numpy())
   self.assertTrue(g.forecast_model.map(lambda label: len(label.split('/'))==4 and sum(map(float,label.split('/')))==100).all());self.assertTrue(g.rating_model.str.startswith('historical-week-0-10').all())
   self.assertTrue((g.rating_history_start==RATING_HISTORY_START).all());self.assertTrue((g.rating_history_end==2026).all());self.assertTrue((g.rating_anchor_week==w).all())
 def test_historical_rating_is_week_contextual_and_anchored(self):
  y=2026;w=5;d=pd.read_csv(ROOT/'data/weekly_team_metrics.csv',dtype={'franchise_id':str});ids=sorted(d.franchise_id.unique());data=load_adl(ROOT,y);s=d.pivot(index='week',columns='franchise_id',values='franchise_score').reindex(index=range(1,13),columns=ids).to_numpy();p=d.pivot(index='week',columns='franchise_id',values='potential_points').reindex(index=range(1,13),columns=ids).to_numpy();data[y]=(ids,s,p);credit=adl_availability_credit(ROOT,y,w,ids);*_,meta=parameters(ROOT,data,y,w,credit);q=pd.read_csv(ROOT/'data/player_strength/team_strength_2026.csv',dtype={'franchise_id':str});rating,anchors=historical_roster_rating(ROOT,y,w,ids,q,meta['cases']['roster_rating'])
  self.assertEqual(anchors['week'],w);self.assertEqual(anchors['start'],2022);self.assertEqual(anchors['end'],2026);self.assertTrue((rating>=0).all());self.assertTrue((rating<=10).all());self.assertTrue(anchors['minimum']<100<anchors['maximum'])
 def test_formula_is_the_selected_fixed_mix(self):
  y=2026;w=5;d=pd.read_csv(ROOT/'data/weekly_team_metrics.csv',dtype={'franchise_id':str});ids=sorted(d.franchise_id.unique());s=d.pivot(index='week',columns='franchise_id',values='franchise_score').reindex(index=range(1,13),columns=ids).to_numpy();p=d.pivot(index='week',columns='franchise_id',values='potential_points').reindex(index=range(1,13),columns=ids).to_numpy();credit=adl_availability_credit(ROOT,y,w,ids);data=load_adl(ROOT,y);data[y]=(ids,s,p);mu,sd,tau,_,f=parameters(ROOT,data,y,w,credit)
  c=f['cases']['forecast'];self.assertEqual(c['weights'],[.35,0,.55,.1]);q=pd.read_csv(ROOT/'data/player_strength/team_strength_2026.csv',dtype={'franchise_id':str});q=q[q.week==w];starter=q.pivot(index='target_week',columns='franchise_id',values='starter_strength').reindex(columns=ids).to_numpy();roster=q.pivot(index='target_week',columns='franchise_id',values='roster_strength').reindex(columns=ids).to_numpy();from player_blend_scoring import adjusted_actual_ppg; ap=adjusted_actual_ppg(ROOT,y,w,ids);raw=.35*(p[:w].mean(0)+credit)[None]+.55*c['conversion'][2]*starter+.1*c['conversion'][3]*roster;den=c['input_latent']+c['input_measurement']/w;expected=s[:w].mean()+c['cross']/den*(raw-raw.mean(1,keepdims=True));np.testing.assert_allclose(mu,expected,atol=1e-10);self.assertAlmostEqual(tau,s[:w].mean()*(f['persistent_uncertainty']['coef'][0]+f['persistent_uncertainty']['coef'][1]*(11-w)/10));np.testing.assert_allclose(mu.mean(1),s[:w].mean())
 def test_roster_move_changes_strength_without_a_game(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'tests') as temp:
   root=Path(temp);shutil.copytree(ROOT/'data/player_strength',root/'data/player_strength');before=build(root,2026,5);path=root/'data/player_strength/fantasy_rosters.csv';r=pd.read_csv(path,dtype={'player_id':str,'franchise_id':str});q=r[(r.week==5)&(r.franchise_id=='0001')&(r.pos=='QB')&(r.roster_status=='ROSTER')]
   self.assertFalse(q.empty);player=q.iloc[0];owner='0001';recipient=next(fid for fid in sorted(r.franchise_id.unique()) if fid!=owner and not ((r.week==5)&(r.franchise_id==fid)&(r.player_id==player.player_id)).any());r=r[~((r.week==5)&(r.franchise_id==owner)&(r.player_id==player.player_id))];moved=player.copy();moved.franchise_id=recipient;r=pd.concat([r,pd.DataFrame([moved])],ignore_index=True);r.to_csv(path,index=False);after=build(root,2026,5)
   b=before[before.week==5].groupby('franchise_id').roster_strength.mean();a=after[after.week==5].groupby('franchise_id').roster_strength.mean();self.assertLess(a[owner],b[owner]);self.assertGreater(a[recipient],b[recipient]);pd.testing.assert_series_equal(a.drop([owner,recipient]),b.drop([owner,recipient]))
 def test_a_fresh_roster_is_required(self):
  with self.assertRaisesRegex(ValueError,'freshly fetched'):refresh(ROOT,{})
from refresh_player_strength_inputs import player_cohort
class CohortRecoveryTests(unittest.TestCase):
 def test_missing_week_one_projection_keeps_scored_and_rostered_players(self):
  first=pd.DataFrame({'player_id':['1'],'first_fs':[12.]})
  meta=pd.DataFrame({'player_id':['1','2'],'pos':['WR','TE'],'week1_team':['CHI','LVR']})
  owners=pd.DataFrame({'player_id':['1','2','3','3'],'pos':['WR','TE','DT','DT'],'team':['CHI','LVR','PHI','PHI']})
  result=player_cohort(first,meta,owners).set_index('player_id')
  self.assertEqual(set(result.index),{'1','2','3'})
  self.assertEqual(result.loc['1','first_fs'],12.)
  self.assertTrue(pd.isna(result.loc['2','first_fs']))
  self.assertTrue(result.loc['2','missing_week1_fs'])
  self.assertTrue(pd.isna(result.loc['3','first_fs']))
  self.assertEqual(result.loc['2','pos'],'TE')

from test_missing_fs_prior import MissingFsPriorTests
if __name__=='__main__':unittest.main()

