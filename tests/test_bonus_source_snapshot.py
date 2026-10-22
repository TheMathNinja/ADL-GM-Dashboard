import copy, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from bonus_source_snapshot import validate_snapshot, request_body, reports_digest
from verify_bonus_receipt import validate_bonus_receipt
import score_readiness
from test_bonus_receipt import bonus_receipt


def fixture(league='ADL',week=9):
    reports={key:{f'{i:04}':[float(i+w) for w in range(week)] for i in range(1,33)} for key in ['TPF','PPF']}
    return dict(version=1,league=league,season=2026,week=week,run_id='123',reports=reports,reports_sha256=reports_digest(reports))

class SourceTests(unittest.TestCase):
    def test_both_leagues_quarter_boundaries_and_preview(self):
        for league in ['ADL','FAFL']:
            for week in [3,6,9,12,17]:
                s=fixture(league,week);self.assertEqual(validate_snapshot(s,league,2026,week,'123'),s['reports'])
                body=request_body(s);ack=bonus_receipt(week,'123',league);ack['source_sha256']=body['source_sha256']
                validate_bonus_receipt(ack,league,2026,week,'123',body['source_sha256'])
                self.assertNotEqual(request_body(s,'preview')['source_sha256'],body['source_sha256'])
    def test_prior_main_snapshot_cannot_substitute_for_fresh_parent(self):
        for edit in [dict(week=8),dict(league='FAFL'),dict(season=2025),dict(run_id='122')]:
            with self.assertRaises(ValueError):validate_snapshot({**fixture(),**edit},'ADL',2026,9,'123')
    def test_missing_team_week_nonfinite_and_tampering_rejected(self):
        for kind in ['team','week','nan','bool','tamper']:
            s=fixture()
            if kind=='team':del s['reports']['TPF']['0032']
            elif kind=='week':s['reports']['TPF']['0001'].pop()
            elif kind=='nan':s['reports']['TPF']['0001'][0]=float('nan')
            elif kind=='bool':s['reports']['TPF']['0001'][0]=True
            else:s['reports']['TPF']['0001'][0]+=1
            with self.assertRaises(ValueError):validate_snapshot(s,'ADL',2026,9,'123')
    def test_old_score_receipt_cannot_satisfy_parent(self):
        s=fixture();ack=bonus_receipt(9);ack['source_sha256']=request_body(s)['source_sha256']
        s['reports']['TPF']['0001'][8]+=0.1;s['reports_sha256']=reports_digest(s['reports'])
        with self.assertRaises(ValueError):validate_bonus_receipt(ack,'ADL',2026,9,'123',request_body(s)['source_sha256'])
    def test_request_checksum_is_order_independent(self):
        s=fixture();reordered=json.loads(json.dumps(s,sort_keys=True))
        self.assertEqual(request_body(s),request_body(reordered))
    def test_official_completion_cannot_be_recorded_without_q3_readback(self):
        for league,lid in [('ADL','60206'),('FAFL','22686')]:
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as tmp:
                root=Path(tmp);(root/'data').mkdir()
                env=dict(CURRENT_SEASON='2026',LEAGUE_ID=lid,READY_WEEK='9',GITHUB_RUN_ID='123',SCORE_STATUS='official',REFRESH_PROCESS='corrections')
                with patch.object(score_readiness,'ROOT',root),patch.dict(os.environ,env),patch.object(sys,'argv',['check','--complete']):
                    with self.assertRaises(OSError):score_readiness.main()
                    self.assertFalse((root/'data/preliminary_refresh_complete.json').exists())
                    ack=bonus_receipt(9,'123',league);ack['results'].pop()
                    (root/'data/bonus_mfl_sync_metadata.json').write_text(json.dumps(ack))
                    with self.assertRaises(ValueError):score_readiness.main()
                    self.assertFalse((root/'data/refresh_receipts/corrections.json').exists())
                    (root/'data/bonus_mfl_sync_metadata.json').write_text(json.dumps(bonus_receipt(9,'123',league)))
                    score_readiness.main()
                    done=json.loads((root/'data/refresh_receipts/corrections.json').read_text())
                    self.assertTrue(done['bonus_mfl_verified']);self.assertEqual(done['week'],9)

if __name__=='__main__':unittest.main()
