"""Per-event processing latency: a separate instrumentation run.

Called by run_benchmark.py (phase "latency"). One child per (dataset,
version): load the events, one untimed warm-up replay, then one
instrumented replay on a fresh book that records perf_counter_ns() around
every process_event call into a preallocated array (GC disabled, same
policy as the timing run). Each replay is under the same time limit.

This is algorithm processing latency only: no queueing or network latency,
and it says nothing about real-time overload capacity. It is never derived
from 1/throughput. Percentiles: nearest-rank (bench_common).

Segments: all events, the first 1,000 and the last 1,000 (for buildup the
book grows from 0 to M orders, so first vs last shows the growth).

Event types: every timed event belongs to exactly one of EVENT_TYPES,
decided from the event and its result (a LIMIT with at least one fill is
"LIMIT traded", also when a residual rests). The type of event i is recorded
in the warm-up replay, so the timed loop does nothing but call the engine
and read the clock. Both replays start from an empty book and process the
same events, so event i has the same result in both; the child checks that
they end with the same book, and the parent checks the counts per type
against the dataset manifest (a difference gives status "mismatch").

Writes <out>/latency_summary.csv, <out>/latency_quantiles.csv (all
percentiles 0..100 plus 99.9 per segment) and <out>/latency_by_type.csv
(count, median, p95, p99, max per event type). Units: nanoseconds.

Child mode (internal): bench_latency.py --child <file> <version>
"""

import argparse
import gc
import time
from array import array

from bench_common import (VERSIONS, append_rows, book_class, dataset_name, emit, load_timed,
                          nearest_rank, read_manifest, rel, rotated, run_child, stop_note,
                          write_rows)

SUMMARY_FIELDS = ["version", "scenario", "seed", "events", "segment", "n", "min_ns", "p50_ns",
                  "p95_ns", "p99_ns", "p999_ns", "max_ns", "mean_ns", "timer_overhead_ns",
                  "status", "note"]
QUANTILE_FIELDS = ["version", "scenario", "seed", "events", "segment", "percentile",
                   "latency_ns"]
TYPE_FIELDS = ["version", "scenario", "seed", "events", "event_type", "count", "p50_ns",
               "p95_ns", "p99_ns", "max_ns", "status", "note"]
PERCENTILES = [float(p) for p in range(101)] + [99.9]
EDGE = 1000                           # first / last 1,000 events
SEGMENTS = ["all", f"first_{EDGE}", f"last_{EDGE}"]
EVENT_TYPES = ["LIMIT resting", "LIMIT traded", "MARKET_SELL", "CANCEL found",
               "CANCEL not_found", "rejected"]
RESTING, TRADED, MARKET, FOUND, NOT_FOUND, REJECTED = range(6)


def type_of(event, result):
    """Index into EVENT_TYPES for one processed event."""
    status = result["status"]
    if status == "rejected":              # first: the event may not even be a dict
        return REJECTED
    if event["type"] == "LIMIT":
        return TRADED if result["fills"] else RESTING
    if event["type"] == "MARKET_SELL":
        return MARKET
    return FOUND if status == "cancelled" else NOT_FOUND


def type_stats(lat, types):
    """Count and nearest-rank percentiles per event type (None: no such event)."""
    out = {}
    for code, name in enumerate(EVENT_TYPES):
        values = sorted(v for v, t in zip(lat, types) if t == code)
        out[name] = {"count": len(values),
                     **{key: nearest_rank(values, p) if values else None
                        for key, p in (("p50_ns", 50), ("p95_ns", 95), ("p99_ns", 99),
                                       ("max_ns", 100))}}
    return out


def type_mismatch(counts, ds):
    """Difference between the recorded types and the dataset manifest ('' = none)."""
    checks = [("events", sum(counts.values()), ds["events"]),
              ("rejected", counts["rejected"], ds["rejected"]),
              ("not_found cancels", counts["CANCEL not_found"], ds["not_found_cancels"])]
    if ds["rejected"] == 0:               # the manifest counts types before validation
        checks += [("limits", counts["LIMIT resting"] + counts["LIMIT traded"], ds["limits"]),
                   ("market sells", counts["MARKET_SELL"], ds["market_sells"]),
                   ("cancels", counts["CANCEL found"] + counts["CANCEL not_found"],
                    ds["cancels"])]
    return "; ".join(f"{name}: {got} recorded, {want} in the manifest"
                     for name, got, want in checks if got != want)


