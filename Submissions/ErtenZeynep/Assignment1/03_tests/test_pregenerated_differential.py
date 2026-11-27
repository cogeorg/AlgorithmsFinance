"""Per-event differential checks on existing 1,000-event workloads."""

from __future__ import annotations

import gzip
import json
import unittest
from pathlib import Path

from orderbook import BaselineOrderBook, OptimizedOrderBook
from support import verify_transition


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED_DATA = PROJECT_ROOT / "02_data" / "generated"


class TestPregeneratedDifferential(unittest.TestCase):
    def test_all_core_thousand_event_streams_match_after_every_event(self) -> None:
        paths = sorted(GENERATED_DATA.glob("*_1000_seed*.jsonl.gz"))
        self.assertEqual(len(paths), 15)
        for path in paths:
            baseline = BaselineOrderBook()
            optimized = OptimizedOrderBook()
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, 1):
                    event = json.loads(line)
                    baseline_before = baseline.canonical_snapshot()
                    optimized_before = optimized.canonical_snapshot()
                    baseline_seq = baseline.last_accepted_seq
                    optimized_seq = optimized.last_accepted_seq
                    baseline_result = baseline.process_event(event)
                    optimized_result = optimized.process_event(event)
                    baseline_after = baseline.canonical_snapshot()
                    optimized_after = optimized.canonical_snapshot()
                    with self.subTest(workload=path.name, line=line_number):
                        verify_transition(
                            baseline_before, event, baseline_result, baseline_after,
                            baseline_seq, baseline.last_accepted_seq,
                        )
                        verify_transition(
                            optimized_before, event, optimized_result, optimized_after,
                            optimized_seq, optimized.last_accepted_seq,
                        )
                        self.assertEqual(optimized_result, baseline_result)
                        self.assertEqual(optimized.last_accepted_seq, baseline.last_accepted_seq)
                        self.assertEqual(optimized_after, baseline_after)


if __name__ == "__main__":
    unittest.main()
