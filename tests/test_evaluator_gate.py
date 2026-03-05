import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning.evaluator_gate import evaluator_gate, load_constitution


class EvaluatorGateTests(unittest.TestCase):
    def test_gate_approve(self):
        c = {
            "summary": "retry storm recurring",
            "recommended_change": "tighten retry policy",
            "evidence": ["ref-1"],
            "risk": "med",
        }
        ok, reason, scores = evaluator_gate(c, load_constitution())
        self.assertTrue(ok, reason)
        self.assertGreater(scores["total_score"], 0.0)

    def test_gate_reject_no_evidence(self):
        c = {
            "summary": "retry storm recurring",
            "recommended_change": "tighten retry policy",
            "evidence": [],
            "risk": "med",
        }
        ok, reason, _ = evaluator_gate(c, load_constitution())
        self.assertFalse(ok)
        self.assertIn("evidence", reason)


if __name__ == "__main__":
    unittest.main()
