"""Shared settings and helpers for the final benchmark (04_benchmarks/bench_*.py).

Run everything through run_benchmark.py, from Assignment1/:
    python 04_benchmarks/run_benchmark.py            full run (committed code only)
    python 04_benchmarks/run_benchmark.py --smoke    M = 1,000 only -> 05_results/smoke/

Every setting that decides what is measured is declared in this file;
run_benchmark.py copies it into benchmark_run.json.

Child protocol: each measurement runs in its own child process
(`python 04_benchmarks/<script> --child ...`). The child prints one JSON
object per line:
    {"start": [...]}   a limited step (one replay) begins
    {"stop":  [...]}   the step's timer has stopped
    {"row":   {...}}   a measured value (also ends a step)
    {"result": {...}}  a diagnostic result
The parent kills the child when a step runs longer than the time limit, and
when nothing arrives for SETUP_LIMIT_S between steps (hang guard).
"""

import csv
import gc
import hashlib
import importlib
import json
import math
import os
import platform
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]                  # Assignment1/
sys.path.insert(0, str(ROOT / "03_code"))

from replay import load_events  # noqa: E402  (.jsonl / .jsonl.gz reader)

GENERATOR = ROOT / "00_instructions" / "generate_orders.py"
RESULTS = ROOT / "05_results"
BENCH = Path(__file__).resolve().parent

# ----- what is measured ------------------------------------------------------
VERSIONS = ["a", "b_sorted", "b_heap"]
SCENARIOS = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]
SIZES = [1_000, 10_000, 100_000]
SEEDS = [42, 43, 44]
LEVELS = 1000                    # generator default --levels
CONCENTRATED_LEVELS = 4          # queue concentration: buildup --levels 4 vs 1000
MILLION = {"scenario": "mixed", "events": 1_000_000, "seed": 43, "levels": LEVELS}
SALE_PCTS = [10, 100, 200]       # large liquidation: % of the book's bid quantity
CONCENTRATION_SALE_PCT = 100     # concentration: sell the whole bid side

# ----- limits and repeats ----------------------------------------------------
TIME_LIMIT_S = 120.0     # per single replay (one warm-up or one timed repeat)
SETUP_LIMIT_S = 900.0    # hang guard for loading, parsing and checks between replays
GRACE_S = 2.0            # pipe-latency allowance before the parent kills a child
WARMUPS = 1              # repeat 0 = warm-up (recorded, excluded from medians)
REPEATS = 5              # repeats 1..5 are timed

GC_POLICY = ("Same for every version: gc.collect() right before each timed step, "
             "gc.disable() while it runs, gc.enable() right after. Applies to "
             "parse, replay, build, sell, latency and memory steps.")
PERCENTILE_CONVENTION = ("nearest-rank: sort the n values x_1 <= ... <= x_n; the "
                         "p-th percentile is x_k with k = ceil(p/100 * n), k >= 1 "
                         "(so p0 = min, p100 = max; no interpolation)")

