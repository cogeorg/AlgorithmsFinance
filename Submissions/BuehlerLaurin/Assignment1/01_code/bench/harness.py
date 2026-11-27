"""Reusable benchmark harness for Algorithms in Finance exercises (standard library only).

The scaffold copies this file to `01_code/bench/harness.py`; import it (01_code is on sys.path via
pytest.ini or `python run.py ...`):

    from bench.harness import (new_run_dir, env_info, time_repeats, latency_ns, percentiles,
                               peak_traced_bytes, traced_curve, append_rows, run_with_timeout)

Conventions (course rules):
- one untimed warm-up, then 5 timed repeats; keep every raw repeat and report the median
- a fresh state from `setup()` for every repeat, built outside the timed region
- prep / run / total reported separately, in seconds
- latency = per-call service time from a closed-loop replay (not response time under load)
- percentiles use the nearest-rank convention: rank = ceil(p/100 * N), 1-based
- memory measured with tracemalloc in a separate run, never together with timing
"""
from __future__ import annotations

import csv
import gc
import math
import os
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence


def env_info(packages: Sequence[str] = ("pytest", "hypothesis", "numpy", "streamlit", "pandas")) -> dict:
    """Machine, Python, package versions and code version (read-only git)."""
    def git(*args: str) -> str:
        try:
            return subprocess.run(["git", *args], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=10).stdout.strip()
        except Exception:
            return ""
    versions = {}
    for p in packages:
        try:
            versions[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            versions[p] = None
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "packages": versions,
        "git_commit": git("rev-parse", "--verify", "-q", "HEAD"),
        "git_dirty": bool(git("status", "--porcelain")),
        "gc_enabled_at_env_capture": gc.isenabled(),
    }


