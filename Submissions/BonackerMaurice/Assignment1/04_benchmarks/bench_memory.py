"""Memory: a separate tracemalloc run, one child per (dataset, version).

Called by run_benchmark.py (phase "memory"). In the child:
  1. load the events BEFORE tracemalloc.start() (input excluded),
  2. tracemalloc.start(); a fresh book; replay every event. The returned
     output of the current event stays referenced while its sample is read
     (about 100 samples; the buffers are preallocated before tracing) and is
     released before the next event, so no history builds up,
  3. after the last event read the traced bytes twice: with that event's
     output still referenced (traced_with_output_bytes, and the peak), then
     after releasing it (traced_current_bytes: the book; CPython's free lists
     can keep a few released dicts and lists, which tracemalloc still counts),
  4. stop tracing, then count what the book retains: live orders, occupied
     levels, queue entries incl. dead (cancelled) ones, index entries incl.
     stale heap keys. Also the process peak working set / max RSS.
Same time limit and GC policy as the timing run.

Book growth during insertion: memory_samples.csv for buildup. Memory after
cancellation churn: cancel_churn rows (few active orders after many
cancels) plus the retained-entry counts in memory_end_state.csv.

Writes memory rows (run_kind "memory") into <out>/benchmark_results.csv,
plus <out>/memory_samples.csv and <out>/memory_end_state.csv.

Child mode (internal): bench_memory.py --child <file> <version>
"""

import argparse
import gc
import tracemalloc
from array import array

from bench_common import (VERSIONS, append_rows, book_class, dataset_name, drop_rows, emit,
                          load_events, process_peak_bytes, read_manifest, rel, rotated,
                          run_child, stop_note, write_rows)
from bench_timing import RESULT_FIELDS, base_row

SAMPLE_FIELDS = ["version", "scenario", "seed", "events", "event_index", "active_orders",
                 "traced_current_bytes"]
END_FIELDS = ["version", "scenario", "seed", "events", "status", "live_orders",
              "price_levels", "queue_entries", "dead_queue_entries", "index_entries",
              "stale_index_entries", "traced_current_bytes", "traced_with_output_bytes",
              "traced_peak_bytes", "process_peak_bytes", "note"]
SAMPLES = 100


def retained(book):
    """What the book holds after the replay (A: one list; B: dict + levels + index)."""
    if isinstance(book.orders, list):                       # Version A
        n = len(book.orders)
        return {"live_orders": n,
                "price_levels": len({(o["side"], o["price_ticks"]) for o in book.orders}),
                "queue_entries": n, "dead_queue_entries": 0,
                "index_entries": "", "stale_index_entries": ""}
    levels = sum(len(book.levels[s]) for s in ("BUY", "SELL"))
    queue = sum(len(lv.queue) for s in ("BUY", "SELL") for lv in book.levels[s].values())
    index = getattr(book, "_heaps", None) or getattr(book, "_keys")
    entries = sum(len(index[s]) for s in ("BUY", "SELL"))
    return {"live_orders": len(book.orders), "price_levels": levels, "queue_entries": queue,
            "dead_queue_entries": queue - len(book.orders), "index_entries": entries,
            "stale_index_entries": entries - levels}


def child(path, version):
    events = load_events(path)
    n = len(events)
    step = max(1, n // SAMPLES)
    count = n // step
    at = array("q", bytes(8 * count))
    active = array("q", bytes(8 * count))
    current = array("q", bytes(8 * count))
    ends = array("q", bytes(8 * 3))      # plain ints kept here would be traced themselves
    cls = book_class(version)

    emit(start=["memory"])
    gc.collect()
    gc.disable()
    tracemalloc.start()
    book = cls()
    process = book.process_event
    k = 0
    result = None
    for i, event in enumerate(events, 1):
        result = None                        # release the previous event's output
        result = process(event)              # this event's output stays referenced ...
        if i % step == 0 and k < count:
            at[k] = i
            active[k] = len(book.orders)
            current[k] = tracemalloc.get_traced_memory()[0]    # ... while it is sampled
            k += 1
    ends[0], ends[1] = tracemalloc.get_traced_memory()         # last output referenced
    result = None                            # release it: the book alone remains
    ends[2] = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()
    gc.enable()
    emit(stop=["memory"])
    emit(result={"samples": [list(at[:k]), list(active[:k]), list(current[:k])],
                 "traced_with_output_bytes": ends[0], "traced_peak_bytes": ends[1],
                 "traced_current_bytes": ends[2],
                 "process_peak_bytes": process_peak_bytes(), **retained(book)})


def run(cfg):
    drop_rows(cfg.results_csv, RESULT_FIELDS, lambda r: r["run_kind"] == "memory")
    samples_csv = cfg.out / "memory_samples.csv"
    end_csv = cfg.out / "memory_end_state.csv"
    write_rows(samples_csv, SAMPLE_FIELDS, [])
    write_rows(end_csv, END_FIELDS, [])
    manifest = {d["dataset"]: d for d in read_manifest(cfg)}
    cells = [manifest[dataset_name(s, m, cfg.diag_seed, 1000)]
             for m in cfg.memory_sizes for s in ("buildup", "crowded", "mixed", "sweep",
                                                 "cancel_churn")]
    for i, ds in enumerate(cells):
        for version in rotated(VERSIONS, i):
            got = {}
            stopped = run_child("bench_memory.py", [ds["file"], version], cfg.time_limit,
                                lambda msg: got.update(msg.get("result", {})) and False)
            key = {"version": version, "scenario": ds["scenario"], "seed": ds["seed"],
                   "events": ds["events"]}
            row = base_row(ds, version, "memory")
            row.update(run_kind="memory", events=ds["events"], phase="replay", repeat=1,
                       warmup=False, peak_active_orders=ds["peak_active_orders"],
                       peak_price_levels=ds["peak_price_levels"])
            if stopped:
                note = stop_note(stopped, ["memory"], cfg.time_limit)
                row.update(status="stopped", note=note)
                end = {**key, "status": "stopped", "note": note}
            else:
                row.update(traced_peak_bytes=got["traced_peak_bytes"],
                           traced_current_bytes=got["traced_current_bytes"], status="ok",
                           note="tracemalloc run; elapsed time not reported (tracing slows it)")
                end = {**key, "status": "ok", "note": "",
                       **{k: got[k] for k in END_FIELDS if k in got}}
                at, active, current = got["samples"]
                append_rows(samples_csv, SAMPLE_FIELDS,
                            [{**key, "event_index": a, "active_orders": b,
                              "traced_current_bytes": c}
                             for a, b, c in zip(at, active, current)])
            append_rows(cfg.results_csv, RESULT_FIELDS, [row])
            append_rows(end_csv, END_FIELDS, [end])
            print(f"  memory  {ds['dataset']:34s} {version:8s} "
                  f"{'STOPPED' if stopped else 'ok'}", flush=True)
    print(f"  wrote memory rows, {rel(samples_csv)}, {rel(end_csv)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", nargs=2, required=True)
    args = parser.parse_args()
    child(*args.child)


if __name__ == "__main__":
    main()
