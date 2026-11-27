"""Measurement regressions: known quantiles, accounting and deadline cleanup."""
import gzip
from pathlib import Path
import signal
import tempfile
import unittest
from benchmark_worker import metadata, summarize_latencies, percentile, deadline, PhaseTimeout

ROOT = Path(__file__).resolve().parents[1]


class TestBenchmark(unittest.TestCase):
    def test_documented_quantiles_and_even_median(self):
        summary = summarize_latencies([4, 1, 3, 2])
        self.assertEqual(summary["median_seconds"], 2.5)
        self.assertEqual(summary["p95_seconds"], 4)
        self.assertEqual(summary["p99_seconds"], 4)
        self.assertEqual(percentile(list(range(1, 101)), .95), 95)
        self.assertEqual(percentile(list(range(1, 101)), .99), 99)
        self.assertEqual(summarize_latencies([])["samples"], 0)

    def test_worked_example_independent_workload_peaks(self):
        (ROOT/"work").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/"work") as temporary:
            path = Path(temporary)/"worked.jsonl.gz"
            with gzip.open(path,"wb") as stream:
                stream.write((ROOT/"data/worked_example.jsonl").read_bytes())
            result = metadata({"path":str(path)})
        self.assertEqual((result["active_order_peak"],result["price_level_peak"]),(5,4))
        self.assertEqual((result["fill_count"],result["remaining_orders"]),(4,2))

    def test_deadline_restores_handler_and_clears_timer(self):
        previous = signal.getsignal(signal.SIGALRM)
        with self.assertRaises(PhaseTimeout):
            with deadline(.01):
                while True:
                    pass
        self.assertEqual(signal.getsignal(signal.SIGALRM),previous)
        self.assertEqual(signal.getitimer(signal.ITIMER_REAL),(0.0,0.0))