def new_run_dir(base: str | Path = "03_results/runs", tag: str = "") -> Path:
    """Create 03_results/runs/<UTC stamp>_<commit7>[-dirty][_tag]/ with env.json inside.

    One folder per run keeps official grids, quick exploratory runs and their
    test output apart, and ties every number to a code version.
    """
    import json
    env = env_info()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}_{(env['git_commit'] or 'nogit')[:7]}{'-dirty' if env['git_dirty'] else ''}"
    d = Path(base) / (f"{name}_{tag}" if tag else name)
    d.mkdir(parents=True, exist_ok=False)
    (d / "env.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    return d


def time_repeats(setup: Callable[[], Any], run: Callable[[Any], Any], *,
                 repeats: int = 5, warmup: int = 1, inner: int = 1,
                 check: Callable[[Any], None] | None = None,
                 disable_gc: bool = False) -> dict:
    """Time `run(state)` on a fresh `state = setup()` per repeat.

    `setup` (e.g. building a fresh book or copying pre-generated events) is timed
    separately as `prep_s`. `inner` > 1 batches very short calls: each call gets its
    own fresh state; the reported values are per call. `check(result)` runs on EVERY
    result (warm-up and all inner calls), each time after the clock has been read, so no
    incorrect result escapes validation and checking never enters the timed region.
    `disable_gc=True` switches the garbage collector off around each timed call (state
    it in the report; run both settings if GC pauses matter).
    """
    perf = time.perf_counter
    gc_was = gc.isenabled()
    prep, runs = [], []
    for i in range(warmup + repeats):
        p_total = r_total = 0.0
        for _ in range(inner):
            t0 = perf(); state = setup(); t1 = perf()
            if disable_gc:
                gc.disable()
            try:
                result = run(state); t2 = perf()
            finally:
                if disable_gc and gc_was:
                    gc.enable()
            p_total += t1 - t0; r_total += t2 - t1
            if check is not None:
                check(result)          # clock already read: validation is not timed
        if i >= warmup:
            prep.append(p_total / inner); runs.append(r_total / inner)
    total = [a + b for a, b in zip(prep, runs)]
    return {
        "prep_s": prep, "run_s": runs, "total_s": total, "inner": inner, "gc_disabled": disable_gc,
        "prep_median_s": statistics.median(prep),
        "run_median_s": statistics.median(runs),
        "total_median_s": statistics.median(total),
    }


def latency_ns(process: Callable[[Any, Any], Any], state: Any, items: Iterable[Any]) -> list[int]:
    """Per-item service time in nanoseconds for `process(state, item)` (instrumentation run only)."""
    clock = time.perf_counter_ns
    out: list[int] = []
    append = out.append
    for item in items:
        t0 = clock(); process(state, item); append(clock() - t0)
    return out


def percentiles(samples: Sequence[float], ps: Sequence[float] = (50, 95, 99)) -> dict:
    """Nearest-rank percentiles plus min/max/n. Pool raw samples; never average percentiles."""
    if not samples:
        return {"n": 0}
    s = sorted(samples)
    n = len(s)
    out = {f"p{g:g}": s[max(1, math.ceil(g / 100 * n)) - 1] for g in ps}
    out.update(n=n, min=s[0], max=s[-1])
    return out


def peak_traced_bytes(setup: Callable[[], Any], run: Callable[[Any], Any], *,
                      include_setup: bool = False) -> dict:
    """tracemalloc current/peak for one run. The returned result is kept alive while measuring."""
    state = None
    if not include_setup:
        state = setup()
    gc.collect()
    tracemalloc.start()
    try:
        if include_setup:
            state = setup()
        result = run(state)
        current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    del result
    return {"current_bytes": current, "peak_bytes": peak, "includes_setup": include_setup}


def traced_curve(process: Callable[[Any, Any], Any], state: Any, items: Sequence[Any], *,
                 every: int = 1000, setup: Callable[[], Any] | None = None,
                 observe: Callable[[Any], tuple] | None = None) -> list[dict]:
    """Memory over time: traced *current* bytes retained by the state at checkpoints.

    Measurement boundary (state it in the report):
    - Input items are preloaded before tracing starts: input storage is not counted.
    - Returned outputs are discarded after each call: only what the structure *keeps*
      is counted. Measure output allocation separately with `peak_traced_bytes`.
    - The samples themselves are written into an array preallocated before tracing,
      so the measurement does not measure its own bookkeeping (a no-op process stays flat).
    - Initial state: with `state` passed in, anything allocated before tracing is NOT
      counted and the curve shows growth relative to the starting state. Pass
      `setup=<callable>` (and state=None) to build the state under tracing; the first
      row (processed=0) then contains the initial state's size.
    """
    from array import array
    if setup is not None and state is not None:
        raise ValueError("pass either state or setup, not both")
    n = len(items)
    n_samples = n // every + 2                    # checkpoints + processed=0 + final
    buf = array("q", bytes(8 * 3 * n_samples))    # (processed, current, peak) per sample
    stats = array("q", bytes(8 * 4 * n_samples)) if observe is not None else None
    gc.collect()
    tracemalloc.start()
    k = 0
    try:
        if setup is not None:
            state = setup()
        cur, peak = tracemalloc.get_traced_memory()
        buf[0], buf[1], buf[2] = 0, cur, peak; k = 1
        if stats is not None:
            stats[0:4] = array("q", observe(state))
        i = 0
        for item in items:
            process(state, item)
            i += 1
            if i % every == 0 or i == n:
                cur, peak = tracemalloc.get_traced_memory()
                j = 3 * k
                buf[j], buf[j + 1], buf[j + 2] = i, cur, peak; k += 1
                if stats is not None:
                    j = 4 * (k - 1)
                    stats[j:j+4] = array("q", observe(state))
    finally:
        tracemalloc.stop()
    out = [{"processed": buf[3 * j], "current_bytes": buf[3 * j + 1], "peak_bytes": buf[3 * j + 2],
            "includes_initial_state": setup is not None} for j in range(k)]
    if stats is not None:
        for j, row in enumerate(out):
            row.update(zip(("live_orders", "price_levels", "heap_entries", "stale_heap_prices"), stats[4*j:4*j+4]))
    return out


TIMING_KEY = ("version", "workload", "seed", "size", "phase", "repeat")


def append_rows(path: str | Path, rows: Iterable[dict], *, unique_by: Sequence[str] | None = None) -> None:
    """Append dict rows to a CSV, writing the header on first use. Columns = union of keys.

    `unique_by` (e.g. TIMING_KEY for timing.csv) refuses a row whose key already exists in
    the file or earlier in the same batch, so a re-run cannot silently add duplicate repeats.
    """
    rows = list(rows)
    if not rows:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    new = not path.exists()
    if unique_by:
        seen = set()
        if not new:
            with path.open(newline="", encoding="utf-8") as f:
                seen = {tuple(str(r.get(k, "")) for k in unique_by) for r in csv.DictReader(f)}
        for r in rows:
            key = tuple(str(r.get(k, "")) for k in unique_by)
            if key in seen:
                raise ValueError(f"{path}: duplicate row for {dict(zip(unique_by, key))}; "
                                 "use a new run folder (new_run_dir) instead of appending again")
            seen.add(key)
    if not new:
        with path.open(newline="", encoding="utf-8") as f:
            existing = next(csv.reader(f), [])
        fields = existing + [k for k in fields if k not in existing]
        if fields != existing:
            raise ValueError(f"{path}: new columns {set(fields) - set(existing)}; write to a new file")
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def run_with_timeout(cmd: Sequence[str], timeout_s: float, *, phase_protocol: bool = False) -> dict:
    """Run one benchmark cell as a subprocess with a declared time limit (Windows-safe).

    A run that hits the limit is reported as status 'stopped', never silently dropped.
    """
    if phase_protocol:
        from bench.guard import run_phased
        return run_phased(cmd, timeout_s)
    t0 = time.perf_counter()
    try:
        cp = subprocess.run(list(cmd), capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout_s)
        status = "ok" if cp.returncode == 0 else f"error({cp.returncode})"
        tail = (cp.stdout + cp.stderr)[-2000:]
    except subprocess.TimeoutExpired:
        status, tail = "stopped", f"exceeded declared limit of {timeout_s}s"
    return {"status": status, "wall_s": time.perf_counter() - t0, "limit_s": timeout_s,
            "cmd": " ".join(cmd), "log_tail": tail}


if __name__ == "__main__":  # self-check
    import json
    r = time_repeats(lambda: list(range(10_000)), lambda xs: sorted(xs, reverse=True),
                     check=lambda out: None)
    print(json.dumps({k: v for k, v in r.items() if k.endswith("median_s")}, indent=1))
    print(percentiles(latency_ns(lambda st, x: st.append(x), [], range(10_000))))
    print(peak_traced_bytes(lambda: None, lambda _: [0] * 100_000))
    print(traced_curve(lambda st, x: st.append([x]), None, list(range(3000)), every=1000, setup=list))
    flat = traced_curve(lambda st, x: None, None, list(range(10_000)), every=1)
    print("no-op process, every=1: first", flat[1]["current_bytes"], "last", flat[-1]["current_bytes"], "bytes")
    print(json.dumps(env_info(), indent=1)[:300])
