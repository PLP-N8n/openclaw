import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vigil.guarded_patch import generate_patch_suggestion, run_sandbox_check, mark_patch_readiness


class GuardedPatchTests(unittest.TestCase):
    def test_patch_flow(self):
        patch = generate_patch_suggestion({"pattern": "retry-storm", "count": 3})
        self.assertIn("target_file", patch)
        sandbox = run_sandbox_check(patch)
        self.assertIn("ok", sandbox)
        marked = mark_patch_readiness(patch, sandbox)
        self.assertIn("ready", marked)


if __name__ == "__main__":
    unittest.main()
