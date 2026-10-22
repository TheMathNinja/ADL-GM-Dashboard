import copy,importlib.util,json,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_bonus_receipt import validate_bonus_receipt
def bonus_receipt(week=3,run_id='123',league='ADL'):
    due=[w for w in (3,6,9,12) if w<=week]
    rows=lambda w:[dict(id=f'{i:04}',week=w,W=(1 if i<=15 else 0)*(2 if w==12 else 1),L=(1 if i>=18 else 0)*(2 if w==12 else 1),T=(1 if 16<=i<=17 else 0)*(2 if w==12 else 1)) for i in range(1,33)]
    return dict(status='success',mode='official',league=league,season=2026,week=week,run_id=run_id,source_sha256='a'*64,verified_at='2026-10-22T18:00:00Z',due_weeks=due,results=[dict(week=w,rows=rows(w)) for w in due])

class ReceiptTests(unittest.TestCase):
 def test_every_due_period(self):
  for week in [1,3,6,9,12,17]:validate_bonus_receipt(bonus_receipt(week),'ADL',2026,week,'123')
 def test_reject_unverified_or_wrong_context(self):
  for key,value in [('status','queued'),('status','failure'),('mode','preview'),('league','FAFL'),('week',2),('run_id','old'),('due_weeks',[]),('verified_at',''),('source_sha256','bad'),('results',[])]:
   with self.subTest(key=key,value=value),self.assertRaises((ValueError,TypeError)):validate_bonus_receipt({**bonus_receipt(),key:value},'ADL',2026,3,'123')
 def test_all_teams_and_totals(self):
  for kind in ['missing','duplicate','invalid']:
   ack=bonus_receipt()
   if kind=='missing':ack['results'][0]['rows'].pop()
   if kind=='duplicate':ack['results'][0]['rows'][-1]['id']='0001'
   if kind=='invalid':ack['results'][0]['rows'][0].update(W=0,L=1)
   with self.assertRaises(ValueError):validate_bonus_receipt(ack,'ADL',2026,3,'123')
 def test_queued_dispatch_still_waits_for_authoritative_readback(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
   root=Path(directory);(root/'data').mkdir();state={};calls=[]
   ref=MagicMock()
   def update(values,**kw):state.update(json.loads(values[0][0]))
   ref.update.side_effect=update
   def read(cell):
    calls.append(cell);ack=bonus_receipt(6,'123')
    ack.update(source_sha256=state['source_sha256'])
    if len(calls)==1:ack['status']='queued'
    return types.SimpleNamespace(value=json.dumps(ack))
   ref.acell.side_effect=read
   spread=MagicMock();spread.service_account_from_dict.return_value.open_by_key.return_value.worksheet.return_value=ref
   payout=types.SimpleNamespace(BOOKS={'ADL':'book'},ROOT=root,load_scores=lambda *a:None)
   spec=importlib.util.spec_from_file_location('sync_bonus_under_test',Path(__file__).resolve().parents[1]/'scripts/sync_bonus_mfl.py');m=importlib.util.module_from_spec(spec)
   with patch.dict(sys.modules,{'sync_payouts':payout,'gspread':spread}):spec.loader.exec_module(m)
   with patch.dict(sys.modules,{'gspread':spread}),patch.object(m,'reports',return_value={}),patch.object(m,'request_bridge',return_value={'status':'success','queued':True}),patch.object(m.time,'sleep'),patch.dict(os.environ,{'CURRENT_SEASON':'2026','READY_WEEK':'6','GITHUB_RUN_ID':'123','SOURCE_RUN_ID':'123','GOOGLE_SERVICE_ACCOUNT_JSON':'{}'}),patch.object(sys,'argv',['sync','--league','ADL','--allow-queued']):m.main()
   self.assertEqual(len(calls),2);self.assertEqual(json.loads((root/'data/bonus_mfl_sync_metadata.json').read_text())['status'],'success')
