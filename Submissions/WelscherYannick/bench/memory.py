"""Memory measurement with tracemalloc for every method of every version (slide 62).

Run from Submissions/WelscherYannick:

    .venv/bin/python bench/memory.py           # full grid, writes results/
    .venv/bin/python bench/memory.py --quick   # smoke run, writes results/quick/

This runs separately from the timing benchmark, because tracing slows Python
down. It uses the same scenarios and the same generated data.

Three traced runs per method and repeat, each in a fresh tracemalloc session.
The input (ids, queries) is built before tracing starts and is never counted.

    prepare  trace prepare(ids); the state is kept alive
    query    prepare outside tracing, then trace query(state, queries);
             the result is kept alive
    total    trace prepare and query together; state and result kept alive

current and peak are read with get_traced_memory() while the returned objects
are still alive; tracing stops right after. Unit: bytes.

What the numbers include
    *_current_B  memory still held at the end of the run: the prepared
                 structure (prepare), the output list (query), both (total)
    *_peak_B     highest traced value during the run, so temporary allocations
                 such as sorting buffers or set resizes are included as well
    output_getsizeof_B  sys.getsizeof of the result list, as a cross-check
What they do not include
    the given input, interpreter and tracemalloc overhead, allocations that do
    not go through Python's allocators, and call-stack frames (CPython keeps
    frames in its own stack area). Objects that open frames refer to are
    traced, though: in v1 every pending recursive call keeps its own int
    objects for lo, hi and mid alive (ints above 256 are separate objects), so
    the recursion shows up indirectly as a slightly higher query peak.
Neither number is auxiliary space as defined in the course: the output is part
of query and total, and the input is excluded everywhere.
"""

import argparse
import csv
import gc
import json
import statistics
import sys
import tracemalloc
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from benchmark import PROJECT_DIR, QUICK, BenchConfig, environment, scenarios

from datagen import DUPLICATE_POLICY, HIT_POLICY, describe, generate
from registry import VERSIONS

COLUMNS = [
    "scenario", "n", "q", "hit_rate_target", "hit_rate_actual", "duplicate_rate", "seed",
    "version", "method", "repeat",
    "prepare_current_B", "prepare_peak_B",
    "query_current_B", "query_peak_B",
    "total_current_B", "total_peak_B",
    "output_getsizeof_B",
]

MEMORY_REPEATS = 3


def _traced(fn, holder):
    """Run fn(holder) in a fresh tracing session. holder is created before
    tracing, so storing results in it allocates nothing that is traced."""
    gc.collect()
    tracemalloc.start()
    try:
        fn(holder)
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return current, peak


def measure_method(method, ids, queries):
    def run_prepare(h):
        h[0] = method.prepare(ids)

    state = method.prepare(ids)  # outside tracing, for the query-only run

    def run_query(h):
        h[1] = method.query(state, queries)

    def run_total(h):
        h[0] = method.prepare(ids)
        h[1] = method.query(h[0], queries)

    prep, query, total = [None, None], [None, None], [None, None]
    p_cur, p_peak = _traced(run_prepare, prep)
    q_cur, q_peak = _traced(run_query, query)
    t_cur, t_peak = _traced(run_total, total)
    return {
        "prepare_current_B": p_cur, "prepare_peak_B": p_peak,
        "query_current_B": q_cur, "query_peak_B": q_peak,
        "total_current_B": t_cur, "total_peak_B": t_peak,
        "output_getsizeof_B": sys.getsizeof(query[1]),
        "result": query[1], "result_total": total[1],
    }


def run_memory(cfg, out_dir, versions=VERSIONS, repeats=MEMORY_REPEATS, log=print):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows, scenario_info = [], []

    for index, settings in enumerate(scenarios(cfg)):
        ids, queries = generate(settings)
        present = set(ids)
        expected = [q in present for q in queries]
        info = describe(settings, ids, queries)
        info["scenario"] = index
        scenario_info.append(info)
        log(f"scenario {index}: n={settings.n} q={settings.q} hit_rate={settings.hit_rate}")

        for repeat in range(repeats):
            for v, methods in versions.items():
                for name, m in methods.items():
                    res = measure_method(m, ids, queries)
                    if res.pop("result") != expected or res.pop("result_total") != expected:
                        raise RuntimeError(f"{v}-{name} returned a wrong result in scenario {index}")
                    rows.append({
                        "scenario": index, "n": settings.n, "q": settings.q,
                        "hit_rate_target": settings.hit_rate,
                        "hit_rate_actual": info["hit_rate_actual"],
                        "duplicate_rate": settings.duplicate_rate, "seed": settings.seed,
                        "version": v, "method": name, "repeat": repeat, **res,
                    })

    rows.sort(key=lambda r: (r["scenario"], r["version"], r["method"], r["repeat"]))
    with open(out_dir / "memory_raw.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": " ".join([Path(sys.argv[0]).name] + sys.argv[1:]),
        **environment(),
        "config": {**asdict(cfg), "memory_repeats": repeats},
        "measurement": {
            "tool": "tracemalloc, fresh session per run, gc.collect() before each run",
            "input_included": False,
            "prepared_structure_included": "prepare and total runs",
            "output_included": "query and total runs",
            "call_stack_frames_included": False,
        },
        "units": {c: "bytes" for c in COLUMNS if c.endswith("_B")},
        "generator": {"duplicate_policy": DUPLICATE_POLICY, "hit_policy": HIT_POLICY},
        "scenarios": scenario_info,
    }
    with open(out_dir / "memory_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    return rows, metadata


def print_summary(rows, log=print):
    cols = ("prepare_current_B", "prepare_peak_B", "query_current_B", "query_peak_B", "total_peak_B")
    groups = {}
    for r in rows:
        groups.setdefault((r["n"], r["q"], r["hit_rate_target"], r["version"], r["method"]), []).append(r)
    log(f"\n{'n':>7} {'q':>4} {'hit':>4} {'ver':>3} {'method':>6} "
        + " ".join(f"{c.removesuffix('_B'):>15}" for c in cols) + "   (bytes, medians)")
    for key in sorted(groups):
        g = groups[key]
        n, q, hit, v, m = key
        log(f"{n:>7} {q:>4} {hit:>4} {v:>3} {m:>6} "
            + " ".join(f"{statistics.median(r[c] for r in g):>15,.0f}" for c in cols))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="small grid for a smoke run")
    parser.add_argument("--out", type=Path, help="output directory")
    args = parser.parse_args(argv)
    cfg = QUICK if args.quick else BenchConfig()
    out = args.out or PROJECT_DIR / ("results/quick" if args.quick else "results")
    rows, metadata = run_memory(cfg, out)
    print_summary(rows)
    if metadata["code"]["uncommitted_changes_in_src_or_bench"]:
        print("\nWARNING: src/ or bench/ has uncommitted changes; results do not match a commit.")
    print(f"\nWrote {len(rows)} rows to {out.relative_to(PROJECT_DIR) if out.is_relative_to(PROJECT_DIR) else out}")


if __name__ == "__main__":
    main()
