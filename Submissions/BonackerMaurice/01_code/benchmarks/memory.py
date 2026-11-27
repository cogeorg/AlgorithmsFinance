"""Memory phase with tracemalloc, run in its own process after timing.

Usage (normally called by benchmarks.run):  python -m benchmarks.memory <run_dir>
What is included and excluded: see DEFINITIONS["memory"] in benchmarks/config.py.
"""
import csv
import gc
import sys
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

from datagen.generator import generate
from search_algos import METHODS, Method

from .config import load_run_config, update_run_config, write_csv


def trace_one(method, ids, queries) -> dict:
    """Fresh tracing run for one method; the input already exists before tracing starts."""
    gc.collect()
    tracemalloc.start()
    try:
        state = method.prepare(ids)
        prepare_current, prepare_peak = tracemalloc.get_traced_memory()
        output = method.query(state, queries)  # state and output stay alive while reading
        total_current, total_peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    del state, output
    return {"prepare_current_bytes": prepare_current, "prepare_peak_bytes": prepare_peak,
            "total_current_bytes": total_current, "total_peak_bytes": total_peak}


def baseline() -> dict:
    """What trace_one reports for a method that allocates nothing (harness bytes)."""
    noop = Method("noop", "v0", "only", "No-op", "", lambda ids: None, lambda state, qs: None)
    return trace_one(noop, [], [])


def run(run_dir) -> None:
    run_dir = Path(run_dir)
    _, grid = load_run_config(run_dir)
    expected = {}  # checksums from the timing phase: memory must see identical inputs
    if (run_dir / "datasets.csv").exists():
        with open(run_dir / "datasets.csv", newline="") as f:
            expected = {row["dataset_id"]: row for row in csv.DictReader(f)}
    rows = []
    for spec in grid.specs():
        ds = generate(spec)
        row = expected.get(spec.dataset_id)
        if row and (row["array_sha256"], row["queries_sha256"]) != (ds.ids_sha256,
                                                                    ds.queries_sha256):
            raise AssertionError(f"{spec.dataset_id}: input differs from the timing phase")
        for m in METHODS:
            rows.append({"dataset_id": spec.dataset_id, "n": spec.n, "q": spec.q,
                         "scenario": spec.scenario, "method": m.method, "version": m.version,
                         **trace_one(m, ds.ids, ds.queries)})
        print(f"memory  {spec.dataset_id:<24} done", flush=True)
    write_csv(run_dir / "memory.csv", rows)
    update_run_config(run_dir, memory_baseline=baseline(), phases={"memory": {
        "status": "done", "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": len(rows)}})


if __name__ == "__main__":
    run(sys.argv[1])
