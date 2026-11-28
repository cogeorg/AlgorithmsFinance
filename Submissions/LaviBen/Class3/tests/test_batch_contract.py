import math
import unittest
from pathlib import Path

from compiled_backend import price_american_put_compiled
from batch import (
    BatchInputError,
    ModelJob,
    prepare_jobs,
    run_batch_once,
)
from market_data import load_price_series, select_full_history


REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "Class3" / "data" / "hourly"


class BatchContractTests(unittest.TestCase):
    def test_full_history_preserves_every_observation_and_gap(self):
        series = load_price_series(DATA_DIR / "BTCUSDT.csv")
        window = select_full_history(series)
        self.assertEqual(len(series.closes), len(window.closes))
        self.assertEqual(43822, window.steps)
        self.assertEqual(1, len(window.gaps))
        self.assertEqual(1, window.gaps[0].missing_hours)

    def test_small_batch_matches_direct_values_and_is_sorted(self):
        jobs = (
            ModelJob("Z_ASSET", 100, 100, 1.2, 0.8, 1.05, 4),
            ModelJob("A_ASSET", 80, 80, 1.15, 0.85, 1.01, 4),
        )
        execution = run_batch_once(jobs, workers=2)
        self.assertEqual(["A_ASSET", "Z_ASSET"],
                         [result.symbol for result in execution.results])
        expected = {
            job.symbol: price_american_put_compiled(
                job.spot, job.strike, job.up, job.down, job.gross_rate, job.steps
            )
            for job in jobs
        }
        self.assertEqual(expected,
                         {result.symbol: result.value for result in execution.results})
        self.assertEqual(2, len(execution.warm_worker_pids))
        self.assertGreaterEqual(execution.wall_seconds, 0)
        for result in execution.results:
            self.assertTrue(math.isfinite(result.value))
            self.assertGreaterEqual(result.value, 0)

    def test_invalid_worker_counts_are_rejected(self):
        job = ModelJob("ONE", 100, 100, 1.2, 0.8, 1.05, 2)
        for workers in (0, -1, 2, True):
            with self.subTest(workers=workers):
                with self.assertRaises(BatchInputError):
                    run_batch_once((job,), workers=workers)

    def test_prepare_all_one_year_jobs(self):
        prepared = prepare_jobs(DATA_DIR, window_name="one_year")
        self.assertEqual(40, len(prepared.jobs))
        self.assertEqual(40, len(prepared.inputs))
        self.assertEqual(8760, {job.steps for job in prepared.jobs}.pop())
        self.assertEqual(sorted(job.symbol for job in prepared.jobs),
                         [job.symbol for job in prepared.jobs])
        self.assertTrue(all(job.spot > 0 for job in prepared.jobs))

    def test_prepare_all_full_jobs(self):
        prepared = prepare_jobs(DATA_DIR, window_name="full")
        self.assertEqual(40, len(prepared.jobs))
        self.assertEqual(43822, {job.steps for job in prepared.jobs}.pop())
        self.assertEqual(1, {item.gap_count for item in prepared.inputs}.pop())


if __name__ == "__main__":
    unittest.main()
