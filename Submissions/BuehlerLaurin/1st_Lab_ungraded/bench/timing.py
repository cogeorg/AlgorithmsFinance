"""Runtime benchmark of all methods and versions (LAB_SPEC.md I1-I6, M1-M7).

Grid (I1, I2)
    n in {1,000, 10,000, 100,000} x q in {1, 100} x hit rate in {1.0, 0.0, 0.5}
    x all 6 entries of ``membership.METHODS``. Duplicate policy "allow" (decision Q1).
    One ``make_case(n, q, hit_rate, seed)`` per grid cell; every method and version
    gets exactly this (ids, queries) pair (I3).

Three quantities per repeat (I5, M7). Unit: seconds.
    prep_s         one ``prepare(ids)``: seconds per preparation.
    query_batch_s  one ``query(state, queries)`` over all q queries: seconds per batch.
                   ``query_per_query_s = query_batch_s / q`` is also saved.
    total_s        one ``query(prepare(ids), queries)``, measured as its own timed
                   block: seconds per prepare + batch. ``prep_plus_query_s`` (the sum of
                   the two separate medians' inputs) is saved as a cross-check.

Rules
    * Clock: ``time.perf_counter`` (M1). Garbage collection is disabled inside timed
      blocks, as ``timeit`` does, and re-enabled right after.
    * Warm-up: one untimed call of each block per method and cell. It also calibrates k (M2).
    * Very short calls (M3): a block repeats the call k times so that it lasts at least
      ``MIN_TIMED_SECONDS``; the value saved is (block time) / k. k is saved per row.
      The cost of the Python loop + lambda call around the call is included; it is measured
      separately as ``overhead_per_call_s`` (an empty lambda timed the same way).
    * Fresh preparation state (M4): prepare is called anew in every prep block and every
      total block; the state used by the query block is built fresh for each repeat.
    * 5 repeats (M2). Methods are measured round-robin in a seeded random order inside each
      repeat, so slow drift of the machine does not always hit the same method.
    * Results are checked against a ``set`` oracle after the clock has stopped (M5).
    * Data generation, checks, file writing and printing are outside timed blocks (M5).
    * No memory tracing in this script (M6); see ``bench/memory.py``.

Output (I4, I6), in ``results/raw/``:
    timing_<stamp>.csv           one row per (cell, method, version, repeat): raw values
    timing_<stamp>_summary.csv   medians over the repeats per (cell, method, version)
    timing_<stamp>_env.json      environment, code version, settings and all case metadata

Run (from Submissions/BuehlerLaurin):  python -m bench.timing
"""

from __future__ import annotations

import argparse
import csv
import gc
import json
import math
import random
import statistics
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from bench.env import SUBMISSION_DIR, collect_env
from datagen.generator import make_case
from membership import METHODS, MethodSpec

SEED = 20261120
N_VALUES = [1_000, 10_000, 100_000]
Q_VALUES = [1, 100]
HIT_RATES = [1.0, 0.0, 0.5]
DUPLICATE_POLICY = "allow"
REPEATS = 5
MIN_TIMED_SECONDS = 0.02
OUT_DIR = SUBMISSION_DIR / "results" / "raw"


# --- Timing primitives ----------------------------------------------------------


def time_block(fn: Callable[[], Any], k: int) -> float:
    """Seconds per call of ``fn``, from one timed block of ``k`` back-to-back calls."""
    gc_was_enabled = gc.isenabled()
    gc.disable()
    try:
        start = time.perf_counter()
        for _ in range(k):
            fn()
        elapsed = time.perf_counter() - start
    finally:
        if gc_was_enabled:
            gc.enable()
    return elapsed / k


def calibrate_k(fn: Callable[[], Any]) -> int:
    """Untimed warm-up call; returns how many calls fill ``MIN_TIMED_SECONDS`` (at least 1)."""
    single = time_block(fn, 1)
    return max(1, math.ceil(MIN_TIMED_SECONDS / max(single, 1e-9)))


