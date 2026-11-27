"""Runtime benchmark for every method of every version (slides 60-61).

Run from Submissions/WelscherYannick:

    .venv/bin/python bench/benchmark.py           # full grid, writes results/
    .venv/bin/python bench/benchmark.py --quick   # small smoke run, writes results/quick/

What is timed (time.perf_counter, unit: seconds)
    prepare_s      one call of prepare(ids): sorting the copy or building the set
    query_batch_s  one call of query(state, queries) for the complete query batch
    total_s        prepare followed by query, timed together as its own run
                   (not the sum of the two values above)
    The per-query time is query_batch_s / q; it is derived, not measured.

How
    * Every method and version gets identical inputs per scenario.
    * Warm-up: before measuring, each operation is run with growing call counts
      until one measurement lasts at least min_measure_s. These runs are
      discarded; the final count is kept as `number`.
    * Each measurement times `number` back-to-back calls and divides by
      `number`, because a single call can be close to the clock resolution.
      The loop overhead per call is measured once and stored in the metadata
      (not subtracted).
    * Each repeat builds fresh state with prepare(); the query batch is timed
      on the state built in that same repeat.
    * `repeats` measurements per operation; the order of the method/version
      pairs is rotated each repeat. The median is the reported statistic; all
      raw values are saved.
    * Garbage collection is paused while timing, as timeit does.
Not timed: data generation, the result check, printing and file writing.
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
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "src"))

from datagen import DUPLICATE_POLICY, HIT_POLICY, GenSettings, describe, generate  # noqa: E402
from registry import VERSIONS  # noqa: E402

COLUMNS = [
    "scenario", "n", "q", "hit_rate_target", "hit_rate_actual", "duplicate_rate", "seed",
    "version", "method", "repeat",
    "prepare_s", "query_batch_s", "total_s",
    "number_prepare", "number_query", "number_total",
]


@dataclass(frozen=True)
class BenchConfig:
    sizes: tuple = (1_000, 10_000, 100_000)
    query_counts: tuple = (1, 100)
    hit_rates: tuple = (1.0, 0.0, 0.5)  # all present, all absent, mixed
    duplicate_rate: float = 0.1
    seed: int = 20261120
    repeats: int = 5
    min_measure_s: float = 0.02
    max_number: int = 1_000_000


QUICK = BenchConfig(sizes=(100, 1_000), query_counts=(1, 10), repeats=3, min_measure_s=0.002)


def scenarios(cfg):
    """All (n, q, hit_rate) combinations. A mixed hit rate needs at least two
    queries, so it is skipped for q = 1."""
    out = []
    for n in cfg.sizes:
        for q in cfg.query_counts:
            for hit_rate in cfg.hit_rates:
                if 0.0 < hit_rate < 1.0 and q < 2:
                    continue
                out.append(GenSettings(n, q, hit_rate, cfg.duplicate_rate, cfg.seed))
    return out


# --- Timing primitives ---------------------------------------------------------

@contextmanager
def _gc_paused():
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


def _timed_prepare(prepare, ids, number):
    with _gc_paused():
        start = perf_counter()
        for _ in range(number):
            state = prepare(ids)
        elapsed = perf_counter() - start
    return elapsed, state


def _timed_query(query, state, queries, number):
    with _gc_paused():
        start = perf_counter()
        for _ in range(number):
            result = query(state, queries)
        elapsed = perf_counter() - start
    return elapsed, result


def _timed_total(prepare, query, ids, queries, number):
    with _gc_paused():
        start = perf_counter()
        for _ in range(number):
            result = query(prepare(ids), queries)
        elapsed = perf_counter() - start
    return elapsed, result


def _choose_number(timed, min_s, max_number):
    """Warm-up: grow the call count until one measurement lasts min_s."""
    number = 1
    while True:
        elapsed = timed(number)
        if elapsed >= min_s or number >= max_number:
            return number
        estimate = math.ceil(number * min_s / max(elapsed, 1e-9) * 1.2)
        number = min(max_number, max(2 * number, estimate))


def calibrate(method, ids, queries, cfg):
    state = method.prepare(ids)
    args = (cfg.min_measure_s, cfg.max_number)
    return (
        _choose_number(lambda k: _timed_prepare(method.prepare, ids, k)[0], *args),
        _choose_number(lambda k: _timed_query(method.query, state, queries, k)[0], *args),
        _choose_number(lambda k: _timed_total(method.prepare, method.query, ids, queries, k)[0], *args),
    )


def measure_pair(method, ids, queries, numbers):
    """One repeat: fresh preparation, query batch on that state, then the
    combined run. Returns seconds per call and both results."""
    n_prep, n_query, n_total = numbers
    prep_elapsed, state = _timed_prepare(method.prepare, ids, n_prep)
    query_elapsed, result = _timed_query(method.query, state, queries, n_query)
    total_elapsed, result_total = _timed_total(method.prepare, method.query, ids, queries, n_total)
    return {
        "prepare_s": prep_elapsed / n_prep,
        "query_batch_s": query_elapsed / n_query,
        "total_s": total_elapsed / n_total,
        "result": result,
        "result_total": result_total,
    }


def loop_overhead_per_call(iterations=1_000_000):
    with _gc_paused():
        start = perf_counter()
        for _ in range(iterations):
            pass
        elapsed = perf_counter() - start
    return elapsed / iterations


# --- Environment ---------------------------------------------------------------

def _run(cmd):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_DIR, timeout=10)
        return out.stdout.strip() if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def environment():
    clock = time.get_clock_info("perf_counter")
    machine = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
    }
    if sys.platform == "darwin":
        machine["model"] = _run(["sysctl", "-n", "hw.model"])
        machine["cpu_brand"] = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
        memsize = _run(["sysctl", "-n", "hw.memsize"])
        machine["memory_bytes"] = int(memsize) if memsize else None
    dirty = _run(["git", "status", "--porcelain", "--", "src", "bench"])
    return {
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "machine": machine,
        "clock": {
            "name": "time.perf_counter",
            "implementation": clock.implementation,
            "resolution_s": clock.resolution,
            "monotonic": clock.monotonic,
        },
        "code": {
            "git_commit": _run(["git", "rev-parse", "HEAD"]),
            "uncommitted_changes_in_src_or_bench": bool(dirty) if dirty is not None else None,
        },
    }


# --- Benchmark run -------------------------------------------------------------

def run_benchmark(cfg, out_dir, versions=VERSIONS, log=print):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = [(v, name, m) for v, methods in versions.items() for name, m in methods.items()]
    rows, scenario_info = [], []

    for index, settings in enumerate(scenarios(cfg)):
        ids, queries = generate(settings)
        present = set(ids)
        expected = [q in present for q in queries]
        info = describe(settings, ids, queries)
        info["scenario"] = index
        scenario_info.append(info)
        log(f"scenario {index}: n={settings.n} q={settings.q} hit_rate={settings.hit_rate}")

        numbers = {(v, name): calibrate(m, ids, queries, cfg) for v, name, m in pairs}
        for repeat in range(cfg.repeats):
            shift = repeat % len(pairs)
            for v, name, m in pairs[shift:] + pairs[:shift]:
                res = measure_pair(m, ids, queries, numbers[(v, name)])
                if res["result"] != expected or res["result_total"] != expected:
                    raise RuntimeError(f"{v}-{name} returned a wrong result in scenario {index}")
                n_prep, n_query, n_total = numbers[(v, name)]
                rows.append({
                    "scenario": index, "n": settings.n, "q": settings.q,
                    "hit_rate_target": settings.hit_rate,
                    "hit_rate_actual": info["hit_rate_actual"],
                    "duplicate_rate": settings.duplicate_rate, "seed": settings.seed,
                    "version": v, "method": name, "repeat": repeat,
                    "prepare_s": res["prepare_s"], "query_batch_s": res["query_batch_s"],
                    "total_s": res["total_s"],
                    "number_prepare": n_prep, "number_query": n_query, "number_total": n_total,
                })

    rows.sort(key=lambda r: (r["scenario"], r["version"], r["method"], r["repeat"]))
    with open(out_dir / "timing_raw.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    metadata = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "command": " ".join([Path(sys.argv[0]).name] + sys.argv[1:]),
        **environment(),
        "config": asdict(cfg),
        "measurement": {
            "statistic": "median over repeats",
            "gc_paused_while_timing": True,
            "warm_up": "growing call counts until one measurement lasts min_measure_s; discarded",
            "loop_overhead_s_per_call": loop_overhead_per_call(),
            "pair_order": "rotated by one position each repeat",
        },
        "units": {
            "prepare_s": "seconds per prepare(ids) call",
            "query_batch_s": "seconds per query(state, queries) call for the whole batch of q queries",
            "total_s": "seconds per prepare + query call, timed together",
        },
        "generator": {"duplicate_policy": DUPLICATE_POLICY, "hit_policy": HIT_POLICY},
        "scenarios": scenario_info,
    }
    with open(out_dir / "timing_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    return rows, metadata


def print_summary(rows, log=print):
    groups = {}
    for r in rows:
        groups.setdefault((r["n"], r["q"], r["hit_rate_target"], r["version"], r["method"]), []).append(r)
    log(f"\n{'n':>7} {'q':>4} {'hit':>4} {'ver':>3} {'method':>6} "
        f"{'prepare_s':>11} {'query_s':>11} {'total_s':>11}   (medians)")
    for key in sorted(groups):
        g = groups[key]
        med = {c: statistics.median(r[c] for r in g) for c in ("prepare_s", "query_batch_s", "total_s")}
        n, q, hit, v, m = key
        log(f"{n:>7} {q:>4} {hit:>4} {v:>3} {m:>6} "
            f"{med['prepare_s']:>11.3e} {med['query_batch_s']:>11.3e} {med['total_s']:>11.3e}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--quick", action="store_true", help="small grid for a smoke run")
    parser.add_argument("--out", type=Path, help="output directory")
    args = parser.parse_args(argv)
    cfg = QUICK if args.quick else BenchConfig()
    out = args.out or PROJECT_DIR / ("results/quick" if args.quick else "results")
    rows, metadata = run_benchmark(cfg, out)
    print_summary(rows)
    if metadata["code"]["uncommitted_changes_in_src_or_bench"]:
        print("\nWARNING: src/ or bench/ has uncommitted changes; results do not match a commit.")
    shown = out.relative_to(PROJECT_DIR) if out.is_relative_to(PROJECT_DIR) else out
    print(f"\nWrote {len(rows)} rows to {shown}")


if __name__ == "__main__":
    main()
