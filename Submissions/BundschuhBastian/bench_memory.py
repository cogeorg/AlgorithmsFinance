"""Memory script for the membership lab (step 6). Run SEPARATELY from the timing script:

    .venv/bin/python bench_memory.py          # writes results/memory_*.csv|json

tracemalloc slows Python down, so these runs say nothing about time, and the timing script
never runs with tracemalloc on. Per measurement:
    * the input (ids, queries, expected answers) is built BEFORE tracing starts, so it is
      not in the numbers;
    * a fresh trace is started (tracemalloc.start) and stopped for every method and phase;
    * the output of the traced call is kept alive until the numbers are read.
Reported in bytes: `current` = memory still allocated when the call has returned,
`peak` = the largest amount allocated at any moment during the call.

Phases (what each number contains):
    prepare  prepare(ids)              current = prepared structure (sorted list / set /
                                       nothing for linear); peak = structure + temporaries
    query    answer(state, queries)    state built before tracing (not counted);
                                       current = output list; peak = output + temporaries
    total    method(ids, queries)      current = output list; peak = prepared structure +
                                       output + temporaries (the structure is freed on return)
Only memory allocated through Python's allocator while tracing is counted. The integer
objects of the input exist before tracing and are shared, never copied: a sorted list or a
set stores references to them, which is what the numbers show.
"""
import argparse
import csv
import gc
import json
import statistics
import sys
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

from bench_time import DUPLICATES, HIT_RATES, QUERY_COUNTS, SEED, SIZES, environment
from datagen import generate
from membership import METHODS, PHASES

HERE = Path(__file__).resolve().parent

UNITS = {"current_bytes": "bytes still allocated when the traced call returned "
                          "(output / prepared structure kept alive)",
         "peak_bytes": "largest number of bytes allocated at any moment of the traced call"}


def traced(call):
    """Run call() under a fresh trace; return (output, current_bytes, peak_bytes)."""
    gc.collect()
    tracemalloc.start()
    try:
        output = call()                     # output stays alive in this frame
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return output, current, peak


def measure_method(name, data, repeats):
    """Return rows {phase, repeat, current_bytes, peak_bytes} for one method."""
    prepare, answer = PHASES[name]
    method = METHODS[name]
    ids, queries, expected = data.ids, data.queries, data.expected
    rows = []
    for repeat in range(1, repeats + 1):
        state, current, peak = traced(lambda: prepare(ids))
        assert answer(state, queries) == expected         # after tracing stopped
        rows.append({"phase": "prepare", "repeat": repeat,
                     "current_bytes": current, "peak_bytes": peak})
        del state

        state = prepare(ids)                              # built before tracing
        result, current, peak = traced(lambda: answer(state, queries))
        assert result == expected
        rows.append({"phase": "query", "repeat": repeat,
                     "current_bytes": current, "peak_bytes": peak})
        del state, result

        result, current, peak = traced(lambda: method(ids, queries))
        assert result == expected
        rows.append({"phase": "total", "repeat": repeat,
                     "current_bytes": current, "peak_bytes": peak})
        del result
    return rows


def run_benchmark(sizes, query_counts, hit_rates, repeats, seed, methods=None, log=None):
    methods = list(methods or METHODS)
    raw, summary = [], []
    for n in sizes:
        for q in query_counts:
            for hit_rate in hit_rates:
                data = generate(n, q, hit_rate, DUPLICATES, seed)    # before any tracing
                ids_before = list(data.ids)
                input_list_bytes = sys.getsizeof(data.ids)
                for name in methods:
                    base = {"n": n, "q": q, "hit_rate": hit_rate, "method": name,
                            "algorithm": name.split("_")[0], "version": name.split("_")[1]}
                    rows = measure_method(name, data, repeats)
                    for phase in ("prepare", "query", "total"):
                        part = [r for r in rows if r["phase"] == phase]
                        for r in part:
                            raw.append({**base, **r})
                        summary.append({
                            **base, "phase": phase, "repeats": repeats,
                            "median_current_bytes": statistics.median(
                                r["current_bytes"] for r in part),
                            "median_peak_bytes": statistics.median(
                                r["peak_bytes"] for r in part),
                            "min_peak_bytes": min(r["peak_bytes"] for r in part),
                            "max_peak_bytes": max(r["peak_bytes"] for r in part),
                            "input_list_bytes_not_traced": input_list_bytes})
                    if log:
                        total = summary[-1]
                        log(f"n={n} q={q} {hit_rate} {name}: total peak "
                            f"{total['median_peak_bytes']:.0f} B")
                assert data.ids == ids_before
    return raw, summary


def write_csv(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args(argv)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    env = environment()
    started = datetime.now(timezone.utc)
    raw, summary = run_benchmark(SIZES, QUERY_COUNTS, HIT_RATES, args.repeats, args.seed,
                                 log=print)
    write_csv(out / "memory_raw.csv", raw)
    write_csv(out / "memory_summary.csv", summary)
    metadata = {
        "script": "bench_memory.py",
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "generator": {"module": "datagen.generate", "duplicates": DUPLICATES,
                      "sizes_n": SIZES, "query_counts_q": QUERY_COUNTS,
                      "hit_rates": HIT_RATES},
        "units": UNITS,
        "method": "tracemalloc; fresh trace per method and phase; input built before tracing "
                  "(not included); output kept alive; run separately from the timing script",
        "included": {
            "input": "NOT included (built before tracing). input_list_bytes_not_traced is "
                     "sys.getsizeof(ids), the list's pointer array only, for reference",
            "prepared_structure": "included in prepare.current and in total.peak "
                                  "(sorted copy: list of n references; set: hash table)",
            "output": "included in query/total current and peak (list of q bool references)"},
        "phases": {"prepare": "prepare(ids)", "query": "answer(state, queries)",
                   "total": "method(ids, queries)"},
        "repeats": args.repeats,
        "environment": env,
    }
    (out / "memory_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"saved {len(raw)} raw rows and {len(summary)} summary rows to {out}")


if __name__ == "__main__":
    main()
