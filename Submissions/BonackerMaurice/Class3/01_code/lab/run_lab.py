"""Class 3 lab: every run, saved to ../02_results/<run_id>/.

    python -m lab.run_lab                      # everything (btc, curve, assets)
    python -m lab.run_lab --only btc curve     # some steps
    python -m lab.run_lab --quick              # small grid for development (gitignored)

Steps
  btc    Tasks 2-4: BTCUSDT, one year (N = 8,760) and the full file (at most five years):
         value, early-exercise boundary, would the holder have exercised.
  curve  Memory/time against N for reference, vectorised and fulltree (main result).
  assets Task 5: all 40 assets, one year and five years, 1 worker vs more workers.
Every step adds rows to runs.csv / runs.md (task 6).
"""
import argparse
import csv
import json
import math
import os
import sys
import time
import tracemalloc
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from american_put.common import tree_log_range
from american_put.fulltree import tree_bytes
from lab import measure
from market import data

CODE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = CODE_DIR.parents[3] / "Class3" / "data" / "hourly"
RESULTS_DIR = CODE_DIR.parent / "02_results"

ONE_YEAR_N = 8760
FIVE_YEARS = 5
CURVE_N = [1000, 2000, 5000, 10000, 20000, None]   # None = full BTC file (43,822)
BEYOND_DATA_N = [55000, 70000]                     # BTC 5-year parameters, no data needed
REFERENCE_MAX_N = 43822                            # pure Python beyond this: not run (time)
REFERENCE_TRACED_MAX_N = 5000                      # pure Python under tracemalloc beyond this: too slow
RAM_FRACTION = 0.8                                 # full tree runs only if it needs < 80% of free RAM
QUICK_CURVE_N = [500, 1000, 2000]


# ------------------------------------------------------------------ helpers

def btc_file():
    return DATA_DIR / "BTCUSDT.csv"


def horizon_window(ts, closes, horizon):
    if horizon == "1y":
        return data.last_window(ts, closes, ONE_YEAR_N)
    return data.window_years(ts, closes, FIVE_YEARS)