def loop_overhead_per_call() -> float:
    """Cost of the timing loop around one call (an empty lambda), seconds per call."""
    noop: Callable[[], None] = lambda: None  # noqa: E731
    k = calibrate_k(noop)
    return statistics.median(time_block(noop, k) for _ in range(REPEATS))


# --- One grid cell --------------------------------------------------------------


def measure_cell(
    methods: Sequence[MethodSpec],
    ids: Sequence[int],
    queries: Sequence[int],
    repeats: int,
    order_rng: random.Random,
) -> list[dict[str, Any]]:
    """Warm up and calibrate every method, then run ``repeats`` round-robin repeats."""
    expected = [x in set(ids) for x in queries]  # oracle, outside timing

    k: dict[str, dict[str, int]] = {}
    for spec in methods:
        warm_state = spec.prepare(ids)
        k[spec.label] = {
            "prep": calibrate_k(lambda: spec.prepare(ids)),
            "query": calibrate_k(lambda: spec.query(warm_state, queries)),
            "total": calibrate_k(lambda: spec.query(spec.prepare(ids), queries)),
        }

    rows: list[dict[str, Any]] = []
    for repeat in range(repeats):
        order = list(methods)
        order_rng.shuffle(order)
        for position, spec in enumerate(order):
            ks = k[spec.label]
            prep_s = time_block(lambda: spec.prepare(ids), ks["prep"])
            state = spec.prepare(ids)  # fresh state for this repeat's query block
            query_batch_s = time_block(lambda: spec.query(state, queries), ks["query"])
            total_s = time_block(lambda: spec.query(spec.prepare(ids), queries), ks["total"])

            if spec.query(spec.prepare(ids), queries) != expected:
                raise AssertionError(f"{spec.label} returned a wrong result")

            rows.append(
                {
                    "method": spec.method,
                    "version": spec.version,
                    "label": spec.label,
                    "repeat": repeat,
                    "order_position": position,
                    "k_prep": ks["prep"],
                    "k_query": ks["query"],
                    "k_total": ks["total"],
                    "prep_s": prep_s,
                    "query_batch_s": query_batch_s,
                    "query_per_query_s": query_batch_s / len(queries) if queries else None,
                    "total_s": total_s,
                    "prep_plus_query_s": prep_s + query_batch_s,
                }
            )
    return rows


# --- Whole grid -----------------------------------------------------------------


def run_grid(
    n_values: Sequence[int] = N_VALUES,
    q_values: Sequence[int] = Q_VALUES,
    hit_rates: Sequence[float] = HIT_RATES,
    methods: Sequence[MethodSpec] | None = None,
    seed: int = SEED,
    repeats: int = REPEATS,
    out_dir: Path = OUT_DIR,
) -> dict[str, Path]:
    """Run the benchmark grid and write raw rows, summary and environment. Returns the paths."""
    methods = list(METHODS.values()) if methods is None else list(methods)
    env = collect_env()
    overhead = loop_overhead_per_call()
    order_rng = random.Random(seed)

    raw_rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for n in n_values:
        for q in q_values:
            for hit_rate in hit_rates:
                ids, queries, meta = make_case(n, q, hit_rate, seed, DUPLICATE_POLICY)
                cases.append(meta)
                for row in measure_cell(methods, ids, queries, repeats, order_rng):
                    raw_rows.append(
                        {
                            "n": n,
                            "q": q,
                            "hit_rate": hit_rate,
                            "realized_hit_rate": meta["realized_hit_rate"],
                            "seed": seed,
                            "duplicate_policy": DUPLICATE_POLICY,
                            "id_range": meta["id_range"],
                            "n_distinct": meta["n_distinct"],
                            **row,
                            "unit": "seconds",
                            "overhead_per_call_s": overhead,
                            "git_commit": env["git_commit"],
                            "git_dirty": env["git_dirty"],
                        }
                    )

    summary_rows = summarize(raw_rows)

    stamp = env["timestamp_utc"].replace(":", "").replace("-", "").replace("+0000", "Z")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "raw": out_dir / f"timing_{stamp}.csv",
        "summary": out_dir / f"timing_{stamp}_summary.csv",
        "env": out_dir / f"timing_{stamp}_env.json",
    }
    write_csv(paths["raw"], raw_rows)
    write_csv(paths["summary"], summary_rows)
    settings = {
        "script": "bench/timing.py",
        "seed": seed,
        "n_values": list(n_values),
        "q_values": list(q_values),
        "hit_rates": list(hit_rates),
        "duplicate_policy": DUPLICATE_POLICY,
        "repeats": repeats,
        "warmup": "1 untimed call per block, method and cell (also calibrates k)",
        "min_timed_seconds": MIN_TIMED_SECONDS,
        "gc_disabled_in_timed_blocks": True,
        "clock": "time.perf_counter",
        "unit": "seconds",
        "definitions": {
            "prep_s": "seconds per prepare(ids) call",
            "query_batch_s": "seconds per query(state, queries) call = one batch of q queries",
            "query_per_query_s": "query_batch_s / q",
            "total_s": "seconds per query(prepare(ids), queries), its own timed block",
            "prep_plus_query_s": "prep_s + query_batch_s of the same repeat (cross-check)",
            "overhead_per_call_s": "timing loop + lambda cost per call, included in all values",
        },
        "methods": [spec.label for spec in methods],
        "overhead_per_call_s": overhead,
    }
    paths["env"].write_text(
        json.dumps({"env": env, "settings": settings, "cases": cases}, indent=2),
        encoding="utf-8",
    )
    return paths


