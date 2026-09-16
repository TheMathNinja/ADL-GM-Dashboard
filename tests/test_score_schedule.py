import importlib.util
import unittest
from datetime import datetime
from pathlib import Path

spec = importlib.util.spec_from_file_location("schedule", Path(__file__).parents[1] / "scripts/score_schedule.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ScheduleTest(unittest.TestCase):
    def decide(self, when, cron):
        return module.schedule_decision(datetime.fromisoformat(when), 2026, "schedule", cron)

    def test_delayed_tuesday(self):
        self.assertEqual(self.decide("2026-09-15T05:47:00+00:00", "0 5 * * 2")["score_status"], "unofficial")
        self.assertEqual(self.decide("2026-09-15T06:12:00+00:00", "0 6 * * 2")["should_run"], "false")

    def test_thursday_dst(self):
        self.assertEqual(self.decide("2026-09-17T09:28:00+00:00", "0 9 * * 4")["score_status"], "official")
        self.assertEqual(self.decide("2026-11-05T10:17:00+00:00", "0 10 * * 4")["score_status"], "official")
        self.assertEqual(self.decide("2026-11-05T09:17:00+00:00", "0 9 * * 4")["should_run"], "false")

    def test_tuesday_standard_time(self):
        self.assertEqual(self.decide("2026-11-03T06:47:00+00:00", "0 6 * * 2")["score_status"], "unofficial")
        self.assertEqual(self.decide("2026-11-03T05:12:00+00:00", "0 5 * * 2")["should_run"], "false")

    def test_window_and_manual(self):
        self.assertEqual(self.decide("2026-09-08T05:47:00+00:00", "0 5 * * 2")["should_run"], "false")
        self.assertEqual(self.decide("2027-01-12T06:47:00+00:00", "0 6 * * 2")["should_run"], "false")
        result = module.schedule_decision(datetime.fromisoformat("2026-08-01T12:00:00+00:00"), 2026,
                                          "workflow_dispatch", status="unofficial", force=True)
        self.assertEqual(result, dict(should_run="true", score_status="unofficial", force_refresh="TRUE"))


if __name__ == "__main__":
    unittest.main()
