#!/usr/bin/env python3
"""Experiment: Version C (bench/variants/book_c_deque.py) against the submitted Version B.

Same protocol as run_timing.py: pre-generated inputs, fresh process per (version, input), 1 warmup +
5 timed replays on a fresh book, every raw repeat saved, median reported. Also one large sell
(100 % of the bid quantity, book restored from the snapshot before every trial) and traced memory
per resting order (traced from before loading, input list dropped afterwards). Results:
results/version_c.json. Version C is a measured experiment, not the submitted revision.
"""
import gc
import json
import subprocess
import sys
import time
import tracemalloc
from statistics import median

from _util import GEN, RESULTS, ROOT, SCENARIOS, input_path, save_json


def worker(kind, impl, arg):
    from bench.variants.book_c_deque import BookC
    from lob.book_b import BookB
    from lob.common import read_events
    cls = {"B": BookB, "C": BookC}[impl]
    if kind == "replay":
        events = read_events(arg)
        times = []
        for rep in range(6):  # repeat 0 = warmup
            book = cls()
            proc = book.process
            t = time.perf_counter()
            for ev in events:
                proc(ev)
            if rep:
                times.append(time.perf_counter() - t)
        print(json.dumps(times))
    elif kind == "sell":
        snap = json.loads(open(arg).read())
        qty = sum(o["qty_units"] for o in snap["orders"] if o["side"] == "BUY")
        times = []
        for rep in range(6):
            book = cls.from_snapshot(snap["orders"], snap["last_seq"])
            t = time.perf_counter()
            book.FillMarketSell({"seq": snap["last_seq"] + 1, "event_id": "x", "type": "MARKET_SELL",
                                 "order_id": "x", "qty_units": qty})
            if rep:
                times.append(time.perf_counter() - t)
        print(json.dumps(times))
    else:  # memory
        gc.collect()
        tracemalloc.start()
        events = read_events(arg)
        book = cls()
        for ev in events:
            book.process(ev)
        del events
        gc.collect()
        current = tracemalloc.get_traced_memory()[0]
        tracemalloc.stop()
        st = book.storage_counts()
        print(json.dumps({"bytes": current, "orders": st["stored_orders"], "stale_entries": st.get("stale_entries", 0)}))


def run(*args):
    return json.loads(subprocess.run([sys.executable, str(ROOT / "bench" / "run_version_c.py"), "--worker", *args],
                                     capture_output=True, text=True, check=True, cwd=ROOT).stdout)


def main():
    out = {"replay_100000": [], "sell_100pct": [], "memory": []}
    for scenario in SCENARIOS:
        for seed in (42, 43, 44):
            path = str(input_path(scenario, 100000, seed))
            b, c = run("replay", "B", path), run("replay", "C", path)
            out["replay_100000"].append({"scenario": scenario, "seed": seed, "B_raw_s": b, "C_raw_s": c,
                                         "B_median_s": median(b), "C_median_s": median(c),
                                         "C_over_B": median(c) / median(b)})
        rows = [r for r in out["replay_100000"] if r["scenario"] == scenario]
        print(f"{scenario:12s} C/B per seed {[round(r['C_over_B'], 2) for r in rows]}", flush=True)
    for levels in (1000, 4):
        snap = str(GEN / f"snapshot_buildup_100000_s42_l{levels}.json")
        b, c = run("sell", "B", snap), run("sell", "C", snap)
        out["sell_100pct"].append({"book": f"buildup_100000_l{levels}", "B_raw_s": b, "C_raw_s": c,
                                   "B_median_s": median(b), "C_median_s": median(c), "C_over_B": median(c) / median(b)})
    for scenario, n in (("buildup", 10000), ("buildup", 100000), ("mixed", 100000), ("cancel_churn", 100000)):
        path = str(input_path(scenario, n, 42))
        b, c = run("memory", "B", path), run("memory", "C", path)
        out["memory"].append({"scenario": scenario, "events": n, "B": b, "C": c})
    save_json(RESULTS / "version_c.json", {"note": __doc__, **out})
    for r in out["sell_100pct"]:
        print(f"sell {r['book']}: C/B {r['C_over_B']:.2f}")
    for r in out["memory"]:
        print(f"memory {r['scenario']} {r['events']}: B {r['B']} C {r['C']}")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        worker(*sys.argv[2:5])
    else:
        main()
