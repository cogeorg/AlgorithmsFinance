"""The timing experiments. Run from the Assignment1 folder:

    python -m bench.experiments              # full grid (about 30 minutes on a laptop)
    python -m bench.experiments --quick      # small grid to check that everything runs
    python -m bench.experiments --million    # also the 1,000,000-event streams

Writes results/*.csv and results/timing_environment.json. Each table has one row per
raw repeat (or one row with status "stopped" if the declared time limit was exceeded).

Experiments (assignment README, "Benchmark experiments"):
  replay         all five workloads: input parsing and engine replay, separately
  liquidation    one fresh bid book; market sells of 10 %, 100 % and 200 % of its bid quantity
  concentration  same order count, 4 versus 1,000 price levels per side; speed and correctness
  churn          cancellation churn: time with and without version B's compaction
"""
import argparse
import math

from lob.book_a import OrderBookA
from lob.book_b import OrderBookB
from lob.events_io import read_events

from .common import (REPEATS, TIME_LIMIT_S, VERSIONS, Stopped, book_peaks, dataset,
                     environment, replay, replay_with_limit, timed, write_csv, write_json)

SCENARIOS = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]
SEEDS = [42, 43, 44]


def _versions(extra_lazy=False):
    v = dict(VERSIONS)
    if extra_lazy:
        v["B_nocompact"] = lambda: OrderBookB(compact=False)
    return v


# ------------------------------------------------------------------ 1. replay
def exp_replay(sizes, seeds, scenarios=SCENARIOS, levels=1000, experiment="replay",
               extra_lazy=False):
    rows = []
    for scenario in scenarios:
        for m in sizes:
            for seed in seeds:
                path = dataset(scenario, m, seed, levels)
                events = read_events(path)                       # warm-up of the reader
                peak_o, peak_l, end_o, end_l = book_peaks(events)
                common = [experiment, scenario, seed, m, levels, peak_o, peak_l, end_o, end_l]
                for rep in range(REPEATS):                       # input reading + parsing
                    t, _ = timed(lambda: read_events(path))
                    rows.append(common + ["-", "parse", rep, t, len(events) / t, "ok", ""])
                for name, make in _versions(extra_lazy).items():
                    try:
                        replay_with_limit(make(), events)        # untimed warm-up with limit
                    except Stopped as s:
                        rows.append(common + [name, "replay", "-", "", "", "stopped",
                                              f"warm-up exceeded {TIME_LIMIT_S:g} s limit: {s}"])
                        print(f"{experiment} {scenario} M={m} seed={seed} {name}: STOPPED ({s})")
                        continue
                    times = []
                    for rep in range(REPEATS):
                        book = make()                            # fresh empty book each time
                        t, _ = timed(lambda: replay(book, events))
                        times.append(t)
                        rows.append(common + [name, "replay", rep, t, m / t, "ok", ""])
                    print(f"{experiment} {scenario} M={m} seed={seed} {name}: "
                          f"median {sorted(times)[2] * 1e3:.1f} ms")
    return rows


REPLAY_HEADER = ["experiment", "scenario", "seed", "events", "levels", "peak_active_orders",
                 "peak_price_levels", "end_active_orders", "end_price_levels", "version",
                 "phase", "repeat", "elapsed_s", "events_per_s", "status", "note"]


# ------------------------------------------------------------------ 2. liquidation
def exp_liquidation(sizes, seed=42, fractions=(0.10, 1.00, 2.00)):
    rows, results = [], {}
    for m in sizes:
        events = read_events(dataset("buildup", m, seed))
        ref = OrderBookB()
        replay(ref, events)
        bids = ref.snapshot()["bids"]
        available = sum(o["qty_units"] for o in bids)
        best_bid = bids[0]["price_ticks"] if bids else None
        for frac in fractions:
            qty = max(1, math.ceil(available * frac))            # 10 % rounded up, >= 1 unit
            sell = {"seq": m + 1, "event_id": f"liq{m}", "type": "MARKET_SELL",
                    "order_id": f"liq{m}", "qty_units": qty}
            for name, make in VERSIONS.items():
                common = ["liquidation", "buildup", seed, m, len(bids), available, frac, qty, name]
                try:
                    replay_with_limit(make(), events)            # warm-up of the construction
                except Stopped as s:
                    rows.append(common + ["-", "", "", "", "", "", "", "", "", "", "", "", "stopped",
                                          f"construction exceeded {TIME_LIMIT_S:g} s limit: {s}"])
                    print(f"liquidation M={m} {frac:.0%} {name}: STOPPED")
                    continue
                for rep in range(-1, REPEATS):                   # rep -1 = untimed warm-up
                    book = make()                                # fresh book: never reuse a depleted one
                    t_build, _ = timed(lambda: replay(book, events))
                    t_sell, r = timed(lambda: book.fill_market_sell(sell))
                    if rep < 0:
                        continue
                    fills = r["fills"]
                    filled = sum(f["qty_units"] for f in fills)
                    gross = sum(f["price_ticks"] * f["qty_units"] for f in fills)   # integers
                    vwap = gross / filled if filled else None                     # display only
                    worst = min((f["price_ticks"] for f in fills), default=None)
                    rows.append(common + [rep, t_build, t_sell, len(fills),
                                          len({f["maker_id"] for f in fills}),
                                          len({f["price_ticks"] for f in fills}),
                                          filled, r["unfilled_qty_units"], gross, best_bid,
                                          vwap, worst, r["status"], ""])
                    results.setdefault((m, frac), {})[name] = r
                print(f"liquidation M={m} {frac:.0%} {name}: done")
    agree = [[m, frac, int(len(v) == 2 and v["A"] == v["B"]) if len(v) == 2 else "",
              ",".join(sorted(v))] for (m, frac), v in results.items()]
    return rows, agree


