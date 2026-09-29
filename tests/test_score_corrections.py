import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import score_corrections as m


class CorrectionsTest(unittest.TestCase):
    def setUp(self):
        self.feed = {'week': '3', 'playerScore': [
            {'id': '001', 'score': '10.50', 'isAvailable': '1'},
            {'id': '002', 'score': '0'}]}
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.enterContext(patch.object(m, 'BASELINE', Path(self.tmp.name) / 'baseline.json'))
        self.enterContext(patch.object(m, 'CAPTURE', Path(self.tmp.name) / 'capture.json'))
        self.enterContext(patch.dict(os.environ, {
            'CURRENT_SEASON': '2026', 'LEAGUE_ID': '60206',
            'GITHUB_REPOSITORY': 'owner/repo', 'WORKER_WORKFLOW': 'refresh.yml',
            'GH_TOKEN': 'test-only'}))

    def snap(self, feed=None):
        return m.snapshot(feed or self.feed, 2026, '60206', 3)

    def baseline(self):
        m.BASELINE.write_text(json.dumps(dict(season=2026, league_id='60206', weeks={'3': self.snap()})))

    def run_poll(self, runs=(), ready=True, dry=False):
        args = ['check', '--week', '3'] + (['--dry-run'] if dry else [])
        with patch.object(sys, 'argv', args), patch.object(m, 'mfl', return_value=self.feed), \
                patch.object(m, 'validate', return_value=(ready, 'test')), \
                patch.object(m, 'request', return_value={'workflow_runs': list(runs)}) as api:
            m.main()
            return api.call_args_list

    def test_et_window_and_dst(self):
        for time, week in [
            ('2026-10-01T07:44:00+00:00', None), ('2026-10-01T07:45:00+00:00', 3),
            ('2026-10-02T03:59:00+00:00', 3), ('2026-10-02T04:00:00+00:00', None),
            ('2026-11-12T08:44:00+00:00', None), ('2026-11-12T08:45:00+00:00', 9),
            ('2026-09-10T08:45:00+00:00', None), ('2027-01-07T08:45:00+00:00', 17),
            ('2027-01-14T08:45:00+00:00', None), ('2026-09-29T08:45:00+00:00', None)]:
            self.assertEqual(m.target_week(datetime.fromisoformat(time), 2026), week, time)

    def test_order_metadata_and_format_do_not_trigger(self):
        before = self.snap()
        self.feed['playerScore'].reverse()
        self.feed['playerScore'][1].update(score='10.500', isAvailable='0')
        self.assertEqual(before, self.snap())

    def test_any_player_change_detected(self):
        before = self.snap()
        self.feed['playerScore'][1]['score'] = '-0.1'
        self.assertEqual(m.changed_players(before, self.snap()), ['002'])

    def test_added_and_removed_players(self):
        before = self.snap()
        self.feed['playerScore'][1]['id'] = '003'
        self.assertEqual(m.changed_players(before, self.snap()), ['002', '003'])

    def test_invalid_feeds(self):
        for edit in [dict(week='2'), dict(playerScore=[]),
                     dict(playerScore=[{'id': '1', 'score': 'NaN'}]),
                     dict(playerScore=[{'id': '1', 'score': '2'}] * 2)]:
            with self.assertRaises(ValueError):
                self.snap({**self.feed, **edit})

    def test_no_change_skips_worker(self):
        self.baseline()
        self.assertEqual(self.run_poll(), [])

    def test_missing_baseline_refreshes_not_silently_adopts(self):
        calls = self.run_poll()
        self.assertEqual(len(calls), 2)
        self.assertFalse(m.BASELINE.exists())
        self.assertEqual(calls[1].args[1]['inputs']['score_status'], 'official')

    def test_changed_score_dispatches_same_week(self):
        self.baseline()
        self.feed['playerScore'][1]['score'] = '1'
        calls = self.run_poll()
        self.assertEqual(calls[1].args[1]['inputs']['ready_week'], '3')
        self.assertEqual(calls[1].args[1]['inputs']['score_revision'], self.snap()['digest'])

    def test_in_progress_suppresses_and_failed_retries(self):
        self.assertEqual(len(self.run_poll([dict(status='in_progress')])), 1)
        self.assertEqual(len(self.run_poll([dict(status='completed', conclusion='failure')]*100)), 2)

    def test_successful_old_revision_does_not_block_new_change(self):
        self.assertEqual(len(self.run_poll([dict(status='completed', conclusion='success')])), 2)

    def test_dry_run_and_unreconciled_feeds_do_not_dispatch(self):
        self.assertEqual(self.run_poll(dry=True), [])
        self.assertEqual(self.run_poll(ready=False), [])

    def test_completion_acknowledges_processed_snapshot(self):
        with patch.object(m, 'mfl', return_value=self.feed):
            m.capture(2026, '60206', 3)
            m.complete(2026, '60206', 3)
        self.assertEqual(m.load_baseline(2026, '60206')['weeks']['3'], self.snap())
        self.assertEqual(self.run_poll(), [])

    def test_midrun_change_not_acknowledged(self):
        with patch.object(m, 'mfl', return_value=self.feed):
            m.capture(2026, '60206', 3)
            self.feed['playerScore'][0]['score'] = '11'
            with self.assertRaises(ValueError):
                m.complete(2026, '60206', 3)
        self.assertFalse(m.BASELINE.exists())

    def test_other_league_or_season_baseline_ignored(self):
        self.baseline()
        self.assertEqual(m.load_baseline(2025, '60206')['weeks'], {})
        self.assertEqual(m.load_baseline(2026, '22686')['weeks'], {})

    def test_reversion_is_a_change(self):
        original = self.snap()
        self.feed['playerScore'][1]['score'] = '1'
        corrected = self.snap()
        self.assertEqual(m.changed_players(corrected, original), ['002'])


if __name__ == '__main__':
    unittest.main()
