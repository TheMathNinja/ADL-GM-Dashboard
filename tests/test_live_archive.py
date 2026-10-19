import sys,unittest,json,gzip,base64,copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import collect_live_bonus as c

class ArchiveTests(unittest.TestCase):
 def snapshot(self):
  return dict(league='ADL',season=2026,week=6,fetchedAt='2026-10-19T01:41:00.123456+00:00',teams=[dict(id='0001',score=100,liveMatchups={'0002':dict(win=.6,tie=.01,loss=.39)},starters=[dict(id='a',seconds=900,pregameProjection=10)])],completed=[],liveProbabilityModel=dict(id='model',seed='123',parameters={'shape':'Normal'}))
 def fake(self):
  calls=[]
  def api(path,token,method='GET',data=None):
   calls.append((path,method,copy.deepcopy(data)))
   if method=='GET' and '/git/ref/' in path:return {'object':{'sha':'head'}}
   if method=='GET' and '/git/commits/' in path:return {'tree':{'sha':'tree'}}
   if method=='POST' and path.endswith('/git/blobs'):return {'sha':'archive-blob'}
   if method=='POST' and path.endswith('/git/trees'):return {'sha':'new-tree'}
   if method=='POST' and path.endswith('/git/commits'):return {'sha':'new-head'}
   if method=='PATCH':return {}
   raise AssertionError((path,method))
  return calls,api
 def test_atomic_archive_roundtrip(self):
  s=self.snapshot();calls,api=self.fake()
  with patch.object(c,'github',api):c.publish('owner/repo','not-a-real-token',s)
  blob=next(data for p,m,data in calls if p.endswith('/git/blobs'))
  record=json.loads(gzip.decompress(base64.b64decode(blob['content'])))
  self.assertEqual(record['snapshot'],s);self.assertEqual(record['schemaVersion'],1)
  tree=next(data for p,m,data in calls if p.endswith('/git/trees'))
  paths=[e['path'] for e in tree['tree']];self.assertIn('live.json',paths)
  archive=next(p for p in paths if p.startswith('archive/'))
  self.assertTrue(archive.startswith('archive/2026/week-06/2026-10-19/'))
  self.assertTrue(archive.endswith('.json.gz'));self.assertEqual(len(tree['tree']),2)
  ref=next(data for p,m,data in calls if m=='PATCH');self.assertEqual(ref,dict(sha='new-head',force=False))
 def test_unchanged_scores_are_separate_scrapes(self):
  s=self.snapshot();first=c.archive_record(s);s['fetchedAt']='2026-10-19T01:42:00.123456+00:00';second=c.archive_record(s)
  self.assertNotEqual(first[0],second[0]);self.assertEqual(gzip.decompress(second[1]),c.archive_record(s)[2])
 def test_archive_failure_does_not_advance_current(self):
  calls,api=self.fake()
  def broken(path,token,method='GET',data=None):
   if path.endswith('/git/blobs'):raise RuntimeError('archive upload failed')
   return api(path,token,method,data)
  with patch.object(c,'github',broken),self.assertRaises(RuntimeError):c.publish('owner/repo','x',self.snapshot())
  self.assertFalse(any(m=='PATCH' for _,m,_ in calls))
 def test_failed_odds_are_still_archived_as_missing(self):
  s=self.snapshot();s.pop('liveProbabilityModel');s['liveProbabilityUnavailable']=True
  record=json.loads(gzip.decompress(c.archive_record(s)[1]))
  self.assertTrue(record['snapshot']['liveProbabilityUnavailable'])

if __name__=='__main__':unittest.main()
