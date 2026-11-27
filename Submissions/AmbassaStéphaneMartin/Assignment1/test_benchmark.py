"""Independent checks of benchmark arithmetic, boundaries and small experiments."""

import argparse
import json
from pathlib import Path
import tempfile
import subprocess
import tracemalloc
import unittest
from unittest.mock import patch

import benchmark as bm
from order_book import BaselineOrderBook, RevisedOrderBook


def arguments(**changes):
    values = dict(counts=[12], seeds=[42], experiments=["replay"],
                  scenarios=["buildup"], levels=1000, versions=list(bm.VERSIONS))
    values.update(changes)
    return argparse.Namespace(**values)


class TestMeasurements(unittest.TestCase):
    def test_known_latency_percentiles_and_throughput(self):
        metrics = bm.latency_statistics(list(range(1, 101)))
        self.assertEqual(metrics["latency_median_seconds"], 50.5)
        self.assertEqual(metrics["latency_p95_seconds"], 95)
        self.assertEqual(metrics["latency_p99_seconds"], 99)
        self.assertEqual(bm.latency_statistics([4, 1, 3, 2])["latency_median_seconds"], 2.5)
        self.assertEqual(bm.latency_statistics([4, 1, 3, 2])["latency_p95_seconds"], 4)
        self.assertEqual(bm.throughput(10, 2), 5)
        self.assertIsNone(bm.throughput(10, 0))

    def test_sale_fraction_is_exact_above_float_precision(self):
        self.assertEqual([bm.requested_quantity(11, p) for p in (10, 100, 200)], [2, 11, 22])
        depth = 10 ** 30 + 1
        self.assertEqual(bm.requested_quantity(depth, 10), 10 ** 29 + 1)
        self.assertEqual(bm.requested_quantity(depth, 200), 2 * depth)
        self.assertIs(type(bm.requested_quantity(depth, 10)), int)

    def test_total_compute_is_median_of_per_repetition_sums(self):
        rows = []
        for init, replay in zip([1, 2, 10, 100, 200], [200, 100, 10, 2, 1]):
            row = dict.fromkeys(bm.METRICS)
            row.update(status="complete", error=None, initialization_seconds=init,
                       replay_seconds=replay, total_compute_seconds=init + replay)
            rows.append(row)
        summary = bm.summarize(rows, 5)
        self.assertEqual(summary["total_compute_seconds"], 102)
        self.assertEqual(summary["initialization_seconds"], 10)
        self.assertEqual(summary["replay_seconds"], 10)

    def test_incomplete_summary_does_not_invent_measurements(self):
        rows = [dict.fromkeys(bm.METRICS) for _ in range(5)]
        for index, row in enumerate(rows):
            row.update(status="complete" if index == 0 else "stopped",
                       error=None if index == 0 else "wall limit", replay_seconds=1 if index == 0 else None)
        summary = bm.summarize(rows, 5)
        self.assertEqual(summary["status"], "incomplete")
        self.assertEqual(summary["completed_repetitions"], 1)
        self.assertIsNone(summary["replay_seconds"])

    def test_primary_clocks_and_fresh_book_boundaries(self):
        books = []
        class Probe:
            def __init__(self):
                self.events = []
                books.append(self)

            def process_event(self, event):
                self.events.append(event)
                return {"fills": [], "unfilled_qty_units": 0}

            def inspect_book(self):
                raise AssertionError("Primary timing must not inspect the book")
        bm.warm_up(Probe, [], [{"seq": 1}])
        for _ in range(5):
            with patch.object(bm.time, "perf_counter", side_effect=[10, 12, 20, 24, 30, 35]):
                row = bm.timed_once(Probe, [{"seq": 1}], [{"seq": 2}], True)
            self.assertEqual(row["initialization_seconds"], 2)
            self.assertEqual(row["construction_seconds"], 4)
            self.assertEqual(row["replay_seconds"], 5)
            self.assertEqual(row["total_compute_seconds"], 11)
            self.assertEqual(row["throughput_events_per_second"], 0.2)
        self.assertEqual(len(books), 6)
        self.assertTrue(all(len(book.events) == 2 for book in books[1:]))

    def test_complete_required_campaign_matrix(self):
        cases = bm.case_matrix(arguments(counts=[1000, 10000, 100000], seeds=[42, 43, 44],
                                         scenarios=list(bm.SCENARIOS)))
        self.assertEqual(len(cases), 45)
        self.assertEqual(len({case["case_id"] for case in cases}), 45)
        self.assertEqual({case["scenario"] for case in cases}, set(bm.SCENARIOS))

    def test_timeout_preserves_completed_repetitions_and_labels_missing_ones(self):
        with tempfile.TemporaryDirectory() as directory:
            case = bm.case_matrix(arguments())[0]
            case["source"] = {"path": "unused.jsonl.gz", "sha256": "unused"}
            job = dict(case=case, version="baseline", phase="timing",
                       checkpoint=str(Path(directory) / "checkpoint.json"))
            first = bm.base_row(job, 1)
            first["replay_seconds"] = 2
            bm.write_json(job["checkpoint"], dict(status="running", rows=[first], error=None))
            with patch.object(bm.subprocess, "run", side_effect=subprocess.TimeoutExpired("worker", 1)):
                rows, summary = bm.run_job(job, 1)
            self.assertEqual(rows[0]["replay_seconds"], 2)
            self.assertEqual([r["status"] for r in rows], ["complete"] + ["stopped"] * 4)
            self.assertTrue(all(r["replay_seconds"] is None for r in rows[1:]))
            self.assertEqual(summary["completed_repetitions"], 1)
            self.assertIsNone(summary["replay_seconds"])


    def test_single_sale_price_levels_are_calculated_after_the_clock_stops(self):
        test = self

        class GuardedFill(dict):
            def __getitem__(self, key):
                if key == "price_ticks":
                    test.assertEqual(clock.call_count, 6)
                return super().__getitem__(key)

        class Probe:
            def process_event(self, event):
                return {"fills": [GuardedFill(price_ticks=6_000_000),
                                  GuardedFill(price_ticks=6_000_000)],
                        "unfilled_qty_units": 0}

        with patch.object(bm.time, "perf_counter", side_effect=[10, 12, 20, 24, 30, 35]) as clock:
            metrics = bm.timed_once(Probe, [{"seq": 1}], [{"seq": 2}], True)
        self.assertEqual(metrics["replay_seconds"], 5)
        self.assertEqual(metrics["fill_count"], 2)
        self.assertEqual(metrics["price_levels_visited"], 1)

    def test_price_levels_are_summarized_and_remain_null_when_incomplete(self):
        rows = []
        for levels in (1, 3, 1, 2, 3):
            row = dict.fromkeys(bm.METRICS)
            row.update(status="complete", error=None, price_levels_visited=levels)
            rows.append(row)
        self.assertEqual(bm.summarize(rows, 5)["price_levels_visited"], 2)
        rows[-1].update(status="stopped", error="wall limit", price_levels_visited=None)
        self.assertIsNone(bm.summarize(rows, 5)["price_levels_visited"])

    def test_diagnostic_comparison_detects_price_level_mismatch(self):
        common = dict(case_id="known-sale", phase="diagnostics", status="complete",
                      result_digest="same-result", snapshot_digest="same-book",
                      fill_count=4, unfilled_qty_units=0, cancelled_qty_units=0,
                      rejected_event_count=0)
        left = dict(common, version="baseline", price_levels_visited=3)
        right = dict(common, version="revised", price_levels_visited=2)
        self.assertEqual(bm.validate_diagnostics([left, right]),
                         [{"case_id": "known-sale", "status": "failed"}])
        right["price_levels_visited"] = 3
        self.assertEqual(bm.validate_diagnostics([left, right]),
                         [{"case_id": "known-sale", "status": "passed"}])


