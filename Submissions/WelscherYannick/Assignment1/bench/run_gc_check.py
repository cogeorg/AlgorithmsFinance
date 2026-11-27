#!/usr/bin/env python3
"""Diagnostic: is Version B's super-linear growth from 100,000 to 1,000,000 buildup events caused by
Python's cyclic garbage collector? Same input, fresh book and fresh process per variant; 1 warmup +
3 timed replays each; GC enabled (default, as in all benchmarks) vs gc.disable() during the replay.
Diagnostic only: the official benchmarks keep the default GC. Results: results/gc_check.json."""
import gc
import json
import subprocess
import sys
import time
from statistics import median

from _util import RESULTS, ROOT, input_path, save_json
from lob.book_b import BookB
from lob.common import read_events


def worker(path, disable):
    events = read_events(path)
    times, collections = [], []
    for rep in range(4):
        gc.collect()
        before = sum(s["collections"] for s in gc.get_stats())
        if disable:
            gc.disable()
        book, t = BookB(), time.perf_counter()
        for ev in events:
            book.process(ev)
        el = time.perf_counter() - t
        gc.enable()
        if rep:
            times.append(el)
            collections.append(sum(s["collections"] for s in gc.get_stats()) - before)
        del book
    print(json.dumps({"times": times, "gc_collections": collections}))


def main():
    out = []
    for scenario, n in (("buildup", 100000), ("buildup", 1000000), ("sweep", 100000)):
        for disable in (False, True):
            r = json.loads(subprocess.run([sys.executable, str(ROOT / "bench" / "run_gc_check.py"), "--worker",
                                           str(input_path(scenario, n, 42)), str(int(disable))],
                                          capture_output=True, text=True, check=True, cwd=ROOT).stdout)
            out.append({"scenario": scenario, "events": n, "gc": "disabled" if disable else "enabled",
                        "median_s": median(r["times"]), "raw_s": r["times"], "gc_collections": r["gc_collections"]})
            print(f"{scenario:8s} {n:>8,} gc {'off' if disable else 'on '}: median {median(r['times']):.4f}s "
                  f"raw {[round(x, 4) for x in r['times']]} collections {r['gc_collections']}", flush=True)
    save_json(RESULTS / "gc_check.json", {"note": __doc__, "runs": out})


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3] == "1")
    else:
        main()
