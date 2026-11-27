"""Choose the v2 binary search: time both candidates (and v1 for reference) on identical inputs.

Purpose: evidence for decision Q3 (docs/REVISION.md). The full benchmark of all
methods is ``bench/timing.py``; this script only compares binary-search variants.

What is timed (LAB_SPEC.md M1-M7)
    prep_s          one call of ``prepare(ids)`` (sorted copy), seconds per call.
    query_batch_s   one call of ``query(state, queries)`` for the whole batch of q
                    queries, seconds per batch. Short batches are timed k times in a
                    row and divided by k (M3); k is recorded.
    total_s         prep_s + query_batch_s, seconds.
    Every repeat builds a fresh sorted copy (M4). Clock: ``time.perf_counter``.
    One untimed warm-up (which also calibrates k), then 5 repeats; medians reported.
    Data generation, result checking and printing happen outside timed regions (M5).

Inputs: ``datagen.generator.make_case`` with fixed seed, duplicate policy "allow",
n in {1,000, 10,000, 100,000}, q = 100, hit rate in {1.0, 0.0, 0.5}. All variants get
the same (ids, queries) per grid cell (I3).

Output: ``results/raw/binary_variants_<timestamp>.csv`` (one row per repeat) and
``results/raw/binary_variants_<timestamp>_env.json`` (environment + settings).

Run (from Submissions/BuehlerLaurin):  python -m bench.binary_variants
"""

from __future__ import annotations

import csv
import json
import math
import statistics
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from bench.env import SUBMISSION_DIR, collect_env
from datagen.generator import make_case
from membership import BINARY_V2_CANDIDATES, METHODS, MethodSpec

SEED = 20261120
N_VALUES = [1_000, 10_000, 100_000]
Q = 100
HIT_RATES = [1.0, 0.0, 0.5]
DUPLICATE_POLICY = "allow"
REPEATS = 5
MIN_TIMED_SECONDS = 0.02  # target length of one timed block for very short calls (M3)

VARIANTS: dict[str, MethodSpec] = {
    "v1-recursive-slicing": METHODS[("binary", "original")],
    "v2-classic": BINARY_V2_CANDIDATES["classic"],
    "v2-lower_bound": BINARY_V2_CANDIDATES["lower_bound"],
}


def time_k_calls(fn: Callable[[], Any], k: int) -> float:
    """Seconds per call, averaged over ``k`` back-to-back calls of ``fn``."""
    start = time.perf_counter()
    for _ in range(k):
        fn()
    return (time.perf_counter() - start) / k


def choose_k(fn: Callable[[], Any]) -> int:
    """Untimed warm-up call that also estimates how many calls fill MIN_TIMED_SECONDS."""
    start = time.perf_counter()
    fn()
    single = time.perf_counter() - start
    return max(1, math.ceil(MIN_TIMED_SECONDS / max(single, 1e-9)))


def measure(spec: MethodSpec, ids: Sequence[int], queries: Sequence[int]) -> list[dict[str, Any]]:
    """Warm up, then REPEATS repeats with fresh preparation state each time."""
    expected = [x in set(ids) for x in queries]  # oracle, computed outside timing

    warm_state = spec.prepare(ids)
    k_query = choose_k(lambda: spec.query(warm_state, queries))
    k_prep = choose_k(lambda: spec.prepare(ids))

    rows: list[dict[str, Any]] = []
    for repeat in range(REPEATS):
        prep_s = time_k_calls(lambda: spec.prepare(ids), k_prep)
        state = spec.prepare(ids)  # fresh state for this repeat (M4)
        query_batch_s = time_k_calls(lambda: spec.query(state, queries), k_query)
        if spec.query(state, queries) != expected:  # validated after the clock stopped
            raise AssertionError(f"{spec.label} returned a wrong result")
        rows.append(
            {
                "repeat": repeat,
                "k_prep": k_prep,
                "k_query": k_query,
                "prep_s": prep_s,
                "query_batch_s": query_batch_s,
                "total_s": prep_s + query_batch_s,
            }
        )
    return rows


def main() -> None:
    env = collect_env()
    stamp = env["timestamp_utc"].replace(":", "").replace("-", "").replace("+0000", "Z")
    out_dir = SUBMISSION_DIR / "results" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path: Path = out_dir / f"binary_variants_{stamp}.csv"
    env_path: Path = out_dir / f"binary_variants_{stamp}_env.json"

    all_rows: list[dict[str, Any]] = []
    for n in N_VALUES:
        for hit_rate in HIT_RATES:
            ids, queries, meta = make_case(n, Q, hit_rate, SEED, DUPLICATE_POLICY)
            for name, spec in VARIANTS.items():
                for row in measure(spec, ids, queries):
                    all_rows.append(
                        {
                            "variant": name,
                            "n": n,
                            "q": Q,
                            "hit_rate": hit_rate,
                            "realized_hit_rate": meta["realized_hit_rate"],
                            "seed": SEED,
                            "duplicate_policy": DUPLICATE_POLICY,
                            "unit": "seconds",
                            "query_batch_is": "per batch of q queries",
                            **row,
                        }
                    )

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    settings = {
        "seed": SEED,
        "n_values": N_VALUES,
        "q": Q,
        "hit_rates": HIT_RATES,
        "duplicate_policy": DUPLICATE_POLICY,
        "repeats": REPEATS,
        "min_timed_seconds": MIN_TIMED_SECONDS,
        "variants": list(VARIANTS),
    }
    env_path.write_text(json.dumps({"env": env, "settings": settings}, indent=2), encoding="utf-8")

    # Summary (printing is outside all timed regions).
    print(f"raw: {csv_path.name}  env: {env_path.name}  git_dirty={env['git_dirty']}")
    print(f"{'n':>7} {'hit':>4} {'variant':<22} {'median query batch [s]':>24} {'per query [us]':>15}")
    for n in N_VALUES:
        for hit_rate in HIT_RATES:
            for name in VARIANTS:
                values = [
                    r["query_batch_s"]
                    for r in all_rows
                    if r["variant"] == name and r["n"] == n and r["hit_rate"] == hit_rate
                ]
                med = statistics.median(values)
                print(f"{n:>7} {hit_rate:>4} {name:<22} {med:>24.3e} {med / Q * 1e6:>15.3f}")


if __name__ == "__main__":
    main()
