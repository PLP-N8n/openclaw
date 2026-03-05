import json
import tempfile
import time
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from learning.raise_loop import load_recent_events, cluster_failures, build_proposals, write_proposals


class RaiseLoopTests(unittest.TestCase):
    def test_load_cluster_build_write(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            now = time.time()
            rows = [
                {"ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now)), "status": "FAIL", "status_code": 503, "task": "t1"},
                {"ts": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now)), "status": "OK", "task": "t2"},
            ]
            p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

            events = load_recent_events([str(p)], since_hours=24)
            self.assertEqual(len(events), 2)

            clusters = cluster_failures(events)
            self.assertGreaterEqual(len(clusters), 1)

            proposals = build_proposals(clusters, {"weights": {"impact": 0.6, "risk": 0.4}, "impact_saturation": 12})
            self.assertGreaterEqual(len(proposals), 1)
            for key in ["id", "category", "summary", "evidence", "impact_score", "risk_score", "confidence", "recommended_change", "target_file", "status"]:
                self.assertIn(key, proposals[0])

            out = write_proposals(proposals, str(Path(td) / "out"))
            self.assertTrue(Path(out).exists())


if __name__ == "__main__":
    unittest.main()
