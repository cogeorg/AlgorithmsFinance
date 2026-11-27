"""Step 5: run the lab tasks and save every result to results/ (CSV and JSON).

    python3 Submissions/HuangJiaxin/Class3/run_lab.py            # full run (several minutes)
    python3 Submissions/HuangJiaxin/Class3/run_lab.py --quick    # small check that it all runs

Tasks (Class 3 slide 31) and extras chosen by Jiaxin (1, 2 and 5):
  bitcoin_1y / bitcoin_5y   tasks 2 to 4: value, European value and premium (extra 1),
                            early-exercise boundary, first exercise on the real path
  assets_1y / assets_5y     task 5: all 40 assets in one run
  runs.csv                  task 6: N, number of assets, seconds, peak traced memory
  memory_full_tree.csv      extra 2: full tree vs two arrays as N doubles
  btc_*_boundary.csv        data for the Bitcoin figure (extra 5, plot_btc.py)

Measurement protocol (as in Assignment 1):
  * time.perf_counter; one untimed warm-up for single-asset runs, then REPEATS timed
    repeats (median and every repeat saved); the 40-asset runs are timed once.
  * Pricing time excludes reading the CSV files; reading is timed separately.
  * tracemalloc in separate runs (timing runs are not traced). Peak traced allocations
    include numpy buffers and Python objects created during the call, not the input
    prices already in memory, the interpreter or native stacks.
"""
import argparse
import csv
import gc
import json
import math
import os
import platform
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data  # noqa: E402
import put  # noqa: E402

RESULTS = HERE / "results"
REPEATS = 3


# ------------------------------------------------------------------ helpers
def params(c):
    return dict(S0=c["S0"], K=c["K"], u=c["u"], d=c["d"], R=c["R"], N=c["N"])


def timed(fn):
    gc.collect()
    gc.disable()
    try:
        t0 = time.perf_counter()
        out = fn()
        return time.perf_counter() - t0, out
    finally:
        gc.enable()


def traced_peak(fn):
    gc.collect()
    tracemalloc.start()
    try:
        fn()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def write_csv(name, header, rows):
    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("saved", RESULTS / name)


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=HERE,
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def boundary_value(b):
    return None if b is None or (isinstance(b, float) and math.isnan(b)) else float(b)


# ------------------------------------------------------------------ one asset
def price_asset(symbol, n, pricer=put.price_numpy, keep_boundary=False):
    return price_loaded(symbol, data.load_closes(symbol), n, pricer, keep_boundary)


def price_loaded(symbol, loaded, n, pricer=put.price_numpy, keep_boundary=False):
    """Calibrate, price the American and the European put, find the first exercise."""
    times, closes = loaded
    tw, pw = data.window(times, closes, n)
    c = data.calibrate(tw, pw)
    value, boundary = pricer(**params(c))
    euro, _ = pricer(**params(c), american=False)
    ex = put.first_exercise(pw, boundary, c["K"])
    row = {"symbol": symbol, "N": c["N"], "start": c["start"], "end": c["end"],
           "hours_spanned": c["hours_spanned"], "S0_K": c["S0"], "P_N": pw[-1],
           "s_hourly": c["s"], "u": c["u"], "q": c["q"], "R_per_period": c["R"],
           "american_value": value, "american_pct_of_S0": 100 * value / c["S0"],
           "european_value": euro, "early_exercise_premium": value - euro,
           "premium_pct_of_american": 100 * (value - euro) / value if value else 0.0,
           "dates_with_boundary": sum(boundary_value(b) is not None for b in boundary),
           "exercised": ex is not None,
           "exercise_t": ex[0] if ex else "", "exercise_time": tw[ex[0]].isoformat() if ex else "",
           "exercise_price": pw[ex[0]] if ex else "", "exercise_payoff": ex[1] if ex else ""}
    if keep_boundary:
        return row, (tw, pw, boundary)
    return row


