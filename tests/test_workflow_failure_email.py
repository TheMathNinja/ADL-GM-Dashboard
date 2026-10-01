import copy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import email_workflow_failures as m


class FailureReports(unittest.TestCase):
    def setUp(self):
        self.run = dict(id=1, run_attempt=1, workflow_id=10, path='.github/workflows/refresh.yml',
                        head_branch='main', event='workflow_dispatch', status='completed', conclusion='failure',
                        name='Refresh FAFL Weekly System', html_url='https://github.com/test/runs/1',
                        created_at='2026-10-01T14:00:00Z', updated_at='2026-10-01T14:10:00Z')
        self.jobs = [dict(name='refresh', conclusion='failure', steps=[
            dict(name='Enter and verify official Bonus Games in MFL', conclusion='failure')])]

    def test_production_not_research_or_pr(self):
        self.assertTrue(m.production(self.run))
        self.assertIsNone(m.production(dict(self.run, path='.github/workflows/evaluate_playoff_model.yml')))
        self.assertIsNone(m.production(dict(self.run, event='pull_request')))
        self.assertIsNone(m.production(dict(self.run, head_branch='test')))

    def test_continued_failure_is_not_hidden_by_success(self):
        self.assertIn('Bonus Games', m.failures(dict(self.run, conclusion='success'), self.jobs)[0])
        self.assertEqual(m.failures(dict(self.run, conclusion='success'), []), [])
        self.assertTrue(m.failures(dict(self.run, conclusion='timed_out'), []))

    def test_report_impact_and_recovery(self):
        subject, body = m.message(m.REPOS[1], self.run, m.production(self.run), m.failures(self.run, self.jobs), self.run)
        self.assertIn('FAILED', subject)
        self.assertIn('Bonus Games', body)
        self.assertIn('later run', body)
        self.assertIn(m.OWNER, body)

    def exercise(self, state=None, dry=False, send_error=None):
        state = state or {'sent': {}, 'checked': {}}
        with patch.dict(os.environ, {'WEEKLY_REPORT_EMAIL_TO': m.OWNER, 'GITHUB_REPOSITORY': m.REPOS[2]}), \
             patch.object(sys, 'argv', ['report'] + (['--dry-run'] if dry else [])), \
             patch.object(m, 'REPOS', [m.REPOS[1]]), \
             patch.object(m, 'runs', return_value=[self.run]), \
             patch.object(m, 'jobs', return_value=self.jobs), \
             patch.object(m.mail, 'document', return_value=state), \
             patch.object(m.mail, 'send_email', side_effect=send_error) as send, \
             patch.object(m, 'save') as save:
            if send_error:
                with self.assertRaises(RuntimeError):
                    m.main()
            else:
                m.main()
            return state, send.call_count, save.call_count

    def test_send_once_and_dry_run_does_not_acknowledge(self):
        state, count, _ = self.exercise(dry=True)
        self.assertEqual(count, 0)
        self.assertFalse(state['sent'])
        state, count, _ = self.exercise()
        self.assertEqual(count, 1)
        _, count, _ = self.exercise(state)
        self.assertEqual(count, 0)

    def test_failed_smtp_is_retried_not_recorded_as_sent(self):
        state, _, saved = self.exercise(send_error=RuntimeError('SMTP unavailable'))
        self.assertFalse(state['sent'])
        self.assertEqual(saved, 0)

    def test_wrong_recipient_rejected_before_any_scan(self):
        with patch.dict(os.environ, {'WEEKLY_REPORT_EMAIL_TO': 'someone@example.com'}), \
             patch.object(sys, 'argv', ['report']), patch.object(m, 'runs') as scan:
            with self.assertRaises(ValueError):
                m.main()
            scan.assert_not_called()

    def test_successful_retry_preserves_original_failed_attempt(self):
        earlier = copy.deepcopy(self.run)
        self.run.update(run_attempt=2, conclusion='success', updated_at='2026-10-01T15:00:00Z')
        with patch.dict(os.environ, {'WEEKLY_REPORT_EMAIL_TO': m.OWNER, 'GITHUB_REPOSITORY': m.REPOS[2]}), \
             patch.object(sys, 'argv', ['report']), patch.object(m, 'REPOS', [m.REPOS[1]]), \
             patch.object(m, 'runs', return_value=[self.run]), patch.object(m, 'api', return_value=earlier), \
             patch.object(m, 'jobs', side_effect=[self.jobs, []]), \
             patch.object(m.mail, 'document', return_value=None), \
             patch.object(m.mail, 'send_email') as send, patch.object(m, 'save'):
            m.main()
            self.assertEqual(send.call_count, 1)
            self.assertIn('later run', send.call_args.args[1])
            self.assertTrue(send.call_args.args[2].endswith(':1:1'))

    def test_pagination_does_not_miss_older_failures(self):
        with patch.object(m, 'api', side_effect=[{'workflow_runs': [self.run] * 100}, {'workflow_runs': [self.run]}]):
            self.assertEqual(len(list(m.runs(m.REPOS[1]))), 101)


if __name__ == '__main__':
    unittest.main()
