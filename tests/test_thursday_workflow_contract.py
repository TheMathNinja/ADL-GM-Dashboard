"""Guard the real Thursday workflow connections, not just the ranking functions."""
import re,unittest,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
class WorkflowContractTests(unittest.TestCase):
 def setUp(self):
  self.league='ADL' if (ROOT/'.github/workflows/refresh_extension_calculator.yml').exists() else 'FAFL'
  self.parent=(ROOT/'.github/workflows'/('refresh_extension_calculator.yml' if self.league=='ADL' else 'refresh.yml')).read_text(encoding='utf8')
  self.child=(ROOT/'.github/workflows/verify_bonus_mfl.yml').read_text(encoding='utf8')
 def test_exact_source_is_uploaded_before_dispatch_and_bound_to_receipt(self):
  names=['Capture exact Bonus Games verification source','Hand off exact Bonus Games verification source','Synchronize and collect official Bonus Games verification','Confirm weekly publication and record processed scores']
  positions=[self.parent.index('- name: '+name) for name in names]
  self.assertEqual(positions,sorted(positions))
  self.assertIn('name: bonus-mfl-source-${{ github.run_id }}',self.parent)
  self.assertIn('overwrite: true',self.parent)
  self.assertIn('name: bonus-mfl-source-${{ inputs.source_run_id }}',self.child)
  self.assertIn('run-id: ${{ inputs.source_run_id }}',self.child)
  self.assertIn('actions: read',self.child)
  self.assertIn('python scripts/verify_bonus_receipt.py --league '+self.league+' --source-snapshot',self.parent)
  self.assertIn('--source-snapshot artifacts/bonus-mfl-source/bonus-mfl-source.json',self.child)
 def test_queued_or_missing_artifact_never_means_complete(self):
  self.assertNotIn('--allow-queued',self.child)
  self.assertIn('if-no-files-found: error',self.child)
  self.assertIn('Require official MFL Bonus Games verification',self.parent)
  self.assertIn('test "$BONUS_MFL_STATUS" = success',self.parent)
  self.assertIn('needs.refresh.result == \'success\'',self.parent)
  self.assertIn('node tests/test_bonus_q3.cjs',self.child)
 def test_q3_dst_and_later_thursday_backup_slots(self):
  from score_corrections import target_week
  self.assertEqual(target_week(datetime(2026,11,12,8,45,tzinfo=timezone.utc),2026),9)
  self.assertIsNone(target_week(datetime(2026,11,12,8,44,tzinfo=timezone.utc),2026))
  workflow=(ROOT/'.github/workflows/poll_score_corrections.yml').read_text()
  # The next UTC day is still Thursday evening in Eastern time.
  for cron in ['30 11 * * 4','0 12 * * 4','30 18 * * 4','30 1 * * 5']:
   self.assertIn("- cron: '"+cron+"'",workflow)
   branch=workflow.split('[ "$OFFSET" = "-0500" ]',1)[1]
   self.assertIn('[ "$SLOT" = "'+cron+'" ]',branch)
 def test_child_failure_reports_are_wired(self):
  workflow=(ROOT/'.github/workflows/email_workflow_failures.yml').read_text()
  self.assertIn('Synchronize MFL Bonus Games',workflow)

if __name__=='__main__':unittest.main()
