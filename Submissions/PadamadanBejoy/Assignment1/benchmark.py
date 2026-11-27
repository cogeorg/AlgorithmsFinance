"""Benchmarks for Version A and Version B (Assignment 1).

Usage (from the project folder):
    python3 benchmark.py            # full run (sizes 1,000 / 10,000 / 100,000; seeds 42, 43, 44)
    python3 benchmark.py --quick    # small smoke run (1,000 events, seed 42) to check everything works

Writes:
    results/timing.csv       one row per timed repeat (raw), plus parse time rows
    results/latency.csv      per-file per-event latency percentiles (separate instrumentation run)
    results/memory.csv       tracemalloc peaks (separate run)
    results/liquidation.csv  10% / 100% / 200% sell against the same fresh bid book
    results/correctness.csv  A vs B agreement per file + worked example check
    results/environment.json Python, OS, machine, git commit, generator settings, limits

Measurement boundaries:
  - Event files are generated OUTSIDE timing (generate_orders.py).
  - Reading/parsing (gzip + json) is timed separately from engine replay.
  - Engine replay: fresh empty book per repeat, 1 warm-up + 5 timed repeats, every repeat saved.
  - Runs exceeding TIME_LIMIT_S are stopped and recorded with status "stopped" (never invented).
"""
import argparse
import csv
import gzip
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc

from orderbook.version_a import OrderBook as BookA
from orderbook.version_b import OrderBook as BookB

VERSIONS = {"A": BookA, "B": BookB}
SCENARIOS = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]
TIME_LIMIT_S = 30.0       # declared per-replay time limit; slower runs are stopped and reported
REPEATS = 5
LEVELS = 1000
RESULTS = "results"
DATA = "data"


class Stopped(Exception):
    pass


# ---------------------------------------------------------------- helpers
def generate(scenario, events, seed):
    path = os.path.join(DATA, f"{scenario}_{events}_s{seed}.jsonl.gz")
    if not os.path.exists(path):
        subprocess.run([sys.executable, "generate_orders.py", "--scenario", scenario,
                        "--events", str(events), "--levels", str(LEVELS),
                        "--seed", str(seed), "--out", path], check=True,
                       stdout=subprocess.DEVNULL)
    return path


def read_events(path):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        return [json.loads(line) for line in f if line.strip()]


def replay(book_class, events, limit=TIME_LIMIT_S):
    """Replay all events on a fresh book. Returns elapsed seconds. Raises Stopped if over limit."""
    book = book_class()
    process = book.process_event
    start = time.perf_counter()
    for i, event in enumerate(events):
        process(event)
        if i % 1000 == 999 and time.perf_counter() - start > limit:
            raise Stopped()
    return time.perf_counter() - start


def percentile(sorted_values, p):
    """Nearest-rank percentile: smallest value with at least p% of values <= it."""
    if not sorted_values:
        return None
    k = max(1, math.ceil(p / 100 * len(sorted_values)))
    return sorted_values[k - 1]


def book_peaks(events):
    """Active-order and occupied-price-level peaks (instrumentation run on Version B;
    both versions hold identical books, verified by the comparison tests)."""
    book = BookB()
    peak_orders = peak_levels = 0
    for event in events:
        book.process_event(event)
        peak_orders = max(peak_orders, len(book.index))
        peak_levels = max(peak_levels, len(book.prices["BUY"]) + len(book.prices["SELL"]))
    return peak_orders, peak_levels


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


