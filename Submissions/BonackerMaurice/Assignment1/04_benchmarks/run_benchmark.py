"""Final benchmark: one command runs every phase and records provenance.

Usage (from Assignment1/):
    python 04_benchmarks/run_benchmark.py                 full run -> 05_results/
    python 04_benchmarks/run_benchmark.py --smoke         M = 1,000 only -> 05_results/smoke/
    python 04_benchmarks/run_benchmark.py --latency-memory          latency and memory only
    python 04_benchmarks/run_benchmark.py --phases data             any selected phases

The full run refuses to start when the code is not committed (git status of
02_tests, 03_code, 04_benchmarks, the generator, pytest.ini and
requirements.txt), so it always measures a known commit. A run of selected
phases has the same rule. --smoke skips that check and records the dirty state.

A run of selected phases replaces only the output of those phases. It keeps
its own record (benchmark_run_<phases>.json, environment_<phases>.json, e.g.
benchmark_run_latency_memory.json), so the record of the full run still
describes the rows it measured. When the data phase is not selected, the
event files must exist and match the sha256 in benchmark_datasets.csv.

Phases, in order (each is a module in 04_benchmarks/):
    tests          the pytest suite; the run stops if anything fails
    data           bench_data: generate datasets outside timing, manifest + checksums
    timing         bench_timing: replay grid (5 scenarios x M x seeds) + million file
    liquidation    bench_timing: sweep book (first 80%) + 10/100/200% sales
    concentration  bench_concentration: buildup --levels 4 vs 1000: timing + correctness
    latency        bench_latency: per-event processing latency (separate run)
    memory         bench_memory: tracemalloc (separate run)
    opcounts       bench_opcounts: operation counts on small sizes (separate run)
    summary        bench_timing: benchmark_summary.csv (median, min, max, throughput)

Outputs (in 05_results/, or 05_results/smoke/ with --smoke):
    environment.json, benchmark_run.json, benchmark_tests.txt,
    benchmark_datasets.csv, benchmark_results.csv, benchmark_summary.csv,
    concentration_check.csv, latency_summary.csv, latency_quantiles.csv,
    latency_by_type.csv, memory_samples.csv, memory_end_state.csv, opcounts.csv
Run nothing else heavy while it runs; plug the laptop in.
"""

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

import bench_concentration
import bench_data
import bench_latency
import bench_memory
import bench_opcounts
import bench_timing
from bench_common import (DEFINITIONS, ROOT, TIME_LIMIT_S, Config, environment, git_info,
                          read_manifest, read_rows, redact, rel, sha256_file,
                          source_fingerprint)

PHASES = ["tests", "data", "timing", "liquidation", "concentration", "latency", "memory",
          "opcounts", "summary"]
NEED_DATA = {"timing", "liquidation", "concentration", "latency", "memory", "opcounts"}
PHASE_OF = {"replay": "timing", "million": "timing", "liquidation": "liquidation",
            "concentration": "concentration", "memory": "memory"}   # experiment -> phase


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_tests(cfg):
    if cfg.smoke:      # do not touch the committed 05_results/tests_by_case.csv
        cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    else:              # also refreshes 05_results/tests_by_case.csv
        cmd = [sys.executable, "04_benchmarks/export_test_results.py"]
    done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    text = redact(done.stdout + done.stderr)
    (cfg.out / "benchmark_tests.txt").write_text(text, encoding="utf-8")
    counts = {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|error|errors)", text)}
    result = {"command": " ".join(["python", *cmd[1:]]), "exit_code": done.returncode,
              "counts": counts, "output": rel(cfg.out / "benchmark_tests.txt")}
    if done.returncode != 0:
        raise RuntimeError(f"tests failed: {counts}")
    return result


def run_phase(name, cfg, run):
    if name == "tests":
        run["tests"] = run_tests(cfg)
    elif name == "data":
        bench_data.run(cfg)
    elif name == "timing":
        bench_timing.run_replays(cfg)
    elif name == "liquidation":
        bench_timing.run_liquidation(cfg)
    elif name == "concentration":
        bench_concentration.run(cfg)
    elif name == "latency":
        bench_latency.run(cfg)
    elif name == "memory":
        bench_memory.run(cfg)
    elif name == "opcounts":
        bench_opcounts.run(cfg)
    elif name == "summary":
        bench_timing.write_summary(cfg)


