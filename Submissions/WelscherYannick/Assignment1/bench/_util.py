"""Shared helpers for the benchmark scripts."""
import csv
import json
import math
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lob.book_a import BookA  # noqa: E402
from lob.book_b import BookB  # noqa: E402

GEN = ROOT / "data" / "generated"
RESULTS = ROOT / "results"
VERSIONS = {"A": BookA, "B": BookB}
SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
SIZES = (1000, 10000, 100000)
SEEDS = (42, 43, 44)
MILLION = [("mixed", 1000000, 42), ("buildup", 1000000, 42)]
REPEATS = 5
CONFIG_LIMIT_S = 120  # declared wall-clock limit per configuration (parse + warmup + 5 repeats)

COLUMNS = ["run_kind", "version", "scenario", "seed", "events", "levels", "phase", "repeat",
           "elapsed_s", "status", "active_orders_peak", "price_levels_peak", "fills",
           "requested_qty_units", "unfilled_qty_units", "makers_touched", "levels_visited",
           "work_steps", "traced_peak_bytes", "traced_current_bytes", "note"]


def input_path(scenario, events, seed, levels=1000):
    return GEN / f"{scenario}_{events}_s{seed}_l{levels}.jsonl.gz"


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})


def read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def nearest_rank(sorted_vals, p):
    """Percentile convention: nearest rank, value at position ceil(p/100 * n) (1-based)."""
    if not sorted_vals:
        return None
    k = max(1, math.ceil(p / 100 * len(sorted_vals)))
    return sorted_vals[k - 1]


def workload_stats(events):
    """Version-independent workload measures from a Version B replay (not timed)."""
    book = BookB()
    peak_b = peak_p = fills = 0
    kinds = {}
    for ev in events:
        res = book.process(ev)
        kinds[res["status"]] = kinds.get(res["status"], 0) + 1
        fills += len(res.get("fills", ()))
        b = len(book.index)
        p = len(book.bid_levels) + len(book.ask_levels)
        if b > peak_b:
            peak_b = b
        if p > peak_p:
            peak_p = p
    return {"active_orders_peak": peak_b, "price_levels_peak": peak_p, "fills": fills,
            "final_active_orders": len(book.index), "statuses": kinds}


def env_info():
    def run(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).stdout.strip()
        except OSError:
            return ""
    return {
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": run(["sysctl", "-n", "machdep.cpu.brand_string"]),
        "cpu_count": run(["sysctl", "-n", "hw.ncpu"]),
        "memory_bytes": run(["sysctl", "-n", "hw.memsize"]),
        "git_commit": run(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(run(["git", "status", "--porcelain", "--", "lob", "bench", "tests"])),
        "dependencies": "Python standard library only; dashboard is self-contained HTML + inline SVG",
    }


def save_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1) + "\n")