class TestWorkloadsAndExperiments(unittest.TestCase):
    def test_single_sale_price_levels_from_independently_known_fills(self):
        unit = 100_000_000
        bids = [
            dict(seq=seq, event_id=name, type="LIMIT", order_id=name, side="BUY",
                 price_ticks=price, qty_units=quantity * unit)
            for seq, name, price, quantity in (
                (1, "A", 6_000_000, 2), (2, "B", 6_000_000, 1),
                (3, "C", 5_999_999, 7), (4, "D", 5_999_998, 20))
        ]
        ask = [dict(seq=1, event_id="ask", type="LIMIT", order_id="ask", side="SELL",
                    price_ticks=6_000_100, qty_units=unit)]
        # Thirty BTC across four makers and three prices. Counts below are literal
        # expectations, independent of the benchmark's distinct-price calculation.
        cases = (
            ("same price", bids, 10, 3 * unit, 2, 1, 0),
            ("multiple prices", bids, 100, 30 * unit, 4, 3, 0),
            ("oversized", bids, 200, 60 * unit, 4, 3, 30 * unit),
            ("no fills", ask, 100, unit, 0, 0, unit),
        )
        for label, setup, percent, quantity, fills, levels, residual in cases:
            for experiment in ("market-sell", "queue-concentration"):
                for version, factory in (("baseline", BaselineOrderBook), ("revised", RevisedOrderBook)):
                    with self.subTest(case=label, experiment=experiment, version=version):
                        task = [dict(seq=len(setup) + 1, event_id="sale", type="MARKET_SELL",
                                     order_id="sale", qty_units=quantity)]
                        case = dict(experiment=experiment, sale_percent=percent)
                        timed = bm.timed_once(factory, setup, task, True)
                        diagnostic = bm.diagnostics_once(factory, version, case, setup, task)
                        for metrics in (timed, diagnostic):
                            self.assertEqual(metrics["fill_count"], fills)
                            self.assertEqual(metrics["price_levels_visited"], levels)
                            self.assertIs(type(metrics["price_levels_visited"]), int)
                            self.assertEqual(metrics["unfilled_qty_units"], residual)

    def test_replay_price_levels_remain_not_applicable(self):
        rows = list(bm.controlled_orders(4, 42, 4))
        task = rows + [dict(seq=5, event_id="sale", type="MARKET_SELL",
                            order_id="sale", qty_units=1)]
        case = dict(experiment="replay", sale_percent=None)
        for version, factory in (("baseline", BaselineOrderBook), ("revised", RevisedOrderBook)):
            metrics = bm.diagnostics_once(factory, version, case, [], task)
            self.assertEqual(metrics["fill_count"], 1)
            self.assertIsNone(metrics["price_levels_visited"])

    def test_decompression_budget_applies_to_decoded_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.jsonl.gz"
            path.write_bytes(bm.gzip.compress(b" " * 5000))
            self.assertLess(path.stat().st_size, 128)
            with self.assertRaisesRegex(ValueError, "Decompressed payload limit"):
                bm.load_events(path, 128, 1)

    def test_memory_budget_stops_tracing_after_failure(self):
        rows = list(bm.controlled_orders(3, 42, 4))
        with self.assertRaisesRegex(MemoryError, "Traced allocation limit"):
            bm.memory_once(RevisedOrderBook, [], rows, {"experiment": "replay"}, 1)
        self.assertFalse(tracemalloc.is_tracing())

    def test_workload_reuse_preserves_bytes_and_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            case = bm.case_matrix(arguments())[0]
            first = bm.ensure_workload(case, directory)
            before = Path(first["path"]).read_bytes()
            second = bm.ensure_workload(case, directory)
            self.assertTrue(second["reused"])
            self.assertEqual(Path(second["path"]).read_bytes(), before)
            Path(second["path"]).write_bytes(before + b"corruption")
            with self.assertRaisesRegex(ValueError, "checksum"):
                bm.ensure_workload(case, directory)

    def test_supplied_fixture_selection_does_not_overwrite_other_seed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "buildup_12.jsonl.gz"
            bm.generate_orders.write_stream(path, bm.generate_orders.events("buildup", 12, 42, 1000))
            bm.write_json(path.with_suffix(".gz.metadata.json"),
                          dict(scenario="buildup", events=12, seed=42, levels=1000, sha256=bm.sha256(path)))
            before = path.read_bytes()
            original = bm.ensure_workload(bm.case_matrix(arguments())[0], directory)
            other = bm.ensure_workload(bm.case_matrix(arguments(seeds=[43]))[0], directory)
            self.assertEqual(Path(original["path"]), path)
            self.assertNotEqual(other["path"], original["path"])
            self.assertEqual(path.read_bytes(), before)

    def test_io_phases_and_integer_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orders.jsonl"
            row = {"seq": 1, "event_id": "one", "qty_units": 100_000_000}
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            events, metrics = bm.load_events(path, 4096, 1)
            self.assertEqual(events, [row])
            self.assertIsNone(metrics["decompress_seconds"])
            self.assertEqual(metrics["io_total_seconds"], metrics["read_seconds"] + metrics["parse_seconds"])
            for invalid in (True, 1.0, 0, -1):
                row["qty_units"] = invalid
                path.write_text(json.dumps(row), encoding="utf-8")
                with self.assertRaises(ValueError):
                    bm.load_events(path, 4096, 1)
            with self.assertRaisesRegex(ValueError, "payload"):
                bm.load_events(path, 1, 1)

    def test_known_sales_match_integer_fifo_oracle(self):
        rows = [
            {"seq": seq, "event_id": name, "order_id": name, "type": "LIMIT",
             "side": "BUY", "price_ticks": price, "qty_units": quantity}
            for seq, name, price, quantity in ((1, "A", 100, 3), (2, "B", 101, 7), (3, "C", 100, 1))
        ]
        # Total depth 11: ceil(10%)=2, 100%=11, 200%=22.
        expected = {10: (["B"], [2], 0), 100: (["B", "A", "C"], [7, 3, 1], 0),
                    200: (["B", "A", "C"], [7, 3, 1], 11)}
        for percent, (makers, quantities, residual) in expected.items():
            case = {"sale_percent": percent}
            setup, task, quantity = bm.split_task(case, rows)
            for factory in (BaselineOrderBook, RevisedOrderBook):
                book = factory()
                bm.replay(book, setup)
                result = book.process_event(task[0])
                self.assertEqual([fill["maker_id"] for fill in result["fills"]], makers)
                self.assertEqual([fill["qty_units"] for fill in result["fills"]], quantities)
                self.assertEqual(result["unfilled_qty_units"], residual)
                self.assertEqual(quantity, {10: 2, 100: 11, 200: 22}[percent])

    def test_controlled_queue_concentration_and_churn_against_baseline(self):
        for levels in (4, 1000):
            rows = list(bm.controlled_orders(12, 42, levels))
            self.assertEqual(len(rows), 12)
            self.assertEqual(len({row["price_ticks"] for row in rows}), min(12, levels))
        baseline, revised = BaselineOrderBook(), RevisedOrderBook()
        retained_peak = 0
        rows = list(bm.churn_orders(120))
        for event in rows:
            self.assertEqual(baseline.process_event(event), revised.process_event(event))
            self.assertEqual(baseline.inspect_book(), revised.inspect_book())
            counts = bm.storage_counts(revised, "revised")
            self.assertLessEqual(counts["retained_queue_entries"],
                                 2 * counts["active_orders"] + 32 * counts["occupied_prices"])
            retained_peak = max(retained_peak, counts["retained_queue_entries"])
        self.assertGreater(retained_peak, 2)
        self.assertEqual(bm.storage_counts(revised, "revised")["retained_queue_entries"], 0)

    def test_diagnostics_counts_known_peaks_fills_and_residual(self):
        case = {"experiment": "market-sell", "sale_percent": 200}
        rows = list(bm.controlled_orders(4, 42, 4))
        setup, task, _ = bm.split_task(case, rows)
        diagnostics = [bm.diagnostics_once(factory, version, case, setup, task)
                       for factory, version in ((BaselineOrderBook, "baseline"), (RevisedOrderBook, "revised"))]
        for result in diagnostics:
            self.assertEqual(result["active_orders_peak"], 4)
            self.assertEqual(result["occupied_prices_peak"], 4)
            self.assertEqual(result["fill_count"], 4)
            self.assertEqual(result["unfilled_qty_units"], sum(row["qty_units"] for row in rows))
            self.assertEqual(result["active_orders_final"], 0)
        self.assertEqual(diagnostics[0]["result_digest"], diagnostics[1]["result_digest"])
        self.assertEqual(diagnostics[0]["snapshot_digest"], diagnostics[1]["snapshot_digest"])


if __name__ == "__main__":
    unittest.main()

