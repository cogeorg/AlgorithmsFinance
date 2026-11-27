#!/usr/bin/env python3
"""One large market sell against the same fresh bid book (10%, 100%, 200% of bid quantity).

Books are built (not timed) by replaying a buildup stream with Version B and saved as a
snapshot. Every trial restores a fresh book from that snapshot (phase "reset", timed
separately) and then times ONE FillMarketSell call (phase "sell": matching, state
updates and fill-list construction together). 1 warmup + 5 timed trials per config,
each config in its own process with the declared time limit.

Work counts (independent of timing): fills F = makers touched, distinct price levels
visited L, unfilled quantity, and for Version A the number of list entries scanned
(each fill rescans the remaining bid list; computed from the fills, so the engine is
not instrumented).

Queue concentration: 10,000 events on 4 vs 1,000 prices per side (same order count).
"""
import hashlib
import json
import math
import subprocess
import sys
import time

from _util import CONFIG_LIMIT_S, GEN, REPEATS, RESULTS, ROOT, VERSIONS, input_path, write_csv
from lob.book_b import BookB
from lob.common import read_events

BOOKS = [("buildup", 10000, 42, 1000), ("buildup", 10000, 42, 4),
         ("buildup", 100000, 42, 1000), ("buildup", 100000, 42, 4)]


def snapshot_path(scenario, events, seed, levels):
    return GEN / f"snapshot_{scenario}_{events}_s{seed}_l{levels}.json"


def worker(version, snap_file, qty):
    snap = json.loads(open(snap_file).read())
    cls = VERSIONS[version]
    sell = {"seq": snap["last_seq"] + 1, "event_id": "liquidation", "type": "MARKET_SELL",
            "order_id": "liquidation-sell", "qty_units": qty}
    for rep in range(REPEATS + 1):  # repeat 0 = warmup
        t = time.perf_counter()
        book = cls.from_snapshot(snap["orders"], snap["last_seq"])
        reset = time.perf_counter() - t
        t = time.perf_counter()
        res = book.FillMarketSell(dict(sell))
        el = time.perf_counter() - t
        digest = hashlib.sha256(json.dumps(res, sort_keys=True).encode()).hexdigest()
        print(json.dumps({"repeat": rep, "reset_s": reset, "sell_s": el, "digest": digest,
                          "fills": len(res["fills"]), "unfilled": res["unfilled_qty_units"],
                          "status": res["status"],
                          "levels_visited": len({f["price_ticks"] for f in res["fills"]})}), flush=True)


def main():
    rows = []
    digests = {}
    for scenario, events, seed, levels in BOOKS:
        book = BookB()
        for ev in read_events(input_path(scenario, events, seed, levels)):
            book.process(ev)
        orders = book.inspect_book()
        bids = [o for o in orders if o["side"] == "BUY"]
        q_total = sum(o["qty_units"] for o in bids)
        sp = snapshot_path(scenario, events, seed, levels)
        sp.write_text(json.dumps({"last_seq": book.last_seq, "orders": orders}))
        n_levels = len({o["price_ticks"] for o in bids})
        sizes = {"10%": max(1, math.ceil(q_total / 10)), "100%": q_total, "200%": 2 * q_total}
        # Reference fills (B) for the work counts
        for label, qty in sizes.items():
            ref = BookB.from_snapshot(orders, book.last_seq)
            ref_res = ref.FillMarketSell({"seq": book.last_seq + 1, "event_id": "liquidation",
                                          "type": "MARKET_SELL", "order_id": "liquidation-sell",
                                          "qty_units": qty})
            # Version A: before each fill it scans every remaining bid to find the best one;
            # a maker leaves the list only when the fill consumed its whole quantity.
            maker_qty = {o["order_id"]: o["qty_units"] for o in bids}
            a_steps, remaining = 0, len(bids)
            for f in ref_res["fills"]:
                a_steps += remaining
                if f["qty_units"] == maker_qty[f["maker_id"]]:
                    remaining -= 1
            base = {"run_kind": "liquidation", "scenario": f"{scenario}_l{levels}", "seed": seed,
                    "events": events, "levels": levels, "active_orders_peak": len(orders),
                    "price_levels_peak": n_levels, "requested_qty_units": qty,
                    "note": f"sale {label} of bid quantity {q_total}; bid orders {len(bids)}"}
            for version in VERSIONS:
                cmd = [sys.executable, str(ROOT / "bench" / "run_liquidation.py"), "--worker",
                       version, str(sp), str(qty)]
                err = ""
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CONFIG_LIMIT_S, cwd=ROOT)
                    out = proc.stdout
                    status = "ok" if proc.returncode == 0 else "failed"
                    err = (proc.stderr.strip().splitlines() or [""])[-1]
                except subprocess.TimeoutExpired as exc:
                    out = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
                    status = "stopped_time_limit"
                recs = [json.loads(line) for line in out.splitlines() if line.strip()]
                for r in recs:
                    digests.setdefault((scenario, events, levels, label), {}).setdefault(version, set()).add(r["digest"])
                    common = {**base, "version": version, "repeat": r["repeat"],
                              "status": "warmup" if r["repeat"] == 0 else "ok",
                              "fills": r["fills"], "makers_touched": r["fills"],
                              "levels_visited": r["levels_visited"],
                              "unfilled_qty_units": r["unfilled"],
                              "work_steps": a_steps if version == "A" else r["fills"] + r["levels_visited"]}
                    rows.append({**common, "phase": "reset", "elapsed_s": f"{r['reset_s']:.6f}"})
                    rows.append({**common, "phase": "sell", "elapsed_s": f"{r['sell_s']:.6f}"})
                if status != "ok":
                    done = sum(1 for r in recs if r["repeat"] > 0)
                    # work counts come from the reference fills, so they are known even when stopped
                    ref_levels = len({f["price_ticks"] for f in ref_res["fills"]})
                    rows.append({**base, "version": version, "phase": "sell", "status": status,
                                 "fills": len(ref_res["fills"]), "makers_touched": len(ref_res["fills"]),
                                 "levels_visited": ref_levels,
                                 "unfilled_qty_units": ref_res["unfilled_qty_units"],
                                 "work_steps": a_steps if version == "A" else len(ref_res["fills"]) + ref_levels,
                                 "note": base["note"] + (f"; killed after {CONFIG_LIMIT_S}s, {done} of {REPEATS} trials finished"
                                                         if status == "stopped_time_limit" else
                                                         f"; worker failed after {done} trials: {err}")})
                sells = sorted(r["sell_s"] for r in recs if r["repeat"] > 0)
                print(f"{version} {scenario}_{events}_l{levels} {label:>4s}: {status} "
                      f"median sell {sells[len(sells) // 2] if sells else float('nan'):.5f}s "
                      f"fills {len(ref_res['fills'])}", flush=True)
            write_csv(RESULTS / "liquidation.csv", rows)
    # identical = one digest over all finished trials; versions = which versions finished at least one
    agree = {"|".join(map(str, k)): {"identical": len(set().union(*v.values())) == 1, "versions": sorted(v)}
             for k, v in digests.items()}
    (RESULTS / "liquidation_agreement.json").write_text(json.dumps(
        {"identical_result_across_versions_and_trials": agree}, indent=1) + "\n")
    print("all identical:", all(a["identical"] for a in agree.values()),
          "| compared A vs B in", sum(a["versions"] == ["A", "B"] for a in agree.values()), "of", len(agree))


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3], int(sys.argv[4]))
    else:
        main()
