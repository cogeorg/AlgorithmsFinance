#!/usr/bin/env python3
"""Per-event processing latency (separate instrumentation run, never mixed with throughput).

time.perf_counter_ns() is read around each process() call; per-event times are kept in
memory for the run. Reported: nearest-rank p50/p95/p99 (value at position
ceil(p/100*n) of the sorted sample), mean and max, per event type, and early (first 10%
of events) vs late (last 10%). This is engine processing latency only: no network,
queueing or parsing. Raw per-event times are saved for the 10,000-event runs.

Runs only configurations whose throughput run finished within the limit
(results/timing.csv); others are listed as not attempted.
"""
import gc
import gzip
import json
import time

from _util import RESULTS, SCENARIOS, VERSIONS, input_path, nearest_rank, read_csv, save_json
from lob.common import read_events

CONFIGS = [(s, n, seed) for n in (10000, 100000) for s in SCENARIOS for seed in (42, 43, 44)]


def summarize(ns):
    s = sorted(ns)
    return {"n": len(s), "p50_ns": nearest_rank(s, 50), "p95_ns": nearest_rank(s, 95),
            "p99_ns": nearest_rank(s, 99), "max_ns": s[-1] if s else None,
            "mean_ns": round(sum(s) / len(s), 1) if s else None}


def histogram(ns):
    """Counts per power-of-two bucket [2^k, 2^(k+1)) ns."""
    h = {}
    for v in ns:
        k = max(v, 1).bit_length() - 1
        h[k] = h.get(k, 0) + 1
    return {str(k): h[k] for k in sorted(h)}


def measure(version, events):
    book = VERSIONS[version]()
    proc = book.process
    pc = time.perf_counter_ns
    lat = [0] * len(events)
    gc.collect()
    for i, ev in enumerate(events):
        t = pc()
        proc(ev)
        lat[i] = pc() - t
    return lat


def main():
    ok = {(r["version"], r["scenario"], int(r["events"]), int(r["seed"]))
          for r in read_csv(RESULTS / "timing.csv") if r["phase"] == "replay" and r["status"] == "ok"}
    stopped = {(r["version"], r["scenario"], int(r["events"]), int(r["seed"]))
               for r in read_csv(RESULTS / "timing.csv") if r["status"] in ("stopped_time_limit", "not_attempted", "failed")}
    out, raw = [], {}
    for scenario, n, seed in CONFIGS:
        events = read_events(input_path(scenario, n, seed))
        kinds = [ev["type"] for ev in events]
        for version in VERSIONS:
            key = (version, scenario, n, seed)
            if key not in ok or key in stopped:
                out.append({"version": version, "scenario": scenario, "events": n, "seed": seed,
                            "status": "not_attempted", "note": "throughput run did not finish within the limit"})
                print(version, scenario, n, "not attempted", flush=True)
                continue
            measure(version, events[: min(2000, n)])  # warmup on a prefix
            lat = measure(version, events)
            tenth = max(1, n // 10)
            rec = {"version": version, "scenario": scenario, "events": n, "seed": seed, "status": "ok",
                   "all": summarize(lat), "early_first_10pct": summarize(lat[:tenth]),
                   "late_last_10pct": summarize(lat[-tenth:]),
                   "by_type": {k: summarize([v for v, t in zip(lat, kinds) if t == k]) for k in sorted(set(kinds))},
                   "histogram_log2_ns": histogram(lat)}
            out.append(rec)
            if n == 10000:
                raw[f"{version}|{scenario}|{n}|{seed}"] = lat
            a = rec["all"]
            print(f"{version} {scenario:12s} {n:>7d}: p50 {a['p50_ns']} p95 {a['p95_ns']} p99 {a['p99_ns']} ns; "
                  f"early p50 {rec['early_first_10pct']['p50_ns']} late p50 {rec['late_last_10pct']['p50_ns']}",
                  flush=True)
    save_json(RESULTS / "latency.json", {"percentile_convention": "nearest rank: ceil(p/100*n)-th smallest",
                                         "timer": "time.perf_counter_ns around book.process(event)",
                                         "runs": out})
    with gzip.open(RESULTS / "latency_raw_10000.json.gz", "wt") as fh:
        json.dump(raw, fh)


if __name__ == "__main__":
    main()
