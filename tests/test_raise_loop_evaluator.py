import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning.raise_loop import build_proposals


class RaiseLoopEvaluatorTests(unittest.TestCase):
    def test_proposals_include_evaluator(self):
        clusters = [
            {
                "category": "retry_storm",
                "count": 6,
                "evidence": ["a@t1", "b@t2"],
                "severity_hint": "med",
                "events": [],
            }
        ]
        proposals = build_proposals(clusters, {"weights": {"impact": 0.6, "risk": 0.4}, "impact_saturation": 12})
        self.assertEqual(len(proposals), 1)
        self.assertIn("evaluator", proposals[0])
        self.assertIn("approved", proposals[0]["evaluator"])


if __name__ == "__main__":
    unittest.main()