def check_data(cfg):
    """The event files a selected phase reuses must be the ones in the manifest."""
    if not (cfg.out / "benchmark_datasets.csv").exists():
        sys.exit("no benchmark_datasets.csv: run --phases data first")
    for ds in read_manifest(cfg):
        path = ROOT / ds["file"]
        if not path.exists() or sha256_file(path) != ds["sha256"]:
            sys.exit(f"{ds['file']} is missing or differs from benchmark_datasets.csv: "
                     "run --phases data first")


def count_status(cfg, phases):
    """Rows of benchmark_results.csv written by these phases, by kind and status."""
    if not cfg.results_csv.exists():
        return {}
    rows = [r for r in read_rows(cfg.results_csv) if PHASE_OF[r["experiment"]] in phases]
    out = {}
    for r in rows:
        out[f"{r['run_kind']}_{r['status']}"] = out.get(f"{r['run_kind']}_{r['status']}", 0) + 1
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--smoke", action="store_true", help="M = 1,000 only, into 05_results/smoke/")
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--phases", nargs="+", choices=PHASES, default=PHASES)
    which.add_argument("--latency-memory", dest="phases", action="store_const",
                       const=["latency", "memory"], help="same as --phases latency memory")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="measure uncommitted code (recorded; not for the final run)")
    parser.add_argument("--time-limit", type=float, default=TIME_LIMIT_S,
                        help=f"seconds per single replay (default {TIME_LIMIT_S:g}; "
                             "only change it to test the stop handling)")
    parser.add_argument("--out", help="output folder (default 05_results/ or 05_results/smoke/)")
    args = parser.parse_args()

    cfg = Config(smoke=args.smoke, out=args.out, time_limit=args.time_limit)
    cfg.out.mkdir(parents=True, exist_ok=True)
    git = git_info()
    if not (args.smoke or args.allow_dirty) and git["code_clean"] is not True:
        sys.exit("refusing a full run: the code is not committed "
                 f"(dirty: {git.get('dirty_code_files')}). Commit first, or use --smoke.")

    phases = [p for p in PHASES if p in args.phases]
    if NEED_DATA.intersection(phases) and "data" not in phases:
        check_data(cfg)
    suffix = "" if phases == PHASES else "_" + "_".join(phases)     # own record per selection

    env = environment(cfg)
    (cfg.out / f"environment{suffix}.json").write_text(json.dumps(env, indent=2) + "\n",
                                                       encoding="utf-8")
    fingerprint = source_fingerprint()
    run = {"status": "running", "command": "python 04_benchmarks/run_benchmark.py "
           + " ".join(sys.argv[1:]), "started_utc": now(), "finished_utc": None,
           "git": git, "measures_committed_code": git["code_clean"] is True,
           "source_sha256_start": fingerprint["sha256"], "source_files": fingerprint["files"],
           "selected_phases": phases, "settings": cfg.describe(),
           "time_limit_is_default": cfg.time_limit == TIME_LIMIT_S,
           "definitions": DEFINITIONS, "tests": None, "phases": []}
    run_path = cfg.out / f"benchmark_run{suffix}.json"

    def save():
        run_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")

    save()
    print(f"benchmark {cfg.describe()['mode']}: commit {git['commit']}, "
          f"code clean {git['code_clean']} -> {rel(cfg.out)}", flush=True)
    name, start = None, time.perf_counter()
    try:
        for name in phases:
            start = time.perf_counter()
            print(f"phase {name} ...", flush=True)
            run_phase(name, cfg, run)
            run["phases"].append({"name": name, "status": "complete",
                                  "seconds": round(time.perf_counter() - start, 1)})
            save()
        run["status"] = "complete"
    except BaseException as exc:   # also Ctrl+C: record where it stopped
        run["phases"].append({"name": name, "status": f"aborted: {type(exc).__name__}",
                              "seconds": round(time.perf_counter() - start, 1)})
        run["status"] = f"aborted in phase {name}: {redact(str(exc))[:500]}"
        raise
    finally:
        end = source_fingerprint()["sha256"]
        run.update(finished_utc=now(), source_sha256_end=end,
                   source_unchanged=end == run["source_sha256_start"],
                   result_rows=count_status(cfg, phases))
        save()
        print(f"benchmark {run['status']}; rows: {run['result_rows']}", flush=True)


if __name__ == "__main__":
    main()
