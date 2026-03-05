import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from reports.daily_autonomy_report import collect_kpis, render_text_report, write_daily_report


class DailyAutonomyReportTests(unittest.TestCase):
    def test_report_functions(self):
        kpis = collect_kpis()
        for key in [
            "pass_at_2",
            "mttr_minutes",
            "msv_hold_rate",
            "token_usage",
            "pending_clarifications",
            "top_failures",
            "top_improvements",
            "spend_governor_summary",
        ]:
            self.assertIn(key, kpis)

        txt = render_text_report(kpis)
        self.assertIn("Daily Autonomy Report", txt)

        with tempfile.TemporaryDirectory() as td:
            out = write_daily_report(kpis, td)
            self.assertTrue(Path(out).exists())


if __name__ == "__main__":
    unittest.main()
