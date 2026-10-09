import unittest,tempfile,json
from pathlib import Path
from copy import deepcopy
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from bonus_outlook_archive import merge_outlooks,preserve_playoff_pages,observed_weeks
import numpy as np

def payload(last=4,season=2026):
 d=dict(league='ADL',season=season,through_week=last)
 for section in ['weeks','cutoffs','models','observations','outlooks']:d[section]={str(w):{'value':section+str(w)} for w in range(1,last+1)}
 return d
class OutlookArchiveTests(unittest.TestCase):
 def test_earlier_scores_models_and_cutoffs_survive_rebuild(self):
  old=payload();new=payload();new['weeks']['1']={'corrected':True};new['models']['1']={'new_model':True};new['observations']['1']={'later_correction':True};merge_outlooks(new,old)
  for section in ['weeks','cutoffs','models','observations','outlooks']:self.assertEqual(new[section]['1'],old[section]['1'])
  new['weeks']['1']['value']='mutation';self.assertNotEqual(new['weeks']['1'],old['weeks']['1'])
 def test_legacy_reconstructions_use_current_model(self):
  old=payload();old['outlooks']['1']={'kind':'reconstructed'};new=payload();new['models']['1']={'new_model':True};merge_outlooks(new,old);self.assertEqual(new['models']['1'],{'new_model':True})
 def test_active_week_can_refresh(self):
  old=payload();new=payload();new['models']['4']={'new_model':True};merge_outlooks(new,old);self.assertEqual(new['models']['4'],{'new_model':True})
 def test_last_week_freezes_on_advance(self):
  old=payload();new=payload(5);new['weeks']['4']={'changed':True};merge_outlooks(new,old);self.assertEqual(new['weeks']['4'],old['weeks']['4'])
 def test_season_reset_and_rollback(self):
  old=payload();new=payload(1,2027);self.assertEqual(merge_outlooks(deepcopy(new),old),new)
  with self.assertRaises(ValueError):merge_outlooks(payload(3),old)
 def test_saved_playoffs_restored_and_current_refreshed(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
   assert Path(folder).resolve().is_relative_to(Path(__file__).resolve().parent)
   root=Path(folder);out=root/'docs/bonus-games';pp=root/'docs/playoff-picture';pp.mkdir(parents=True);archive=out/'outlooks/2026';archive.mkdir(parents=True)
   for w in range(1,4):
    (archive/f'through-week-{w:02}-playoffs.html').write_text('saved'+str(w));(pp/f'ADL_2026_W{w+1:02}_playoff_and_draft_forecast.html').write_text('rebuilt')
   (pp/'index.html').write_text('current');preserve_playoff_pages(root,out,payload())
   for w in range(1,4):self.assertEqual((pp/f'ADL_2026_W{w+1:02}_playoff_and_draft_forecast.html').read_text(),'saved'+str(w))
   self.assertEqual((archive/'through-week-04-playoffs.html').read_text(),'current')
 def test_weekly_ties_and_records_use_own_scores(self):
  ids=[str(i).zfill(4) for i in range(32)];s=np.array([np.arange(32,dtype=float),np.arange(32,dtype=float)]);s[0,0]=1;p=s+10;data=observed_weeks(ids,s,p);self.assertEqual(data['1'][0]['record'],'0-30-1');self.assertEqual(data['1'][0]['ap'],.5);self.assertTrue(data['1'][0]['tied']);self.assertEqual(data['2'][0]['record'],'0-31-0')
if __name__=='__main__':unittest.main()
