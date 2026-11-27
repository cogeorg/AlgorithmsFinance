"""Instrumentation runs, kept SEPARATE from the primary timing (bench/experiments.py):

    python -m bench.instrumentation            # latency, memory and operation counts
    python -m bench.instrumentation --quick

1. Latency: perf_counter_ns around every single event; percentiles per event type and for
   the first versus the last 10 % of events (submission bursts as the book grows).
   Percentile convention: nearest rank (smallest value with at least p % of events <= it).
   This is algorithm processing latency only: no queueing or network delay; reciprocal
   throughput is NOT used as a latency estimate.
2. Memory: tracemalloc, one run per configuration. Tracing starts AFTER the events are
   preloaded, so the input is excluded (its size is measured separately). Each event's
   result is dropped after the event. Reports the peak during replay, the book after the
   replay, and the traced size at 10 % steps (growth during insertion, state after churn).
3. Operation counts (small runs): list elements scanned (A); heap pushes and pops, price
   levels created and deleted, compactions (B). They explain the timing plots.
"""
import argparse
import csv
import gc
import gzip
import heapq
import time
import tracemalloc

from lob.book_a import OrderBookA
from lob.book_b import OrderBookB
from lob.events_io import read_events

from .common import (RESULTS, TIME_LIMIT_S, dataset, environment, percentile, write_csv,
                     write_json)

SCENARIOS = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]
MAKERS = {"A": OrderBookA, "B": OrderBookB, "B_nocompact": lambda: OrderBookB(compact=False)}


# ------------------------------------------------------------------ 1. latency
def latency_run(make, events):
    """Per-event processing times in nanoseconds, or None if the time limit is exceeded."""
    book, out = make(), []
    process, clock = book.process, time.perf_counter_ns
    start = time.perf_counter()
    gc.collect()
    gc.disable()
    try:
        for i, e in enumerate(events):
            t0 = clock()
            process(e)
            out.append(clock() - t0)
            if i % 256 == 0 and time.perf_counter() - start > TIME_LIMIT_S:
                return None
    finally:
        gc.enable()
    return out


