"""Per-event processing latency: a separate instrumented run, never part of the primary timing.

For every event: `perf_counter_ns` before and after `book.process(e)`. The two timer calls
themselves cost `timer_overhead_ns` (measured here, reported, NOT subtracted). Like the timing
runs, gc stays ENABLED (gc.collect() before the replay), so gc pauses show up in the tail. This is algorithm processing latency only: no queueing, no
network, no I/O; it says nothing about real-time overload capacity, and it is not 1 / throughput.

Percentile convention: nearest rank. For n sorted values, p-th percentile = value at rank
ceil(p / 100 * n) (1-based). p50, p95, p99.
Rows are split by event type (ALL, LIMIT, CANCEL, MARKET_SELL; a type with no event in the window
has no row) and by window: `all`, `first1000` and `last1000` events of the stream (how latency
changes while a flood grows the book; asked for buildup and crowded, computed for every scenario),
plus 20 equal chunks in order (latency_by_position.csv, ALL types).
Instrumented sizes: 10,000 and 100,000 events (seed 42); A at 100,000 only if its timing run took
less than 60 s (see bench.bench_counts.allowed). Every size is a block with a canary before and
after (bench.blocks); every row has start time and power state.

    .venv/bin/python -m bench.bench_latency
"""
from __future__ import annotations

import argparse
import gc
import json
import time

from bench import common
from bench.blocks import canary_around, stamp
from bench.common import RESULTS, append_csv, percentile_nearest_rank, read_csv, stream_path
from bench.bench_counts import allowed
from bench.harness import run_limited
from lob import VERSIONS
from lob.common import load_events

SUMMARY = RESULTS / "latency_summary.csv"
BY_POSITION = RESULTS / "latency_by_position.csv"
HIST = RESULTS / "latency_hist.json"
SUMMARY_FIELDS = ["start_utc", "power_source", "battery_percent", "low_power_mode", "version",
                  "scenario", "seed", "events", "event_type", "window", "n", "p50_ns", "p95_ns",
                  "p99_ns", "max_ns", "mean_ns", "timer_overhead_ns", "status", "reason"]
POS_FIELDS = ["start_utc", "power_source", "battery_percent", "low_power_mode", "version", "scenario", "seed", "events", "chunk", "n", "p50_ns", "p95_ns", "p99_ns"]


def timer_overhead_ns(samples: int = 200_000) -> int:
    """Median cost of one back-to-back pair of perf_counter_ns calls (the instrumentation cost)."""
    clock = time.perf_counter_ns
    deltas = []
    for _ in range(samples):
        t0 = clock()
        deltas.append(clock() - t0)
    deltas.sort()
    return percentile_nearest_rank(deltas, 50)


def _replay_latency(cls, events, gc_on: bool = True) -> list[int]:
    book = cls()
    process = book.process
    clock = time.perf_counter_ns
    lat = [0] * len(events)
    gc.collect()                       # gc stays enabled, as in the timing runs
    if not gc_on:                      # only for the gc_off test (--gc-test)
        gc.disable()
    for i, e in enumerate(events):
        t0 = clock()
        process(e)
        lat[i] = clock() - t0
    gc.enable()
    return lat


def stats(values: list[int]) -> dict:
    s = sorted(values)
    return {"n": len(s), "p50_ns": percentile_nearest_rank(s, 50),
            "p95_ns": percentile_nearest_rank(s, 95), "p99_ns": percentile_nearest_rank(s, 99),
            "max_ns": s[-1], "mean_ns": sum(s) / len(s)}


TYPES = ("LIMIT", "CANCEL", "MARKET_SELL")
WINDOW_SIZE = 1000


def summarize(lat: list[int], types: list[str] | None = None) -> dict:
    """Stats per (event type, window). `types[i]` is the type of event i (None: ALL only)."""
    n = len(lat)
    w = min(WINDOW_SIZE, n)
    windows = {"all": range(n), "first1000": range(w), "last1000": range(n - w, n)}
    stats_by: dict[str, dict] = {}
    for wname, idx in windows.items():
        for etype in ("ALL", *TYPES):
            vals = [lat[i] for i in idx if etype == "ALL" or (types and types[i] == etype)]
            if vals:
                stats_by[f"{etype}|{wname}"] = stats(vals)
    chunk = n // 20
    chunks = ([lat[i * chunk:(i + 1) * chunk if i < 19 else n] for i in range(20)]
              if chunk else [])                          # fewer than 20 events: no chunks
    hist: dict[int, int] = {}
    for v in lat:                                   # histogram bins: floor(log2(ns))
        hist[max(v, 1).bit_length() - 1] = hist.get(max(v, 1).bit_length() - 1, 0) + 1
    return {"windows": stats_by, "chunks": [stats(c) for c in chunks], "hist_log2_ns": hist}


def latency_worker(conn, version: str, path: str) -> None:
    events = load_events(path)
    overhead = timer_overhead_ns()
    conn.send(("unit_start", "latency"))
    lat = _replay_latency(VERSIONS[version], events)
    conn.send(("unit_done", "latency", {"overhead": overhead, **summarize(lat, [e["type"] for e in events])}))


