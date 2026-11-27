"""Large-liquidation test (single runs, exploration).

Usage (from Assignment1/):
    python 04_benchmarks/liquidation.py --version a

Book: the first 80% of 00_instructions/data/sweep_10000.jsonl.gz (8,000
LIMIT events; buys and sells that never cross). Its total bid quantity Q
is the sum of resting BUY quantities.

Sales: one MARKET_SELL of 10% (ceil, at least 1 unit), 100% and 200% of Q.
Each sale runs on its OWN freshly built book, so no sale reuses a depleted
book. Per sale two timings with time.perf_counter, one run each:
  build_seconds: replaying the 8,000 build events on a fresh book
  sell_seconds:  process_event(market sell): validation, matching, state
                 updates and fill-list construction

Writes 05_results/liquidation_version_<v>.csv.
"""

import argparse
import csv
import importlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "03_code"))

from replay import load_events  # noqa: E402

SOURCE = ROOT / "00_instructions" / "data" / "sweep_10000.jsonl.gz"
SALE_PCTS = [10, 100, 200]
FIELDS = ["version", "scenario", "seed", "book_events", "bid_orders",
          "bid_price_levels", "bid_qty_units", "sale_pct", "requested_qty_units",
          "fills", "makers_touched", "price_levels_visited", "sold_qty_units",
          "unfilled_qty_units", "status", "build_seconds", "sell_seconds"]


def build(version, events):
    book = importlib.import_module(f"lob_{version}").OrderBook()
    start = time.perf_counter()
    for e in events:
        book.process_event(e)
    return book, time.perf_counter() - start


def requested_qty(pct, total):
    return max(1, -(-total * pct // 100))  # integer ceil, at least 1 unit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", choices=["a", "b_sorted", "b_heap"], required=True)
    args = parser.parse_args()

    events = load_events(SOURCE)
    book_events = events[: len(events) * 4 // 5]
    assert all(e["type"] == "LIMIT" for e in book_events)
    next_seq = book_events[-1]["seq"] + 1

    rows = []
    for pct in SALE_PCTS:
        book, build_s = build(args.version, book_events)
        bids = [o for o in book.inspect_book() if o["side"] == "BUY"]
        total = sum(o["qty_units"] for o in bids)
        qty = requested_qty(pct, total)
        sale = {"seq": next_seq, "event_id": f"liquidation_{pct}pct",
                "type": "MARKET_SELL", "order_id": f"liq_{pct}pct", "qty_units": qty}

        start = time.perf_counter()
        result = book.process_event(sale)
        sell_s = time.perf_counter() - start

        fills = result["fills"]
        sold = sum(f["qty_units"] for f in fills)
        # Conservation and sanity checks (outside timing).
        assert sold + result["unfilled_qty_units"] == qty
        bids_after = sum(o["qty_units"] for o in book.inspect_book() if o["side"] == "BUY")
        assert bids_after == total - sold
        if pct >= 100:
            assert bids_after == 0 and sold == total

        rows.append({
            "version": args.version, "scenario": "sweep", "seed": 42,
            "book_events": len(book_events),
            "bid_orders": len(bids),
            "bid_price_levels": len({o["price_ticks"] for o in bids}),
            "bid_qty_units": total,
            "sale_pct": pct,
            "requested_qty_units": qty,
            "fills": len(fills),
            "makers_touched": len({f["maker_id"] for f in fills}),
            "price_levels_visited": len({f["price_ticks"] for f in fills}),
            "sold_qty_units": sold,
            "unfilled_qty_units": result["unfilled_qty_units"],
            "status": result["status"],
            "build_seconds": f"{build_s:.6f}",
            "sell_seconds": f"{sell_s:.6f}",
        })
        print(" ".join(f"{k}={rows[-1][k]}" for k in FIELDS), flush=True)

    out = ROOT / "05_results" / f"liquidation_version_{args.version}.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
