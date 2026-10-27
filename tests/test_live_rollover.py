import base64
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import collect_live_bonus as c


class RolloverTests(unittest.TestCase):
    def receipt(self, league='ADL'):
        return dict(season=2026, week=7, league_id={'ADL':'60206','FAFL':'22686'}[league],
                    status='success', process='corrections', bonus_mfl_verified=True,
                    payouts_verified=True, run_id='123')

    def test_only_verified_current_season_official_receipt_advances_week(self):
        for league in ('ADL', 'FAFL'):
            receipt = self.receipt(league)
            self.assertEqual(c.correction_next_week(receipt, league, 2026, 7, '123'), 8)
            for field, value in [('season',2025),('status','failure'),('process','preliminary'),
                                 ('bonus_mfl_verified',False),('payouts_verified',False),('league_id','other')]:
                invalid = dict(receipt, **{field:value})
                self.assertEqual(c.correction_next_week(invalid, league, 2026), 1)
                with self.assertRaises(ValueError): c.correction_next_week(invalid, league, 2026, 7, '123')
            with self.assertRaises(ValueError): c.correction_next_week(receipt, league, 2026, 7, 'old-run')
            self.assertEqual(c.correction_next_week(dict(receipt, week=12), league, 2026), 13)
            self.assertEqual(c.correction_next_week(dict(receipt, week=17), league, 2026), 13)

    def test_wrong_explicit_week_is_rejected_not_relabelled(self):
        collector = c.Collector('ADL', minimum_week=8)
        with patch.object(collector, 'get', return_value={'week':'7'}) as get:
            with self.assertRaisesRegex(ValueError, 'requested upcoming week'): collector.collect()
            self.assertEqual(get.call_args.args, ('liveScoring', '&DETAILS=1&W=8'))

    def test_preview_week_cannot_be_used_to_publish(self):
        with patch.object(sys, 'argv', ['watch', '--league', 'ADL', '--once', '--preview-week', '8']), \
                patch.object(c, 'publish') as publish, self.assertRaises(SystemExit):
            c.main()
        publish.assert_not_called()

    def test_pregame_rollover_uses_new_lineups_and_corrected_history(self):
        for league in ('ADL', 'FAFL'):
            collector = c.Collector(league, minimum_week=2)
            fs = [dict(id=f'{i:04}', score='0', players={'player':[
                dict(id='new', score='0', status='starter', gameSecondsRemaining='3600')]}) for i in range(1,33)]
            calls = []
            def get(kind, extra='', **kwargs):
                calls.append((kind, extra))
                if kind == 'liveScoring':
                    return dict(week='2', franchise=fs) if '&W=2' in extra else dict(week='1')
                if kind == 'weeklyResults':
                    return dict(week='1', franchise=[dict(id=f['id'], score='123.4', opt_pts='150') for f in fs])
                return {
                    'league':dict(starters=dict(count='1',iop_starters='0',idp_starters='1',position=[dict(name='LB',limit='1')])),
                    'players':dict(player=[dict(id='new',name='Upcoming starter',position='LB',team='DEN')]),
                    'rosters':dict(franchise=[dict(id=f['id'],player=[dict(id='new',status='ROSTER')]) for f in fs]),
                    'projectedScores':dict(week='2',playerScore=[dict(id='new',score='10')]),
                    'playerScores':dict(playerScore=[]),'injuries':dict(injury=[])}[kind]
            no_sim = types.SimpleNamespace(load_model=lambda league:{},add_probabilities=lambda snapshot,model:snapshot)
            with patch.object(collector,'get',side_effect=get), patch.object(collector,'scoring_details',return_value={}), \
                    patch.object(collector,'game_states',return_value={'DEN':dict(state='pre',kickoff=1)}), \
                    patch.object(c,'load_calibration',return_value={}), patch.dict(sys.modules,{'live_win_probability':no_sim}):
                result = collector.collect()
            self.assertEqual((result['week'],result['sourceWeek']), (2,2))
            self.assertEqual(result['completed'][0]['teams'][0]['score'],123.4)
            self.assertEqual(result['teams'][0]['score'],0)
            self.assertEqual(result['teams'][0]['starters'][0]['name'],'Upcoming starter')
            self.assertIn(('projectedScores','&W=2'),calls)
            self.assertIn(('injuries','&W=2'),calls)

    def test_no_backward_week_or_timestamp_or_postseason_regression(self):
        old=dict(league='ADL',season=2026,week=8,fetchedAt='2026-10-29T14:00:00Z')
        self.assertFalse(c.snapshot_advances(old,dict(old,week=7,fetchedAt='2026-10-29T15:00:00Z')))
        self.assertFalse(c.snapshot_advances(old,dict(old,fetchedAt='2026-10-29T13:00:00Z')))
        self.assertTrue(c.snapshot_advances(old,dict(old,week=9)))
        self.assertFalse(c.snapshot_advances(dict(old,complete=True),old))
        self.assertTrue(c.snapshot_advances(old,dict(old,season=2027,week=1)))

    def test_branch_guard_prevents_a_late_worker_overwriting_rollover(self):
        old=dict(league='ADL',season=2026,week=8,fetchedAt='2026-10-29T14:00:00Z')
        calls=[]
        def api(path,token,method='GET',data=None):
            calls.append(method)
            if '/git/ref/' in path:return {'object':{'sha':'head'}}
            if '/git/blobs' in path:return {'sha':'blob'}
            if '/contents/watch-state.json' in path:return {'content':base64.b64encode(json.dumps(old).encode()).decode()}
            raise AssertionError(path)
        with patch.object(c,'github',side_effect=api):
            c.publish('owner/repo','token',dict(old,week=7,fetchedAt='2026-10-29T15:00:00Z'))
        self.assertNotIn('PATCH',calls)

    def test_newer_correction_beats_a_later_scrape_from_old_worker(self):
        current=dict(league='ADL',season=2026,week=8,fetchedAt='2026-10-29T14:00:00Z',
                     officialCorrectionWeek=7,officialCorrectionAt='2026-10-29T13:00:00Z')
        stale=dict(current,fetchedAt='2026-10-29T15:00:00Z',officialCorrectionWeek=6)
        self.assertFalse(c.snapshot_advances(current,stale))
        stale=dict(current,fetchedAt='2026-10-29T15:00:00Z',officialCorrectionAt='2026-10-29T12:00:00Z')
        self.assertFalse(c.snapshot_advances(current,stale))
        self.assertTrue(c.snapshot_advances(current,dict(current,fetchedAt='2026-10-29T15:00:00Z')))

    def test_eastern_window_matches_frontend_fixture(self):
        for iso, expected in json.loads((Path(__file__).parent/'fixtures/live_watch_windows.json').read_text()):
            self.assertEqual(c.window(dt.datetime.fromisoformat(iso)), expected, iso)


if __name__=='__main__': unittest.main()
