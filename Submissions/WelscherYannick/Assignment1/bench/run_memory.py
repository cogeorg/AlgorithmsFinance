#!/usr/bin/env python3
"""Traced Python allocations with tracemalloc (separate from timing).

Measurement boundary, per configuration (fresh process each):
  phase "input"           : reading+parsing the file into a list of dicts (current bytes
                            after loading = size of the preloaded input; peak includes
                            gzip/json temporaries).
  phase "replay_peak"     : tracing starts AFTER the input is loaded, so the input is
                            EXCLUDED. Peak covers the book, the current event's result
                            (fills list) and temporaries. No trade history is stored.
  phase "book_after"      : current traced bytes after the replay with the last result
                            dropped = memory held by the book state alone.
  phase "checkpoint"      : current traced bytes at 10 points during the replay, read
                            while the event's returned result is still held.
tracemalloc counts Python-level allocations only: it is neither pure auxiliary space
nor total process memory (interpreter, allocator slack, freed-but-cached arenas).
"""
import gc
import json
import subprocess
import sys
import tracemalloc

from _util import (CONFIG_LIMIT_S, RESULTS, ROOT, SCENARIOS, VERSIONS, input_path, read_csv,
                   write_csv)
from lob.common import read_events

CONFIGS = [(s, n, seed) for n in (10000, 100000) for s in SCENARIOS for seed in (42, 43, 44)]


def worker(version, scenario, n, seed):
    path = input_path(scenario, n, seed)
    gc.collect()
    tracemalloc.start()
    events = read_events(path)
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(json.dumps({"phase": "input", "current": cur, "peak": peak}), flush=True)

    gc.collect()
    tracemalloc.start()
    book = VERSIONS[version]()
    checkpoints = {max(1, n * k // 10) for k in range(1, 11)}
    res = None
    for i, ev in enumerate(events, 1):
        res = book.process(ev)
        if i in checkpoints:
            cur, _ = tracemalloc.get_traced_memory()  # result `res` still referenced
            st = book.storage_counts()
            print(json.dumps({"phase": "checkpoint", "event": i, "current": cur,
                              "stored_orders": st["stored_orders"], "stored_levels": st["stored_levels"]}),
                  flush=True)
    _, peak = tracemalloc.get_traced_memory()
    del res
    gc.collect()
    cur, _ = tracemalloc.get_traced_memory()
    st = book.storage_counts()
    tracemalloc.stop()
    print(json.dumps({"phase": "replay_peak", "peak": peak}), flush=True)
    print(json.dumps({"phase": "book_after", "current": cur, "stored_orders": st["stored_orders"],
                      "stored_levels": st["stored_levels"]}), flush=True)

    # Variant traced from BEFORE loading: after dropping the input list, everything still traced
    # is held by the book, including id strings and ints that the JSON parser created.
    del book, events
    gc.collect()
    tracemalloc.start()
    events = read_events(path)
    book = VERSIONS[version]()
    for ev in events:
        book.process(ev)
    del events
    gc.collect()
    cur, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    st = book.storage_counts()
    print(json.dumps({"phase": "book_after_incl_input_objects", "current": cur, "stored_orders": st["stored_orders"],
                      "stored_levels": st["stored_levels"]}), flush=True)


def main():
    timing = read_csv(RESULTS / "timing.csv")
    bad = {(r["version"], r["scenario"], int(r["events"]), int(r["seed"])) for r in timing
           if r["status"] in ("stopped_time_limit", "not_attempted", "failed")}
    ok = {(r["version"], r["scenario"], int(r["events"]), int(r["seed"])) for r in timing
          if r["phase"] == "replay" and r["status"] == "ok"} - bad
    rows = []
    for scenario, n, seed in CONFIGS:
        for version in VERSIONS:
            base = {"run_kind": "memory", "version": version, "scenario": scenario, "seed": seed,
                    "events": n, "levels": 1000}
            if (version, scenario, n, seed) not in ok:
                rows.append({**base, "phase": "replay_peak", "status": "not_attempted",
                             "note": "throughput run did not finish within the limit"})
                print(version, scenario, n, seed, "not attempted", flush=True)
                continue
            cmd = [sys.executable, str(ROOT / "bench" / "run_memory.py"), "--worker", version,
                   scenario, str(n), str(seed)]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=4 * CONFIG_LIMIT_S, cwd=ROOT)
                out = proc.stdout
                status = "ok" if proc.returncode == 0 else "failed"
            except subprocess.TimeoutExpired as exc:
                out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                status = "stopped_time_limit"
            for line in out.splitlines():
                r = json.loads(line)
                row = {**base, "phase": r["phase"], "status": status,
                       "traced_peak_bytes": r.get("peak", ""), "traced_current_bytes": r.get("current", ""),
                       "active_orders_peak": r.get("stored_orders", ""),
                       "price_levels_peak": r.get("stored_levels", "")}
                if r["phase"] == "checkpoint":
                    row["repeat"] = r["event"]
                    row["note"] = "repeat column = events processed so far"
                if r["phase"] in ("book_after", "book_after_incl_input_objects"):
                    row["note"] = "active_orders_peak/price_levels_peak columns = stored entries at the end"
                rows.append(row)
            peak = next((json.loads(x)["peak"] for x in out.splitlines() if '"replay_peak"' in x), None)
            after = next((json.loads(x)["current"] for x in out.splitlines() if '"book_after"' in x), None)
            print(f"{version} {scenario:12s} {n:>7d} s{seed}: replay peak {peak} B, book after {after} B", flush=True)
            write_csv(RESULTS / "memory.csv", rows)
    write_csv(RESULTS / "memory.csv", rows)


if __name__ == "__main__":
    if len(sys.argv) == 6 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5]))
    else:
        main()