DEFINITIONS = {
    "elapsed_seconds": "time.perf_counter() difference around the measured step only, in seconds",
    "phase parse": "gzip decompression + JSON parsing of the whole file into a list of dicts "
                   "(03_code/replay.py load_events); one measurement per child process",
    "phase replay": "a fresh empty book, then process_event for every preloaded event in file "
                    "order; fills are counted on the fly (len of each result's fill list); "
                    "results are not stored (no history). Creating the empty book and "
                    "freeing the previous one are outside the timer",
    "phase build": "a fresh empty book, then process_event for the build prefix: sweep = first "
                   "80% of the file (LIMIT events only, they never cross), buildup = the whole file",
    "phase sell": "one process_event(MARKET_SELL) on the book just built: validation, matching, "
                  "state updates and fill-list construction. Every repeat builds a new book, so "
                  "no sale reuses a depleted book",
    "requested_qty_units": "max(1, ceil(bid_qty * pct / 100)), integer arithmetic",
    "warm-up": f"repeat 0 ({WARMUPS} warm-up) is recorded with warmup=True and excluded from "
               "medians; repeats 1..5 are timed",
    "summary": "median, min and max over the 5 timed repeats; spread_pct = (max - min) / median",
    "throughput_events_per_s": "events / median replay (or build) seconds",
    "time_limit": f"{TIME_LIMIT_S:g} s per single replay, build or sell (warm-up included). A "
                  "step that runs longer is stopped (child killed) and recorded as "
                  "'stopped'; the cell's remaining repeats are skipped and recorded as "
                  "'stopped' too. Missing values are never estimated. A stopped build stops "
                  "every sale size of that book, because the builds are identical",
    "gc_policy": GC_POLICY,
    "peaks": "peak_active_orders / peak_price_levels are properties of the dataset, from a "
             "separate counting pass on B-sorted outside timing (all versions agree: "
             "differential tests). Build rows and sell rows show the built book's "
             "active orders and occupied levels",
    "correctness per replay": "after every timed replay (outside the timer) the fill count and "
                              "the final book size are compared with the dataset manifest; "
                              "a difference gives status 'mismatch'",
    "latency": "separate instrumentation run: perf_counter_ns() around each process_event "
               "call (the discarded result is freed inside the window), after one untimed "
               "warm-up replay. Algorithm processing latency "
               "only: no queueing or network latency, and no real-time capacity claim. Never "
               "derived from 1/throughput. Includes one timer call (timer_overhead_ns)",
    "latency event types": "every timed event has exactly one type, from the event and its "
               "result: LIMIT resting (no fill, the whole order rests), LIMIT traded (at "
               "least one fill, also if a residual rests), MARKET_SELL, CANCEL found "
               "(cancelled), CANCEL not_found, rejected. The types are recorded in the "
               "warm-up replay of the same events, so the timed loop is unchanged; the "
               "final books of both replays and the counts per type (against the dataset "
               "manifest) are checked. Count 0 = the type does not occur in that file. "
               "With fewer than 100 events of a type, p99 (nearest rank) equals the max",
    "percentile": PERCENTILE_CONVENTION,
    "memory": "separate tracemalloc run in its own child process. Events are preloaded BEFORE "
              "tracemalloc.start(), so the input is excluded. Included: the book (orders, "
              "levels, FIFO queues, price index) and the returned output (result dict and "
              "fill list) of the current event, which stays referenced while the sample is "
              "read and is released before the next event. Every sample in "
              "memory_samples.csv therefore holds the book plus one event's output. "
              "Validation temporaries are in the peak only. No history is saved. "
              "traced_peak_bytes = maximum during the replay, with the current event's "
              "output; traced_with_output_bytes = after the last event, its output still "
              "referenced; traced_current_bytes = after that output is released: the book, "
              "still alive. Released dicts and lists can stay in CPython's free lists, which "
              "tracemalloc still counts, so after an event with few or no fills the two end "
              "values can be equal",
    "traced vs auxiliary vs process memory": "Traced bytes are the Python allocations seen by "
              "tracemalloc while tracing (object sizes incl. headers and container "
              "over-allocation). Auxiliary space is the algorithm's extra space as a count "
              "(O(B) orders + O(P) levels + index entries, incl. stale entries), independent "
              "of byte sizes. Process memory (peak working set / max RSS) also holds the "
              "interpreter, modules, the preloaded events, allocator caches and memory not "
              "returned to the OS; recorded once per memory child as process_peak_bytes, "
              "for context only",
    "operation counts": "separate diagnostic run with counting subclasses (not timed): orders "
                        "scanned per event in A; best-price calls, stale heap pops, levels "
                        "created/removed, queue pops, compactions in B",
}


