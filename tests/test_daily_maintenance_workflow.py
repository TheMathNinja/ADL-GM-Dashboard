from pathlib import Path
import unittest


WORKFLOW = Path(__file__).parents[1] / '.github' / 'workflows' / 'daily_adl_league_maintenance.yml'


class DailyMaintenanceWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW.read_text(encoding='utf-8')

    def test_commissioner_jobs_run_in_their_own_repository(self):
        self.assertNotIn(
            'uses: TheMathNinja/ADL-Commissioner-Dashboard/.github/workflows/',
            self.text,
        )
        for workflow in (
            'update_dashboard.yml',
            'waiver-cap-corrections.yml',
            'daily-commissioner-alerts.yml',
        ):
            self.assertIn(f'gh workflow run {workflow}', self.text)
            self.assertIn(f'--workflow {workflow}', self.text)

    def test_each_remote_run_is_correlated_and_must_succeed(self):
        self.assertEqual(self.text.count('-f orchestrator_run_id="${GITHUB_RUN_ID}"'), 3)
        self.assertEqual(self.text.count('gh run watch "${run_id}"'), 3)
        self.assertEqual(self.text.count('--exit-status'), 3)

    def test_only_dispatch_token_crosses_repository_boundary(self):
        # The one inherited-secret use is the local GM roster workflow.
        self.assertEqual(self.text.count('secrets: inherit'), 1)
        self.assertEqual(
            self.text.count('GH_TOKEN: ${{ secrets.ADL_GITHUB_WORKFLOW_TOKEN }}'),
            3,
        )


if __name__ == '__main__':
    unittest.main()
