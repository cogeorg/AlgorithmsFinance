#!/usr/bin/env python3
"""Measured effect of each Version B revision step (same protocol as run_timing.py).

  step1_levels   : price levels + order index, generic validation (first revision)
  step2_fastpath : + fused fast-path process() (profiling: ~60% of time was validation/dispatch)
  step3_lists    : + orders as 4-item lists instead of objects (= submitted lob/book_b.py)

Each variant: same pre-generated 100,000-event inputs (seed 42), parse excluded, 1 warmup +
5 timed replays on a fresh book, fresh process per (variant, scenario). Before timing, the
variant's results and final book are checked to be identical to the submitted Version B.
"""
import importlib
import json
import subprocess
import sys
import time

from _util import REPEATS, RESULTS, ROOT, SCENARIOS, input_path, write_csv
from lob.common import read_events

VARIANTS = {"step1_levels": "bench.variants.book_b_step1_levels",
            "step2_fastpath": "bench.variants.book_b_step2_fastpath",
            "step3_lists": "lob.book_b"}


def worker(variant, path):
    cls = importlib.import_module(VARIANTS[variant]).BookB
    events = read_events(path)
    ref, cand = importlib.import_module("lob.book_b").BookB(), cls()
    same = all(ref.process(ev) == cand.process(ev) for ev in events) and ref.inspect_book() == cand.inspect_book()
    print(json.dumps({"identical_to_submitted_B": same}), flush=True)
    for rep in range(REPEATS + 1):
        book = cls()
        proc = book.process
        t = time.perf_counter()
        for ev in events:
            proc(ev)
        print(json.dumps({"repeat": rep, "elapsed_s": time.perf_counter() - t}), flush=True)


def main():
    rows = []
    for scenario in SCENARIOS:
        path = input_path(scenario, 100000, 42)
        for variant in VARIANTS:
            out = subprocess.run([sys.executable, str(ROOT / "bench" / "run_revision_steps.py"), "--worker", variant,
                                  str(path)], capture_output=True, text=True, cwd=ROOT, check=True).stdout
            recs = [json.loads(x) for x in out.splitlines()]
            same = recs[0]["identical_to_submitted_B"]
            for r in recs[1:]:
                rows.append({"run_kind": "revision_steps", "version": f"B_{variant}", "scenario": scenario, "seed": 42,
                             "events": 100000, "levels": 1000, "phase": "replay", "repeat": r["repeat"],
                             "elapsed_s": f"{r['elapsed_s']:.6f}", "status": "warmup" if r["repeat"] == 0 else "ok",
                             "note": "results identical to submitted Version B" if same else "RESULTS DIFFER"})
            times = sorted(r["elapsed_s"] for r in recs[1:] if r["repeat"] > 0)
            print(f"{scenario:12s} {variant:15s} median {times[len(times) // 2] * 1000:7.1f} ms  identical={same}", flush=True)
    write_csv(RESULTS / "revision_steps.csv", rows)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3])
    else:
        main()