GC_TEST = RESULTS / "latency_gc_test.csv"
GC_FIELDS = ["start_utc", "power_source", "battery_percent", "low_power_mode", "label", "version",
             "scenario", "seed", "events", "p50_ns", "p99_ns", "p999_ns", "max_ns",
             "events_over_1ms", "top5_index_ns", "gc_collections", "status", "reason"]


def gc_test_worker(conn, version: str, path: str, gc_on: bool) -> None:
    """One latency replay with gc on or off; reports the largest spikes and gc activity."""
    events = load_events(path)
    conn.send(("unit_start", "gc"))
    before = sum(g["collections"] for g in gc.get_stats())
    lat = _replay_latency(VERSIONS[version], events, gc_on)
    collections = sum(g["collections"] for g in gc.get_stats()) - before
    s = sorted(lat)
    top = sorted(range(len(lat)), key=lat.__getitem__, reverse=True)[:5]
    conn.send(("unit_done", "gc", {
        "p50_ns": percentile_nearest_rank(s, 50), "p99_ns": percentile_nearest_rank(s, 99),
        "p999_ns": percentile_nearest_rank(s, 99.9), "max_ns": s[-1],
        "events_over_1ms": sum(1 for v in lat if v > 1_000_000),
        "top5_index_ns": ";".join(f"{i}:{lat[i]}" for i in top), "gc_collections": collections}))


def gc_test(args) -> int:
    """B on buildup, 100,000 events, seed 42: gc_off, gc_on, gc_off, gc_on (canary around).
    Question: are the rare very long events garbage-collector pauses?"""
    path = str(stream_path("buildup", 100000, 42))
    with canary_around("latency_gc_test"):
        for label, gc_on in (("gc_off", False), ("gc_on", True), ("gc_off", False), ("gc_on", True)):
            st0 = stamp()
            res = run_limited(gc_test_worker, ("B", path, gc_on), args.limit_seconds)
            msgs = [m for m in res["messages"] if m[0] == "unit_done"]
            base = {**st0, "label": label, "version": "B", "scenario": "buildup", "seed": 42,
                    "events": 100000}
            if res["outcome"] == "end" and msgs:
                append_csv(GC_TEST, GC_FIELDS, {**base, **msgs[0][2], "status": "ok"})
                print(label, msgs[0][2]["max_ns"], "ns max", msgs[0][2]["top5_index_ns"], flush=True)
            else:
                append_csv(GC_TEST, GC_FIELDS, {**base, "status": res["outcome"],
                                                "reason": res["error"] or "limit reached"})
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--sizes", nargs="+", type=int, default=[10000, 100000])
    parser.add_argument("--limit-seconds", type=float, default=common.LIMIT_SECONDS)
    parser.add_argument("--gc-test", action="store_true",
                        help="extra run: B buildup 100,000 with gc off vs on (latency_gc_test.csv)")
    args = parser.parse_args(argv)
    if args.gc_test:
        return gc_test(args)
    done = {(r["version"], r["scenario"], r["events"]) for r in read_csv(SUMMARY)}
    hist_all = json.loads(HIST.read_text()) if HIST.exists() else {}
    for events in args.sizes:
        todo = [(v, sc) for sc in common.SCENARIOS for v in ("A", "B")
                if (v, sc, str(events)) not in done]
        if not todo:
            continue
        with canary_around(f"latency_{events}"):
            for version, scenario in todo:
                base = {"version": version, "scenario": scenario, "seed": 42, "events": events}
                reason = allowed(version, scenario, events)
                if reason:
                    append_csv(SUMMARY, SUMMARY_FIELDS, {**stamp(), **base, "event_type": "ALL",
                                                         "window": "all", "status": "not_run",
                                                         "reason": reason})
                    print(version, scenario, events, "not_run:", reason, flush=True)
                    continue
                st0 = stamp()
                res = run_limited(latency_worker, (version, str(stream_path(scenario, events, 42))),
                                  args.limit_seconds)
                msgs = [m for m in res["messages"] if m[0] == "unit_done"]
                if res["outcome"] != "end" or not msgs:
                    append_csv(SUMMARY, SUMMARY_FIELDS, {
                        **st0, **base, "event_type": "ALL", "window": "all",
                        "status": res["outcome"],
                        "reason": res["error"] or f"limit reached; events done {res['events_done']}"})
                    print(version, scenario, events, res["outcome"], flush=True)
                    continue
                payload = msgs[0][2]
                for key, st in payload["windows"].items():
                    etype, window = key.split("|")
                    append_csv(SUMMARY, SUMMARY_FIELDS, {**st0, **base, "event_type": etype,
                                                         "window": window, **st,
                                                         "timer_overhead_ns": payload["overhead"],
                                                         "status": "ok"})
                for i, st in enumerate(payload["chunks"]):
                    append_csv(BY_POSITION, POS_FIELDS, {**st0, **base, "chunk": i, **st})
                hist_all[f"{version}|{scenario}|{events}"] = payload["hist_log2_ns"]
                HIST.write_text(json.dumps(hist_all))
                print(version, scenario, events, "ok",
                      payload["windows"]["ALL|all"]["p50_ns"], "ns p50", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
