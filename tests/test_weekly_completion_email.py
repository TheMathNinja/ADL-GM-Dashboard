import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import email_weekly_completion as m


class CompletionEmailTest(unittest.TestCase):
    def setUp(self):
        self.receipt = dict(payouts_verified=True, season=2026, week=3, league_id='60206', status='success',
                            process='preliminary', run_id='123',
                            triggered_at='2026-09-29T04:30:05+00:00')
        self.payout = dict(status='success', run_id='123', through_week=3, season=2026, league='ADL', logos=dict(status='success',run_id='123'))
        self.run = dict(status='completed', conclusion='success', created_at='2026-09-29T04:30:06Z', html_url='https://github.com/example/run/123')
        self.marker = dict(run_id='123', season=2026, week=3)
        self.job = dict(status='completed', conclusion='success', started_at='2026-09-29T04:31:00Z', completed_at='2026-09-29T04:40:00Z')
        self.feed = dict(week='3', playerScore=[dict(id='1', score='4')])
        self.baseline = dict(season=2026, league_id='60206', weeks={'3': m.snapshot(self.feed, 2026, '60206', 3)})

    def verify(self, active=False):
        def api(url):
            if '/workflows/' in url: return {'workflow_runs': [dict(status='in_progress')] if active else []}
            if '/jobs?' in url: return {'jobs': [self.job]}
            if 'weekly-refresh-status' in url: return self.marker
            return self.run
        with patch.object(m, 'get_json', side_effect=api), patch.object(m, 'document', side_effect=lambda repo, path: self.payout if path.endswith('payouts_sync_metadata.json') else self.baseline), patch.object(m, 'mfl', return_value=self.feed):
            return m.published('ADL', self.receipt)

    def test_both_leagues_required_for_preliminary(self):
        self.assertIsNone(m.choose_receipts('preliminary', {'ADL': {'preliminary': self.receipt}, 'FAFL': {}}))

    def test_correction_requires_official_other_league(self):
        correction = dict(self.receipt, process='corrections')
        chosen = m.choose_receipts('corrections', {'ADL': {'corrections': correction}, 'FAFL': {'preliminary': self.receipt}})
        self.assertIsNone(chosen)

    def test_wrong_week_or_failed_receipt_holds(self):
        for other in [dict(self.receipt, week=2), dict(self.receipt, status='failure')]:
            self.assertIsNone(m.choose_receipts('preliminary', {'ADL': {'preliminary': self.receipt}, 'FAFL': {'preliminary': other}}))

    def test_missing_or_stale_payouts_hold_email(self):
        self.payout['run_id'] = 'old'
        self.assertIsNone(self.verify())
        self.payout['run_id'] = '123'
        self.payout['logos']['status'] = 'failure'
        self.assertIsNone(self.verify())
        self.payout['logos']['status'] = 'success'
        self.receipt.pop('payouts_verified')
        self.assertIsNone(self.verify())

    def test_unverified_mfl_entries_hold_correction_email(self):
        self.receipt.update(process='corrections',bonus_mfl_verified=False)
        self.assertIsNone(self.verify())

    def test_success_and_live_site_pass(self):
        self.assertEqual(self.verify()['finished'], self.job['completed_at'])

    def test_running_or_failed_workflow_holds(self):
        self.assertIsNone(self.verify(active=True))
        self.run['conclusion'] = 'failure'
        self.assertIsNone(self.verify())

    def test_old_or_missing_deployment_holds(self):
        self.marker['run_id'] = '122'
        self.assertIsNone(self.verify())
        self.marker = None
        self.assertIsNone(self.verify())

    def test_unprocessed_correction_holds(self):
        self.feed['playerScore'][0]['score'] = '5'
        self.assertIsNone(self.verify())

    def test_unfinished_job_holds(self):
        self.job['status'] = 'in_progress'
        self.assertIsNone(self.verify())

    def test_eastern_time_and_duration(self):
        result = self.verify()
        _, body = m.message('preliminary', [result])
        self.assertIn('12:30:05 AM EDT', body)
        self.assertIn('9.0 minutes', body)
        self.assertNotIn('\nADL\n', body)
        self.assertNotIn('Shiny hosting delays', body)
        self.assertIn('01:00:00 AM EST', m.local_time('2026-11-12T06:00:00Z'))

    def test_manual_run_does_not_invent_scrape_trigger(self):
        self.receipt['triggered_at'] = ''
        _, body = m.message('preliminary', [self.verify()])
        self.assertIn('no MFL-check trigger', body)

    def test_recipient_list_and_no_cc(self):
        env = dict(WEEKLY_REPORT_EMAIL_TO='owner@example.com', ADL_ALERT_EMAIL_FROM='Sender <sender@example.com>',
                   ADL_SMTP_SERVER='smtp://smtp.example.com:587', ADL_SMTP_USERNAME='user', ADL_SMTP_PASSWORD='test-only')
        with patch.dict(os.environ, env), patch.object(m.smtplib, 'SMTP') as factory:
            m.send_email('Report', 'Body', 'key')
            smtp = factory.return_value.__enter__.return_value
            smtp.starttls.assert_called_once()
            call = smtp.send_message.call_args
            self.assertEqual(call.kwargs['to_addrs'], ['owner@example.com'])
            self.assertIsNone(call.args[0]['Cc'])
            self.assertIsNone(call.args[0]['Bcc'])
        with patch.dict(os.environ, env), patch.object(m.smtplib, 'SMTP') as factory:
            m.send_email('Report', 'Body', 'key', 'one@example.com,two@example.com')
            call = factory.return_value.__enter__.return_value.send_message.call_args
            self.assertEqual(call.kwargs['to_addrs'], ['one@example.com', 'two@example.com'])

    def test_sent_pair_is_not_sent_again(self):
        fafl = dict(self.receipt, league_id='22686', run_id='456')
        chosen = {'ADL': self.receipt, 'FAFL': fafl}
        keys = {m.report_key('preliminary', [dict(league=l, receipt=r)]) for l, r in chosen.items()}
        def doc(repo, path):
            if path == m.STATE_PATH: return {'sent': {key: {} for key in keys}}
            if path.endswith('corrections.json'): return None
            return self.receipt if 'ADL-' in repo else fafl
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'TheMathNinja/ADL-GM-Dashboard'}), patch.object(sys, 'argv', ['report']), \
                patch.object(m, 'document', side_effect=doc), patch.object(m, 'maybe_send_gotw'), \
                patch.object(m, 'send_email') as send, patch.object(m, 'published') as live:
            m.main()
            send.assert_not_called()
            live.assert_not_called()

    def test_correction_message_lists_material_impacts(self):
        result = self.verify()
        result['receipt'] = dict(result['receipt'], process='corrections')
        result['impact'] = dict(run_id='123', week=3,
            ext_pr=[dict(player='James Conner', position='RB', old_score=12, new_score=13, old_rank=7, new_rank=6)],
            all_play=[dict(franchise='Carolina Panthers', old_wins=13, new_wins=12)],
            bonus_games=[dict(franchise='Carolina Panthers', event='Q1', old_result='T', new_result='L')])
        subject, body = m.message('corrections', [result])
        self.assertIn('ADL 2026 Week 3', subject)
        self.assertIn('Week 3 ADL EXT PR changes (rostered, eligible players only)', body)
        self.assertIn('RB7 to RB6', body)
        self.assertIn('Week 3 All-Play changes', body)
        self.assertIn('CAR correction: 13 to 12 APW.', body)
        self.assertIn('Q1 Bonus Game changed from T to L', body)

    def test_correction_message_rejects_stale_equal_score_pr_change(self):
        result = self.verify()
        result['receipt'] = dict(result['receipt'], process='corrections')
        result['impact'] = dict(run_id='123', week=3,
            ext_pr=[dict(player='Nolan Smith', position='DE', old_score=8.6, new_score=8.6,
                         old_rank=42, new_rank=43)],
            all_play=[], bonus_games=[])
        _, body = m.message('corrections', [result])
        self.assertNotIn('Nolan Smith', body)
        self.assertIn('No EXT PR', body)

    def test_other_week_corrections_render_at_bottom(self):
        result = self.verify()
        result['receipt'] = dict(result['receipt'], process='corrections')
        result['impact'] = dict(run_id='123', week=4, ext_pr=[], all_play=[], bonus_games=[],
            other_weeks=[dict(week=2, ext_pr=[], all_play=[dict(
                franchise='New York Giants', old_wins=27, new_wins=26)])])
        _, body = m.message('corrections', [result])
        self.assertIn('Corrections outside the current week', body)
        self.assertIn('Week 2 All-Play changes', body)
        self.assertIn('NYG correction: 27 to 26 APW.', body)

    def test_game_of_week_ranking_and_message(self):
        swing=[];elo=[];franchises=[]
        for i in range(32):
            name=f'Team {i+1}'
            elo.append(dict(week='4',franchise_name=name,elo=str(1600-i)))
            franchises.append(dict(id=f'{i+1:04}',h2hw='3',h2hl='1',h2ht='0'))
        for game in range(16):
            a=2*game;b=a+1
            swing.append(dict(season='2026',through_week='4',target_week='5',
                team_a_id=f'{a+1:04}',team_a=f'Team {a+1}',team_b_id=f'{b+1:04}',team_b=f'Team {b+1}',
                team_a_playoff_if_win='70',team_a_playoff_if_loss='50',team_b_playoff_if_win='60',team_b_playoff_if_loss='50',
                team_a_swing=str(20-game/2),team_b_swing='10',combined_swing=str(30-game/2)))
        week,candidates=m.gotw_candidates('ADL',swing,elo,dict(franchise=franchises))
        self.assertEqual(week,5)
        self.assertEqual(candidates[0]['team_a'],'Team 1')
        subject,body=m.gotw_message(2026,5,{'ADL':candidates,'FAFL':candidates})
        self.assertIn('Week 5',subject)
        self.assertIn('Playoff Percentage Points Up For Grabs: 30.0 (#1 of 16)',body)
        self.assertIn('Blurb:',body)

    def test_game_of_week_is_sent_only_once(self):
        state={'sent': {'gotw:2026:5': {}}}
        with patch.object(m, 'csv_document') as csv_rows, patch.object(m, 'mfl'), \
                patch.object(m, 'gotw_candidates', return_value=(5, [])), patch.object(m, 'send_email') as send:
            csv_rows.return_value=[{'season':'2026','through_week':'4','target_week':'5'}]
            self.assertFalse(m.maybe_send_gotw(state))
            send.assert_not_called()

    def test_missing_league_dispatches_calculation_only_repair(self):
        state={'sent': {}}
        swing=[{'season':'2026','through_week':'4','target_week':'5'}]
        elo=[{'week':'4','franchise_name':'Team 1','elo':'1500'}]
        def rows(repo, path):
            if 'ADL-' in repo: return swing if path.endswith('playoff_swing.csv') else elo
            return []
        with patch.object(m, 'csv_document', side_effect=rows), \
                patch.object(m, 'ensure_swing_refresh') as repair:
            self.assertFalse(m.maybe_send_gotw(state))
            repair.assert_called_once_with('FAFL', 4)

    def test_lagging_league_dispatches_only_that_repair(self):
        state={'sent': {}}
        def rows(repo, path):
            through = '4' if 'ADL-' in repo else '3'
            if path.endswith('playoff_swing.csv'):
                return [{'season':'2026','through_week':through,'target_week':str(int(through)+1)}]
            return [{'week':through,'franchise_name':'Team 1','elo':'1500'}]
        with patch.object(m, 'csv_document', side_effect=rows), \
                patch.object(m, 'ensure_swing_refresh') as repair:
            self.assertFalse(m.maybe_send_gotw(state))
            repair.assert_called_once_with('FAFL', 4)

    def test_active_repair_is_not_dispatched_twice(self):
        runs={'workflow_runs':[{'status':'in_progress','display_title':'FAFL manual preview'}]}
        with patch.object(m, 'orchestration_json', return_value=runs) as api:
            self.assertFalse(m.ensure_swing_refresh('FAFL', 4))
            self.assertEqual(api.call_count, 1)


if __name__ == '__main__':
    unittest.main()
