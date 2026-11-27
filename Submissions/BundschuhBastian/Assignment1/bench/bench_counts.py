"""Operation counters: a separate, instrumented run (never part of the primary timings).

The engines are not modified. Their functions are wrapped while a stream is replayed:
  Version A (list scans)    scan_is_live, scan_best_index, scan_cancel = records examined
                            (comparisons); best_index_calls. Not counted: the C-level memmove of
                            list.pop(i), which also grows with B.
  Version B (price levels)  key_inserts / key_shift_elements (sorted price list: elements moved
                            by insort), key_deletes / key_delete_shift_elements, levels_dropped,
                            compactions / compaction_records_moved (lazy cancel, step 9).
  Both (from the results)   fills, makers_touched (= fills: a maker appears once per event),
                            levels_visited (distinct fill prices per event, summed).
Instrumented sizes (small M): 1,000 and 10,000 events for A and B (`--sizes` can add 100,000;
A there only when its timing run took less than 60 s). Every size is a block with a canary before
and after (bench.blocks); every row has start time and power state.

    .venv/bin/python -m bench.bench_counts
"""
from __future__ import annotations

import argparse
import collections
import contextlib
from bisect import bisect_left, bisect_right

from bench import common
from bench.blocks import canary_around, stamp
from bench.common import RESULTS, append_csv, read_csv, stream_path
from bench.harness import run_limited
from lob import VERSIONS
from lob.common import load_events

OUT = RESULTS / "counters.csv"
COUNTER_FIELDS = ["fills", "makers_touched", "levels_visited", "scan_is_live", "scan_best_index",
                  "best_index_calls", "scan_cancel", "key_inserts", "key_shift_elements",
                  "key_deletes", "key_delete_shift_elements", "levels_dropped", "compactions",
                  "compaction_records_moved"]
FIELDS = ["start_utc", "power_source", "battery_percent", "low_power_mode", "version", "scenario", "seed", "events", "levels", "status", "reason",
          "elapsed_seconds"] + COUNTER_FIELDS


@contextlib.contextmanager
def instrumented(version: str, counts: collections.Counter):
    """Wrap the engine of `version` so that it fills `counts`; undo on exit."""
    if version == "A":
        from lob import version_a as mod
        cls = mod.OrderBookA
        saved = (cls._is_live, cls._best_index, cls.CancelOrder)
        orig_best, orig_cancel = cls._best_index, cls.CancelOrder

        def is_live(self, order_id):
            for side in (self._bids, self._asks):
                for rec in side:
                    counts["scan_is_live"] += 1
                    if rec[mod.ID] == order_id:
                        return True
            return False

        def best_index(side, is_bid):
            counts["best_index_calls"] += 1
            counts["scan_best_index"] += max(0, len(side) - 1)
            return orig_best(side, is_bid)

        def cancel(self, event):
            target = event["target_order_id"]
            for side in (self._bids, self._asks):
                for rec in side:
                    counts["scan_cancel"] += 1
                    if rec[mod.ID] == target:
                        return orig_cancel(self, event)
            return orig_cancel(self, event)

        cls._is_live, cls._best_index, cls.CancelOrder = is_live, staticmethod(best_index), cancel
        try:
            yield
        finally:
            cls._is_live, cls.CancelOrder = saved[0], saved[2]
            cls._best_index = staticmethod(saved[1])      # it is a staticmethod in the engine
    else:
        from lob import version_b as mod
        side_cls = mod._Side
        saved_attrs = (mod.insort, mod.bisect_left, side_cls.__dict__["compact_if_needed"],
                       side_cls.drop_level)
        orig_compact = side_cls.compact_if_needed
        orig_drop = side_cls.drop_level

        def insort(keys, key):
            pos = bisect_right(keys, key)
            counts["key_inserts"] += 1
            counts["key_shift_elements"] += len(keys) - pos
            keys.insert(pos, key)

        def bisect_left_counted(keys, key):
            pos = bisect_left(keys, key)
            counts["key_deletes"] += 1
            counts["key_delete_shift_elements"] += len(keys) - pos - 1
            return pos

        def compact(level):
            dead = level[mod.DEAD]
            orig_compact(level)
            if dead and level[mod.DEAD] == 0:
                counts["compactions"] += 1
                counts["compaction_records_moved"] += len(level[mod.QUEUE])

        def drop(self, price):
            counts["levels_dropped"] += 1
            orig_drop(self, price)

        mod.insort, mod.bisect_left = insort, bisect_left_counted
        side_cls.compact_if_needed, side_cls.drop_level = staticmethod(compact), drop
        try:
            yield
        finally:
            mod.insort, mod.bisect_left = saved_attrs[0], saved_attrs[1]
            side_cls.compact_if_needed, side_cls.drop_level = saved_attrs[2], saved_attrs[3]


