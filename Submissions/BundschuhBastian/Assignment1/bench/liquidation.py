"""Large liquidation: the same fresh bid book, sells of 10%, 100% and 200% of its bid quantity.

Book: the first N BUY limits of the generator's `buildup` stream (1000 price levels), seed 42,
N in {10,000; 100,000} (`--books crowded --sizes ...` also possible); nothing crosses, so all N rest.
gc stays enabled, as in the timing runs (gc.collect() before each trial). Phase 6c: every size is a
block with a canary before and after (bench.blocks); every row has start time and power state.
A at 100,000 bids runs under the same 600 s limit (stopped if exceeded, nothing estimated).
Sale quantity = ceil(fraction * total bid quantity) (at least 1 unit), integer arithmetic.
Every trial builds a fresh empty book (build time reported separately), then times ONLY the sell
(`process` of one MARKET_SELL: matching, state updates and fill-list construction included).
Per trial: makers touched (= fills), price levels visited (distinct fill prices), unfilled
remainder, and a sha256 of the fill list (A and B must give the same digest).

Protocol per (version, book, fraction): first trial timed; <= 60 s total -> it is the warm-up and
5 timed trials follow; > 60 s -> it is the only measurement. A trial is limited to 600 s (build +
sell). If a trial is stopped, the remaining fractions of the same book are recorded as not_run,
because they need the same construction.

    .venv/bin/python -m bench.liquidation
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import itertools
import json
import statistics
import time

import generate_orders
from bench import common
from bench.blocks import canary_around, stamp
from bench.common import RESULTS, append_csv, read_csv
from bench.harness import run_limited
from lob import VERSIONS

RAW = RESULTS / "liquidation_raw.csv"
SUMMARY = RESULTS / "liquidation_summary.csv"
FRACTIONS = (("10%", 1, 10), ("100%", 1, 1), ("200%", 2, 1))
KEYS = ["version", "book", "levels", "bids", "fraction"]
STAMP = ["start_utc", "power_source", "battery_percent", "low_power_mode"]
RAW_FIELDS = STAMP + KEYS + ["sale_qty_units", "total_bid_qty_units", "phase", "repeat", "status",
                     "build_seconds", "sell_seconds", "fills", "makers_touched", "price_levels_visited",
                     "unfilled_qty_units", "fills_digest", "limit_seconds"]
SUMMARY_FIELDS = STAMP + KEYS + ["status", "reason", "repeats", "sale_qty_units", "total_bid_qty_units",
                         "median_sell_seconds", "min_sell_seconds", "max_sell_seconds",
                         "median_build_seconds", "fills", "makers_touched", "price_levels_visited",
                         "unfilled_qty_units", "fills_digest"]
BOOKS = {"buildup": 1000, "crowded": 4}


def bid_events(scenario: str, n: int) -> list[dict]:
    """The first n BUY LIMIT events of the generator stream (seq increasing, with gaps)."""
    stream = generate_orders.events(scenario, 4 * n + 100, 42, 1000)
    return list(itertools.islice((r for r in stream if r["type"] == "LIMIT" and r["side"] == "BUY"),
                                 n))


def sale_quantity(total: int, num: int, den: int) -> int:
    """ceil(total * num / den), at least 1 (integers only)."""
    return max(1, -(-total * num // den))


def _replay_build(cls, rows):
    book = cls()
    process = book.process
    for e in rows:
        process(e)
    return book


def _trial(cls, rows, sale_event, conn, tag) -> dict:
    gc.collect()                       # gc stays enabled (as in the timing runs)
    conn.send(("phase", tag, "build"))
    t0 = time.perf_counter()
    book = _replay_build(cls, rows)
    t1 = time.perf_counter()
    conn.send(("phase", tag, "sell"))
    t2 = time.perf_counter()
    result = book.process(sale_event)
    t3 = time.perf_counter()
    fills = result["fills"]
    return {"build_s": t1 - t0, "sell_s": t3 - t2, "fills": len(fills), "makers": len(fills),
            "levels": len({f["price_ticks"] for f in fills}),
            "unfilled": result["unfilled_qty_units"], "status": result["status"],
            "digest": hashlib.sha256(json.dumps(fills, sort_keys=True).encode()).hexdigest()}


def liquidation_worker(conn, version: str, scenario: str, n: int, slow_first_s: float,
                       repeats: int) -> None:
    rows = bid_events(scenario, n)
    total = sum(r["qty_units"] for r in rows)
    cls = VERSIONS[version]
    conn.send(("book", len(rows), total))
    for name, num, den in FRACTIONS:
        qty = sale_quantity(total, num, den)
        sale = {"seq": rows[-1]["seq"] + 1, "event_id": "liq", "type": "MARKET_SELL",
                "order_id": "liq", "qty_units": qty}
        conn.send(("fraction", name, qty))
        tag = f"{name}:first"
        conn.send(("unit_start", tag))
        first = _trial(cls, rows, sale, conn, tag)
        conn.send(("unit_done", tag, first))
        if first["build_s"] + first["sell_s"] > slow_first_s:
            conn.send(("mode", name, "single"))
            continue
        conn.send(("mode", name, "warmup"))
        for r in range(repeats):
            tag = f"{name}:timed{r}"
            conn.send(("unit_start", tag))
            conn.send(("unit_done", tag, _trial(cls, rows, sale, conn, tag)))


def run_book(version, scenario, levels, n, limit_s, slow_first_s, repeats) -> None:
    base = {**stamp(), "version": version, "book": scenario, "levels": levels, "bids": n}
    res = run_limited(liquidation_worker, (version, scenario, n, slow_first_s, repeats), limit_s)
    qty, mode, trials, phase_at_stop = {}, {}, {}, None
    total = None
    for m in res["messages"]:
        if m[0] == "book":
            total = m[2]
        elif m[0] == "fraction":
            qty[m[1]] = m[2]
        elif m[0] == "mode":
            mode[m[1]] = m[2]
        elif m[0] == "unit_done":
            trials[m[1]] = m[2]
        elif m[0] == "phase":
            phase_at_stop = (m[1], m[2])
    stopped_fraction = res["stopped_tag"].split(":")[0] if res["stopped_tag"] else None
    blocked = False
    for name, _, _ in FRACTIONS:
        key = {**base, "fraction": name}
        if blocked or (res["outcome"] == "error" and name not in qty):
            append_csv(SUMMARY, SUMMARY_FIELDS, {**key, "status": "not_run", "reason":
                       (f"construction/trial of fraction {stopped_fraction} was stopped at the "
                        f"{limit_s:g} s limit; same book" if blocked else res["error"])})
            continue
        rows, ok = [], []
        first = trials.get(f"{name}:first")
        if first:
            rows.append(("single" if mode.get(name) == "single" else "warmup", 0, first))
        for r in range(common.TIMED_REPEATS):
            t = trials.get(f"{name}:timed{r}")
            if t:
                rows.append(("timed", r, t))
        for phase, rep, t in rows:
            append_csv(RAW, RAW_FIELDS, {**key, "sale_qty_units": qty[name],
                       "total_bid_qty_units": total, "phase": phase, "repeat": rep, "status": "ok",
                       "build_seconds": t["build_s"], "sell_seconds": t["sell_s"], "fills": t["fills"],
                       "makers_touched": t["makers"], "price_levels_visited": t["levels"],
                       "unfilled_qty_units": t["unfilled"], "fills_digest": t["digest"],
                       "limit_seconds": limit_s})
        timed = [t for phase, _, t in rows if phase in ("timed", "single")]
        summary = {**key, "status": "ok", "repeats": len(timed), "total_bid_qty_units": total}
        if name in qty:
            summary["sale_qty_units"] = qty[name]
        if res["outcome"] == "stopped" and name == stopped_fraction:
            summary.update(status="stopped", reason=(
                f"trial reached the {limit_s:g} s limit during {phase_at_stop[1] if phase_at_stop else '?'}"
                f"; events done {res['events_done']}"))
            append_csv(RAW, RAW_FIELDS, {**key, "sale_qty_units": qty.get(name),
                       "total_bid_qty_units": total, "phase": "single" if mode.get(name) is None
                       else "timed", "repeat": 0, "status": "stopped",
                       "build_seconds": "", "sell_seconds": res["stopped_after_s"],
                       "limit_seconds": limit_s})
            blocked = True
        elif res["outcome"] == "error":
            summary.update(status="error", reason=res["error"])
        if timed:
            sells = [t["sell_s"] for t in timed]
            summary.update(median_sell_seconds=statistics.median(sells), min_sell_seconds=min(sells),
                           max_sell_seconds=max(sells),
                           median_build_seconds=statistics.median(t["build_s"] for t in timed),
                           fills=timed[0]["fills"],
                           makers_touched=timed[0]["makers"], price_levels_visited=timed[0]["levels"],
                           unfilled_qty_units=timed[0]["unfilled"], fills_digest=timed[0]["digest"])
        append_csv(SUMMARY, SUMMARY_FIELDS, summary)
        print(version, scenario, n, name, summary["status"], summary.get("median_sell_seconds", ""),
              flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--sizes", nargs="+", type=int, default=[10000, 100000])
    parser.add_argument("--books", nargs="+", default=["buildup"], choices=sorted(BOOKS))
    parser.add_argument("--versions", nargs="+", default=["A", "B"])
    parser.add_argument("--limit-seconds", type=float, default=common.LIMIT_SECONDS)
    parser.add_argument("--slow-first-seconds", type=float, default=common.SLOW_FIRST_SECONDS)
    parser.add_argument("--repeats", type=int, default=common.TIMED_REPEATS)
    args = parser.parse_args(argv)
    done = {(r["version"], r["book"], r["bids"]) for r in read_csv(SUMMARY)}
    for n in args.sizes:
        todo = [(sc, v) for sc in args.books for v in args.versions
                if (v, sc, str(n)) not in done]
        if not todo:
            continue
        with canary_around(f"liquidation_{n}"):
            for scenario, version in todo:
                run_book(version, scenario, BOOKS[scenario], n, args.limit_seconds,
                         args.slow_first_seconds, args.repeats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
