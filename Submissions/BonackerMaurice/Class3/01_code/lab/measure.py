"""Measurement helpers: environment, one pricing call in a fresh process, memory sampling.

Seconds: time.perf_counter around one pricing call (no tracemalloc running).
Traced peak: tracemalloc peak of a second, identical call (NumPy reports its buffers
to tracemalloc). Process peak: psutil peak working set of the process (Windows) minus
the working set just before the call, i.e. includes interpreter-level overhead.
"""
import hashlib
import json
import os
import platform
import subprocess
import sys
import threading
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import psutil

from american_put import fulltree, reference, vectorised

PRICERS = {
    "reference": reference.price_american_put,   # pure Python, O(N) memory
    "vectorised": vectorised.price_american_put, # NumPy, O(N) memory
    "fulltree": fulltree.price_american_put,     # NumPy, O(N^2) memory (stores every node)
}

CODE_DIR = Path(__file__).resolve().parents[1]
GB = 1024**3
MB = 1024**2


def ram_available_bytes():
    return psutil.virtual_memory().available


def peak_process_bytes(proc=None):
    """Peak working set on Windows (peak_wset); falls back to current RSS elsewhere."""
    info = (proc or psutil.Process()).memory_info()
    return getattr(info, "peak_wset", info.rss)


def boundary_sha256(boundary):
    text = ",".join("" if b is None else repr(b) for b in boundary)
    return hashlib.sha256(text.encode()).hexdigest()


def git_info():
    def run(*args):
        try:
            return subprocess.run(["git", *args], cwd=CODE_DIR, capture_output=True, text=True,
                                  check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    status = run("status", "--porcelain", "--", str(CODE_DIR))
    return {
        "commit": run("rev-parse", "HEAD"),
        "branch": run("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": None if status is None else bool(status),
    }


def environment():
    vm = psutil.virtual_memory()
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
        "ram_total_gb": round(vm.total / GB, 2),
        "ram_available_gb_at_start": round(vm.available / GB, 2),
        "packages": {"numpy": np.__version__, "psutil": psutil.__version__},
        "git": git_info(),
    }


def run_cell(pricer_name, S0, K, u, d, R, N, traced=True):
    """One measurement. Meant to run in a fresh worker process (see measure_in_fresh_process)."""
    pricer = PRICERS[pricer_name]
    before = psutil.Process().memory_info().rss
    start = time.perf_counter()
    result = pricer(S0, K, u, d, R, N)
    seconds = time.perf_counter() - start
    process_peak = peak_process_bytes() - before
    out = {
        "seconds": seconds,
        "process_peak_mb": process_peak / MB,
        "value": result.value,
        "boundary_sha256": boundary_sha256(result.boundary),
        "traced_peak_mb": None,
    }
    del result
    if traced:
        tracemalloc.start()
        pricer(S0, K, u, d, R, N)
        out["traced_peak_mb"] = tracemalloc.get_traced_memory()[1] / MB
        tracemalloc.stop()
    return out


def measure_in_fresh_process(pricer_name, params, traced=True):
    """Run run_cell in a new process, so peak memory is not inherited from earlier cells."""
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(max_workers=1) as pool:
        return pool.submit(run_cell, pricer_name, *params, traced=traced).result()


class MemorySampler:
    """Background thread: samples the summed RSS of this process and all its children.

    Gives the peak total memory actually in use at one moment during a parallel run.
    """

    def __init__(self, interval=0.1):
        self.interval = interval
        self.peak = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        me = psutil.Process()
        while not self._stop.is_set():
            total = 0
            for p in [me, *me.children(recursive=True)]:
                try:
                    total += p.memory_info().rss
                except psutil.Error:
                    pass
            self.peak = max(self.peak, total)
            time.sleep(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, default=str) + "\n")


def pid():
    return os.getpid()
