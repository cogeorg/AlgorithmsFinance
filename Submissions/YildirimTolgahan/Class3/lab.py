"""Class 3 lab: PriceAmericanPut on hourly market data, tasks 1-6.

    python lab.py              all runs; writes results/
    python lab.py --quick      lab runs only (skips the slow comparison runs)

Every run executes twice in a fresh interpreter.  The first gives the clock
(loading, calibration, pricing and the exercise search; interpreter start-up
and imports excluded) and the peak resident memory of the whole process.  The
second runs under tracemalloc and gives the peak of the allocations made by a
pricing call, largest over the assets of the run: the loaded prices and the
interpreter are not in that number.
"""

import csv
import json
import math
import subprocess
import sys
import time
import tracemalloc
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np

from american_put import (
    calibrate, first_exercise, price_band, price_dense, price_slides, PutResult,
)

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[2] / "Class3" / "data" / "hourly"
OUT = HERE / "results"
YEAR = 8760

# name: (method, symbols, window, lab task, description)
RUNS = {
    "btc_1y_band":   ("band",   "BTC", YEAR, "2, 3", "band"),
    "btc_5y_band":   ("band",   "BTC", None, "4",    "band"),
    "all_1y_band":   ("band",   "ALL", YEAR, "5",    "band"),
    "all_5y_band":   ("band",   "ALL", None, "5",    "band"),
    "btc_1y_slides": ("slides", "BTC", YEAR, "-",    "slides, pure Python"),
    "btc_1y_dense":  ("dense",  "BTC", YEAR, "-",    "slides, NumPy rows"),
    "btc_1y_tree":   ("tree",   "BTC", YEAR, "-",    "NumPy rows, whole tree stored"),
    "btc_5y_dense":  ("dense",  "BTC", None, "-",    "slides, NumPy rows"),
}
QUICK = ["btc_1y_band", "btc_5y_band", "all_1y_band", "all_5y_band"]


def symbols():
    return sorted(path.stem for path in DATA.glob("*USDT.csv"))


