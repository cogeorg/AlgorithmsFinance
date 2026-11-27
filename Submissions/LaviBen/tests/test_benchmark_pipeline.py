"""Small, fast integration tests for benchmark and dashboard generation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from benchmark import ALGORITHMS, SCENARIOS, run_benchmarks, write_results
from dashboard import build_dashboard


class BenchmarkPipelineTests(unittest.TestCase):
    def test_fixed_case_matrix_is_shared_by_every_algorithm(self) -> None:
        sizes = [4]
        query_counts = [1, 3]
        run = run_benchmarks(
            sizes,
            query_counts,
            scenarios=SCENARIOS,
            repeats=2,
            base_seed=12,
        )

        expected_cases = len(sizes) * len(query_counts) * len(SCENARIOS)
        self.assertEqual(len(run.cases), expected_cases)
        self.assertEqual(len(run.raw_results), expected_cases * len(ALGORITHMS) * 2)
        self.assertEqual(len(run.summary), expected_cases * len(ALGORITHMS))

        for case in run.cases:
            case_rows = [row for row in run.raw_results if row.case_id == case.case_id]
            self.assertEqual(
                {row.algorithm for row in case_rows},
                {algorithm.name for algorithm in ALGORITHMS},
            )
            self.assertEqual({row.input_sha256 for row in case_rows}, {case.input_sha256})
            self.assertTrue(all(row.combined_ns >= row.preparation_ns for row in case_rows))
            self.assertTrue(all(row.combined_ns >= row.query_batch_ns for row in case_rows))

        self.assertEqual(run.metadata["units"]["raw_timings"], "nanoseconds")
        self.assertIn("python_version", run.metadata["environment"])
        self.assertIn("machine", run.metadata["environment"])
        self.assertIn("git_commit", run.metadata["code_version"])

    def test_results_and_dashboard_are_reproducible_artifacts(self) -> None:
        run = run_benchmarks(
            [3],
            [1],
            scenarios=("mixed",),
            repeats=1,
            base_seed=7,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_directory = Path(temporary_directory)
            artifacts = write_results(run, output_directory)
            dashboard_path = build_dashboard(
                artifacts["results_json"],
                output_directory / "runtime_dashboard.html",
            )

            payload = json.loads(
                artifacts["results_json"].read_text(encoding="utf-8")
            )
            dashboard = dashboard_path.read_text(encoding="utf-8")

            self.assertEqual(len(payload["summary"]), len(ALGORITHMS))
            self.assertTrue(artifacts["raw_csv"].is_file())
            self.assertTrue(artifacts["summary_csv"].is_file())
            self.assertTrue(artifacts["input_manifest_json"].is_file())
            self.assertIn("Search runtime dashboard", dashboard)
            self.assertIn("Binary search iterative v2", dashboard)
            self.assertIn("Preparation median", dashboard)


if __name__ == "__main__":
    unittest.main()
