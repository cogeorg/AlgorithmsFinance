"""Timing script for the membership lab (step 5). Run from this folder:

    .venv/bin/python bench_time.py            # writes results/timing_*.csv|json

What is timed (time.perf_counter, seconds):
    prepare  sorting / set construction            prepare(ids)
    query    the whole query batch, state ready    answer(state, queries)
    total    method(ids, queries) in one call       prepare + queries, timed on its own
Not timed: data generation, the correctness checks, printing, creating the fresh state
for the `query` phase, saving results.

Protocol per (n, q, hit rate, method, phase):
    1. Calibrate k (calls per repeat) from single calls so one repeat lasts >= target
       (default 20 ms); very short phases are timed as k calls together and divided by k.
    2. One untimed warm-up repeat.
    3. `repeats` timed repeats (default 5). Each repeat starts from a FRESH prepared state
       (for `prepare` and `total`, every call builds a new state anyway). The garbage
       collector is run before and switched off during a repeat.
    4. After the clock stops, the result is compared with the expected answers.
    5. Report the median of the repeats; the raw repeats are saved too.
All methods and versions get the identical dataset object (same ids, same queries).
"""
import argparse
import csv
import gc
import json
import math
import os
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import get_clock_info, perf_counter

from datagen import generate
from membership import METHODS, PHASES

HERE = Path(__file__).resolve().parent
SIZES = [1000, 10_000, 100_000]
QUERY_COUNTS = [1, 100]
HIT_RATES = ["all-present", "all-absent", "mixed"]
DUPLICATES = "none"
SEED = 20260
K_MAX = 100_000

UNITS = {
    "seconds_per_batch": "seconds for ONE execution of the phase (prepare, all q queries, "
                         "or prepare+all q queries); = repeat time / calls_per_repeat",
    "seconds_per_query": "seconds_per_batch / q; only for phases 'query' and 'total' "
                         "(preparation does not belong to one query, so it is left empty)",
}


# ---- generic measurement ----------------------------------------------------------

def calibrate(setup, run, target_s):
    """Calls per repeat so that one repeat lasts about target_s (1 .. K_MAX)."""
    context = setup()
    singles = []
    for _ in range(3):
        start = perf_counter()
        run(context, 1)
        singles.append(perf_counter() - start)
    single = max(min(singles), 1e-9)
    return max(1, min(K_MAX, math.ceil(target_s / single)))


def measure(setup, run, check, k, repeats):
    """Return seconds per execution for each repeat (setup/check are outside the clock)."""
    check(run(setup(), k))                      # untimed warm-up repeat
    samples = []
    for _ in range(repeats):
        context = setup()                       # fresh state, not timed
        gc.collect()
        gc.disable()
        try:
            start = perf_counter()
            output = run(context, k)
            elapsed = perf_counter() - start
        finally:
            gc.enable()
        check(output)                           # after the clock reading
        samples.append(elapsed / k)
    return samples


def phase_definitions(name, data):
    """For one method: {phase: (setup, run, check)}; all use the identical `data`."""
    prepare, answer = PHASES[name]
    method = METHODS[name]
    ids, queries, expected = data.ids, data.queries, data.expected

    def run_prepare(_, k):
        state = None
        for _ in range(k):
            state = prepare(ids)
        return state

    def run_query(state, k):
        result = None
        for _ in range(k):
            result = answer(state, queries)
        return result

    def run_total(_, k):
        result = None
        for _ in range(k):
            result = method(ids, queries)
        return result

    def check_state(state):
        assert answer(state, queries) == expected

    def check_result(result):
        assert result == expected

    return {
        "prepare": (lambda: None, run_prepare, check_state),
        "query": (lambda: prepare(ids), run_query, check_result),
        "total": (lambda: None, run_total, check_result),
    }


# ---- whole benchmark --------------------------------------------------------------

