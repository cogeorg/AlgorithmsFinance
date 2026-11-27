"""Scaling exploration: replay time vs event count M (single runs, not the benchmark).

Usage (from Assignment1/), after 04_benchmarks/generate_data.py:
    python 04_benchmarks/scaling.py --version a

For every scenario and M in SIZES, one child process:
  1. loads 05_results/data/<scenario>_<M>.jsonl.gz (not timed),
  2. replays it on a fresh book, engine time only (process_event loop,
     time.perf_counter, invariants off),
  3. derives peak active orders / peak occupied price levels AFTER timing
     from the returned results (a shadow book: resting residuals, fills and
     cancels), and cross-checks the final size against inspect_book().
The parent kills a child after TIME_LIMIT_S seconds of child wall time
(loading + replay + counting) and records status "stopped" with empty
values. Missing values are never estimated.

Writes 05_results/scaling_version_<v>.csv (rewritten after every run, so
progress survives an interruption) and scaling_version_<v>.meta.json.
"""

import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_code"))
DATA = ROOT / "05_results" / "data"
RESULTS = ROOT / "05_results"

SCENARIOS = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]
SIZES = [1000, 10000, 30000, 100000]
SEED = 42
TIME_LIMIT_S = 600  # 10 minutes per run
FIELDS = ["version", "scenario", "seed", "events", "peak_active_orders",
          "peak_price_levels", "fills", "seconds", "status"]


def shadow_peaks(events, results):
    """Peak active orders and occupied (side, price) levels, from results only."""
    active = {}          # order_id -> [side, price, qty]
    levels = Counter()   # (side, price) -> number of active orders
    peak_orders = peak_levels = 0

    def remove(order_id):
        side, price, _ = active.pop(order_id)
        levels[(side, price)] -= 1
        if levels[(side, price)] == 0:
            del levels[(side, price)]

    for e, r in zip(events, results):
        status = r["status"]
        if status == "rejected":
            continue
        for f in r.get("fills", []):
            maker = active[f["maker_id"]]
            maker[2] -= f["qty_units"]
            if maker[2] == 0:
                remove(f["maker_id"])
        if e["type"] == "LIMIT" and status == "resting":
            active[e["order_id"]] = [e["side"], e["price_ticks"], r["unfilled_qty_units"]]
            levels[(e["side"], e["price_ticks"])] += 1
        elif status == "cancelled":
            remove(e["target_order_id"])
        peak_orders = max(peak_orders, len(active))
        peak_levels = max(peak_levels, len(levels))
    return peak_orders, peak_levels, len(active)


def child(path, version):
    """Run one replay and print one JSON line."""
    import importlib
    from replay import load_events

    events = load_events(path)
    book = importlib.import_module(f"lob_{version}").OrderBook()
    process = book.process_event
    start = time.perf_counter()
    results = [process(e) for e in events]
    seconds = time.perf_counter() - start

    peak_orders, peak_levels, final = shadow_peaks(events, results)
    assert final == len(book.inspect_book()), "shadow book disagrees with engine"
    print(json.dumps({
        "events": len(events),
        "peak_active_orders": peak_orders,
        "peak_price_levels": peak_levels,
        "fills": sum(len(r.get("fills", [])) for r in results),
        "seconds": f"{seconds:.6f}",
    }))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, check=True)
        dirty = subprocess.run(["git", "status", "--porcelain", "03_code"], cwd=ROOT,
                               capture_output=True, text=True, check=True)
        return out.stdout.strip(), bool(dirty.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return None, None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["a", "b_sorted", "b_heap"], required=True)
    parser.add_argument("--child", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.child:
        child(args.child, args.version)
        return

    out_csv = RESULTS / f"scaling_version_{args.version}.csv"
    commit, dirty = git_commit()
    meta = {
        "what": "single-run scaling exploration, engine replay time only",
        "time_limit_seconds_per_run": TIME_LIMIT_S,
        "time_limit_covers": "child wall time: loading + replay + peak counting",
        "seconds_covers": "process_event loop only; loading/parsing excluded",
        "invariant_checks": False,
        "repeats": 1,
        "seed": SEED, "sizes": SIZES, "scenarios": SCENARIOS, "levels": 1000,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "git_commit": commit, "code_dirty": dirty,
        "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    rows = []
    for m in SIZES:
        for scenario in SCENARIOS:
            path = DATA / f"{scenario}_{m}.jsonl.gz"
            row = {"version": args.version, "scenario": scenario, "seed": SEED,
                   "events": m, "peak_active_orders": "", "peak_price_levels": "",
                   "fills": "", "seconds": "", "status": ""}
            try:
                done = subprocess.run(
                    [sys.executable, __file__, "--version", args.version,
                     "--child", str(path)],
                    capture_output=True, text=True, timeout=TIME_LIMIT_S, check=True)
                row.update(json.loads(done.stdout.strip().splitlines()[-1]))
                row["status"] = "ok"
            except subprocess.TimeoutExpired:
                row["status"] = "stopped"
            rows.append(row)
            write_csv(out_csv, rows)
            print(" ".join(f"{k}={row[k]}" for k in FIELDS), flush=True)
    meta["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (RESULTS / f"scaling_version_{args.version}.meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