def load(symbol, window):
    """Last window + 1 closes (all rows if window is None) with their timestamps."""
    with open(DATA / f"{symbol}.csv", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        rows = deque(reader, maxlen=None if window is None else window + 1)
    return [row[0] for row in rows], [float(row[1]) for row in rows]


def hours_between(first, last):
    stamp = lambda text: datetime.fromisoformat(text.replace("Z", "+00:00"))
    return (stamp(last) - stamp(first)).total_seconds() / 3600.0


def peak_process_bytes():
    """Peak resident memory of this process."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.K32GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        kernel.K32GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb)
        return counters.PeakWorkingSetSize
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def price(method, c):
    if method == "band":
        return price_band(c.S0, c.K, c.u, c.d, c.R, c.N)
    if method == "dense":
        return price_dense(c.S0, c.K, c.u, c.d, c.R, c.N)
    if method == "tree":
        return price_dense(c.S0, c.K, c.u, c.d, c.R, c.N, store_tree=True)[0]
    value, jstar, boundary = price_slides(c.S0, c.K, c.u, c.d, c.R, c.N)
    return PutResult(value, np.array(jstar), np.array(boundary), c.N * (c.N + 1) // 2)


def worker(name, trace):
    """One run, start to finish, in this process.  Prints one JSON line."""
    method, which, window, _, _ = RUNS[name]
    if trace:
        tracemalloc.start()
    start = time.perf_counter()
    pricing = 0.0
    pricing_peak = 0        # allocations made by the pricing call alone
    assets = []
    for symbol in (symbols() if which == "ALL" else ["BTCUSDT"]):
        stamps, closes = load(symbol, window)
        c = calibrate(closes, hours_between(stamps[0], stamps[-1]))
        if trace:
            before = tracemalloc.get_traced_memory()[0]
            tracemalloc.reset_peak()
        tick = time.perf_counter()
        result = price(method, c)
        pricing += time.perf_counter() - tick
        if trace:
            pricing_peak = max(pricing_peak, tracemalloc.get_traced_memory()[1] - before)
        hit = first_exercise(closes, result)
        assets.append({
            "symbol": symbol, "N": c.N, "T_years": c.T, "s_hourly": c.s, "u": c.u,
            "R": c.R, "K": c.K, "put_value": result.value,
            "first_close": stamps[0], "last_close": stamps[-1],
            "exercise_t": hit[0] if hit else None,
            "exercise_date": stamps[hit[0]] if hit else "never",
            "exercise_payoff": hit[1] if hit else None,
            "payoff_at_expiry": max(c.K - closes[-1], 0.0),
            "dates_with_boundary": int((result.jstar >= 0).sum()),
            "nodes": result.nodes,
        })
        if name in ("btc_1y_band", "btc_5y_band") and not trace:
            OUT.mkdir(exist_ok=True)
            with open(OUT / f"boundary_{name[:6]}.csv", "w", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["t", "timestamp_utc", "close", "jstar", "boundary"])
                for t in range(c.N + 1):
                    j = int(result.jstar[t])
                    writer.writerow([t, stamps[t], closes[t], j if j >= 0 else "",
                                     repr(float(result.boundary[t])) if j >= 0 else "none"])
        del result
    seconds = time.perf_counter() - start
    print(json.dumps({"name": name, "seconds": seconds, "pricing_seconds": pricing,
                      "pricing_peak": pricing_peak if trace else None,
                      "process_peak": peak_process_bytes(), "assets": assets}))


def run(name):
    out = {}
    for trace in (False, True):
        command = [sys.executable, str(HERE / "lab.py"), "--worker", name]
        done = subprocess.run(command + (["--trace"] if trace else []),
                              capture_output=True, text=True, cwd=HERE)
        if done.returncode:
            raise RuntimeError(f"{name} failed:\n{done.stderr}")
        out[trace] = json.loads(done.stdout.strip().splitlines()[-1])
    timed, traced = out[False], out[True]
    for a, b in zip(timed["assets"], traced["assets"]):
        assert a["put_value"] == b["put_value"] and a["exercise_t"] == b["exercise_t"]
    timed["pricing_peak"] = traced["pricing_peak"]
    return timed


def mib(x):
    return f"{x / 2**20:,.1f}"


def main():
    names = QUICK if "--quick" in sys.argv else list(RUNS)
    OUT.mkdir(exist_ok=True)

    value = price_band(100, 100, 1.2, 0.8, 1.05, 2).value
    assert round(value, 4) == 7.9932, value
    print(f"Task 1: two-period tree {value:.4f}")

    results = {}
    for name in names:
        results[name] = run(name)
        r = results[name]
        print(f"{name:14s} {r['seconds']:8.2f} s   pricing {mib(r['pricing_peak']):>8s} MiB"
              f"   process {mib(r['process_peak']):>8s} MiB", flush=True)

    lines = ["| Task | Method | N | Assets | Nodes updated | Seconds | of which pricing "
             "| Peak memory, pricing (MiB) | Peak memory, process (MiB) |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    rows = []
    for name in names:
        method, _, _, task, text = RUNS[name]
        r = results[name]
        n = max(a["N"] for a in r["assets"])
        nodes = sum(a["nodes"] for a in r["assets"])
        lines.append(
            f"| {task} | {text} | {n:,} | {len(r['assets'])} | {nodes:,} | {r['seconds']:.2f} "
            f"| {r['pricing_seconds']:.2f} | {mib(r['pricing_peak'])} | {mib(r['process_peak'])} |")
        rows.append([name, task, text, n, len(r["assets"]), nodes, r["seconds"],
                     r["pricing_seconds"], r["pricing_peak"], r["process_peak"]])
    (OUT / "table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(OUT / "runs.csv", "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["run", "task", "method", "N", "assets", "nodes_updated", "seconds",
                         "pricing_seconds", "peak_pricing_bytes", "peak_process_bytes"])
        writer.writerows(rows)

    for name in ("all_1y_band", "all_5y_band"):
        if name in results:
            assets = results[name]["assets"]
            with open(OUT / f"puts_{name[:6]}.csv", "w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(assets[0]))
                writer.writeheader()
                writer.writerows(assets)

    for name in ("btc_1y_band", "btc_5y_band"):
        if name in results:
            a = results[name]["assets"][0]
            print(f"\n{name}: N = {a['N']:,}, s = {a['s_hourly']:.6f}, K = {a['K']:,.2f}")
            print(f"  put value {a['put_value']:,.4f} ({100 * a['put_value'] / a['K']:.2f}% of K)")
            if a["exercise_t"] is None:
                print("  exercise: never")
            else:
                print(f"  exercise: t = {a['exercise_t']:,} ({a['exercise_date']}), "
                      f"payoff {a['exercise_payoff']:,.2f}")
            print(f"  payoff if held to expiry: {a['payoff_at_expiry']:,.2f}")

    if all(k in results for k in ("btc_1y_band", "btc_1y_dense", "btc_1y_slides")):
        values = [results[k]["assets"][0]["put_value"]
                  for k in ("btc_1y_band", "btc_1y_dense", "btc_1y_slides", "btc_1y_tree")]
        assert max(values) - min(values) < 1e-8 * values[0], values
    n = max(a["N"] for a in results["btc_5y_band"]["assets"])
    print(f"\nWhole five-year tree as float64: {(n + 1) ** 2 * 8 / 2**30:.1f} GiB "
          f"square, {(n + 1) * (n + 2) * 4 / 2**30:.1f} GiB triangular (not run).")
    print((OUT / "table.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    if "--worker" in sys.argv:
        worker(sys.argv[sys.argv.index("--worker") + 1], "--trace" in sys.argv)
    else:
        main()