def write_csv(name, rows, fields):
    with open(os.path.join(RESULTS, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- experiments
def run_timing(files, timing_rows):
    for (scenario, n, seed), path in files:
        t0 = time.perf_counter()
        events = read_events(path)
        parse_s = time.perf_counter() - t0
        peak_orders, peak_levels = book_peaks(events)
        timing_rows.append(dict(version="-", scenario=scenario, seed=seed, events=n, phase="parse",
                                repeat=1, elapsed_s=f"{parse_s:.6f}", status="ok",
                                active_peak=peak_orders, level_peak=peak_levels))
        for v, cls in VERSIONS.items():
            try:
                replay(cls, events)                       # warm-up (not recorded)
                for r in range(1, REPEATS + 1):
                    s = replay(cls, events)
                    timing_rows.append(dict(version=v, scenario=scenario, seed=seed, events=n,
                                            phase="replay", repeat=r, elapsed_s=f"{s:.6f}",
                                            status="ok", active_peak=peak_orders,
                                            level_peak=peak_levels))
                print(f"  timing {v} {scenario} n={n} seed={seed}: ok")
            except Stopped:
                timing_rows.append(dict(version=v, scenario=scenario, seed=seed, events=n,
                                        phase="replay", repeat=0, elapsed_s="",
                                        status=f"stopped>{TIME_LIMIT_S:.0f}s",
                                        active_peak=peak_orders, level_peak=peak_levels))
                print(f"  timing {v} {scenario} n={n} seed={seed}: STOPPED (> {TIME_LIMIT_S}s)")


def run_latency(files, rows):
    """Separate instrumentation run: per-event processing time with perf_counter_ns."""
    for (scenario, n, seed), path in files:
        if seed != 42:
            continue
        events = read_events(path)
        for v, cls in VERSIONS.items():
            book = cls()
            lat = []
            start = time.perf_counter()
            stopped = False
            for i, event in enumerate(events):
                t = time.perf_counter_ns()
                book.process_event(event)
                lat.append(time.perf_counter_ns() - t)
                if i % 1000 == 999 and time.perf_counter() - start > TIME_LIMIT_S:
                    stopped = True
                    break
            if stopped:
                rows.append(dict(version=v, scenario=scenario, seed=seed, events=n, window="all",
                                 p50_us="", p95_us="", p99_us="", status=f"stopped>{TIME_LIMIT_S:.0f}s"))
                continue
            tenth = max(1, len(lat) // 10)
            for window, values in [("all", lat), ("first10pct", lat[:tenth]), ("last10pct", lat[-tenth:])]:
                s = sorted(values)
                rows.append(dict(version=v, scenario=scenario, seed=seed, events=n, window=window,
                                 p50_us=f"{percentile(s, 50) / 1000:.3f}",
                                 p95_us=f"{percentile(s, 95) / 1000:.3f}",
                                 p99_us=f"{percentile(s, 99) / 1000:.3f}", status="ok"))
        print(f"  latency {scenario} n={n}: done")


def run_memory(files, rows):
    """Separate tracemalloc run. Events are preloaded BEFORE tracing starts, so the input is
    NOT included; traced = book structures + per-event results (results are discarded each
    event, no trade history kept)."""
    for (scenario, n, seed), path in files:
        if seed != 42:
            continue
        events = read_events(path)
        for v, cls in VERSIONS.items():
            tracemalloc.start()
            book = cls()
            start = time.perf_counter()
            stopped = False
            for i, event in enumerate(events):
                book.process_event(event)
                if i % 1000 == 999 and time.perf_counter() - start > TIME_LIMIT_S:
                    stopped = True
                    break
            current, peak = tracemalloc.get_traced_memory()
            active = len(book.snapshot()) if not stopped else ""
            tracemalloc.stop()
            rows.append(dict(version=v, scenario=scenario, seed=seed, events=n,
                             peak_traced_bytes="" if stopped else peak,
                             final_traced_bytes="" if stopped else current,
                             final_active_orders=active,
                             status=f"stopped>{TIME_LIMIT_S:.0f}s" if stopped else "ok"))
        print(f"  memory {scenario} n={n}: done")


def run_liquidation(sizes, rows):
    """Fresh bid book from the first n events of a buildup stream; then ONE market sell of
    10%, 100% or 200% of the total bid quantity. The book is rebuilt for every repeat
    (construction timed separately), so no test reuses a depleted book."""
    for n in sizes:
        events = read_events(generate("buildup", n, 42))
        for v, cls in VERSIONS.items():
            probe = cls()
            for e in events:
                probe.process_event(e)
            total_bid = sum(o["qty_units"] for o in probe.snapshot() if o["side"] == "BUY")
            for pct in (10, 100, 200):
                qty = max(1, math.ceil(total_bid * pct / 100))
                sell = {"seq": len(events) + 1, "event_id": "liq", "type": "MARKET_SELL",
                        "order_id": "liq", "qty_units": qty}
                for r in range(1, REPEATS + 1):
                    book = cls()
                    t0 = time.perf_counter()
                    try:
                        for i, e in enumerate(events):
                            book.process_event(e)
                            if i % 1000 == 999 and time.perf_counter() - t0 > TIME_LIMIT_S:
                                raise Stopped()
                    except Stopped:
                        rows.append(dict(version=v, events=n, pct=pct, requested_qty=qty, repeat=r,
                                         build_s="", sell_s="", fills="", makers_touched="",
                                         levels_visited="", unfilled_qty="",
                                         status=f"stopped>{TIME_LIMIT_S:.0f}s"))
                        break
                    build_s = time.perf_counter() - t0
                    t1 = time.perf_counter()
                    res = book.process_event(sell)
                    sell_s = time.perf_counter() - t1
                    rows.append(dict(version=v, events=n, pct=pct, requested_qty=qty, repeat=r,
                                     build_s=f"{build_s:.6f}", sell_s=f"{sell_s:.6f}",
                                     fills=len(res["fills"]),
                                     makers_touched=len({f["maker_id"] for f in res["fills"]}),
                                     levels_visited=len({f["price_ticks"] for f in res["fills"]}),
                                     unfilled_qty=res["unfilled_qty_units"], status="ok"))
        print(f"  liquidation n={n}: done")


def run_correctness(files, rows):
    """A vs B: every result identical, final books identical. Plus worked example."""
    for (scenario, n, seed), path in files:
        if n > 10000:
            continue                         # A too slow beyond this; covered by tests + 10k files
        events = read_events(path)
        a, b = BookA(), BookB()
        ok = all(a.process_event(e) == b.process_event(e) for e in events)
        ok = ok and a.snapshot() == b.snapshot()
        rows.append(dict(check=f"A==B every event: {scenario} n={n} seed={seed}",
                         result="pass" if ok else "FAIL"))
    events = read_events(os.path.join(DATA, "worked_example.jsonl"))
    with open(os.path.join(DATA, "worked_expected.json")) as f:
        exp = json.load(f)
    for v, cls in VERSIONS.items():
        book = cls()
        for e in events:
            res = book.process_event(e)
        ok = (res["fills"] == exp["market_sell_result"]["fills"]
              and book.snapshot() == exp["remaining_orders"])
        rows.append(dict(check=f"worked example matches expected (Version {v})",
                         result="pass" if ok else "FAIL"))


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="small smoke run")
    args = ap.parse_args()
    sizes = [1000] if args.quick else [1000, 10000, 100000]
    seeds = [42] if args.quick else [42, 43, 44]
    os.makedirs(RESULTS, exist_ok=True)

    print("Generating event files (outside timing)...")
    files = [((s, n, seed), generate(s, n, seed)) for n in sizes for seed in seeds for s in SCENARIOS]

    timing, latency, memory, liquidation, correctness = [], [], [], [], []
    print("Timing..."); run_timing(files, timing)
    write_csv("timing.csv", timing, ["version", "scenario", "seed", "events", "phase", "repeat",
                                     "elapsed_s", "status", "active_peak", "level_peak"])
    print("Latency (instrumentation run)..."); run_latency(files, latency)
    write_csv("latency.csv", latency, ["version", "scenario", "seed", "events", "window",
                                       "p50_us", "p95_us", "p99_us", "status"])
    print("Memory (tracemalloc run)..."); run_memory(files, memory)
    write_csv("memory.csv", memory, ["version", "scenario", "seed", "events", "peak_traced_bytes",
                                     "final_traced_bytes", "final_active_orders", "status"])
    print("Liquidation..."); run_liquidation([n for n in sizes if n <= 10000] or sizes, liquidation)
    write_csv("liquidation.csv", liquidation, ["version", "events", "pct", "requested_qty", "repeat",
                                               "build_s", "sell_s", "fills", "makers_touched",
                                               "levels_visited", "unfilled_qty", "status"])
    print("Correctness..."); run_correctness(files, correctness)
    write_csv("correctness.csv", correctness, ["check", "result"])

    env = {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
           "processor": platform.processor(), "git_commit": git_commit(),
           "generator": {"script": "generate_orders.py", "levels": LEVELS, "sizes": sizes,
                         "seeds": seeds, "scenarios": SCENARIOS},
           "time_limit_s": TIME_LIMIT_S, "repeats": REPEATS, "warmup_runs": 1,
           "percentile_convention": "nearest-rank",
           "memory_boundary": "events preloaded before tracemalloc.start(); input excluded; "
                              "book + transient per-event results included; no trade history kept",
           "dependencies": "Python standard library only (pytest for tests)"}
    with open(os.path.join(RESULTS, "environment.json"), "w") as f:
        json.dump(env, f, indent=2)
    print("Done. Results in results/")


if __name__ == "__main__":
    main()
