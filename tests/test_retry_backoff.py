import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gateway.retry_backoff import should_retry, backoff_delay, circuit_open


class RetryBackoffTests(unittest.TestCase):
    def test_retry_rules(self):
        self.assertTrue(should_retry(429, "rate_limit"))
        self.assertTrue(should_retry(503, "upstream"))
        self.assertFalse(should_retry(404, "not_found"))

    def test_backoff_and_circuit(self):
        d = backoff_delay(2)
        self.assertGreaterEqual(d, 0.0)
        self.assertTrue(circuit_open(5))
        self.assertFalse(circuit_open(4))


if __name__ == "__main__":
    unittest.main()