class Config:
    """What one run measures. --smoke keeps M = 1,000 only."""

    def __init__(self, smoke=False, out=None, time_limit=TIME_LIMIT_S):
        self.smoke = smoke
        self.out = Path(out).resolve() if out else (RESULTS / "smoke" if smoke else RESULTS)
        self.data = self.out / "data" / "bench"
        self.time_limit = float(time_limit)
        self.sizes = [1_000] if smoke else SIZES
        self.seeds = SEEDS
        self.million = None if smoke else MILLION
        small = 1_000 if smoke else 10_000
        self.latency_cells = [(s, small) for s in SCENARIOS]
        if not smoke:
            self.latency_cells.append(("buildup", 100_000))   # long burst
        self.memory_sizes = [1_000] if smoke else [10_000, 100_000]
        self.opcount_sizes = [1_000] if smoke else [1_000, 10_000]
        self.diag_seed = 42            # latency, memory and operation counts

    @property
    def results_csv(self):
        return self.out / "benchmark_results.csv"

    def describe(self):
        return {
            "mode": "smoke" if self.smoke else "full",
            "output_dir": rel(self.out),
            "data_dir": rel(self.data),
            "versions": VERSIONS, "scenarios": SCENARIOS, "sizes": self.sizes,
            "seeds": self.seeds, "levels": LEVELS,
            "concentrated_levels": CONCENTRATED_LEVELS,
            "million": self.million, "sale_pcts": SALE_PCTS,
            "concentration_sale_pct": CONCENTRATION_SALE_PCT,
            "time_limit_s_per_replay": self.time_limit,
            "setup_limit_s": SETUP_LIMIT_S, "grace_s": GRACE_S,
            "warmups": WARMUPS, "repeats": REPEATS,
            "gc_policy": GC_POLICY, "percentile_convention": PERCENTILE_CONVENTION,
            "latency_cells": [{"scenario": s, "events": m, "seed": self.diag_seed}
                              for s, m in self.latency_cells],
            "memory_sizes": self.memory_sizes, "opcount_sizes": self.opcount_sizes,
            "diagnostic_seed": self.diag_seed,
        }


# ----- small helpers ---------------------------------------------------------

def rel(path):
    """Path relative to Assignment1/ (never an absolute home path in outputs)."""
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).name


def redact(text):
    """Remove the repository location and the home folder from saved text."""
    for old, new in ((str(ROOT), "<Assignment1>"), (ROOT.as_posix(), "<Assignment1>"),
                     (str(Path.home()), "<home>"), (Path.home().as_posix(), "<home>")):
        text = text.replace(old, new)
    return text


def dataset_name(scenario, events, seed, levels):
    return f"{scenario}_M{events}_seed{seed}_L{levels}"


def book_class(version):
    return importlib.import_module(f"lob_{version}").OrderBook


