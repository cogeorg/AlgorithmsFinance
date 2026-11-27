"""Memory with `tracemalloc`, in a separate run (never during primary timing).

What is counted: Python allocations made while tracing is on, i.e. the book structures, the result
dicts and fill lists while they are alive (they are discarded right after each event), and
temporary objects of the engine. Not counted: the preloaded event list (loaded BEFORE tracing
starts), the interpreter, native memory outside Python's allocator, allocator slack. No trade
history is kept (SPEC D16), so "saved history" is zero by design. tracemalloc slows replay
(several times) and its numbers are not total process memory or auxiliary space.

Runs per version: every stream of 10,000 and 100,000 events (seed 42) plus two stress streams that
are built in memory: `insert_then_cancel` (N non-crossing orders, then N-1 cancels in order;
shows growth while inserting and what stays after the cancellations).
For each run: bytes held after each 10% of the events, bytes held at the end, peak bytes.
A at 100,000 events only if its timing run took less than 60 s.

    .venv/bin/python -m bench.bench_memory
"""
from __future__ import annotations

import argparse
import gc
import itertools
import json
import tracemalloc

import generate_orders
from bench import common
from bench.blocks import canary_around, stamp
from bench.common import RESULTS, append_csv, read_csv, stream_path
from bench.bench_counts import allowed
from bench.harness import run_limited
from lob import VERSIONS
from lob.common import load_events

OUT = RESULTS / "memory.csv"
FIELDS = ["start_utc", "power_source", "battery_percent", "low_power_mode", "version", "scenario", "seed", "events", "status", "reason", "final_bytes", "peak_bytes",
          "bytes_after_insertion", "checkpoints_bytes", "active_orders_end"]
STRESS = "insert_then_cancel"


def stress_events(n: int) -> list[dict]:
    """n non-crossing LIMIT orders (buildup stream, both sides), then cancels of all but the last."""
    rows = [r for r in itertools.islice(generate_orders.events("buildup", n, 42, 1000), n)]
    seq = n
    for row in rows[:-1]:
        seq += 1
        rows_cancel = {"seq": seq, "event_id": f"c{seq}", "type": "CANCEL",
                       "target_order_id": row["order_id"]}
        rows.append(rows_cancel)
    return rows


def _replay_memory(cls, events, insert_count):
    book = cls()
    process = book.process
    n = len(events)
    step = max(1, n // 10)
    marks, after_insert = [], None
    gc.collect()
    tracemalloc.start()
    base = tracemalloc.get_traced_memory()[0]
    tracemalloc.reset_peak()
    for i, e in enumerate(events):
        process(e)
        if (i + 1) % step == 0:
            marks.append(tracemalloc.get_traced_memory()[0] - base)
        if i + 1 == insert_count:
            after_insert = tracemalloc.get_traced_memory()[0] - base
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return book, {"final_bytes": current - base, "peak_bytes": peak - base,
                  "bytes_after_insertion": after_insert, "checkpoints_bytes": marks}


def memory_worker(conn, version: str, scenario: str, events_n: int) -> None:
    if scenario == STRESS:
        events = stress_events(events_n)
        insert_count = events_n
    else:
        events = load_events(stream_path(scenario, events_n, 42))
        insert_count = 0
    conn.send(("unit_start", "memory"))
    book, payload = _replay_memory(VERSIONS[version], events, insert_count)
    payload["active_orders_end"] = len(book.snapshot())
    conn.send(("unit_done", "memory", payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--sizes", nargs="+", type=int, default=[10000, 100000])
    parser.add_argument("--limit-seconds", type=float, default=common.LIMIT_SECONDS)
    args = parser.parse_args(argv)
    done = {(r["version"], r["scenario"], r["events"]) for r in read_csv(OUT)}
    for events in args.sizes:
        todo = [(v, sc) for sc in (*common.SCENARIOS, STRESS) for v in ("A", "B")
                if (v, sc, str(events)) not in done]
        if not todo:
            continue
        with canary_around(f"memory_{events}"):
            for version, scenario in todo:
                base = {"version": version, "scenario": scenario, "seed": 42, "events": events}
                reason = allowed(version, scenario, events) if scenario != STRESS else (
                    None if version == "B" or events <= 10000 else
                    allowed(version, "buildup", events))
                if reason:
                    append_csv(OUT, FIELDS, {**stamp(), **base, "status": "not_run",
                                             "reason": reason})
                    print(version, scenario, events, "not_run:", reason, flush=True)
                    continue
                st0 = stamp()
                res = run_limited(memory_worker, (version, scenario, events), args.limit_seconds)
                msgs = [m for m in res["messages"] if m[0] == "unit_done"]
                if res["outcome"] == "end" and msgs:
                    p = msgs[0][2]
                    append_csv(OUT, FIELDS, {**st0, **base, "status": "ok", **p,
                                             "checkpoints_bytes": json.dumps(p["checkpoints_bytes"])})
                else:
                    append_csv(OUT, FIELDS, {**st0, **base, "status": res["outcome"],
                                             "reason": res["error"] or
                                             f"limit reached; events done {res['events_done']}"})
                print(version, scenario, events, res["outcome"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