LIQ_HEADER = ["experiment", "scenario", "seed", "events", "bid_orders", "available_bid_units",
              "fraction", "requested_units", "version", "repeat", "construction_s", "sale_s",
              "fill_count", "makers_touched", "price_levels_visited", "filled_units",
              "unfilled_units", "gross_tick_units", "best_bid_ticks", "vwap_ticks",
              "worst_fill_ticks", "status", "note"]


# ------------------------------------------------------------------ 3. concentration checks
def concentration_correctness(sizes, seeds):
    """Same order count, 4 vs 1,000 levels: A and B agree, and a full liquidation of the
    resulting bid book follows price-time priority (fills by price, then arrival)."""
    out = []
    for m in sizes:
        for seed in seeds:
            for levels in (4, 1000):
                events = read_events(dataset("buildup", m, seed, levels))
                b = OrderBookB()
                replay(b, events)
                bids = b.snapshot()["bids"]
                arrival = {o["order_id"]: (-o["price_ticks"], o["arrival_seq"]) for o in bids}
                sale = b.fill_market_sell({"seq": m + 1, "event_id": "x", "type": "MARKET_SELL",
                                           "order_id": "x", "qty_units": sum(o["qty_units"] for o in bids)})
                order = [arrival[f["maker_id"]] for f in sale["fills"]]
                fifo_ok = order == sorted(order) and len(order) == len(bids)
                a_ok = ""
                if m <= 10_000:                                  # A within the time limit
                    a = OrderBookA()
                    replay(a, events)
                    b2 = OrderBookB()
                    replay(b2, events)
                    a_ok = int(a.snapshot() == b2.snapshot())
                out.append(["concentration", "buildup", seed, m, levels, len(bids),
                            len({o["price_ticks"] for o in bids}), int(fifo_ok), a_ok])
    return out


CONC_HEADER = ["experiment", "scenario", "seed", "events", "levels", "bid_orders",
               "bid_price_levels", "full_sale_follows_price_time", "versions_agree_on_book"]


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--million", action="store_true")
    ap.add_argument("--million-only", action="store_true",
                    help="only the 1,000,000-event streams; writes results/timing_million_raw.csv")
    args = ap.parse_args()
    if args.million_only:
        rows = exp_replay([1_000_000], [42], scenarios=["buildup", "mixed", "cancel_churn"],
                          experiment="replay_million")
        write_csv("timing_million_raw.csv", REPLAY_HEADER, rows)
        write_json("timing_million_environment.json", environment(
            "bench/experiments.py --million-only", sizes=[1_000_000], seeds=[42],
            scenarios=["buildup", "mixed", "cancel_churn"], levels=1000))
        print("saved results/timing_million_raw.csv, timing_million_environment.json")
        return
    sizes = [1_000, 10_000] if args.quick else [1_000, 10_000, 100_000]
    seeds = [42] if args.quick else SEEDS

    rows = exp_replay(sizes, seeds)
    if args.million:
        rows += exp_replay([1_000_000], [42], scenarios=["buildup", "mixed", "cancel_churn"],
                           experiment="replay_million")
    conc_sizes = [10_000] if args.quick else [10_000, 100_000]
    rows += exp_replay(conc_sizes, seeds, scenarios=["buildup"], levels=4,
                       experiment="concentration")
    rows += exp_replay(sizes, seeds, scenarios=["cancel_churn"], experiment="churn",
                       extra_lazy=True)
    write_csv("timing_raw.csv", REPLAY_HEADER, rows)

    liq_rows, liq_agree = exp_liquidation(sizes)
    write_csv("liquidation_raw.csv", LIQ_HEADER, liq_rows)
    write_csv("liquidation_versions_agree.csv", ["events", "fraction", "results_identical",
                                                  "versions_run"], liq_agree)

    write_csv("concentration_correctness.csv", CONC_HEADER,
              concentration_correctness(conc_sizes, seeds))

    write_json("timing_environment.json", environment(
        "bench/experiments.py", sizes=sizes, seeds=seeds, scenarios=SCENARIOS,
        million=args.million, quick=args.quick, levels=1000, concentration_levels=[4, 1000],
        liquidation={"scenario": "buildup", "seed": 42, "fractions": [0.1, 1.0, 2.0]},
        units={"elapsed_s": "seconds per complete replay or sale", "events_per_s": "throughput",
               "qty": "1e-8 BTC units", "price": "0.01 USD ticks"}))
    print("saved results/timing_raw.csv, liquidation_raw.csv, liquidation_versions_agree.csv, "
          "concentration_correctness.csv, timing_environment.json")


if __name__ == "__main__":
    main()
