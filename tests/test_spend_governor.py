import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gateway.spend_governor import (
    apply_spend_governor,
    daily_governor_impact,
    load_daily_spend,
    load_policy,
    spend_state,
    should_force_batch,
)


class SpendGovernorTests(unittest.TestCase):
    def test_daily_spend_and_state(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "usage.jsonl"
            now = datetime.now(timezone.utc).isoformat()
            old = "2020-01-01T00:00:00+00:00"
            rows = [
                {"ts": now, "cost_usd": 1.2},
                {"ts": now, "cost_usd": 1.0},
                {"ts": old, "cost_usd": 50.0},
            ]
            p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            spend = load_daily_spend(str(p))
            self.assertAlmostEqual(spend["daily_spend_usd"], 2.2, places=3)

            policy = load_policy()
            st = spend_state(spend, policy)
            self.assertIn(st["status"], {"OK", "NEAR_LIMIT", "CAPPED"})

    def test_daily_governor_impact(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "routing.jsonl"
            now = datetime.now(timezone.utc).isoformat()
            rows = [
                {"ts": now, "downgraded_by_spend_governor": True, "cloud_call_blocked": True},
                {"ts": now, "downgraded_by_spend_governor": True, "cloud_call_blocked": False},
            ]
            p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            impact = daily_governor_impact(str(p))
            self.assertEqual(impact["downgrades_triggered"], 2)
            self.assertEqual(impact["cloud_calls_blocked"], 1)

    def test_cloud_downgrade_and_batch(self):
        policy = {
            "policy": {
                "daily_cap_usd": 5.0,
                "near_limit_ratio": 0.85,
                "cloud_only_for_high_stakes": True,
                "downgrade_lane_when_near": "local-strong",
                "downgrade_lane_when_capped": "local-fast",
            },
            "batch_mode": {"heavy_token_threshold": 1000, "heavy_task_types": ["benchmark"]},
        }
        lane = {"name": "cloud-reasoning", "provider": "openrouter", "model": "x"}
        st = {"status": "NEAR_LIMIT", "daily_spend_usd": 4.5, "daily_cap_usd": 5.0}
        out = apply_spend_governor(lane, "med", "benchmark", 1200, st, policy)
        self.assertEqual(out["provider"], "ollama")
        self.assertTrue(out["forced_batch_mode"])
        self.assertEqual(out["execution_mode"], "batch")

    def test_should_force_batch(self):
        policy = {"batch_mode": {"heavy_token_threshold": 1000, "heavy_task_types": ["bulk_ingest"]}}
        self.assertTrue(should_force_batch("bulk_ingest", 100, policy))
        self.assertTrue(should_force_batch("interactive", 1200, policy))
        self.assertFalse(should_force_batch("interactive", 100, policy))


if __name__ == "__main__":
    unittest.main()