def latency_summary(version, scenario, m, events, ns):
    rows = []
    n = len(ns)
    windows = {"all": range(n), "first_10pct": range(n // 10), "last_10pct": range(n - n // 10, n)}
    for window, idx in windows.items():
        for kind in ["ALL", "LIMIT", "CANCEL", "MARKET_SELL"]:
            vals = sorted(ns[i] / 1000 for i in idx if kind == "ALL" or events[i].get("type") == kind)
            if not vals:
                continue
            rows.append([version, scenario, m, window, kind, len(vals), percentile(vals, 50),
                         percentile(vals, 95), percentile(vals, 99), vals[-1]])
    return rows


def exp_latency(sizes, raw_size):
    summary, stopped = [], []
    raw_path = RESULTS / f"latency_raw_{raw_size}.csv.gz"
    RESULTS.mkdir(exist_ok=True)
    with gzip.open(raw_path, "wt", newline="") as raw_file:
        raw = csv.writer(raw_file)
        raw.writerow(["version", "scenario", "events", "index", "type", "latency_ns"])
        for scenario in SCENARIOS:
            for m in sizes:
                events = read_events(dataset(scenario, m, 42))
                for version in ["A", "B"]:
                    ns = latency_run(MAKERS[version], events)
                    if ns is None:
                        stopped.append([version, scenario, m, f"exceeded {TIME_LIMIT_S:g} s limit"])
                        print(f"latency {scenario} M={m} {version}: STOPPED")
                        continue
                    summary += latency_summary(version, scenario, m, events, ns)
                    if m == raw_size:
                        raw.writerows([version, scenario, m, i, events[i].get("type"), t]
                                      for i, t in enumerate(ns))
                    print(f"latency {scenario} M={m} {version}: done")
    return summary, stopped


LAT_HEADER = ["version", "scenario", "events", "window", "event_type", "count", "p50_us",
              "p95_us", "p99_us", "max_us"]


# ------------------------------------------------------------------ 2. memory
def memory_run(make, events, steps=10):
    gc.collect()
    tracemalloc.start()
    book = make()
    process = book.process
    marks, n, start = [], len(events), time.perf_counter()
    for i, e in enumerate(events):
        result = process(e)
        del result
        if (i + 1) % max(1, n // steps) == 0:
            marks.append(tracemalloc.get_traced_memory()[0])
        if i % 256 == 0 and time.perf_counter() - start > TIME_LIMIT_S:
            tracemalloc.stop()
            return None
    gc.collect()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    extra = {}
    if isinstance(book, OrderBookB):
        extra = dict(zip(["stale_deque_entries", "stale_heap_entries"], book.stale_entries()))
    return current, peak, marks, book.active_order_count(), extra


def input_bytes(path):
    gc.collect()
    tracemalloc.start()
    events = read_events(path)
    current = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    del events
    return current


def exp_memory(sizes):
    rows, growth = [], []
    for scenario in SCENARIOS:
        for m in sizes:
            path = dataset(scenario, m, 42)
            in_bytes = input_bytes(path)
            events = read_events(path)
            versions = ["A", "B"] + (["B_nocompact"] if scenario == "cancel_churn" else [])
            for version in versions:
                r = memory_run(MAKERS[version], events)
                if r is None:
                    rows.append([version, scenario, m, in_bytes, "", "", "", "", "", "stopped"])
                    print(f"memory {scenario} M={m} {version}: STOPPED")
                    continue
                current, peak, marks, active, extra = r
                rows.append([version, scenario, m, in_bytes, peak, current, active,
                             extra.get("stale_deque_entries", ""), extra.get("stale_heap_entries", ""), "ok"])
                growth += [[version, scenario, m, (k + 1) * 10, b] for k, b in enumerate(marks)]
                print(f"memory {scenario} M={m} {version}: peak {peak / 1e6:.2f} MB")
    return rows, growth


MEM_HEADER = ["version", "scenario", "events", "input_bytes_preloaded", "replay_peak_bytes",
              "book_bytes_after_replay", "active_orders_after", "stale_deque_entries",
              "stale_heap_entries", "status"]


# ------------------------------------------------------------------ 3. operation counts
class CountingA(OrderBookA):
    def __init__(self):
        super().__init__()
        self.ops = {"list_elements_scanned": 0, "list_removals": 0}

    def _best(self, side):
        self.ops["list_elements_scanned"] += len(self.orders)
        return super()._best(side)

    def _find(self, order_id):
        self.ops["list_elements_scanned"] += len(self.orders)
        return super()._find(order_id)

    def _match(self, *args, **kw):
        before = len(self.orders)
        out = super()._match(*args, **kw)
        self.ops["list_removals"] += before - len(self.orders)
        return out


class CountingB(OrderBookB):
    def __init__(self, compact=True):
        super().__init__(compact)
        self.ops = {"heap_pushes": 0, "heap_stale_pops": 0, "levels_created": 0,
                    "levels_deleted": 0, "heap_rebuilds": 0}

    def _best_price(self, side):
        heap, levels = self.heaps[side], self.levels[side]
        while heap and ((-heap[0] if side == "BUY" else heap[0]) not in levels):
            heapq.heappop(heap)
            self.ops["heap_stale_pops"] += 1
        return super()._best_price(side)

    def _rest(self, order):
        new = order.price not in self.levels[order.side]
        super()._rest(order)
        if new:
            self.ops["levels_created"] += 1
            self.ops["heap_pushes"] += 1

    def _drop_level(self, side, price):
        before = len(self.heaps[side])
        super()._drop_level(side, price)
        self.ops["levels_deleted"] += 1
        if len(self.heaps[side]) < before:
            self.ops["heap_rebuilds"] += 1


def exp_counts(sizes):
    rows = []
    for scenario in SCENARIOS:
        for m in sizes:
            events = read_events(dataset(scenario, m, 42))
            for version, make in [("A", CountingA), ("B", CountingB),
                                  ("B_nocompact", lambda: CountingB(compact=False))]:
                book = make()
                fills = 0
                for e in events:
                    fills += len(book.process(e).get("fills", []))
                for op, value in book.ops.items():
                    rows.append([version, scenario, m, op, value])
                rows.append([version, scenario, m, "maker_fills", fills])
            print(f"counts {scenario} M={m}: done")
    return rows


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    lat_sizes = [10_000] if args.quick else [10_000, 100_000]
    mem_sizes = [10_000] if args.quick else [10_000, 100_000]
    count_sizes = [1_000] if args.quick else [1_000, 10_000]

    summary, stopped = exp_latency(lat_sizes, raw_size=10_000)
    write_csv("latency_summary.csv", LAT_HEADER, summary)
    write_csv("latency_stopped.csv", ["version", "scenario", "events", "reason"], stopped)
    mem, growth = exp_memory(mem_sizes)
    write_csv("memory.csv", MEM_HEADER, mem)
    write_csv("memory_growth.csv", ["version", "scenario", "events", "percent_of_events",
                                    "traced_bytes"], growth)
    write_csv("operation_counts.csv", ["version", "scenario", "events", "operation", "count"],
              exp_counts(count_sizes))
    write_json("instrumentation_environment.json", environment(
        "bench/instrumentation.py", latency_sizes=lat_sizes, memory_sizes=mem_sizes,
        count_sizes=count_sizes, seed=42, percentile_convention="nearest rank",
        latency_unit="microseconds per event (engine only)",
        memory_boundary="tracing starts after events are preloaded; input measured separately; "
                        "each event result dropped after the event; no trade history kept"))
    print("saved latency, memory and operation-count results")


if __name__ == "__main__":
    main()
