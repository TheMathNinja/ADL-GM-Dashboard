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
        self.receipt = dict(season=2026, week=3, league_id='60206', status='success',
                            process='preliminary', run_id='123',
                            triggered_at='2026-09-29T04:30:05+00:00')
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
        with patch.object(m, 'get_json', side_effect=api), patch.object(m, 'document', return_value=self.baseline), patch.object(m, 'mfl', return_value=self.feed):
            return m.published('ADL', self.receipt)

    def test_both_leagues_required_for_preliminary(self):
        self.assertIsNone(m.choose_receipts('preliminary', {'ADL': {'preliminary': self.receipt}, 'FAFL': {}}))

    def test_correction_can_use_unchanged_other_league(self):
        correction = dict(self.receipt, process='corrections')
        chosen = m.choose_receipts('corrections', {'ADL': {'corrections': correction}, 'FAFL': {'preliminary': self.receipt}})
        self.assertEqual(chosen['FAFL']['process'], 'preliminary')

    def test_wrong_week_or_failed_receipt_holds(self):
        for other in [dict(self.receipt, week=2), dict(self.receipt, status='failure')]:
            self.assertIsNone(m.choose_receipts('preliminary', {'ADL': {'preliminary': self.receipt}, 'FAFL': {'preliminary': other}}))

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
        self.assertIn('01:00:00 AM EST', m.local_time('2026-11-12T06:00:00Z'))

    def test_manual_run_does_not_invent_scrape_trigger(self):
        self.receipt['triggered_at'] = ''
        _, body = m.message('preliminary', [self.verify()])
        self.assertIn('no MFL-check trigger', body)

    def test_recipient_is_single_and_no_cc(self):
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
        with patch.dict(os.environ, dict(env, WEEKLY_REPORT_EMAIL_TO='one@example.com,two@example.com')):
            with self.assertRaises(ValueError): m.send_email('Report', 'Body', 'key')

    def test_sent_pair_is_not_sent_again(self):
        fafl = dict(self.receipt, league_id='22686', run_id='456')
        chosen = {'ADL': self.receipt, 'FAFL': fafl}
        key = m.report_key('preliminary', [dict(league=l, receipt=r) for l, r in chosen.items()])
        def doc(repo, path):
            if path == m.STATE_PATH: return {'sent': {key: {}}}
            if path.endswith('corrections.json'): return None
            return self.receipt if 'ADL-' in repo else fafl
        with patch.dict(os.environ, {'GITHUB_REPOSITORY': 'TheMathNinja/ADL-GM-Dashboard'}), patch.object(sys, 'argv', ['report']), \
                patch.object(m, 'document', side_effect=doc), patch.object(m, 'send_email') as send, patch.object(m, 'published') as live:
            m.main()
            send.assert_not_called()
            live.assert_not_called()


if __name__ == '__main__':
    unittest.main()