def timer_overhead_ns(n=20_000):
    clock = time.perf_counter_ns
    gaps = []
    for _ in range(n):
        t0 = clock()
        gaps.append(clock() - t0)
    gaps.sort()
    return gaps[n // 2]


def child(path, version):
    events, _ = load_timed(path)
    cls = book_class(version)
    overhead = timer_overhead_ns()

    n = len(events)
    types = bytearray(n)                  # event type of every event (see the docstring)
    emit(start=["warm-up"])
    book = cls()
    process = book.process_event
    gc.collect()
    gc.disable()
    for i, event in enumerate(events):
        types[i] = type_of(event, process(event))
    gc.enable()
    emit(stop=["warm-up"])
    warm_book = book.inspect_book()
    del process, book

    lat = array("q", bytes(8 * n))
    emit(start=["latency"])
    book = cls()
    process = book.process_event
    clock = time.perf_counter_ns
    gc.collect()
    gc.disable()
    for i, event in enumerate(events):
        t0 = clock()
        process(event)
        lat[i] = clock() - t0
    gc.enable()
    emit(stop=["latency"])
    assert book.inspect_book() == warm_book, "the two replays end with different books"

    segments = {"all": lat, f"first_{EDGE}": lat[:EDGE], f"last_{EDGE}": lat[-EDGE:]}
    out = {}
    for name, values in segments.items():
        values = sorted(values)
        out[name] = {"n": len(values), "mean": sum(values) / len(values),
                     "quantiles": [nearest_rank(values, p) for p in PERCENTILES]}
    emit(result={"segments": out, "types": type_stats(lat, types),
                 "timer_overhead_ns": overhead})


def run(cfg):
    summary_csv = cfg.out / "latency_summary.csv"
    quantile_csv = cfg.out / "latency_quantiles.csv"
    type_csv = cfg.out / "latency_by_type.csv"
    write_rows(summary_csv, SUMMARY_FIELDS, [])
    write_rows(quantile_csv, QUANTILE_FIELDS, [])
    write_rows(type_csv, TYPE_FIELDS, [])
    manifest = {d["dataset"]: d for d in read_manifest(cfg)}
    for i, (scenario, m) in enumerate(cfg.latency_cells):
        ds = manifest[dataset_name(scenario, m, cfg.diag_seed, 1000)]
        for version in rotated(VERSIONS, i):
            key = {"version": version, "scenario": scenario, "seed": ds["seed"], "events": m}
            got = {}
            stopped = run_child("bench_latency.py", [ds["file"], version], cfg.time_limit,
                                lambda msg: got.update(msg.get("result", {})) and False)
            summary, quantiles, by_type = [], [], []
            outcome = "ok"
            if stopped:
                outcome = "STOPPED"
                note = stop_note(stopped, stopped["step"] or ["latency"], cfg.time_limit)
                for seg in SEGMENTS:
                    summary.append({**key, "segment": seg, "status": "stopped", "note": note})
                for name in EVENT_TYPES:
                    by_type.append({**key, "event_type": name, "status": "stopped",
                                    "note": note})
            else:
                problem = type_mismatch({t: s["count"] for t, s in got["types"].items()}, ds)
                if problem:
                    outcome = "TYPE MISMATCH"
                for name, s in got["types"].items():
                    by_type.append({**key, "event_type": name, **s,
                                    "status": "mismatch" if problem else "ok",
                                    "note": problem})
                for seg, s in got["segments"].items():
                    q = dict(zip(PERCENTILES, s["quantiles"]))
                    summary.append({**key, "segment": seg, "n": s["n"], "min_ns": q[0.0],
                                    "p50_ns": q[50.0], "p95_ns": q[95.0], "p99_ns": q[99.0],
                                    "p999_ns": q[99.9], "max_ns": q[100.0],
                                    "mean_ns": f"{s['mean']:.1f}",
                                    "timer_overhead_ns": got["timer_overhead_ns"],
                                    "status": "ok", "note": ""})
                    quantiles += [{**key, "segment": seg, "percentile": p, "latency_ns": v}
                                  for p, v in zip(PERCENTILES, s["quantiles"])]
            append_rows(summary_csv, SUMMARY_FIELDS, summary)
            append_rows(quantile_csv, QUANTILE_FIELDS, quantiles)
            append_rows(type_csv, TYPE_FIELDS, by_type)
            print(f"  latency {ds['dataset']:34s} {version:8s} {outcome}", flush=True)
    print(f"  wrote {rel(summary_csv)}, {rel(quantile_csv)}, {rel(type_csv)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", nargs=2, required=True)
    args = parser.parse_args()
    child(*args.child)


if __name__ == "__main__":
    main()