def requested_qty(pct, total):
    return max(1, -(-total * pct // 100))       # integer ceil, at least 1 unit


def rotated(items, i):
    """Rotate the version order per cell, so no version always runs first."""
    k = i % len(items)
    return items[k:] + items[:k]


def nearest_rank(sorted_values, p):
    n = len(sorted_values)
    k = max(1, math.ceil(p / 100 * n))
    return sorted_values[min(k, n) - 1]


def load_timed(path):
    """Load and parse one event file; returns (events, seconds)."""
    gc.collect()
    gc.disable()
    try:
        start = time.perf_counter()
        events = load_events(path)
        seconds = time.perf_counter() - start
    finally:
        gc.enable()
    return events, seconds


def emit(**message):
    print(json.dumps(message), flush=True)


# ----- CSV ------------------------------------------------------------------

def read_rows(path):
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_rows(path, fields, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def append_rows(path, fields, rows):
    """Append rows (progress survives an interruption); header on first write."""
    path = Path(path)
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh), None)
        if header != fields:
            raise RuntimeError(f"{rel(path)} has a different header; delete it first")
    else:
        write_rows(path, fields, [])
    with path.open("a", newline="", encoding="utf-8") as fh:
        csv.DictWriter(fh, fieldnames=fields).writerows(rows)


def drop_rows(path, fields, drop):
    """Rewrite path without the rows for which drop(row) is true (a phase rerun)."""
    rows = read_rows(path)
    if rows or Path(path).exists():
        write_rows(path, fields, [r for r in rows if not drop(r)])


def read_manifest(cfg):
    rows = read_rows(cfg.out / "benchmark_datasets.csv")
    if not rows:
        raise RuntimeError("no dataset manifest: run the data phase first")
    for r in rows:
        for k, v in r.items():
            if v.lstrip("-").isdigit():
                r[k] = int(v)
    return rows


# ----- child processes ---------------------------------------------------------

def run_child(script, args, time_limit, on_message):
    """Run `python 04_benchmarks/<script> --child <args>` under the limits.

    on_message(msg) is called for every message except "start"; if it returns
    a step key (or True) the child is killed: that step finished above the limit.
    Returns None when the child finished, else a dict
    {"reason": "limit" | "over_limit" | "setup", "step": [...] or None}.
    """
    cmd = [sys.executable, str(BENCH / script), "--child", *map(str, args)]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8")
    lines = queue.Queue()
    errors = []

    def pump_stdout():
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    def pump_stderr():
        for line in proc.stderr:
            errors.append(line)

    threading.Thread(target=pump_stdout, daemon=True).start()
    threading.Thread(target=pump_stderr, daemon=True).start()

    step = None
    deadline = time.monotonic() + SETUP_LIMIT_S
    stopped = None
    while True:
        try:
            line = lines.get(timeout=max(0.0, deadline - time.monotonic()))
        except queue.Empty:
            stopped = {"reason": "limit" if step else "setup", "step": step}
            break
        if line is None:
            break
        message = json.loads(line)
        if "start" in message:
            step = message["start"]
            deadline = time.monotonic() + time_limit + GRACE_S
            continue
        step = None
        deadline = time.monotonic() + SETUP_LIMIT_S
        over = on_message(message)
        if over:
            stopped = {"reason": "over_limit", "step": None if over is True else list(over)}
            break
    if stopped:
        proc.kill()
        proc.wait()
        return stopped
    if proc.wait() != 0:
        raise RuntimeError(f"child failed: {script} {' '.join(map(str, args))}\n"
                           + redact("".join(errors)[-3000:]))
    return None


def step_label(step):
    """["build", 10, 0] -> "build 10% repeat 0"; ["latency"] -> "latency"."""
    if len(step) == 3:
        phase, pct, r = step
        return f"{phase}{f' {pct}%' if pct != '' else ''} repeat {r}"
    return " ".join(str(x) for x in step)


def stop_note(stopped, key, time_limit):
    """Note for a measurement that was not taken because of a stop."""
    if stopped["reason"] == "setup":
        return f"stopped: no progress for {SETUP_LIMIT_S:g} s (hang guard); not measured"
    if stopped["step"] is not None and list(key) == list(stopped["step"]):
        return f"stopped: exceeded the {time_limit:g} s limit; not measured"
    what = step_label(stopped["step"]) if stopped["step"] else "an earlier step"
    return f"stopped: skipped after {what} was stopped"


# ----- provenance ------------------------------------------------------------

CODE_PATHS = ["02_tests", "03_code", "04_benchmarks", "00_instructions/generate_orders.py",
              "pytest.ini", "requirements.txt"]
FINGERPRINT_GLOBS = ["02_tests/*.py", "03_code/*.py", "04_benchmarks/*.py",
                     "00_instructions/generate_orders.py", "pytest.ini", "requirements.txt"]


def _git(*args):
    try:
        done = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8")
    except OSError:
        return None
    return done.stdout.rstrip() if done.returncode == 0 else None


def git_info():
    commit = _git("rev-parse", "HEAD")
    if commit is None:
        return {"commit": None, "branch": None, "code_clean": None, "tree_clean": None}
    code = _git("status", "--porcelain", "--", *CODE_PATHS) or ""
    tree = _git("status", "--porcelain") or ""
    here = _git("status", "--porcelain", "--", ".") or ""
    return {
        "commit": commit,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "code_paths": CODE_PATHS,
        "code_clean": code == "",
        "dirty_code_files": [line[3:] for line in code.splitlines()],
        "tree_clean": tree == "",
        "dirty_files_in_assignment1": [line[3:] for line in here.splitlines()],
    }


def source_fingerprint():
    """sha256 over the code files (line endings normalised to LF)."""
    files = sorted({p for pattern in FINGERPRINT_GLOBS for p in ROOT.glob(pattern)})
    total = hashlib.sha256()
    per_file = {}
    for path in files:
        data = path.read_bytes().replace(b"\r\n", b"\n")
        name = rel(path)
        per_file[name] = hashlib.sha256(data).hexdigest()
        total.update(name.encode() + b"\0" + data + b"\0")
    return {"sha256": total.hexdigest(), "files": per_file}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _cpu_name():
    if sys.platform == "win32":
        try:
            import winreg
            key = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
                return winreg.QueryValueEx(k, "ProcessorNameString")[0].strip()
        except OSError:
            pass
    elif sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    elif sys.platform == "darwin":
        name = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                              capture_output=True, text=True).stdout.strip()
        if name:
            return name
    return platform.processor()


