"""Tests for the short report generated only from saved results."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from build_report import render_report, write_report_markdown
from tests.test_dashboard import REPORT


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURRENT_COMMIT = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=PROJECT_ROOT,
    check=True,
    capture_output=True,
    text=True,
).stdout.strip()


class ReportingTests(unittest.TestCase):
    def test_latency_table_pools_saved_samples_across_seeds(self) -> None:
        seed_samples = {
            42: [1, 1, 100],
            43: [2, 2, 2],
            44: [3, 3, 3],
        }
        latency_records = []
        for seed, samples in seed_samples.items():
            ordered = sorted(samples)
            latency_records.append(
                {
                    **REPORT["records"][0],
                    "dataset_id": f"stream__mixed__m100__seed{seed}__levels1000",
                    "measurement_kind": "latency",
                    "phase": "per_event_instrumented",
                    "version": "revised",
                    "seed": seed,
                    "event_count": 100,
                    "samples_ns": samples,
                    "sample_count": len(samples),
                    "p50_ns": ordered[1],
                    "p95_ns": ordered[-1],
                    "p99_ns": ordered[-1],
                }
            )

        report = render_report({**REPORT, "records": latency_records})

        # Pooled samples are [1,1,2,2,2,3,3,3,100], whose nearest-rank
        # p50/p95/p99 values are 2/100/100. Median seed-level p99 was only 3.
        self.assertIn("| 2 | 100 | 100 |", report)
        self.assertNotIn("| 2 | 3 | 3 |", report)

    def test_runtime_table_pools_completed_raw_repeats_across_seeds(self) -> None:
        raw_records = []
        summary_records = []
        seed_samples = {
            42: [1.0, 2.0, 100.0],
            43: [3.0, 4.0, 5.0],
            44: [6.0, 7.0, 8.0],
        }
        for seed, samples in seed_samples.items():
            dataset_id = f"stream__mixed__m100__seed{seed}__levels1000"
            for repeat, elapsed in enumerate(samples):
                raw_records.append(
                    {
                        **REPORT["records"][0],
                        "dataset_id": dataset_id,
                        "seed": seed,
                        "repeat": repeat,
                        "elapsed_seconds": elapsed,
                        "throughput_events_per_second": 100 / elapsed,
                    }
                )
            summary_records.append(
                {
                    **raw_records[-1],
                    "measurement_kind": "timing_summary",
                    "repeat": None,
                    "elapsed_seconds_median": samples[1],
                    "throughput_events_per_second_median": 100 / samples[1],
                    "expected_repeat_count": 3,
                    "completed_repeat_count": 3,
                    "stopped_repeat_count": 0,
                    "missing_repeat_count": 0,
                    "completion_status": "complete",
                }
            )

        report = render_report(
            {**REPORT, "records": [*raw_records, *summary_records]}
        )

        # The nine raw repeats have median 5.0. The old median-of-seed-medians
        # calculation returned 4.0 while claiming to summarize raw repeats.
        self.assertIn("| 5.000000 |", report)
        self.assertNotIn("| 4.000000 |", report)

    def test_report_contains_required_assignment_sections(self) -> None:
        timing_summary = {
            **REPORT["records"][0],
            "measurement_kind": "timing_summary",
            "phase": "application_total",
            "version": "revised",
            "liquidation_percent": 100,
            "elapsed_seconds_median": 0.2,
            "throughput_events_per_second_median": 5_000,
        }
        report = render_report(
            {**REPORT, "records": [*REPORT["records"], timing_summary]}
        )
        for heading in (
            "# Limit order book report",
            "## Specification and boundaries",
            "## Correctness evidence",
            "## Implementation and revision",
            "## Runtime and throughput",
            "## Processing latency",
            "## Memory",
            "## Bottleneck and operation counts",
            "## Limitations",
            "## Reproducibility",
        ):
            self.assertIn(heading, report)
        self.assertIn("provisional_smoke", report)
        self.assertIn("abc123", report)
        self.assertIn(
            "| Experiment | Scenario | M | Levels | Version | Phase | Sale % |",
            report,
        )
        self.assertIn("Completed correctness rows passing", report)
        self.assertIn("stopped by the declared limit", report)
        self.assertIn("Partial timing summaries:", report)

    def test_report_output_is_byte_stable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "one.md"
            second = Path(directory) / "two.md"
            write_report_markdown(REPORT, first)
            write_report_markdown(REPORT, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_report_discloses_expected_stopped_and_missing_repeats(self) -> None:
        summary = {
            **REPORT["records"][0],
            "measurement_kind": "timing_summary",
            "phase": "engine_replay",
            "version": "revised",
            "repeat": None,
            "elapsed_seconds_median": 0.2,
            "expected_repeat_count": 5,
            "completed_repeat_count": 2,
            "stopped_repeat_count": 1,
            "missing_repeat_count": 2,
            "completion_status": "partial",
            "stopped": False,
        }
        revision_three = {
            **REPORT,
            "settings": {
                **REPORT["settings"],
                "measurement_integrity_revision": 3,
            },
            "records": [
                *REPORT["records"],
                {
                    **REPORT["records"][0],
                    "version": "revised",
                    "repeat": 0,
                    "elapsed_seconds": 0.1,
                },
                {
                    **REPORT["records"][0],
                    "version": "revised",
                    "repeat": 1,
                    "elapsed_seconds": 0.3,
                },
                {
                    **REPORT["records"][0],
                    "version": "revised",
                    "repeat": 2,
                    "elapsed_seconds": 0.4,
                    "stopped": True,
                    "stop_reason": "declared limit",
                },
                summary,
            ],
        }

        report = render_report(revision_three)

        self.assertIn("2/5 (1 stopped, 2 missing)", report)
        self.assertIn("Missing timing repeats: 2.", report)

    def test_report_labels_bounded_operation_count_coverage(self) -> None:
        operation_counts = {
            **REPORT["records"][0],
            "measurement_kind": "operation_counts",
            "phase": "diagnostic_prefix_instrumented",
            "version": "revised",
            "events_requested": 100,
            "events_processed": 100,
            "active_order_peak": 12,
            "occupied_price_level_peak": 4,
            "fill_count": 3,
            "maker_price_levels_visited": 2,
            "final_active_order_count": 9,
        }

        report = render_report({**REPORT, "records": [operation_counts]})

        self.assertIn("Requested / processed", report)
        self.assertIn("100 / 100", report)

    def test_report_repeat_coverage_includes_fully_stopped_summaries(self) -> None:
        partial = {
            **REPORT["records"][0],
            "measurement_kind": "timing_summary",
            "phase": "engine_replay",
            "version": "baseline",
            "seed": 42,
            "repeat": None,
            "elapsed_seconds_median": 0.2,
            "expected_repeat_count": 5,
            "completed_repeat_count": 2,
            "stopped_repeat_count": 3,
            "missing_repeat_count": 0,
            "completion_status": "partial",
            "stopped": False,
        }
        stopped = {
            **partial,
            "seed": 43,
            "dataset_id": "stream__mixed__m1000__seed43__levels1000",
            "elapsed_seconds_median": None,
            "completed_repeat_count": 0,
            "stopped_repeat_count": 5,
            "completion_status": "stopped",
            "stopped": True,
            "stop_reason": "all raw repeats stopped at the declared limit",
        }
        revision_three = {
            **REPORT,
            "settings": {
                **REPORT["settings"],
                "measurement_integrity_revision": 3,
            },
            "records": [
                {
                    **REPORT["records"][0],
                    "repeat": 0,
                    "elapsed_seconds": 0.1,
                },
                {
                    **REPORT["records"][0],
                    "repeat": 1,
                    "elapsed_seconds": 0.3,
                },
                *[
                    {
                        **REPORT["records"][0],
                        "repeat": repeat,
                        "elapsed_seconds": 0.4,
                        "stopped": True,
                        "stop_reason": "declared limit",
                    }
                    for repeat in range(2, 5)
                ],
                *[
                    {
                        **REPORT["records"][0],
                        "dataset_id": "stream__mixed__m1000__seed43__levels1000",
                        "seed": 43,
                        "repeat": repeat,
                        "elapsed_seconds": 0.4,
                        "stopped": True,
                        "stop_reason": "declared limit",
                    }
                    for repeat in range(5)
                ],
                partial,
                stopped,
            ],
        }

        report = render_report(revision_three)

        self.assertIn("2/10 (8 stopped)", report)

    def test_legacy_clean_report_is_marked_superseded(self) -> None:
        legacy = {
            **REPORT,
            "run_label": "canonical",
            "environment": {**REPORT["environment"], "git_dirty": False},
        }

        report = render_report(legacy)

        self.assertIn("SUPERSEDED: legacy measurement evidence.", report)
        self.assertNotIn(
            "**Evidence status:** Canonical clean-tree evidence.",
            report,
        )

        revision_two = {
            **legacy,
            "settings": {
                **legacy["settings"],
                "measurement_integrity_revision": 2,
            },
        }
        revision_two_report = render_report(revision_two)
        self.assertIn("SUPERSEDED: legacy measurement evidence.", revision_two_report)
        self.assertNotIn(
            "**Evidence status:** Canonical clean-tree evidence.",
            revision_two_report,
        )

        corrected = {
            **legacy,
            "environment": {
                **legacy["environment"],
                "git_commit": CURRENT_COMMIT,
            },
            "settings": {
                **legacy["settings"],
                "measurement_integrity_revision": 4,
            },
        }
        corrected_report = render_report(corrected)
        self.assertIn(
            "**Evidence status:** Canonical clean-tree evidence.",
            corrected_report,
        )
        self.assertNotIn(
            "SUPERSEDED: legacy measurement evidence.",
            corrected_report,
        )


if __name__ == "__main__":
    unittest.main()