def _replay_counted(version: str, events: list[dict], instrument: bool) -> tuple[list[dict], dict]:
    """Replay with (or without) counters. Returns (all results, counters)."""
    counts: collections.Counter = collections.Counter()
    book = VERSIONS[version]()
    results = []
    context = instrumented(version, counts) if instrument else contextlib.nullcontext()
    with context:
        for e in events:
            r = book.process(e)
            results.append(r)
            fills = r["fills"]
            if fills:
                counts["fills"] += len(fills)
                counts["makers_touched"] += len(fills)
                counts["levels_visited"] += len({f["price_ticks"] for f in fills})
    return results, dict(counts)


def counters_worker(conn, version: str, path: str) -> None:
    events = load_events(path)
    conn.send(("unit_start", "counted"))
    import time
    start = time.perf_counter()
    _, counts = _replay_counted(version, events, True)
    conn.send(("unit_done", "counted", (counts, time.perf_counter() - start)))


def allowed(version: str, scenario: str, events: int) -> str | None:
    """None if this instrumented run may start, else the reason it is not run."""
    if version == "B" or events <= 10000:
        return None
    row = common.run_result(read_csv(RESULTS / "time_raw.csv"), "A", scenario, 42, events, 1000)
    if row is not None:
        if row["status"] == "ok" and float(row["median_seconds"]) < common.A_MILLION_THRESHOLD:
            return None
        return (f"A timing run at {events} events on {scenario}: status {row['status']}, "
                f"median {row['median_seconds'] or 'n/a'} s (needs < 60 s)")
    return f"A timing run at {events} events on {scenario} not recorded yet"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--sizes", nargs="+", type=int, default=[1000, 10000])
    parser.add_argument("--limit-seconds", type=float, default=common.LIMIT_SECONDS)
    args = parser.parse_args(argv)
    done = {(r["version"], r["scenario"], r["events"]) for r in read_csv(OUT)}
    for events in args.sizes:
        todo = [(v, sc) for sc in common.SCENARIOS for v in ("A", "B")
                if (v, sc, str(events)) not in done]
        if not todo:
            continue
        with canary_around(f"counts_{events}"):
            for version, scenario in todo:
                base = {"version": version, "scenario": scenario, "seed": 42, "events": events,
                        "levels": 1000}
                reason = allowed(version, scenario, events)
                if reason:
                    append_csv(OUT, FIELDS, {**stamp(), **base, "status": "not_run",
                                             "reason": reason})
                    print(version, scenario, events, "not_run:", reason, flush=True)
                    continue
                st0 = stamp()
                res = run_limited(counters_worker, (version, str(stream_path(scenario, events, 42))),
                                  args.limit_seconds)
                done_msgs = [m for m in res["messages"] if m[0] == "unit_done"]
                if res["outcome"] == "end" and done_msgs:
                    counts, elapsed = done_msgs[0][2]
                    append_csv(OUT, FIELDS, {**st0, **base, "status": "ok",
                                             "elapsed_seconds": elapsed, **counts})
                else:
                    append_csv(OUT, FIELDS, {**st0, **base, "status": res["outcome"],
                                             "reason": res["error"] or "limit reached"})
                print(version, scenario, events, res["outcome"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