def _ram_bytes():
    if sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                       [(n, ctypes.c_ulonglong) for n in
                        ("total", "avail", "page_total", "page_avail", "virt_total",
                         "virt_avail", "ext_avail")]
        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.total
        return None
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def _on_ac_power():
    if sys.platform != "win32":
        return None
    import ctypes

    class PowerStatus(ctypes.Structure):
        _fields_ = [("ac", ctypes.c_ubyte), ("battery_flag", ctypes.c_ubyte),
                    ("battery_pct", ctypes.c_ubyte), ("system_flag", ctypes.c_ubyte),
                    ("life", ctypes.c_ulong), ("full_life", ctypes.c_ulong)]
    status = PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return None
    return {0: False, 1: True}.get(status.ac)


def process_peak_bytes():
    """Peak working set (Windows) or max RSS (POSIX) of this process, in bytes."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + \
                       [(n, ctypes.c_size_t) for n in
                        ("peak_ws", "ws", "peak_paged", "paged", "peak_nonpaged",
                         "nonpaged", "pagefile", "peak_pagefile")]
        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters),
                                               wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters),
                                      counters.cb):
            return counters.peak_ws
        return None
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def environment(cfg):
    from importlib import metadata

    packages = {}
    for name in ("pytest", "matplotlib"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    clock = time.get_clock_info("perf_counter")
    gen = {"script": rel(GENERATOR), "sha256": sha256_file(GENERATOR),
           "rng": "random.Random(seed)", "scenarios": SCENARIOS, "sizes": cfg.sizes,
           "seeds": cfg.seeds, "levels": LEVELS,
           "concentrated_levels": CONCENTRATED_LEVELS, "million": cfg.million,
           "command": "python 00_instructions/generate_orders.py --scenario <s> --events <M> "
                      "--levels <L> --seed <seed> --out <file>",
           "checksums": rel(cfg.out / "benchmark_datasets.csv")}
    return {
        "python": {"version": platform.python_version(),
                   "implementation": platform.python_implementation(),
                   "compiler": platform.python_compiler(),
                   "build": list(platform.python_build())},
        "packages": packages,
        "engine_dependencies": "standard library only",
        "os": {"system": platform.system(), "release": platform.release(),
               "version": platform.version(), "platform": platform.platform()},
        "machine": {"architecture": platform.machine(), "cpu": _cpu_name(),
                    "logical_cpus": os.cpu_count(), "ram_bytes": _ram_bytes(),
                    "on_ac_power": _on_ac_power()},
        "perf_counter": {"implementation": clock.implementation,
                         "resolution_s": clock.resolution, "monotonic": clock.monotonic},
        "git": git_info(),
        "source_fingerprint": source_fingerprint()["sha256"],
        "generator": gen,
    }
