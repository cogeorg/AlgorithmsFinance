"""Shared run conditions for the Phase 6b instrumented runs (same as timing run 2, README).

`stamp()`: start time (UTC) and power state, written on every result row.
`canary_around(block)`: runs the canary (B, mixed, 100,000 events, seed 42, warm-up + 5 repeats;
results/canary_raw.csv) before and after a block of runs. If the two medians differ clearly, the
runs in between were taken on a machine in a different state and are repeated.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime

from bench import bench_time, common


def stamp() -> dict:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    return {"start_utc": now, **common.power_state()}


@contextlib.contextmanager
def canary_around(block: str):
    args = argparse.Namespace(limit_seconds=common.LIMIT_SECONDS,
                              slow_first_seconds=common.SLOW_FIRST_SECONDS,
                              repeats=common.TIMED_REPEATS)
    bench_time.canary(block, "before", args)
    yield
    bench_time.canary(block, "after", args)
