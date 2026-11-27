"""Tests-first contract for benchmark data and measurement helpers."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import subprocess
import tempfile
from time import sleep
import unittest
from unittest.mock import patch

from measurement.datasets import (
    DatasetSpec,
    event_checksum,
    generate_events,
    liquidation_request,
    load_dataset,
    write_dataset,
)
from measurement.metrics import (
    MeasurementTimeout,
    latency_replay,
    nearest_rank,
    replay_diagnostics,
    timed_replay,
    traced_memory_replay,
    validate_report,
)
import measurement.metrics as measurement_metrics
from orderbook.baseline import BaselineOrderBook
from orderbook.revised import RevisedOrderBook
import tools.run_benchmarks as benchmark_runner


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class MeasurementContractTests(unittest.TestCase):
    def test_measurement_integrity_revision_is_four(self) -> None:
        self.assertEqual(benchmark_runner.MEASUREMENT_INTEGRITY_REVISION, 4)

    def test_application_totals_reject_unpaired_parse_and_replay_repeats(self) -> None:
        base = {
            "dataset_id": "repeat-pairing-audit",
            "experiment": "stream",
            "scenario": "mixed",
            "seed": 42,
            "event_count": 10,
            "levels": 2,
            "event_sha256": "audit",
        }
        records = [
            {
                **base,
                "measurement_kind": "timing",
                "phase": "input_read_parse",
                "version": "shared",
                "repeat": repeat,
                "elapsed_seconds": 0.1,
                "events_processed": 10,
                "attempted": True,
                "stopped": False,
            }
            for repeat in range(2)
        ]
        records.extend(
            {
                **base,
                "measurement_kind": "timing",
                "phase": "engine_replay",
                "version": "revised",
                "repeat": repeat,
                "elapsed_seconds": 0.2,
                "events_processed": 10,
                "attempted": True,
                "stopped": False,
            }
            for repeat in range(5)
        )

        with self.assertRaisesRegex(ValueError, "unpaired timing repeats"):
            benchmark_runner.append_application_totals(records)

    def test_timing_summary_records_expected_and_missing_repeat_counts(self) -> None:
        raw = [
            {
                "elapsed_seconds": 0.1,
                "throughput_events_per_second": 100.0,
                "stopped": False,
            },
            {
                "elapsed_seconds": 0.2,
                "throughput_events_per_second": 50.0,
                "stopped": False,
            },
        ]
        records: list[dict[str, object]] = []

        benchmark_runner.append_timing_summary(
            records,
            raw,
            {"dataset_id": "missing-repeat-audit"},
            "engine_replay",
            "revised",
            expected_repeat_count=5,
        )

        self.assertEqual(
            {
                key: records[0][key]
                for key in (
                    "expected_repeat_count",
                    "completed_repeat_count",
                    "stopped_repeat_count",
                    "missing_repeat_count",
                    "completion_status",
                )
            },
            {
                "expected_repeat_count": 5,
                "completed_repeat_count": 2,
                "stopped_repeat_count": 0,
                "missing_repeat_count": 3,
                "completion_status": "partial",
            },
        )

    def test_operation_diagnostics_are_bounded_and_preserve_stopped_evidence(self) -> None:
        class SlowBook:
            def ProcessEvent(self, event):
                del event
                while True:
                    pass

        outcome = replay_diagnostics(
            SlowBook,
            ({"type": "LIMIT"},),
            time_limit_seconds=0.01,
        )

        self.assertEqual(outcome["stopped"], True)
        self.assertEqual(outcome["events_processed"], 0)
        self.assertIn("exceeded 0.01 seconds", outcome["stop_reason"])

    def test_operation_diagnostic_final_counts_stay_inside_limit(self) -> None:
        inside_limit = False

        @contextmanager
        def tracked_limit(seconds):
            del seconds
            nonlocal inside_limit
            inside_limit = True
            try:
                yield
            finally:
                inside_limit = False

        class AuditBook:
            def ProcessEvent(self, event):
                del event
                return {"status": "resting", "fills": []}

        def bounded_counts(book):
            del book
            self.assertTrue(inside_limit)
            return 1, 1

        with (
            patch.object(measurement_metrics, "time_limit", tracked_limit),
            patch.object(measurement_metrics, "book_counts", side_effect=bounded_counts),
        ):
            replay_diagnostics(AuditBook, ({"type": "LIMIT"},), 1.0)

    def test_stream_operation_counts_use_only_configured_diagnostic_prefix(self) -> None:
        events = tuple(
            {
                "event_id": f"event{seq}",
                "seq": seq,
                "type": "CANCEL",
                "target_order_id": "missing",
            }
            for seq in range(1, 11)
        )
        metadata = {
            "dataset_id": "diagnostic-prefix-audit",
            "experiment": "stream",
            "scenario": "mixed",
            "seed": 42,
            "event_count": 10,
            "levels": 2,
            "event_sha256": "audit",
        }
        observed: list[tuple[int, float | None]] = []

        def fake_diagnostics(book_class, diagnostic_events, time_limit_seconds=None):
            del book_class
            observed.append((len(diagnostic_events), time_limit_seconds))
            return {
                "events_processed": len(diagnostic_events),
                "events_requested": len(diagnostic_events),
                "stopped": False,
            }

        with patch.object(
            benchmark_runner,
            "replay_diagnostics",
            side_effect=fake_diagnostics,
        ):
            records = benchmark_runner.stream_measurements(
                events,
                metadata,
                versions=(),
                repeats=1,
                warmup_events=1,
                diagnostic_events=3,
                latency_events=None,
                time_limit_seconds=0.5,
                include_memory=False,
            )

        self.assertEqual(observed, [(3, 0.5)])
        operation_row = next(
            row for row in records if row["measurement_kind"] == "operation_counts"
        )
        self.assertEqual(operation_row["events_requested"], 3)
        self.assertEqual(operation_row["events_processed"], 3)
        self.assertEqual(operation_row["stopped"], False)

    def test_liquidation_correctness_objects_are_released_before_timing(self) -> None:
        destroyed: list[str] = []
        attempt_number = 0

        class TrackedDict(dict):
            def __init__(self, label, *args, **kwargs):
                self.label = label
                super().__init__(*args, **kwargs)

            def __del__(self):
                destroyed.append(self.label)

        class TrackedList(list):
            def __init__(self, label, *args):
                self.label = label
                super().__init__(*args)

            def __del__(self):
                destroyed.append(self.label)

        def fake_attempt(*args, **kwargs):
            del args, kwargs
            nonlocal attempt_number
            attempt_number += 1
            fills = TrackedList(f"fills-{attempt_number}")
            result = TrackedDict(
                f"result-{attempt_number}",
                {
                    "status": "unfilled",
                    "fills": fills,
                    "unfilled_qty_units": 1,
                },
            )
            state = TrackedList(f"state-{attempt_number}")
            return TrackedDict(
                f"attempt-{attempt_number}",
                {
                    "events_processed": 2,
                    "result": result,
                    "state": state,
                    "stopped": False,
                },
            )

        def assert_released(*args, **kwargs):
            del args, kwargs
            self.assertEqual(attempt_number, 6)
            self.assertEqual(len(destroyed), 24)

        setup = (
            {
                "seq": 1,
                "event_id": "event1",
                "type": "LIMIT",
                "order_id": "b1",
                "side": "BUY",
                "price_ticks": 100,
                "qty_units": 10,
            },
        )
        metadata = {
            "dataset_id": "correctness-cleanup-audit",
            "experiment": "liquidation",
            "scenario": "bid_book",
            "seed": 42,
            "event_count": 1,
            "levels": 1,
            "event_sha256": "audit",
        }

        with (
            patch.dict(
                benchmark_runner.IMPLEMENTATIONS,
                {"baseline": object, "revised": object},
                clear=True,
            ),
            patch.object(
                benchmark_runner,
                "replay_diagnostics",
                return_value={
                    "events_processed": 1,
                    "events_requested": 1,
                    "stopped": False,
                },
            ),
            patch.object(
                benchmark_runner,
                "liquidation_correctness_attempt",
                side_effect=fake_attempt,
            ),
            patch.object(benchmark_runner, "warm_up", side_effect=assert_released),
        ):
            benchmark_runner.liquidation_measurements(
                setup,
                metadata,
                versions=("baseline",),
                repeats=0,
                warmup_events=1,
                time_limit_seconds=0.5,
                include_memory=False,
            )

    def test_completed_replay_excludes_time_limit_setup_and_cleanup(self) -> None:
        log: list[str] = []
        clock_calls = 0

        @contextmanager
        def tracked_limit(seconds):
            del seconds
            log.append("limit_enter")
            yield
            log.append("limit_exit")

        def fake_clock() -> float:
            nonlocal clock_calls
            clock_calls += 1
            log.append(f"clock{clock_calls}")
            return float(clock_calls)

        class AuditBook:
            def ProcessEvent(self, event):
                del event
                log.append("process")
                return {}

        with (
            patch.object(measurement_metrics, "time_limit", tracked_limit),
            patch.object(measurement_metrics, "perf_counter", side_effect=fake_clock),
        ):
            outcome = timed_replay(AuditBook, ({"seq": 1},), 1.0)

        self.assertEqual(outcome["stopped"], False)
        self.assertEqual(
            log,
            ["limit_enter", "clock1", "process", "clock2", "limit_exit"],
        )

    def test_parse_repeat_cleanup_occurs_outside_next_timing_window(self) -> None:
        log: list[str] = []
        clock_calls = 0
        read_calls = 0

        class ParsedSentinel:
            def __init__(self, number: int) -> None:
                self.number = number

            def __del__(self) -> None:
                log.append(f"cleanup{self.number}")

        def fake_clock() -> float:
            nonlocal clock_calls
            clock_calls += 1
            log.append(f"clock{clock_calls}")
            return float(clock_calls)

        def fake_read_events(path: Path):
            del path
            nonlocal read_calls
            read_calls += 1
            log.append(f"read{read_calls}")
            return (ParsedSentinel(read_calls),)

        metadata = {
            "dataset_id": "parse-cleanup-audit",
            "experiment": "stream",
            "scenario": "mixed",
            "seed": 42,
            "event_count": 1,
            "levels": 1,
            "event_sha256": "audit",
        }
        with (
            patch.object(benchmark_runner, "perf_counter", side_effect=fake_clock),
            patch.object(
                benchmark_runner,
                "read_events",
                side_effect=fake_read_events,
            ),
        ):
            benchmark_runner.parse_measurements(
                Path("unused"), metadata, repeats=2
            )

        self.assertGreater(log.index("cleanup1"), log.index("clock2"))
        self.assertLess(log.index("cleanup1"), log.index("clock3"))

    def test_compare_versions_checks_canonical_book_after_every_event(self) -> None:
        instances = []

        class AuditBook:
            def __init__(self) -> None:
                self.inspect_calls = 0
                instances.append(self)

            def ProcessEvent(self, event):
                return {"event_id": event["event_id"], "status": "accepted"}

            def InspectBook(self):
                self.inspect_calls += 1
                return []

        events = tuple(
            {"event_id": f"event{seq}", "seq": seq}
            for seq in range(1, 4)
        )
        with patch.dict(
            benchmark_runner.IMPLEMENTATIONS,
            {"baseline": AuditBook, "revised": AuditBook},
            clear=True,
        ):
            result = benchmark_runner.compare_versions(events)

        self.assertEqual(result["events_compared"], 3)
        self.assertEqual([book.inspect_calls for book in instances], [3, 3])

    def test_compare_versions_preserves_bounded_stopped_evidence(self) -> None:
        @contextmanager
        def immediate_timeout(seconds):
            raise MeasurementTimeout(f"phase exceeded {seconds} seconds")
            yield

        with patch.object(benchmark_runner, "time_limit", immediate_timeout):
            result = benchmark_runner.compare_versions(
                ({"event_id": "event1", "seq": 1},),
                time_limit_seconds=0.01,
            )

        self.assertEqual(result["events_requested"], 1)
        self.assertEqual(result["events_compared"], 0)
        self.assertEqual(result["stopped"], True)
        self.assertIn("exceeded 0.01 seconds", result["stop_reason"])

    def test_liquidation_book_cleanup_occurs_outside_next_build_timer(self) -> None:
        clock_calls = 0
        cleanup_clock_counts: list[int] = []
        clock_inside_limit: list[bool] = []
        inside_limit = False

        @contextmanager
        def tracked_limit(seconds):
            del seconds
            nonlocal inside_limit
            inside_limit = True
            try:
                yield
            finally:
                inside_limit = False

        class AuditBook:
            def __del__(self) -> None:
                cleanup_clock_counts.append(clock_calls)

            def ProcessEvent(self, event):
                status = "resting" if event["type"] == "LIMIT" else "unfilled"
                return {
                    "event_id": event["event_id"],
                    "order_id": event["order_id"],
                    "status": status,
                    "unfilled_qty_units": event["qty_units"],
                    "fills": [],
                }

            def InspectBook(self):
                return []

        def fake_clock() -> float:
            nonlocal clock_calls
            clock_calls += 1
            clock_inside_limit.append(inside_limit)
            return float(clock_calls)

        setup = (
            {
                "seq": 1,
                "event_id": "event1",
                "type": "LIMIT",
                "order_id": "b1",
                "side": "BUY",
                "price_ticks": 100,
                "qty_units": 10,
            },
        )
        metadata = {
            "dataset_id": "liquidation-cleanup-audit",
            "experiment": "liquidation",
            "scenario": "bid_book",
            "seed": 42,
            "event_count": 1,
            "levels": 1,
            "event_sha256": "audit",
        }
        correctness = {
            "events_processed": 2,
            "result": {
                "event_id": "liquidation",
                "order_id": "liquidation",
                "status": "unfilled",
                "unfilled_qty_units": 1,
                "fills": [],
            },
            "state": [],
            "stopped": False,
        }

        with (
            patch.dict(
                benchmark_runner.IMPLEMENTATIONS,
                {"baseline": AuditBook, "revised": AuditBook},
                clear=True,
            ),
            patch.object(
                benchmark_runner,
                "replay_diagnostics",
                return_value={"events_processed": 1},
            ),
            patch.object(
                benchmark_runner,
                "liquidation_correctness_attempt",
                return_value=correctness,
            ),
            patch.object(benchmark_runner, "warm_up"),
            patch.object(benchmark_runner, "time_limit", tracked_limit),
            patch.object(
                benchmark_runner,
                "perf_counter",
                side_effect=fake_clock,
            ),
        ):
            benchmark_runner.liquidation_measurements(
                setup,
                metadata,
                versions=("baseline",),
                repeats=2,
                warmup_events=1,
                time_limit_seconds=None,
                include_memory=False,
            )

        self.assertTrue(cleanup_clock_counts)
        self.assertTrue(all(clock_inside_limit), clock_inside_limit)
        self.assertTrue(
            all(count % 4 == 0 for count in cleanup_clock_counts),
            cleanup_clock_counts,
        )

    def test_unattempted_liquidation_sale_has_no_invented_elapsed_time(self) -> None:
        @contextmanager
        def forced_timeout(seconds):
            del seconds
            raise benchmark_runner.MeasurementTimeout("forced build stop")
            yield  # pragma: no cover

        setup = (
            {
                "seq": 1,
                "event_id": "event1",
                "type": "LIMIT",
                "order_id": "b1",
                "side": "BUY",
                "price_ticks": 100,
                "qty_units": 10,
            },
        )
        metadata = {
            "dataset_id": "liquidation-timeout-audit",
            "experiment": "liquidation",
            "scenario": "bid_book",
            "seed": 42,
            "event_count": 1,
            "levels": 1,
            "event_sha256": "audit",
        }
        correctness = {
            "events_processed": 2,
            "result": {
                "event_id": "liquidation",
                "order_id": "liquidation",
                "status": "unfilled",
                "unfilled_qty_units": 1,
                "fills": [],
            },
            "state": [],
            "stopped": False,
        }

        with (
            patch.object(
                benchmark_runner,
                "replay_diagnostics",
                return_value={"events_processed": 1},
            ),
            patch.object(
                benchmark_runner,
                "liquidation_correctness_attempt",
                return_value=correctness,
            ),
            patch.object(benchmark_runner, "warm_up"),
            patch.object(benchmark_runner, "time_limit", forced_timeout),
        ):
            records = benchmark_runner.liquidation_measurements(
                setup,
                metadata,
                versions=("baseline",),
                repeats=1,
                warmup_events=1,
                time_limit_seconds=1.0,
                include_memory=False,
            )

        sale_rows = [
            row
            for row in records
            if row["measurement_kind"] == "timing"
            and row["phase"] == "individual_sale"
        ]
        self.assertEqual(len(sale_rows), 3)
        for row in sale_rows:
            self.assertTrue(row["stopped"])
            self.assertEqual(row["attempted"], False)
            self.assertIsNone(row["elapsed_seconds"])
            self.assertEqual(row["events_processed"], 0)
            self.assertEqual(
                row["stop_reason"],
                "book build stopped; sale not attempted",
            )

    def test_timing_summary_labels_partial_repeat_sets(self) -> None:
        raw = [
            {
                "elapsed_seconds": float(index + 1),
                "throughput_events_per_second": 100.0,
                "stopped": False,
            }
            for index in range(4)
        ]
        raw.append(
            {
                "elapsed_seconds": 5.0,
                "stopped": True,
                "stop_reason": "phase exceeded limit",
            }
        )
        records: list[dict[str, object]] = []

        benchmark_runner.append_timing_summary(
            records,
            raw,
            {"dataset_id": "summary-audit"},
            "engine_replay",
            "baseline",
        )

        self.assertEqual(len(records), 1)
        summary = records[0]
        self.assertEqual(summary["completed_repeat_count"], 4)
        self.assertEqual(summary["stopped_repeat_count"], 1)
        self.assertEqual(summary["completion_status"], "partial")
        self.assertEqual(summary["stopped"], False)

        mixed_records: list[dict[str, object]] = []
        benchmark_runner.append_timing_summary(
            mixed_records,
            [
                {
                    "elapsed_seconds": 5.0,
                    "stopped": True,
                    "stop_reason": "phase exceeded limit",
                }
            ],
            {"dataset_id": "summary-mixed-audit"},
            "engine_replay",
            "baseline",
            expected_repeat_count=2,
        )
        self.assertEqual(mixed_records[0]["completed_repeat_count"], 0)
        self.assertEqual(mixed_records[0]["stopped_repeat_count"], 1)
        self.assertEqual(mixed_records[0]["missing_repeat_count"], 1)
        self.assertEqual(mixed_records[0]["completion_status"], "partial")
        self.assertEqual(mixed_records[0]["stopped"], False)

    def test_application_total_handles_unattempted_null_source(self) -> None:
        base = {
            "dataset_id": "application-total-audit",
            "experiment": "liquidation",
            "scenario": "bid_book",
            "seed": 42,
            "event_count": 1,
            "levels": 1,
            "event_sha256": "audit",
        }
        records = [
            {
                **base,
                "measurement_kind": "timing",
                "phase": "input_read_parse",
                "version": "shared",
                "repeat": 0,
                "elapsed_seconds": 0.25,
                "attempted": True,
                "stopped": False,
            },
            {
                **base,
                "measurement_kind": "timing",
                "phase": "build_plus_sale",
                "version": "baseline",
                "repeat": 0,
                "elapsed_seconds": None,
                "events_processed": 0,
                "attempted": False,
                "stopped": True,
                "stop_reason": "book build was not attempted",
            },
        ]

        benchmark_runner.append_application_totals(records)

        total = next(
            record
            for record in records
            if record["measurement_kind"] == "timing"
            and record["phase"] == "application_total"
        )
        self.assertEqual(total["elapsed_seconds"], 0.25)
        self.assertEqual(total["input_read_parse_seconds"], 0.25)
        self.assertIsNone(total["engine_seconds"])
        self.assertEqual(total["operation_attempted"], False)
        self.assertEqual(total["attempted"], True)
        self.assertEqual(total["stopped"], True)
        self.assertEqual(total["stop_reason"], "book build was not attempted")

    def test_dataset_generation_is_deterministic_and_identified(self) -> None:
        spec = DatasetSpec("stream", "mixed", 100, 42, 20)
        first = generate_events(spec)
        second = generate_events(spec)
        other = generate_events(DatasetSpec("stream", "mixed", 100, 43, 20))

        self.assertEqual(first, second)
        self.assertNotEqual(first, other)
        self.assertEqual(event_checksum(first), event_checksum(second))
        self.assertNotEqual(event_checksum(first), event_checksum(other))
        self.assertEqual([event["seq"] for event in first], list(range(1, 101)))
        self.assertIn("stream__mixed__m100__seed42__levels20", spec.dataset_id)

    def test_stable_gzip_round_trip_and_metadata(self) -> None:
        spec = DatasetSpec("stream", "buildup", 25, 7, 10)
        events = generate_events(spec)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f"{spec.dataset_id}.jsonl.gz"
            metadata = write_dataset(path, spec, events)
            loaded, loaded_metadata = load_dataset(path)

            self.assertEqual(loaded, events)
            self.assertEqual(loaded_metadata, metadata)
            self.assertEqual(metadata["event_sha256"], event_checksum(events))
            self.assertEqual(metadata["event_count"], 25)
            self.assertEqual(metadata["synthetic"], True)
            self.assertEqual(metadata["calibrated_to_exchange_data"], False)

    def test_liquidation_requests_use_fresh_book_percentages(self) -> None:
        spec = DatasetSpec("liquidation", "bid_book", 40, 42, 8)
        events = generate_events(spec)
        total = sum(event["qty_units"] for event in events)

        self.assertTrue(all(event["type"] == "LIMIT" for event in events))
        self.assertTrue(all(event["side"] == "BUY" for event in events))
        self.assertEqual(liquidation_request(total, 10), max(1, (total + 9) // 10))
        self.assertEqual(liquidation_request(total, 100), total)
        self.assertEqual(liquidation_request(total, 200), total * 2)

    def test_liquidation_correctness_work_respects_declared_limit(self) -> None:
        class SlowBaseline(BaselineOrderBook):
            def ProcessEvent(self, event):
                sleep(0.02)
                return super().ProcessEvent(event)

        spec = DatasetSpec("liquidation", "bid_book", 2, 42, 8)
        events = generate_events(spec)
        metadata = {
            "dataset_id": spec.dataset_id,
            "experiment": spec.experiment,
            "scenario": spec.scenario,
            "event_count": spec.event_count,
            "seed": spec.seed,
            "levels": spec.levels,
            "event_sha256": event_checksum(events),
        }
        with patch.dict(
            benchmark_runner.IMPLEMENTATIONS,
            {"baseline": SlowBaseline, "revised": RevisedOrderBook},
            clear=True,
        ):
            records = benchmark_runner.liquidation_measurements(
                events,
                metadata,
                versions=(),
                repeats=1,
                warmup_events=1,
                time_limit_seconds=0.01,
                include_memory=False,
            )

        correctness = [
            record
            for record in records
            if record["measurement_kind"] == "correctness"
        ]
        self.assertEqual(len(correctness), 3)
        self.assertTrue(all(record["stopped"] for record in correctness))
        self.assertTrue(
            all("baseline" in record["stop_reason"] for record in correctness)
        )

    def test_nearest_rank_percentile_convention(self) -> None:
        samples = [50, 10, 40, 20, 30]
        self.assertEqual(nearest_rank(samples, 0), 10)
        self.assertEqual(nearest_rank(samples, 50), 30)
        self.assertEqual(nearest_rank(samples, 95), 50)
        self.assertEqual(nearest_rank(samples, 100), 50)
        with self.assertRaises(ValueError):
            nearest_rank([], 50)

    def test_latency_separates_event_types_and_early_late_windows(self) -> None:
        events = generate_events(DatasetSpec("stream", "mixed", 100, 42, 20))
        latency = latency_replay(RevisedOrderBook, events, 2.0)

        self.assertEqual(latency["stopped"], False)
        self.assertEqual(latency["sample_count"], 100)
        self.assertEqual(sum(item["count"] for item in latency["by_event_type"].values()), 100)
        self.assertEqual(latency["early_window"]["count"], 10)
        self.assertEqual(latency["late_window"]["count"], 10)
        self.assertEqual(latency["early_late_window_size"], 10)
        for summary in (
            *latency["by_event_type"].values(),
            latency["early_window"],
            latency["late_window"],
        ):
            self.assertGreaterEqual(summary["p99_ns"], summary["p50_ns"])

    def test_diagnostics_are_version_independent(self) -> None:
        events = generate_events(DatasetSpec("stream", "mixed", 100, 42, 20))
        baseline = replay_diagnostics(BaselineOrderBook, events)
        revised = replay_diagnostics(RevisedOrderBook, events)

        self.assertEqual(baseline, revised)
        self.assertEqual(baseline["events_processed"], 100)
        self.assertGreaterEqual(baseline["active_order_peak"], 0)
        self.assertGreaterEqual(baseline["occupied_price_level_peak"], 0)
        self.assertGreaterEqual(baseline["fill_count"], 0)

    def test_traced_memory_has_explicit_boundary_and_fresh_runs(self) -> None:
        events = generate_events(DatasetSpec("stream", "cancel_churn", 100, 42, 20))
        first = traced_memory_replay(BaselineOrderBook, events)
        second = traced_memory_replay(RevisedOrderBook, events)

        for record in (first, second):
            self.assertGreaterEqual(record["peak_traced_bytes"], record["current_traced_bytes"])
            self.assertGreaterEqual(record["current_traced_bytes"], 0)
            self.assertEqual(record["input_included"], False)
            self.assertEqual(record["book_included"], True)
            self.assertEqual(record["final_output_included"], True)
            self.assertEqual(record["prior_outputs_retained"], False)
            self.assertEqual(record["tracing_scope"], "fresh_per_version")
            self.assertEqual(len(record["allocation_checkpoints"]), 3)
            self.assertEqual(
                record["allocation_checkpoints"][-1]["events_processed"],
                100,
            )

    def test_declared_time_limit_labels_stopped_timing_and_memory(self) -> None:
        class SlowBook:
            def ProcessEvent(self, event):
                del event
                while True:
                    pass

        timing = timed_replay(SlowBook, ({"seq": 1},), 0.01)
        memory = traced_memory_replay(SlowBook, ({"seq": 1},), 0.01)

        for record in (timing, memory):
            self.assertEqual(record["stopped"], True)
            self.assertIn("exceeded 0.01 seconds", record["stop_reason"])
            self.assertEqual(record["events_processed"], 0)
        self.assertGreaterEqual(memory["peak_traced_bytes"], 0)

    def test_report_schema_rejects_missing_or_invented_measurements(self) -> None:
        report = {
            "schema_version": 1,
            "run_label": "provisional_smoke",
            "environment": {"python_version": "test"},
            "settings": {"repeats": 1},
            "datasets": [],
            "records": [
                {
                    "measurement_kind": "timing",
                    "phase": "engine_replay",
                    "version": "baseline",
                    "repeat": 0,
                    "elapsed_seconds": 0.1,
                    "stopped": False,
                }
            ],
        }
        validate_report(report)

        missing_elapsed = dict(report)
        missing_elapsed["records"] = [dict(report["records"][0])]
        del missing_elapsed["records"][0]["elapsed_seconds"]
        with self.assertRaises(ValueError):
            validate_report(missing_elapsed)

        invented = dict(report)
        invented["records"] = [dict(report["records"][0], stopped=True)]
        with self.assertRaises(ValueError):
            validate_report(invented)

        not_attempted = dict(report)
        not_attempted["records"] = [
            {
                **report["records"][0],
                "stopped": True,
                "attempted": False,
                "elapsed_seconds": None,
                "stop_reason": "precondition stopped; phase not attempted",
            }
        ]
        validate_report(not_attempted)

        false_null = dict(report)
        false_null["records"] = [
            {
                **report["records"][0],
                "elapsed_seconds": None,
                "attempted": True,
            }
        ]
        with self.assertRaises(ValueError):
            validate_report(false_null)

    def test_revision_three_report_validation_rejects_contradictory_records(self) -> None:
        def report_with(*records):
            return {
                "schema_version": 1,
                "run_label": "provisional_smoke",
                "environment": {"python_version": "test"},
                "settings": {
                    "repeats": 5,
                    "parse_repeats": 5,
                    "measurement_integrity_revision": 3,
                },
                "datasets": [],
                "records": list(records),
            }

        timing = {
            "dataset_id": "d",
            "measurement_kind": "timing",
            "phase": "engine_replay",
            "version": "revised",
            "repeat": 0,
            "elapsed_seconds": 0.1,
            "attempted": True,
            "stopped": False,
        }
        summary = {
            "dataset_id": "d",
            "measurement_kind": "timing_summary",
            "phase": "engine_replay",
            "version": "revised",
            "repeat": None,
            "expected_repeat_count": 5,
            "completed_repeat_count": 2,
            "stopped_repeat_count": 0,
            "missing_repeat_count": 3,
            "completion_status": "complete",
            "elapsed_seconds_median": 0.1,
            "stopped": False,
        }
        memory = {
            "dataset_id": "d",
            "measurement_kind": "memory",
            "phase": "engine_replay",
            "version": "revised",
            "current_traced_bytes": -1,
            "peak_traced_bytes": 0,
            "stopped": False,
        }
        latency = {
            "dataset_id": "d",
            "measurement_kind": "latency",
            "phase": "per_event_instrumented",
            "version": "revised",
            "samples_ns": [10, 20, 30],
            "sample_count": 3,
            "p50_ns": 999,
            "p95_ns": 30,
            "p99_ns": 30,
            "stopped": False,
        }

        invalid_reports = {
            "nonboolean stopped": report_with({**timing, "stopped": 0}),
            "nonboolean attempted": report_with({**timing, "attempted": 1}),
            "contradictory summary": report_with(summary),
            "negative memory": report_with(memory),
            "incorrect latency percentile": report_with(latency),
            "duplicate raw repeat": report_with(timing, dict(timing)),
        }
        for label, report in invalid_reports.items():
            with self.subTest(label=label), self.assertRaises(ValueError):
                validate_report(report)

    def test_revision_three_summaries_reconcile_with_raw_timing_rows(self) -> None:
        timing = {
            "dataset_id": "d",
            "measurement_kind": "timing",
            "phase": "engine_replay",
            "version": "revised",
            "repeat": 0,
            "elapsed_seconds": 0.1,
            "attempted": True,
            "stopped": False,
        }
        summary = {
            "dataset_id": "d",
            "measurement_kind": "timing_summary",
            "phase": "engine_replay",
            "version": "revised",
            "repeat": None,
            "expected_repeat_count": 1,
            "completed_repeat_count": 1,
            "stopped_repeat_count": 0,
            "missing_repeat_count": 0,
            "completion_status": "complete",
            "elapsed_seconds_median": 0.1,
            "stopped": False,
        }
        report = {
            "schema_version": 1,
            "run_label": "provisional_smoke",
            "environment": {"python_version": "test"},
            "settings": {"measurement_integrity_revision": 3},
            "datasets": [],
            "records": [timing, summary],
        }
        validate_report(report)

        bad_median = {
            **report,
            "records": [timing, {**summary, "elapsed_seconds_median": 9.9}],
        }
        with self.assertRaisesRegex(ValueError, "median"):
            validate_report(bad_median)

        bad_count = {
            **report,
            "records": [
                timing,
                {
                    **summary,
                    "expected_repeat_count": 2,
                    "completed_repeat_count": 2,
                },
            ],
        }
        with self.assertRaisesRegex(ValueError, "raw timing"):
            validate_report(bad_count)

    def test_empty_report_cannot_claim_canonical_evidence(self) -> None:
        empty_canonical = {
            "schema_version": 1,
            "run_label": "canonical",
            "environment": {"git_dirty": False},
            "settings": {"measurement_integrity_revision": 3},
            "datasets": [],
            "records": [],
        }

        with self.assertRaisesRegex(ValueError, "canonical"):
            validate_report(empty_canonical)

    def test_revision_four_canonical_evidence_is_tied_to_datasets_and_commit(self) -> None:
        current_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        record = {
            "dataset_id": "declared",
            "measurement_kind": "correctness",
            "phase": "diagnostic_prefix",
            "version": "shared",
            "stopped": False,
        }
        canonical = {
            "schema_version": 1,
            "run_label": "canonical",
            "environment": {"git_dirty": False, "git_commit": current_commit},
            "settings": {"measurement_integrity_revision": 4},
            "datasets": [{"dataset_id": "declared"}],
            "records": [record],
        }
        validate_report(canonical)

        undeclared = {
            **canonical,
            "records": [{**record, "dataset_id": "not-declared"}],
        }
        with self.assertRaisesRegex(ValueError, "declared dataset"):
            validate_report(undeclared)

        nonexistent_commit = {
            **canonical,
            "environment": {"git_dirty": False, "git_commit": "0" * 40},
        }
        with self.assertRaisesRegex(ValueError, "git commit"):
            validate_report(nonexistent_commit)


if __name__ == "__main__":
    unittest.main()
