import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gateway.try_heal_retry import try_heal_retry


class TryHealRetryTests(unittest.TestCase):
    def test_recovers_after_retry(self):
        calls = {"n": 0}

        def exec_fn(req):
            calls["n"] += 1
            if calls["n"] < 3:
                return {"status_code": 503, "error_type": "upstream"}
            return {"status_code": 200, "data": "ok"}

        out = try_heal_retry(exec_fn, {"max_tokens": 500})
        self.assertTrue(out["ok"])
        self.assertEqual(out["final"]["status_code"], 200)
        self.assertGreaterEqual(len(out["trace"]), 3)

    def test_stops_on_non_retryable(self):
        def exec_fn(_req):
            return {"status_code": 503, "error_type": "schema_error"}

        out = try_heal_retry(exec_fn, {})
        self.assertFalse(out["ok"])
        self.assertEqual(out["final"]["error_type"], "schema_error")


if __name__ == "__main__":
    unittest.main()