def fmt_ts(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def append_runs(out, rows):
    """Task 6 table: N, assets, wall-clock seconds, peak memory, for every run."""
    path = out / "runs.csv"
    old = list(csv.DictReader(open(path))) if path.exists() else []
    write_csv(path, old + rows)
    write_runs_md(out)


def write_runs_md(out):
    rows = list(csv.DictReader(open(out / "runs.csv")))
    cols = ["run", "version", "N", "assets", "workers", "wall_s", "traced_peak_mb",
            "process_peak_mb", "status"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        lines.append("| " + " | ".join(r.get(c, "") for c in cols) + " |")
    (out / "runs.md").write_text("\n".join(lines) + "\n")


def r3(x):
    return "" if x is None else f"{x:.3f}"


def mb(x):
    return "" if x is None else f"{x:.1f}"


def exercise_fields(hit):
    if hit is None:
        return {"exercised": "never", "exercise_t": "", "exercise_utc": "", "exercise_price": "",
                "exercise_payoff": ""}
    return {"exercised": "yes", "exercise_t": hit.t, "exercise_utc": fmt_ts(hit.timestamp),
            "exercise_price": hit.price, "exercise_payoff": hit.payoff}


def calibration_fields(cal):
    """Calibration plus the float-range headroom: log10 of S0*d^N and S0*u^N
    (a float covers about -307.7 .. 308.3)."""
    lo, hi = tree_log_range(cal.S0, cal.u, cal.d, cal.N)
    return {"N": cal.N, "T_years": cal.T, "s": cal.s, "sN": cal.s * cal.N, "u": cal.u,
            "d": cal.d, "R": cal.R, "S0": cal.S0, "K": cal.K,
            "log10_S_min": lo / math.log(10), "log10_S_max": hi / math.log(10)}


# ------------------------------------------------------------------ step: btc (tasks 2-4)

def step_btc(out, quick):
    ts, closes = data.load_hourly(btc_file())
    horizons = ["1y"] if quick else ["1y", "5y"]
    summary, runs = [], []
    for horizon in horizons:
        wts, wcl = horizon_window(ts, closes, horizon)
        versions = ["vectorised", "reference"] if horizon == "1y" else ["vectorised"]
        results = {}
        for version in versions:
            priced = data.price_window(wts, wcl, measure.PRICERS[version])
            results[version] = priced
            # Seconds and memory for the table: the same call, measured in a fresh process.
            cal = priced.calibration
            params = (cal.S0, cal.K, cal.u, cal.d, cal.R, cal.N)
            cell = measure.measure_in_fresh_process(version, params, traced=version != "reference")
            print(f"btc {horizon} {version}: N={cal.N} value={priced.value:.4f} "
                  f"{cell['seconds']:.1f}s", flush=True)
            runs.append({"run": f"btc-{horizon}", "version": version, "N": cal.N,
                         "assets": 1, "workers": 1, "wall_s": r3(cell["seconds"]),
                         "traced_peak_mb": mb(cell["traced_peak_mb"]),
                         "process_peak_mb": mb(cell["process_peak_mb"]), "status": "ok"})
        main = results["vectorised"]
        agree = ""
        if "reference" in results:
            ref = results["reference"]
            agree = (ref.value == main.value) and (ref.boundary == main.boundary)
        cal = main.calibration
        summary.append({"asset": "BTCUSDT", "horizon": horizon, "start_utc": fmt_ts(wts[0]),
                        "end_utc": fmt_ts(wts[-1]), **calibration_fields(cal),
                        "value": main.value, "value_pct_of_S0": 100 * main.value / cal.S0,
                        **exercise_fields(main.exercise),
                        "reference_equals_vectorised": agree})
        write_csv(out / f"btc_{horizon}_boundary.csv",
                  ({"t": t, "timestamp_utc": fmt_ts(x), "close": p,
                    "boundary": "" if b is None else b}
                   for t, (x, p, b) in enumerate(zip(wts, wcl, main.boundary))))
    write_csv(out / "btc.csv", summary)
    append_runs(out, runs)


# ------------------------------------------------------------------ step: curve (main result)

def curve_cells(quick):
    """(N, source, params) for every grid point. Params = (S0, K, u, d, R, N)."""
    ts, closes = data.load_hourly(btc_file())
    cells = []
    for N in (QUICK_CURVE_N if quick else CURVE_N):
        wts, wcl = data.last_window(ts, closes, N if N else len(closes) - 1)
        cal = data.calibrate(wts, wcl)
        cells.append((cal.N, "btc data, last N+1 hours", (cal.S0, cal.K, cal.u, cal.d, cal.R, cal.N)))
    if not quick:
        cal = data.calibrate(*data.window_years(ts, closes, FIVE_YEARS))
        for N in BEYOND_DATA_N:  # longer than the file: reuse the 5-year per-hour u, d, R
            cells.append((N, "btc 5-year u, d, R (synthetic N)", (cal.S0, cal.K, cal.u, cal.d, cal.R, N)))
    return cells


def step_curve(out, quick, ram_checks):
    rows, runs = [], []
    for N, source, params in curve_cells(quick):
        for version in ["reference", "vectorised", "fulltree"]:
            row = {"version": version, "N": N, "source": source, "tree_gb": "",
                   "ram_available_gb": "", "seconds": "", "traced_peak_mb": "",
                   "process_peak_mb": "", "value": "", "boundary_sha256": "", "status": ""}
            if version == "reference" and N > REFERENCE_MAX_N:
                row["status"] = "not run: pure Python too slow beyond the data length"
            else:
                if version == "fulltree":
                    need, free = tree_bytes(N), measure.ram_available_bytes()
                    row["tree_gb"] = f"{need / measure.GB:.2f}"
                    row["ram_available_gb"] = f"{free / measure.GB:.2f}"
                    ram_checks.append({"when_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                       "N": N, "tree_gb": round(need / measure.GB, 2),
                                       "ram_available_gb": round(free / measure.GB, 2)})
                    if need > RAM_FRACTION * free:
                        row["status"] = (f"out of memory: tree needs {need / measure.GB:.1f} GB, "
                                         f"{free / measure.GB:.1f} GB free (not attempted)")
                if not row["status"]:
                    # tracemalloc slows pure Python about 18x (it traces every float object);
                    # the reference's traced peak is measured up to N = 5,000, its process
                    # peak always.
                    traced = not (version == "reference" and N > REFERENCE_TRACED_MAX_N)
                    try:
                        cell = measure.measure_in_fresh_process(version, params, traced=traced)
                        row.update(seconds=r3(cell["seconds"]), traced_peak_mb=mb(cell["traced_peak_mb"]),
                                   process_peak_mb=mb(cell["process_peak_mb"]), value=cell["value"],
                                   boundary_sha256=cell["boundary_sha256"], status="ok")
                    except MemoryError:
                        row["status"] = "out of memory: MemoryError"
                    except Exception as exc:  # e.g. the worker process was killed
                        row["status"] = f"failed: {type(exc).__name__}: {exc}"
            print(f"curve N={N} {version}: {row['seconds'] or '-'} s, traced {row['traced_peak_mb'] or '-'} MB, "
                  f"process {row['process_peak_mb'] or '-'} MB, {row['status']}", flush=True)
            rows.append(row)
            runs.append({"run": "curve", "version": version, "N": N, "assets": 1, "workers": 1,
                         "wall_s": row["seconds"], "traced_peak_mb": row["traced_peak_mb"],
                         "process_peak_mb": row["process_peak_mb"], "status": row["status"]})
            write_csv(out / "memory_curve.csv", rows)
    append_runs(out, runs)


# ------------------------------------------------------------------ step: assets (task 5)

def price_asset(path, horizon):
    """One asset in a worker process: price, boundary, exercise, seconds, peak memory."""
    ts, closes = data.load_hourly(path)
    wts, wcl = horizon_window(ts, closes, horizon)
    tracemalloc.start()
    start = time.perf_counter()
    priced = data.price_window(wts, wcl, measure.PRICERS["vectorised"])
    seconds = time.perf_counter() - start
    traced_peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    cal = priced.calibration
    return {"asset": Path(path).stem, "horizon": horizon, "start_utc": fmt_ts(wts[0]),
            "end_utc": fmt_ts(wts[-1]), **calibration_fields(cal), "value": priced.value,
            "value_pct_of_S0": 100 * priced.value / cal.S0, **exercise_fields(priced.exercise),
            "seconds": seconds, "traced_peak_mb": traced_peak / measure.MB,
            "worker_pid": os.getpid(), "worker_peak_mb": measure.peak_process_bytes() / measure.MB}


def step_assets(out, quick):
    files = sorted(DATA_DIR.glob("*.csv"))
    files = [f for f in files if f.stem != "SP500"]   # the S&P file is optional and not committed
    if quick:
        files = files[:4]
    cores = os.cpu_count()
    worker_counts = sorted({1, max(1, cores // 2), cores})
    horizons = ["1y"] if quick else ["1y", "5y"]
    per_asset, runs = [], []
    for horizon in horizons:
        for workers in worker_counts:
            with measure.MemorySampler() as sampler:
                start = time.perf_counter()
                with ProcessPoolExecutor(max_workers=workers) as pool:
                    results = list(pool.map(price_asset, files, [horizon] * len(files)))
                wall = time.perf_counter() - start
            per_worker = {}
            for r in results:
                per_worker[r["worker_pid"]] = max(per_worker.get(r["worker_pid"], 0), r["worker_peak_mb"])
            Ns = sorted({r["N"] for r in results})
            print(f"assets {horizon} workers={workers}: {len(results)} assets, {wall:.1f} s wall, "
                  f"total peak {sampler.peak / measure.MB:.0f} MB", flush=True)
            runs.append({"run": f"assets-{horizon}", "version": "vectorised",
                         "N": Ns[0] if len(Ns) == 1 else f"{Ns[0]}-{Ns[-1]}",
                         "assets": len(results), "workers": workers, "wall_s": r3(wall),
                         "traced_peak_mb": mb(max(r["traced_peak_mb"] for r in results)) + " per asset (max)",
                         "process_peak_mb": f"{max(per_worker.values()):.1f} per worker (max); "
                                            f"{sampler.peak / measure.MB:.1f} total (sampled)",
                         "status": f"ok; sum of per-asset seconds {sum(r['seconds'] for r in results):.1f}"})
            if workers == worker_counts[-1]:
                per_asset.extend({k: v for k, v in r.items() if k not in ("worker_pid",)} for r in results)
    write_csv(out / "assets.csv", per_asset)
    append_runs(out, runs)


# ------------------------------------------------------------------ main

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", choices=["btc", "curve", "assets"])
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--out", help="existing results folder to add to (default: a new run_id)")
    args = parser.parse_args(argv)
    steps = args.only or ["btc", "curve", "assets"]

    env = measure.environment()
    if args.out:
        out = Path(args.out)
    else:
        sha = (env["git"]["commit"] or "nogit")[:7]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out = RESULTS_DIR / f"{stamp}_{sha}{'_dirty' if env['git']['dirty'] else ''}{'_quick' if args.quick else ''}"
    out.mkdir(parents=True, exist_ok=True)
    env_path = out / "environment.json"
    env_all = json.loads(env_path.read_text()) if env_path.exists() else {"runs": []}
    env_all["runs"].append({"steps": steps, "command": " ".join(["python -m lab.run_lab", *sys.argv[1:]]),
                            **env, "ram_checks_before_fulltree": []})
    measure.write_json(env_path, env_all)
    print(f"results -> {out}  (free RAM {env['ram_available_gb_at_start']} GB of {env['ram_total_gb']} GB)",
          flush=True)

    ram_checks = env_all["runs"][-1]["ram_checks_before_fulltree"]
    for step in steps:
        start = time.perf_counter()
        if step == "btc":
            step_btc(out, args.quick)
        elif step == "curve":
            step_curve(out, args.quick, ram_checks)
        elif step == "assets":
            step_assets(out, args.quick)
        print(f"step {step} done in {time.perf_counter() - start:.0f} s", flush=True)
        env_all["runs"][-1]["ram_available_gb_at_end"] = round(measure.ram_available_bytes() / measure.GB, 2)
        measure.write_json(env_path, env_all)


if __name__ == "__main__":   # required on Windows: worker processes re-import this module
    main()