def run_benchmark(sizes, query_counts, hit_rates, repeats, target_s, seed,
                  methods=None, log=None):
    methods = list(methods or METHODS)
    raw, summary, datasets = [], [], []
    for n in sizes:
        for q in query_counts:
            for hit_rate in hit_rates:
                data = generate(n, q, hit_rate, DUPLICATES, seed)    # not timed
                ids_before = list(data.ids)
                queries_before = list(data.queries)
                datasets.append({**data.settings, "hits": sum(data.expected)})
                for name in methods:
                    for phase, (setup, run, check) in phase_definitions(name, data).items():
                        k = calibrate(setup, run, target_s)
                        samples = measure(setup, run, check, k, repeats)
                        base = {"n": n, "q": q, "hit_rate": hit_rate, "method": name,
                                "algorithm": name.split("_")[0],
                                "version": name.split("_")[1], "phase": phase}
                        for index, seconds in enumerate(samples, start=1):
                            raw.append({**base, "repeat": index, "calls_per_repeat": k,
                                        "seconds_per_batch": seconds,
                                        "seconds_per_query": (seconds / q
                                                              if phase != "prepare" else "")})
                        median = statistics.median(samples)
                        summary.append({**base, "repeats": repeats, "calls_per_repeat": k,
                                        "median_seconds_per_batch": median,
                                        "min_seconds_per_batch": min(samples),
                                        "max_seconds_per_batch": max(samples),
                                        "median_seconds_per_query": (median / q
                                                                     if phase != "prepare" else "")})
                        if log:
                            log(f"n={n} q={q} {hit_rate} {name} {phase}: "
                                f"median {median:.3e} s (k={k})")
                assert data.ids == ids_before and data.queries == queries_before
    return raw, summary, datasets


# ---- environment ------------------------------------------------------------------

def _run(command):
    try:
        return subprocess.run(command, cwd=HERE, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def environment():
    clock = get_clock_info("perf_counter")
    info = {
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count_logical": os.cpu_count(),
        "perf_counter": {"implementation": clock.implementation,
                         "resolution_seconds": clock.resolution,
                         "monotonic": clock.monotonic},
        "git_commit": _run(["git", "rev-parse", "HEAD"]),
        "git_branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "git_uncommitted_changes_outside_results": bool(
            _run(["git", "status", "--porcelain", "--", ".", ":(exclude)results"])),
    }
    if sys.platform == "darwin":
        info["cpu_model"] = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        memory = _run(["sysctl", "-n", "hw.memsize"])
        info["memory_bytes"] = int(memory) if memory.isdigit() else None
    return info


def write_csv(path, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--target-ms", type=float, default=20.0,
                        help="minimum duration of one timed repeat (calls are grouped)")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", type=Path, default=HERE / "results")
    args = parser.parse_args(argv)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    env = environment()                     # before writing any result file
    started = datetime.now(timezone.utc)
    raw, summary, datasets = run_benchmark(
        SIZES, QUERY_COUNTS, HIT_RATES, args.repeats, args.target_ms / 1000, args.seed,
        log=print)
    write_csv(out / "timing_raw.csv", raw)
    write_csv(out / "timing_summary.csv", summary)
    metadata = {
        "script": "bench_time.py",
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "seed": args.seed,
        "generator": {"module": "datagen.generate", "duplicates": DUPLICATES,
                      "sizes_n": SIZES, "query_counts_q": QUERY_COUNTS,
                      "hit_rates": HIT_RATES,
                      "note": "same seed for every configuration; the identical dataset "
                              "object is given to every method and version"},
        "datasets": datasets,
        "methods": list(METHODS),
        "phases": {"prepare": "prepare(ids): sorting / set construction (linear: none)",
                   "query": "answer(state, queries): whole query batch, state already built",
                   "total": "method(ids, queries) timed on its own (not the sum of the two)"},
        "units": UNITS,
        "protocol": {"timer": "time.perf_counter", "repeats": args.repeats,
                     "statistic": "median over repeats",
                     "warmup": "one untimed repeat after calibration",
                     "calibration": f"k calls per repeat so a repeat lasts >= "
                                    f"{args.target_ms} ms (k <= {K_MAX}); min of 3 single calls",
                     "fresh_state": "new prepared state before every repeat",
                     "gc": "gc.collect() before, gc disabled during each repeat",
                     "excluded": ["data generation", "correctness checks", "printing",
                                  "creating the fresh state for phase 'query'", "saving"],
                     "order": "n, q, hit rate, method (listed order), phase "
                              "(prepare, query, total)"},
        "environment": env,
    }
    (out / "timing_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"saved {len(raw)} raw rows and {len(summary)} summary rows to {out}")


if __name__ == "__main__":
    main()
