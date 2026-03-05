import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from actions.oap_router import to_oap, validate_oap, reject_non_actionable


class OAPRouterTests(unittest.TestCase):
    def test_oap_flow(self):
        insight = {
            "summary": "reduce retry storm",
            "recommended_change": "tighten retries",
            "risk": "high",
            "evidence": ["ref1"],
            "confidence": 0.8,
        }
        oap = to_oap(insight)
        self.assertEqual(oap["priority"], "P1")
        ok, msg = validate_oap(oap, "nonexistent-schema.json")
        self.assertTrue(ok, msg)

        actionable = reject_non_actionable([insight, {"summary": "bad"}])
        self.assertEqual(len(actionable), 1)


if __name__ == "__main__":
    unittest.main()
