"""Saved-result dashboard generation tests; no benchmark is run here."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from dashboard import evidence_status, render_dashboard, write_dashboard


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURRENT_COMMIT = subprocess.run(
    ["git", "rev-parse", "HEAD"],
    cwd=PROJECT_ROOT,
    check=True,
    capture_output=True,
    text=True,
).stdout.strip()


REPORT = {
    "schema_version": 1,
    "run_label": "provisional_smoke",
    "created_at_utc": "2026-11-21T12:00:00+00:00",
    "environment": {
        "python_version": "3.test",
        "platform": "test-platform",
        "git_commit": "abc123",
        "git_dirty": True,
    },
    "settings": {"repeats": 2, "time_limit_seconds_per_phase": 1},
    "datasets": [
        {
            "dataset_id": "stream__mixed__m1000__seed42__levels1000",
            "experiment": "stream",
            "scenario": "mixed",
            "event_count": 1000,
            "seed": 42,
            "levels": 1000,
            "event_sha256": "deadbeef",
        }
    ],
    "records": [
        {
            "measurement_kind": "timing",
            "phase": "engine_replay",
            "version": "baseline",
            "dataset_id": "stream__mixed__m1000__seed42__levels1000",
            "experiment": "stream",
            "scenario": "mixed",
            "event_count": 1000,
            "seed": 42,
            "levels": 1000,
            "event_sha256": "deadbeef",
            "repeat": 0,
            "elapsed_seconds": 0.1,
            "time_unit": "seconds",
            "stopped": False,
        },
        {
            "measurement_kind": "memory",
            "phase": "engine_replay",
            "version": "revised",
            "dataset_id": "stream__mixed__m1000__seed42__levels1000",
            "experiment": "stream",
            "scenario": "mixed",
            "event_count": 1000,
            "seed": 42,
            "levels": 1000,
            "event_sha256": "deadbeef",
            "current_traced_bytes": 100,
            "peak_traced_bytes": 200,
            "stopped": False,
        },
        {
            "measurement_kind": "correctness",
            "phase": "diagnostic_prefix",
            "version": "shared",
            "dataset_id": "stream__mixed__m1000__seed42__levels1000",
            "experiment": "stream",
            "scenario": "mixed",
            "event_count": 1000,
            "seed": 42,
            "levels": 1000,
            "event_sha256": "deadbeef",
            "ordered_results_equal": True,
            "final_books_equal": True,
            "stopped": False,
        },
    ],
}


class DashboardTests(unittest.TestCase):
    def test_evidence_status_rejects_invalid_revision_four_claim(self) -> None:
        invalid = {
            **REPORT,
            "run_label": "canonical",
            "environment": {
                **REPORT["environment"],
                "git_dirty": False,
                "git_commit": "0" * 40,
            },
            "settings": {
                **REPORT["settings"],
                "measurement_integrity_revision": 4,
            },
        }

        label, explanation, canonical = evidence_status(invalid)

        self.assertEqual(label, "Invalid measurement evidence.")
        self.assertIn("git commit", explanation)
        self.assertFalse(canonical)

    def test_dashboard_contains_required_saved_result_views(self) -> None:
        html = render_dashboard(REPORT)

        for text in (
            "Saved-results dashboard",
            "Timing and throughput",
            "Processing latency",
            "Empirical cumulative distribution (ECDF)",
            "Traced memory",
            "Liquidation",
            "Correctness",
            "Raw repeats",
            "Stopped, partial, or missing evidence",
            "Completion status",
            "Expected repeats",
            "Missing repeats",
            "Curves plot only complete repeat sets",
            "Environment and settings",
            "provisional_smoke",
            "test-platform",
        ):
            self.assertIn(text, html)
        self.assertIn("setDefault('experiment','stream')", html)
        self.assertIn("seriesKey", html)
        self.assertIn("completionStatus(r)==='complete'", html)
        self.assertIn("completionStatus(r)==='missing'", html)
        self.assertIn("events_requested", html)
        self.assertIn("ecdfChart", html)
        self.assertNotIn("run_benchmarks.py", html)

    def test_latency_ecdf_uses_saved_samples_without_rerunning(self) -> None:
        latency = {
            **REPORT["records"][0],
            "measurement_kind": "latency",
            "phase": "per_event_instrumented",
            "version": "revised",
            "samples_ns": [10, 20, 20, 40],
            "sample_count": 4,
            "p50_ns": 20,
            "p95_ns": 40,
            "p99_ns": 40,
        }

        html = render_dashboard({**REPORT, "records": [latency]})

        self.assertIn('"samples_ns":[10,20,20,40]', html)
        self.assertIn("latencyEcdf", html)
        self.assertIn("samples_ns", html)
        self.assertNotIn("run_benchmarks.py", html)

    def test_dashboard_output_is_byte_stable_for_same_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.html"
            second = Path(directory) / "second.html"
            write_dashboard(REPORT, first)
            write_dashboard(REPORT, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())

        placeholder_report = {
            **REPORT,
            "settings": {
                **REPORT["settings"],
                "saved_marker": "__STATUS_HTML__ __STATUS_CLASS__",
            },
        }
        placeholder_html = render_dashboard(placeholder_report)
        self.assertIn(
            '"saved_marker":"__STATUS_HTML__ __STATUS_CLASS__"',
            placeholder_html,
        )

    def test_legacy_clean_report_is_marked_superseded(self) -> None:
        legacy = {
            **REPORT,
            "run_label": "canonical",
            "environment": {**REPORT["environment"], "git_dirty": False},
        }

        html = render_dashboard(legacy)

        self.assertIn("Superseded legacy measurement evidence.", html)
        self.assertNotIn("Canonical clean-tree evidence.", html)

        revision_two = {
            **legacy,
            "settings": {
                **legacy["settings"],
                "measurement_integrity_revision": 2,
            },
        }
        revision_two_html = render_dashboard(revision_two)
        self.assertIn("Superseded legacy measurement evidence.", revision_two_html)
        self.assertNotIn("Canonical clean-tree evidence.", revision_two_html)

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
        corrected_html = render_dashboard(corrected)
        self.assertIn("Canonical clean-tree evidence.", corrected_html)
        self.assertNotIn(
            "Superseded legacy measurement evidence.",
            corrected_html,
        )


if __name__ == "__main__":
    unittest.main()