# ------------------------------------------------------------------ tasks
def bitcoin(n, label, rows_runs):
    row, (tw, pw, boundary) = price_asset("BTCUSDT", n, keep_boundary=True)
    write_csv(f"btc_{label}_boundary.csv", ["t", "timestamp_utc", "price", "boundary"],
              [[t, tw[t].isoformat(), pw[t], boundary_value(boundary[t])]
               for t in range(len(pw))])
    times, closes = data.load_closes("BTCUSDT")
    c = data.calibrate(*data.window(times, closes, n))
    for name, pricer in (("numpy", put.price_numpy), ("plain", put.price_plain)):
        p = params(c)
        repeats = REPEATS if name == "numpy" else 1          # plain Python is slow: one run
        if name == "numpy":
            pricer(**p)                                      # warm-up
        secs = [timed(lambda: pricer(**p))[0] for _ in range(repeats)]
        peak = traced_peak(lambda: pricer(**p)) if (name == "numpy" or label != "5y") else ""
        if peak == "":
            print(f"bitcoin {label} plain: {secs[0]:.1f} s (memory not traced: Theta(N) like numpy)")
            rows_runs.append([f"bitcoin_{label}", name, c["N"], 1, 0, secs[0], "",
                              "plain Python timed once; memory not traced at five years"])
            continue
        for i, s in enumerate(secs):
            rows_runs.append([f"bitcoin_{label}", name, c["N"], 1, i, s, peak, ""])
        print(f"bitcoin {label} {name}: median {sorted(secs)[len(secs) // 2]:.2f} s, "
              f"peak {peak / 1e6:.2f} MB")
    return row


def all_assets(n, label, rows_runs):
    syms = data.symbols()
    t_load, loaded = timed(lambda: {s: data.load_closes(s) for s in syms})

    def run():
        return [price_loaded(s, loaded[s], n) for s in syms]

    secs, rows = timed(run)
    peak = traced_peak(run)
    rows_runs.append([f"assets_{label}", "numpy", n if n else len(loaded[syms[0]][1]) - 1,
                      len(syms), 0, secs, peak,
                      f"American and European put per asset; reading 40 files took "
                      f"{t_load:.2f} s (not included)"])
    print(f"assets {label}: {secs:.1f} s for {len(syms)} assets, peak {peak / 1e6:.2f} MB")
    write_csv(f"assets_{label}.csv", list(rows[0]), [list(r.values()) for r in rows])
    return t_load


def memory_full_tree(sizes):
    """Extra 2: memory and time of the full tree vs two arrays as N doubles."""
    s = 0.0046                                               # Bitcoin's hourly volatility
    rows = []
    for n in sizes:
        p = dict(S0=100.0, K=100.0, u=math.exp(s), d=math.exp(-s), R=math.exp(0.04 / 8760), N=n)
        for name, pricer in (("full_tree", put.price_full_tree), ("two_arrays_plain", put.price_plain),
                             ("two_arrays_numpy", put.price_numpy)):
            secs, (v, _) = timed(lambda: pricer(**p))
            peak = traced_peak(lambda: pricer(**p))
            rows.append([name, n, (n + 1) * (n + 2) // 2, secs, peak, peak / (n + 1), v])
            print(f"memory N={n} {name}: {peak / 1e6:.1f} MB, {secs:.2f} s")
    write_csv("memory_full_tree.csv", ["version", "N", "tree_nodes", "seconds",
                                       "peak_traced_bytes", "bytes_per_period", "value"], rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    global REPEATS
    runs = []
    if args.quick:
        REPEATS = 1
        RESULTS_QUICK = HERE / "results_quick"
        globals()["RESULTS"] = RESULTS_QUICK
        rows = [bitcoin(500, "quick", runs)]
        memory_full_tree([50, 100])
    else:
        rows = [bitcoin(data.HOURS_PER_YEAR, "1y", runs), bitcoin(None, "5y", runs)]
        t1 = all_assets(data.HOURS_PER_YEAR, "1y", runs)
        t5 = all_assets(None, "5y", runs)
        memory_full_tree([250, 500, 1000, 2000, 4000])
    write_csv("bitcoin.csv", list(rows[0]), [list(r.values()) for r in rows])
    write_csv("runs.csv", ["run", "version", "N", "assets", "repeat", "seconds",
                           "peak_traced_bytes", "note"], runs)
    env = {"timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
           "cpu_count": os.cpu_count(), "numpy": np.__version__, "code_commit": git_commit(),
           "repeats_single_asset": REPEATS, "rate": data.RATE,
           "year_length_days": data.SECONDS_PER_YEAR / 86400,
           "one_year_N": data.HOURS_PER_YEAR, "quick": args.quick,
           "exercise_rule": "exercise if K - S > 0 and K - S >= continuation value",
           "first_exercise_rule": "first t >= 1 with P_t <= b_t and K - P_t > 0"}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "environment.json").write_text(json.dumps(env, indent=2) + "\n")
    print("saved", RESULTS / "environment.json")


if __name__ == "__main__":
    main()
