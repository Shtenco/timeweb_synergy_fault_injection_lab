from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from experiments.fault_injection_lab import percentile, run_mode


class FaultInjectionTests(unittest.TestCase):
    def test_percentile_interpolates(self):
        self.assertEqual(percentile([1.0, 3.0, 5.0], 50), 3.0)
        self.assertEqual(percentile([1.0, 3.0, 5.0], 25), 2.0)

    def test_retry_failover_recovers_during_replica_terminations(self):
        with tempfile.TemporaryDirectory() as directory:
            summary, outcomes = run_mode(Path(directory), run_id=7, mode="retry_failover", n=80)

        self.assertEqual(summary["requests"], 80)
        self.assertEqual(summary["success"], 80)
        self.assertEqual(summary["failed"], 0)
        self.assertEqual(summary["injected_process_terminations"], 3)
        self.assertEqual(len(outcomes), 80)
        self.assertTrue(all(item["success"] == 1 for item in outcomes))
        self.assertGreater(summary["retry_attempts_extra"], 0)


if __name__ == "__main__":
    unittest.main()
