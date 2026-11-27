"""Memory measurement with ``tracemalloc`` (LAB_SPEC.md MEM1-MEM6), separate from timing (M6).

Grid: the same as ``bench/timing.py`` (n x q x hit rate, seed, duplicate policy "allow"),
all 6 entries of ``membership.METHODS``, identical inputs per cell (I3).

Procedure for every (cell, method/version, phase, repeat), following MEM1-MEM4
    1. The input (ids, queries) is built by the generator BEFORE tracing starts.
       -> The input is never counted.
    2. ``tracemalloc.start()`` -- a fresh tracing run for each measurement (MEM2).
    3. Run the phase, keeping every returned object alive in a local variable (MEM4).
    4. ``tracemalloc.get_traced_memory()`` -> (current_bytes, peak_bytes).
    5. ``tracemalloc.stop()``. The result is checked against a ``set`` oracle afterwards.

Phases and what they include (saved as explicit flags in every row, MEM6)
    phase      traced code                       prepared structure   output   input
    prepare    state = prepare(ids)              yes                  no       no
    query      result = query(state, queries)    no (built before)    yes      no
    total      state = prepare(ids);             yes                  yes      no
               result = query(state, queries)

    current_bytes  bytes still allocated when read (objects kept alive: state and/or result).
    peak_bytes     the highest traced value during the phase, including temporary objects
                   that were already freed (for example v1's slices).

Notes for interpretation (MEM6)
    * tracemalloc counts Python allocations only, not every native allocation, and not
      interpreter overhead. It is not the same as process memory (RSS) and not exactly
      "auxiliary space".
    * Our IDs are large ints. ``sorted`` and ``set`` store references to the existing int
      objects; they do not copy the ints. So the prepared structure costs about 8 bytes per
      reference plus container overhead (list) or a hash table (set).
    * ``True``/``False`` are singletons: an output list costs about 8 bytes per query.
    * ``state_getsizeof_bytes`` = ``sys.getsizeof(state)`` (container only, shallow), measured
      outside tracing, is saved as a cross-check of the prepare phase.
      ``state_is_input`` is True for linear search: its state IS the caller's list, so its
      getsizeof is the input's size, not new memory (its traced prepare cost is 0).
    * The optional ``psutil`` RSS run (MEM5) is not done: psutil is not installed.

Output, in ``results/memory/``:
    memory_<stamp>.csv           one row per (cell, method, phase, repeat)
    memory_<stamp>_summary.csv   median per (cell, method, phase)
    memory_<stamp>_env.json      environment, code version, settings, case metadata

Run (from Submissions/BuehlerLaurin):  python -m bench.memory
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tracemalloc
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from bench.env import SUBMISSION_DIR, collect_env
from bench.timing import DUPLICATE_POLICY, HIT_RATES, N_VALUES, Q_VALUES, SEED, write_csv
from datagen.generator import make_case
from membership import METHODS, MethodSpec

REPEATS = 3
OUT_DIR = SUBMISSION_DIR / "results" / "memory"

PHASE_FLAGS: dict[str, dict[str, bool]] = {
    "prepare": {"includes_input": False, "includes_prepared": True, "includes_output": False},
    "query": {"includes_input": False, "includes_prepared": False, "includes_output": True},
    "total": {"includes_input": False, "includes_prepared": True, "includes_output": True},
}


def trace_phase(
    spec: MethodSpec, phase: str, ids: Sequence[int], queries: Sequence[int]
) -> tuple[int, int, Any, list[bool] | None]:
    """One fresh tracing run of one phase. Returns (current, peak, state, result).

    State and result are returned so they stay alive until after the reading (MEM4)
    and can be checked afterwards.
    """
    state: Any = None
    result: list[bool] | None = None
    if phase == "query":
        state = spec.prepare(ids)  # built before tracing: not counted

    tracemalloc.start()
    if phase == "prepare":
        state = spec.prepare(ids)
    elif phase == "query":
        result = spec.query(state, queries)
    elif phase == "total":
        state = spec.prepare(ids)
        result = spec.query(state, queries)
    else:
        tracemalloc.stop()
        raise ValueError(f"unknown phase {phase!r}")
    current, peak = tracemalloc.get_traced_memory()  # state and result are still alive
    tracemalloc.stop()
    return current, peak, state, result


def run_grid(
    n_values: Sequence[int] = N_VALUES,
    q_values: Sequence[int] = Q_VALUES,
    hit_rates: Sequence[float] = HIT_RATES,
    methods: Sequence[MethodSpec] | None = None,
    seed: int = SEED,
    repeats: int = REPEATS,
    out_dir: Path = OUT_DIR,
) -> dict[str, Path]:
    """Run all memory measurements and write raw rows, summary and environment."""
    if tracemalloc.is_tracing():
        raise RuntimeError("tracemalloc is already running; memory runs need a fresh start")
    methods = list(METHODS.values()) if methods is None else list(methods)
    env = collect_env()

    raw_rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for n in n_values:
        for q in q_values:
            for hit_rate in hit_rates:
                ids, queries, meta = make_case(n, q, hit_rate, seed, DUPLICATE_POLICY)
                cases.append(meta)
                expected = [x in set(ids) for x in queries]
                for spec in methods:
                    for phase in PHASE_FLAGS:
                        for repeat in range(repeats):
                            current, peak, state, result = trace_phase(spec, phase, ids, queries)
                            if result is not None and result != expected:
                                raise AssertionError(f"{spec.label} returned a wrong result")
                            raw_rows.append(
                                {
                                    "n": n,
                                    "q": q,
                                    "hit_rate": hit_rate,
                                    "realized_hit_rate": meta["realized_hit_rate"],
                                    "seed": seed,
                                    "duplicate_policy": DUPLICATE_POLICY,
                                    "n_distinct": meta["n_distinct"],
                                    "method": spec.method,
                                    "version": spec.version,
                                    "label": spec.label,
                                    "phase": phase,
                                    "repeat": repeat,
                                    "current_bytes": current,
                                    "peak_bytes": peak,
                                    **PHASE_FLAGS[phase],
                                    "output_kept_alive": result is not None,
                                    "state_getsizeof_bytes": sys.getsizeof(state)
                                    if state is not None
                                    else None,
                                    "state_is_input": state is ids,
                                    "unit": "bytes",
                                    "tool": "tracemalloc",
                                    "git_commit": env["git_commit"],
                                    "git_dirty": env["git_dirty"],
                                }
                            )
                            del state, result

    summary_rows = summarize(raw_rows)

    stamp = env["timestamp_utc"].replace(":", "").replace("-", "").replace("+0000", "Z")
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "raw": out_dir / f"memory_{stamp}.csv",
        "summary": out_dir / f"memory_{stamp}_summary.csv",
        "env": out_dir / f"memory_{stamp}_env.json",
    }
    write_csv(paths["raw"], raw_rows)
    write_csv(paths["summary"], summary_rows)
    settings = {
        "script": "bench/memory.py",
        "tool": "tracemalloc (Python allocations only)",
        "seed": seed,
        "n_values": list(n_values),
        "q_values": list(q_values),
        "hit_rates": list(hit_rates),
        "duplicate_policy": DUPLICATE_POLICY,
        "repeats": repeats,
        "unit": "bytes",
        "phases": {
            phase: {"traced": text, **PHASE_FLAGS[phase]}
            for phase, text in (
                ("prepare", "state = prepare(ids)"),
                ("query", "result = query(state, queries); state built before tracing"),
                ("total", "state = prepare(ids); result = query(state, queries)"),
            )
        },
        "definitions": {
            "current_bytes": "traced bytes still allocated at reading time (state/result alive)",
            "peak_bytes": "highest traced bytes during the phase, including freed temporaries",
            "state_getsizeof_bytes": "sys.getsizeof(state), shallow, measured outside tracing",
            "state_is_input": "True if the state is the caller's input object (linear search)",
        },
        "rss": "not measured (psutil not installed; optional per MEM5)",
        "methods": [spec.label for spec in methods],
    }
    paths["env"].write_text(
        json.dumps({"env": env, "settings": settings, "cases": cases}, indent=2),
        encoding="utf-8",
    )
    return paths


def summarize(raw_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Median current/peak bytes over the repeats for every cell, method/version and phase."""
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in raw_rows:
        key = (row["n"], row["q"], row["hit_rate"], row["label"], row["phase"])
        groups.setdefault(key, []).append(row)

    summary: list[dict[str, Any]] = []
    for rows in groups.values():  # insertion order = grid order, methods in registry order
        first = rows[0]
        summary.append(
            {
                "n": first["n"],
                "q": first["q"],
                "hit_rate": first["hit_rate"],
                "method": first["method"],
                "version": first["version"],
                "label": first["label"],
                "phase": first["phase"],
                "repeats": len(rows),
                "current_bytes_median": statistics.median(r["current_bytes"] for r in rows),
                "peak_bytes_median": statistics.median(r["peak_bytes"] for r in rows),
                "peak_bytes_max": max(r["peak_bytes"] for r in rows),
                "includes_input": first["includes_input"],
                "includes_prepared": first["includes_prepared"],
                "includes_output": first["includes_output"],
                "state_getsizeof_bytes": first["state_getsizeof_bytes"],
                "state_is_input": first["state_is_input"],
                "unit": "bytes",
            }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Membership memory measurement (tracemalloc)")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--repeats", type=int, default=REPEATS)
    args = parser.parse_args()

    paths = run_grid(seed=args.seed, repeats=args.repeats)
    print(f"raw:     {paths['raw']}")
    print(f"summary: {paths['summary']}")
    print(f"env:     {paths['env']}")


if __name__ == "__main__":
    main()
