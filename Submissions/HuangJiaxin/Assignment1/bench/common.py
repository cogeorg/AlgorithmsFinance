"""Shared helpers for all experiments: datasets, environment metadata, timing, CSV output.

Timing rules (assignment README, "Time and latency"):
* time.perf_counter; one untimed warm-up; five timed repeats; every raw repeat is saved.
* Every replay starts from a fresh, empty book; events are pre-generated and preloaded.
* Garbage collection runs before each timed block and is disabled during it.
* A declared time limit stops runs that are too slow (reported as "stopped", never invented).
"""
import csv
import gc
import json
import math
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lob.book_a import OrderBookA  # noqa: E402
from lob.book_b import OrderBookB  # noqa: E402

GENERATED = ROOT / "data" / "generated"
RESULTS = ROOT / "results"
REPEATS = 5
TIME_LIMIT_S = float(os.environ.get("LOB_TIME_LIMIT_S", "30"))   # declared per-run limit

VERSIONS = {"A": OrderBookA, "B": OrderBookB}


class Stopped(Exception):
    """A run exceeded the declared time limit."""

    def __init__(self, processed, elapsed):
        super().__init__(f"stopped after {processed} events and {elapsed:.1f} s")
        self.processed, self.elapsed = processed, elapsed


# ------------------------------------------------------------------ datasets
def dataset_name(scenario, events, seed, levels=1000):
    return f"{scenario}_{events}_s{seed}_L{levels}.jsonl.gz"


def dataset(scenario, events, seed, levels=1000):
    """Path of a generated dataset; generates it (outside any timing) if missing."""
    path = GENERATED / dataset_name(scenario, events, seed, levels)
    if not path.exists():
        GENERATED.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(ROOT / "generate_orders.py"), "--scenario", scenario,
                        "--events", str(events), "--levels", str(levels), "--seed", str(seed),
                        "--out", str(path)], check=True, stdout=subprocess.DEVNULL)
    return path


# ------------------------------------------------------------------ replay and timing
def replay(book, events):
    process = book.process
    for e in events:
        process(e)


def replay_with_limit(book, events, limit=TIME_LIMIT_S):
    """Untimed warm-up replay that checks the declared time limit every 256 events."""
    process = book.process
    start = time.perf_counter()
    for i, e in enumerate(events):
        process(e)
        if i % 256 == 0 and time.perf_counter() - start > limit:
            raise Stopped(i + 1, time.perf_counter() - start)


def timed(fn):
    """Elapsed seconds of fn(); GC collected before and disabled during the block."""
    gc.collect()
    gc.disable()
    try:
        t0 = time.perf_counter()
        out = fn()
        elapsed = time.perf_counter() - t0
    finally:
        gc.enable()
    return elapsed, out


def median(values):
    s = sorted(values)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def percentile(sorted_values, p):
    """Nearest-rank percentile: the smallest value with at least p % of values <= it."""
    n = len(sorted_values)
    if n == 0:
        return None
    return sorted_values[max(0, math.ceil(p / 100 * n) - 1)]


# ------------------------------------------------------------------ book statistics
def book_peaks(events):
    """Peak active orders and occupied price levels over a stream (untimed; uses B,
    whose state equals A's after every event, see tests/test_equivalence.py)."""
    b = OrderBookB()
    peak_orders = peak_levels = 0
    for e in events:
        b.process(e)
        peak_orders = max(peak_orders, b.active_order_count())
        peak_levels = max(peak_levels, b.price_level_count())
    return peak_orders, peak_levels, b.active_order_count(), b.price_level_count()


# ------------------------------------------------------------------ metadata and output
def _git(*args):
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment(script, **settings):
    commit = os.environ.get("CODE_COMMIT") or _git("rev-parse", "HEAD")
    dirty = _git("status", "--porcelain", "--", ".", ":(exclude)results")
    deps = {}
    for pkg in ["pandas", "streamlit", "pytest"]:
        try:
            deps[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            deps[pkg] = None
    return {
        "script": script,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "dependencies": deps,
        "code_commit": commit or "unknown",
        "uncommitted_changes_outside_results": None if dirty is None else bool(dirty),
        "time_limit_s_per_run": TIME_LIMIT_S,
        "repeats": REPEATS,
        "warm_up": "one untimed run per configuration",
        "clock": "time.perf_counter",
        "gc": "collected before and disabled during each timed block",
        **settings,
    }


def write_csv(name, header, rows):
    RESULTS.mkdir(exist_ok=True)
    with open(RESULTS / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    return RESULTS / name


def write_json(name, obj):
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / name).write_text(json.dumps(obj, indent=2) + "\n")
    return RESULTS / name
