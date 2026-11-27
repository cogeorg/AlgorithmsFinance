"""Tests of the workload generators, measurement helpers, result files and dashboard export.

Added after the engines; the engine tests are in test_orderbook.py and test_adversarial.py.
The benchmark workers run in-process here on tiny inputs, so nothing is timed for the report.
"""
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock

import benchmark
import book_b
from book_a import OrderBookA
from book_b import OrderBookB
import dashboard
from events import format_usd
from instrumented import CountingBookB
from test_adversarial import hunting_stream
from test_orderbook import cancel, limit, market
import verify_results
import workloads

HERE = Path(__file__).resolve().parent
TINY = {"sizes": [200], "single_seed_sizes": [], "seeds": [42], "levels": 1000, "repeats": 5,
        "replay_limit_seconds": 30.0, "sale_limit_seconds": 30.0, "memory_limit_bytes": 256 << 20,
        "fixed_single_seed_sizes": [], "concentration_orders": 200, "concentration_levels": [4],
        "concentration_seeds": [42], "sale_percents": [10, 100, 200], "order_seed": 7}


class StatisticsTests(unittest.TestCase):
    def test_nearest_rank_percentile(self):
        hundred = list(range(1, 101))
        self.assertEqual([benchmark.percentile(hundred, p) for p in (50, 95, 99, 100)], [50, 95, 99, 100])
        self.assertEqual([benchmark.percentile([7], p) for p in (50, 95, 99)], [7, 7, 7])
        self.assertEqual([benchmark.percentile([1, 2, 3, 4], p) for p in (50, 75, 76, 95)], [2, 3, 4, 4])
        self.assertEqual(benchmark.percentile([10, 20, 30], 1), 10)
        self.assertIsNone(benchmark.percentile([], 50))

    def test_latency_summary_is_order_independent(self):
        summary = benchmark.latency_summary([900, 100, 500, 300, 700])
        self.assertEqual((summary["count"], summary["p50_ns"], summary["p99_ns"], summary["max_ns"], summary["mean_ns"]),
                         (5, 500, 900, 900, 500))
        self.assertEqual(benchmark.latency_summary([]), {"count": 0})

    def test_histogram_bins_cover_every_value(self):
        values = [0, 1, 99, 100, 158, 159, 999, 1000, 10**9, 10**12]
        bins = benchmark.histogram(values)
        self.assertEqual(sum(bins), len(values))
        self.assertEqual(bins[0], 5)                   # below 10^2.2 ns, including clamped small values
        self.assertEqual(bins[1], 1)                   # 159 ns
        self.assertEqual(bins[4], 1)                   # 999 ns
        self.assertEqual(bins[5], 1)                   # exactly 1 microsecond starts the second decade
        self.assertEqual(bins[-1], 1)                  # clamped large value

    def test_block_bounds_hit_every_checkpoint_and_respect_block_size(self):
        for count in (20, 137, 1000, 30_000, 100_000, 1_000_003):
            bounds = benchmark.block_bounds(count)
            ends = [end for end, _ in bounds]
            self.assertEqual(ends, sorted(set(ends)))
            self.assertEqual(ends[-1], count)
            self.assertEqual([end for end, mark in bounds if mark],
                             sorted({count * i // 20 for i in range(1, 21)} - {0}))
            self.assertLessEqual(max(b - a for a, b in zip([0] + ends, ends)), benchmark.BLOCK_MAX)


class WorkloadTests(unittest.TestCase):
    def test_mass_cancel_shape_and_reproducibility(self):
        for count in (8, 200, 1001):
            events = list(workloads.mass_cancel_events(count, 42, 1000))
            self.assertEqual(events, list(workloads.mass_cancel_events(count, 42, 1000)))
            self.assertNotEqual(events, list(workloads.mass_cancel_events(count, 43, 1000)))
            self.assertEqual([e["seq"] for e in events], list(range(1, count + 1)))
            adds, spared = count // 2, max(2, count // 100)
            self.assertTrue(all(e["type"] == "LIMIT" for e in events[:adds]))
            self.assertTrue(all(e["type"] == "CANCEL" for e in events[adds:]))
            self.assertEqual(workloads.build_boundary("mass_cancel", count), adds)
            for cls in (OrderBookA, OrderBookB):
                book = cls()
                statuses = [book.ProcessEvent(e)["status"] for e in events]
                self.assertEqual(statuses.count("resting"), adds)          # passive: nothing trades
                self.assertEqual(statuses.count("cancelled"), adds - spared)
                self.assertEqual(statuses.count("not_found"), count - adds - (adds - spared))
                self.assertEqual(book.active_orders(), spared)

    def test_sale_quantity_rounds_up_to_at_least_one_unit(self):
        self.assertEqual([workloads.sale_quantity(total, 10) for total in (1, 5, 10, 11, 1000)], [1, 1, 1, 2, 100])
        self.assertEqual(workloads.sale_quantity(7, 100), 7)
        self.assertEqual(workloads.sale_quantity(7, 200), 14)

    def test_sorted_fill_plan_agrees_with_both_engines(self):
        for levels in (1, 4, 1000):
            bids = list(workloads.bid_book_events(300, levels, 5))
            total = sum(b["qty_units"] for b in bids)
            for percent in (10, 100, 200):
                wanted = workloads.sale_quantity(total, percent)
                fills, unfilled = workloads.plan_market_sell(bids, wanted, "sale")
                self.assertEqual(sum(f["qty_units"] for f in fills) + unfilled, wanted)
                for cls in (OrderBookA, OrderBookB):
                    book = cls()
                    for bid in bids:
                        book.ProcessEvent(bid)
                    result = book.FillMarketSell("sale", wanted)
                    self.assertEqual((result["fills"], result["unfilled_qty_units"]), (fills, unfilled))

    def test_supplied_sample_is_used_and_generated_files_are_described(self):
        self.assertEqual(workloads.dataset_path("mixed", 10_000, 42), HERE / "data" / "mixed_10000.jsonl.gz")
        info = workloads.ensure_dataset("mixed", 10_000, 42)
        recorded = json.loads((HERE / "data" / "mixed_10000.jsonl.gz.metadata.json").read_text(encoding="utf-8"))
        self.assertTrue(info["supplied_with_assignment"])
        self.assertEqual(info["sha256_compressed"], recorded["sha256"])
        other = workloads.ensure_dataset("mass_cancel", 200, 42)
        self.assertFalse(other["supplied_with_assignment"])
        self.assertIn("workloads.py --scenario mass_cancel --events 200", other["command"])

    def test_display_rounding_happens_only_in_formatting(self):
        self.assertEqual(format_usd(3_594_000_000_000_000), "359400.00")
        self.assertEqual(format_usd(1), "0.00")
        self.assertEqual(format_usd(50_000_000), "0.00")          # half a cent rounds to even
        self.assertEqual(format_usd(150_000_000), "0.02")
        self.assertEqual(format_usd(10**40 + 10**10), "1000000000000000000000000000001.00")


class CounterTests(unittest.TestCase):
    """The operation counts must describe the real heap work (found wrong by an independent review)."""

    def test_push_and_stale_discard_are_counted_when_a_match_rebuilds_the_heaps(self):
        events = [limit(i + 1, f"b{i}", "BUY", 900 - i, 1) for i in range(50)]
        events.append(limit(51, "a0", "SELL", 1000, 1))
        seq = 51
        for i in [9] + list(range(13, 50)):
            seq += 1
            events.append(cancel(seq, f"b{i}"))
        book = CountingBookB()
        for event in events:
            book.ProcessEvent(event)
        self.assertEqual((book.counters["heap_pushes"], book.counters["heap_rebuilds"]), (51, 0))
        result = book.ProcessEvent(limit(seq + 1, "x", "SELL", 890, 11))
        self.assertEqual((len(result["fills"]), result["unfilled_qty_units"]), (10, 1))
        self.assertEqual(book.counters["heap_rebuilds"], 1)
        self.assertEqual(book.counters["heap_pushes"], 52)           # the residual opened level 890
        self.assertEqual(book.counters["stale_heap_discards"], 1)    # the entry of cancelled b9 at 891
        self.assertEqual(book.counters["heap_pops"], 10)             # ten levels emptied by matching
        book.check_invariants()

    def test_stale_entries_discarded_by_inspection_are_counted(self):
        book = CountingBookB()
        for event in (limit(1, "p", "BUY", 100, 1), limit(2, "q", "BUY", 90, 1), cancel(3, "p")):
            book.ProcessEvent(event)
        self.assertEqual(book.best_bid(), 90)
        self.assertEqual(book.counters["stale_heap_discards"], 1)
        book.ProcessEvent(market(4, "m", 1))
        self.assertEqual((book.counters["stale_heap_discards"], book.counters["heap_pops"]), (1, 1))

    def test_counts_balance_with_heap_sizes_and_results_are_unchanged(self):
        # Without rebuilds, every heap entry is one push that has not been popped yet.
        with mock.patch.object(book_b, "HEAP_SLACK", 10**9):
            for seed in range(8):
                plain, counting = OrderBookB(), CountingBookB()
                for event in hunting_stream(random.Random(seed), 600, prices=(1, 60)):
                    self.assertEqual(counting.ProcessEvent(event), plain.ProcessEvent(event))
                    c = counting.counters
                    self.assertEqual(c["heap_pushes"] - c["heappop_calls"],
                                     len(counting._bid_heap) + len(counting._ask_heap))
                    self.assertEqual(c["heappop_calls"], c["heap_pops"] + c["stale_heap_discards"])
                self.assertEqual(counting.InspectBook(), plain.InspectBook())
        self.assertIs(book_b.heappop.__module__, "_heapq")           # the wrappers were removed again


class WorkerTests(unittest.TestCase):
    def replay_spec(self, version, scenario="mixed", count=400, **extra):
        info = workloads.ensure_dataset(scenario, count, 42)
        spec = {"experiment": "replay", "version": version, "scenario": scenario, "seed": 42, "events": count,
                "levels": 1000, "file": info["file"], "repeats": 5, "replay_limit_seconds": 30.0,
                "memory_limit_bytes": 256 << 20}
        spec.update(extra)
        return spec

    def test_replay_cell_has_all_separate_passes_and_versions_agree(self):
        rows = {}
        for version in "AB":
            spec = self.replay_spec(version)
            messages, note = benchmark.run_child("replay", spec, in_process=True)
            row = rows[version] = benchmark.collect_replay(spec, messages, note)
            self.assertEqual(row["status"], "ok", row.get("error"))
            self.assertEqual([r["repeat"] for r in row["repeats"]], [1, 2, 3, 4, 5])
            self.assertTrue(all(len(r["checkpoint_seconds"]) == 20 for r in row["repeats"]))
            self.assertEqual(row["latency"]["overall"]["count"], 400)
            self.assertEqual(sum(s["count"] for s in row["latency"]["by_type"].values()), 400)
            self.assertEqual(len(row["latency"]["deciles"]), 10)
            self.assertEqual(len(row["memory"]["checkpoints"]), 20)
            self.assertGreaterEqual(row["memory"]["peak_bytes"], row["memory"]["final_current_bytes"])
            self.assertFalse(row["memory"]["input_inside_trace"])
            self.assertTrue(row["counters"])
        for key in ("results_sha256", "book_sha256", "statuses", "fill_count", "peak_active_orders"):
            self.assertEqual(rows["A"]["outcome"][key], rows["B"]["outcome"][key])
        self.assertIsNone(rows["A"]["outcome"]["peak_price_levels"])
        self.assertGreater(rows["B"]["outcome"]["peak_price_levels"], 0)

    def test_phase_split_for_build_then_sweep(self):
        spec = self.replay_spec("B", scenario="sweep")
        row = benchmark.collect_replay(spec, *benchmark.run_child("replay", spec, in_process=True))
        self.assertEqual(row["build_events"], 320)
        self.assertAlmostEqual(row["build_seconds_median"] + row["tail_seconds_median"], row["replay_seconds_median"],
                               delta=row["replay_seconds_median"])
        self.assertGreater(row["build_seconds_median"], 0)

    def test_replay_over_its_limit_is_reported_as_stopped_not_dropped(self):
        spec = self.replay_spec("A", scenario="buildup", count=2000, replay_limit_seconds=0.0)
        row = benchmark.collect_replay(spec, *benchmark.run_child("replay", spec, in_process=True))
        self.assertEqual(row["status"], "stopped")
        self.assertLess(row["events_completed"], 2000)
        self.assertEqual(len(row["repeats"]), 1)
        self.assertIsNone(row["latency"])
        self.assertIsNone(row["memory"])
        self.assertNotIn("replay_seconds_median", row)

    def test_fixed_book_sale_counts_explain_the_baseline(self):
        orders = 120
        for version in "AB":
            spec = {"experiment": "fixed_book", "scenario": "bid_book", "version": version, "seed": 42,
                    "book_orders": orders, "levels": 1000, "sale_pct": 100, "repeats": 5, "sale_limit_seconds": 30.0}
            row = benchmark.collect_fixed(spec, *benchmark.run_child("fixed_book", spec, in_process=True))
            self.assertEqual(row["status"], "ok", row.get("error"))
            outcome = row["outcome"]
            self.assertTrue(outcome["matches_sorted_fill_plan"])
            self.assertEqual((outcome["fill_count"], outcome["makers_touched"], outcome["unfilled_qty_units"],
                              outcome["remaining_orders"]), (orders, orders, 0, 0))
            self.assertEqual(row["requested_qty_units"], row["available_bid_qty_units"])
            self.assertTrue(all(r["sell_seconds"] > 0 and r["construction_seconds"] > 0 for r in row["repeats"]))
            if version == "A":       # one full scan per fill over a list shrinking from N to 1
                self.assertEqual(row["counters"]["records_examined_best"], orders * (orders + 1) // 2)
                self.assertEqual(row["counters"]["best_scans"], orders)
            else:                    # one heap pop per emptied price level
                self.assertEqual(row["counters"]["heap_pops"], outcome["price_levels_visited"])

    def test_oversized_sale_reports_the_discarded_remainder(self):
        spec = {"experiment": "fixed_book", "scenario": "bid_book", "version": "B", "seed": 42, "book_orders": 50,
                "levels": 4, "sale_pct": 200, "repeats": 5, "sale_limit_seconds": 30.0}
        row = benchmark.collect_fixed(spec, *benchmark.run_child("fixed_book", spec, in_process=True))
        self.assertEqual(row["outcome"]["status"], "partial")
        self.assertEqual(row["outcome"]["unfilled_qty_units"], row["available_bid_qty_units"])
        self.assertEqual(row["outcome"]["price_levels_visited"], row["outcome"]["peak_price_levels"])

    def test_worker_error_is_reported_as_an_error_row(self):
        spec = self.replay_spec("A", file="data/does_not_exist.jsonl.gz")
        row = benchmark.collect_replay(spec, *benchmark.run_child("replay", spec, in_process=True))
        self.assertEqual(row["status"], "error")
        self.assertIn("does_not_exist", row["error"])


class PipelineTests(unittest.TestCase):
    def test_tiny_run_saves_consistent_files_and_a_reproducible_dashboard(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            folder = Path(folder)
            data = benchmark.run(folder, TINY, in_process=True)
            self.assertFalse((folder / "measurements.partial.json").exists())
            self.assertEqual(len(data["replay"]), 2 * len(workloads.SCENARIOS))
            self.assertEqual(len(data["fixed_book"]), 2 * 2 * 3)
            saved = json.loads((folder / "measurements.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["metadata"]["settings"], TINY)
            self.assertTrue(all(row["status"] == "ok" for row in saved["replay"] + saved["fixed_book"]))
            a_rows = [r for r in saved["replay"] if r["version"] == "A"]
            self.assertTrue(all(r["outcome"]["peak_price_levels"] is not None for r in a_rows))
            (folder / "test_after.txt").write_text("Ran 12 tests in 1.0s\n\nOK\n", encoding="utf-8")
            (folder / "test_before.txt").write_text("Ran 12 tests in 0.1s\n\nFAILED (errors=30)\n", encoding="utf-8")
            (folder / "note.json").write_text("{}", encoding="utf-8")
            dashboard.build(folder / "measurements.json", folder / "dashboard.html")
            page = (folder / "dashboard.html").read_text(encoding="utf-8")
            payload = page.split('<script type="application/json" id="dataset">', 1)[1].split("</script>", 1)[0]
            embedded = json.loads(payload)
            self.assertEqual(embedded["replay"], saved["replay"])
            self.assertEqual(embedded["tests"]["after"]["passed"], 12)
            self.assertEqual((embedded["tests"]["before"]["problems"], embedded["tests"]["before"]["passed"]), (30, None))
            self.assertNotIn("__DATA__", page)
            self.assertNotIn("__JSON_LINK__", page)
            self.assertNotIn(b"\r\n", (folder / "dashboard.html").read_bytes())
            report = verify_results.verify(folder)
            self.assertTrue(report["dashboard_byte_identical_rebuild"])
            self.assertEqual(report["cells_stopped_at_declared_limit"], 0)

    def test_resume_reuses_finished_cells(self):
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            folder = Path(folder)
            settings = dict(TINY, sale_percents=[100], concentration_levels=[])
            first = benchmark.run(folder, settings, in_process=True)
            cells = {benchmark.cell_key(kind, spec): {"status": "ok", "experiment": spec["experiment"], "marker": True, "events": None,
                                                      **{k: v for k, v in spec.items()}, "repeats": []}
                     for kind, spec in benchmark.build_plan(settings)[1]}
            (folder / "measurements.partial.json").write_text(json.dumps(
                {"settings": settings, "source_sha256": benchmark.source_hashes(), "cells": cells}), encoding="utf-8")
            second = benchmark.run(folder, settings, resume=True, in_process=True)
            self.assertTrue(all(row.get("marker") for row in second["replay"] + second["fixed_book"]))
            self.assertFalse(any(row.get("marker") for row in first["replay"]))

    def test_dashboard_escapes_markup_in_saved_text(self):
        data = {"metadata": {"note": "</script><script>alert(1)</script>"}, "replay": [{"scenario": "x"}]}
        with tempfile.TemporaryDirectory(dir=HERE) as folder:
            source, output = Path(folder) / "measurements.json", Path(folder) / "dashboard.html"
            source.write_text(json.dumps(data), encoding="utf-8")
            dashboard.build(source, output)
            page = output.read_text(encoding="utf-8")
            payload = page.split('<script type="application/json" id="dataset">', 1)[1].split("</script>", 1)[0]
            self.assertEqual(json.loads(payload)["metadata"], data["metadata"])
            self.assertEqual(page.count("alert(1)"), 1)
            first = output.read_bytes()
            dashboard.build(source, output)
            self.assertEqual(output.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
