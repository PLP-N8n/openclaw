import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vigil.vigil_runner import run_vigil_cycle


class VigilRunnerTests(unittest.TestCase):
    def test_run_cycle(self):
        out = run_vigil_cycle(since_hours=24)
        self.assertIn("event", out)
        self.assertIn("rbt", out)
        self.assertIn("top_thorn", out)


if __name__ == "__main__":
    unittest.main()
