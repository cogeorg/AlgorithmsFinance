#!/usr/bin/env python3
"""Correctness evidence saved for the dashboard (not timed).

For every input below and after EVERY event:
  * the independent oracle (tests/oracle.py) checks Version B's result and book,
  * Version A and Version B must return identical results and identical canonical books.
Also runs the unit-test suite and records its summary.
"""
import subprocess
import sys
import time

from _util import RESULTS, ROOT, SCENARIOS, SEEDS, input_path, save_json
from lob.book_a import BookA
from lob.book_b import BookB
from lob.common import read_events
from tests import oracle

INPUTS = ([(ROOT / "data" / f"{s}_10000.jsonl.gz", s, 10000, 42) for s in SCENARIOS]
          + [(input_path(s, 1000, seed), s, 1000, seed) for s in SCENARIOS for seed in SEEDS])


def check(path):
    events = read_events(path)
    a, b = BookA(), BookB()
    last_seq = 0
    stats = {"accepted": 0, "rejected": 0, "fills": 0, "max_active": 0}
    before = b.inspect_book()
    for i, ev in enumerate(events):
        ra, rb = a.process(ev), b.process(ev)
        after = b.inspect_book()
        last_seq = oracle.check_event(before, ev, rb, after, last_seq)
        if ra != rb:
            return {"ok": False, "error": f"A/B results differ at event {i}", **stats}
        if a.inspect_book() != after:
            return {"ok": False, "error": f"A/B books differ after event {i}", **stats}
        stats["rejected" if rb["status"] == "rejected" else "accepted"] += 1
        stats["fills"] += len(rb.get("fills", ()))
        stats["max_active"] = max(stats["max_active"], len(after))
        before = after
    b.check_internal()
    return {"ok": True, "error": "", **stats}


def main():
    rows = []
    for path, scenario, events, seed in INPUTS:
        t = time.perf_counter()
        try:
            res = check(path)
        except AssertionError as exc:
            res = {"ok": False, "error": f"oracle: {exc}"}
        res.update(input=str(path.relative_to(ROOT)), scenario=scenario, events=events, seed=seed,
                   checked_every_event=True, seconds=round(time.perf_counter() - t, 1))
        rows.append(res)
        print(("OK  " if res["ok"] else "FAIL"), res["input"], res.get("error", ""), flush=True)
    unit = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
                          cwd=ROOT, capture_output=True, text=True)
    summary = [line for line in unit.stderr.strip().splitlines() if line.startswith(("Ran ", "OK", "FAILED"))]
    save_json(RESULTS / "correctness.json", {"per_event_checks": rows, "unit_tests": summary,
                                             "unit_tests_ok": unit.returncode == 0})
    print(summary)


if __name__ == "__main__":
    main()
