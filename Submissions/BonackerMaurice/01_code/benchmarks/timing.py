"""Timing phase: prepare, query batch and total, per method and version.

Usage (normally called by benchmarks.run):  python -m benchmarks.timing <run_dir>
Protocol: see DEFINITIONS in benchmarks/config.py and AGENTS.md section 6.
"""
import gc
import math
import statistics
import sys
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from time import perf_counter

from datagen.generator import checksum, generate
from search_algos import METHODS

from .config import SEGMENTS, load_run_config, update_run_config, write_csv

MAX_CALLS = 1_000_000


def measure(fn, calls: int) -> float:
    """Total seconds for `calls` back-to-back calls of fn(), with gc disabled."""
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        start = perf_counter()
        for _ in range(calls):
            fn()
        elapsed = perf_counter() - start
    finally:
        if gc_was_enabled:
            gc.enable()
    return elapsed


def calibrate(fn, min_seconds: float) -> int:
    """Warm-up plus choice of calls so one measurement lasts >= min_seconds.

    Once a trial reaches the target, 25% more calls are added as a margin, because
    later repeats can run faster than the (cold) calibration trial. A single call
    that already takes min_seconds is not batched. The actual duration of every
    measurement is elapsed_s * calls_per_measurement (both saved in the raw CSV).
    """
    calls = 1
    while True:
        elapsed = measure(fn, calls)
        if elapsed >= min_seconds or calls >= MAX_CALLS:
            return calls if calls == 1 else min(MAX_CALLS, math.ceil(calls * 1.25))
        estimate = int(calls * min_seconds / elapsed * 1.1) + 1 if elapsed > 0 else calls * 10
        calls = min(MAX_CALLS, max(2 * calls, estimate))


def make_fn(method, segment: str, ids, queries):
    """Zero-argument callable for one segment. The query segment gets a fresh state."""
    if segment == "prepare":
        return partial(method.prepare, ids)
    if segment == "query":
        state = method.prepare(ids)  # built outside the timed loop, fresh per repeat
        return partial(method.query, state, queries)
    return lambda: method.query(method.prepare(ids), queries)


def _noop(*args):
    return None


def harness_overhead(min_seconds: float) -> dict:
    """Per-call cost of the timing loop with the same wrapper shapes as make_fn:
    functools.partial (prepare and query segments) and a lambda (total segment)."""
    result = {}
    for name, fn in (("noop_call_s", partial(_noop, None)),
                     ("noop_lambda_call_s", lambda: _noop(None))):
        calls = calibrate(fn, min_seconds)
        result[name] = statistics.median(measure(fn, calls) / calls for _ in range(5))
    return result


def preflight(ids, queries, methods=METHODS) -> None:
    """Every method must return exact bools, be correct and leave the input unchanged."""
    reference_set = set(ids)
    expected = [q in reference_set for q in queries]
    ids_before, queries_before = checksum(ids), checksum(queries)
    for m in methods:
        result = m.query(m.prepare(ids), queries)
        if result != expected or any(type(r) is not bool for r in result):
            raise AssertionError(f"{m.key} returned wrong results; aborting benchmark")
    if checksum(ids) != ids_before or checksum(queries) != queries_before:
        raise AssertionError("a method modified its input; aborting benchmark")


def run(run_dir) -> None:
    run_dir = Path(run_dir)
    _, grid = load_run_config(run_dir)
    methods = list(METHODS)
    datasets, raw = [], []

    overhead = harness_overhead(grid.min_measure_seconds)

    for spec in grid.specs():
        ds = generate(spec)
        ids, queries = ds.ids, ds.queries
        preflight(ids, queries)
        info = ds.summary()
        datasets.append(info)
        base = {k: info[k] for k in ("dataset_id", "n", "q", "scenario", "realized_hit_rate")}

        calls = {(m.key, seg): calibrate(make_fn(m, seg, ids, queries), grid.min_measure_seconds)
                 for m in methods for seg in SEGMENTS}
        for repeat in range(grid.repeats):
            shift = repeat % len(methods)
            for m in methods[shift:] + methods[:shift]:
                for seg in SEGMENTS:
                    fn = make_fn(m, seg, ids, queries)
                    n_calls = calls[(m.key, seg)]
                    gc.collect()
                    elapsed = measure(fn, n_calls) / n_calls
                    raw.append({**base, "method": m.method, "version": m.version,
                                "segment": seg, "repeat": repeat,
                                "calls_per_measurement": n_calls, "elapsed_s": elapsed})

        if checksum(ids) != info["array_sha256"] or checksum(queries) != info["queries_sha256"]:
            raise AssertionError(f"input changed during timing of {spec.dataset_id}")
        print(f"timing  {spec.dataset_id:<24} done", flush=True)

    summary = []
    groups = {}
    for row in raw:
        key = (row["dataset_id"], row["method"], row["version"], row["segment"])
        groups.setdefault(key, []).append(row)
    for rows in groups.values():
        values = [r["elapsed_s"] for r in rows]
        first = rows[0]
        summary.append({**{k: first[k] for k in ("dataset_id", "n", "q", "scenario",
                                                  "realized_hit_rate", "method", "version",
                                                  "segment")},
                        "repeats": len(values), "median_s": statistics.median(values),
                        "min_s": min(values), "max_s": max(values)})

    write_csv(run_dir / "datasets.csv", datasets)
    write_csv(run_dir / "timings_raw.csv", raw)
    write_csv(run_dir / "timings_summary.csv", summary)
    update_run_config(run_dir, **overhead, phases={"timing": {
        "status": "done", "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "datasets": len(datasets), "raw_rows": len(raw)}})


if __name__ == "__main__":
    run(sys.argv[1])
