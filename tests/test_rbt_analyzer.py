import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vigil.rbt_analyzer import classify_rbt, extract_patterns


class RBTAnalyzerTests(unittest.TestCase):
    def test_classify_and_extract(self):
        events = [
            {"event": "maintenance_run", "status": "OK", "task": "health-snapshot"},
            {"event": "maintenance_failure", "status": "FAIL", "task": "backup-rotate", "exit_code": 1},
            {"event": "maintenance_failure", "status": "FAIL", "task": "backup-rotate", "exit_code": 1},
            {"event": "maintenance_failure", "status": "FAIL", "task": "backup-rotate", "exit_code": 1},
            {"event": "maintenance_failure", "status": "FAIL", "task": "backup-rotate", "exit_code": 1},
            {"event": "maintenance_failure", "status": "FAIL", "task": "backup-rotate", "exit_code": 1},
        ]
        patterns = extract_patterns(events)
        self.assertTrue(any(p["pattern"].startswith("task:") for p in patterns))
        rbt = classify_rbt(events)
        self.assertIn("roses", rbt)
        self.assertIn("buds", rbt)
        self.assertIn("thorns", rbt)
        self.assertTrue(any(t["severity"] == "high" for t in rbt["thorns"]))


if __name__ == "__main__":
    unittest.main()