def summarize(raw_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Median (and min/max) over the repeats for every cell and method/version."""
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in raw_rows:
        key = (row["n"], row["q"], row["hit_rate"], row["method"], row["version"])
        groups.setdefault(key, []).append(row)

    method_order = {"linear": 0, "binary": 1, "hash": 2}
    version_order = {"original": 0, "revised": 1}

    def sort_key(key: tuple[Any, ...]) -> tuple[Any, ...]:
        n, q, hit_rate, method, version = key
        return (n, q, -hit_rate, method_order.get(method, 9), version_order.get(version, 9))

    summary: list[dict[str, Any]] = []
    for key in sorted(groups, key=sort_key):
        n, q, hit_rate, method, version = key
        rows = groups[key]
        entry: dict[str, Any] = {
            "n": n,
            "q": q,
            "hit_rate": hit_rate,
            "realized_hit_rate": rows[0]["realized_hit_rate"],
            "method": method,
            "version": version,
            "label": rows[0]["label"],
            "repeats": len(rows),
        }
        for field in ("prep_s", "query_batch_s", "total_s", "prep_plus_query_s"):
            values = [r[field] for r in rows]
            entry[f"{field}_median"] = statistics.median(values)
            entry[f"{field}_min"] = min(values)
            entry[f"{field}_max"] = max(values)
        entry["query_per_query_s_median"] = entry["query_batch_s_median"] / q if q else None
        entry["unit"] = "seconds"
        summary.append(entry)
    return summary


def write_csv(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def print_summary(summary_path: Path) -> None:
    """Print median total / prep / query-batch times (outside all timing)."""
    with summary_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    print(f"{'n':>7} {'q':>4} {'hit':>4} {'method-version':<17} "
          f"{'prep [s]':>10} {'batch [s]':>10} {'total [s]':>10}")
    for r in rows:
        print(
            f"{int(r['n']):>7} {int(r['q']):>4} {float(r['hit_rate']):>4} {r['label']:<17} "
            f"{float(r['prep_s_median']):>10.2e} {float(r['query_batch_s_median']):>10.2e} "
            f"{float(r['total_s_median']):>10.2e}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Membership runtime benchmark")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    args = parser.parse_args()

    paths = run_grid(seed=args.seed, repeats=args.repeats)
    print(f"raw:     {paths['raw']}")
    print(f"summary: {paths['summary']}")
    print(f"env:     {paths['env']}")
    print_summary(paths["summary"])


if __name__ == "__main__":
    main()
