"""Fixed-book 10%, 100%, and 200% large-sell experiments."""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
import time
from pathlib import Path

from lob import make_book


FIELDS = [
    "version",
    "seed",
    "initial_orders",
    "available_prices",
    "sale_percent",
    "repeat",
    "construction_seconds",
    "sell_seconds",
    "requested_qty_units",
    "available_bid_qty_units",
    "fill_count",
    "makers_touched",
    "price_levels_visited",
    "unfilled_qty_units",
]


def bid_events(count: int, levels: int, seed: int):
    rng = random.Random(seed)
    rows = []
    for seq in range(1, count + 1):
        rows.append(
            {
                "seq": seq,
                "event_id": f"b{seq}",
                "type": "LIMIT",
                "order_id": f"b{seq}",
                "side": "BUY",
                "price_ticks": 6_000_000 - rng.randrange(levels),
                "qty_units": rng.randint(1, 100) * 1_000_000,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initial-orders", type=int, default=10000)
    parser.add_argument("--price-levels", nargs="+", type=int, default=[4, 1000])
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("results/liquidation_results.csv"))
    args = parser.parse_args()

    rows = []
    for seed in args.seeds:
        for levels in args.price_levels:
            source = bid_events(args.initial_orders, levels, seed)
            total_qty = sum(event["qty_units"] for event in source)
            for version in ("A", "B"):
                for percent in (10, 100, 200):
                    sale_qty = max(1, math.ceil(total_qty * percent / 100))
                    for repeat in range(1, args.repeats + 1):
                        # Construction is primary timing, so heavy operation counters
                        # are enabled only for the separately timed sell.
                        book = make_book(version, instrument=False)
                        construction_start = time.perf_counter()
                        for event in source:
                            book.process_event(event)
                        construction_seconds = time.perf_counter() - construction_start
                        book.instrument = True
                        sell = {
                            "seq": len(source) + 1,
                            "event_id": "large-sell",
                            "type": "MARKET_SELL",
                            "order_id": "large-sell",
                            "qty_units": sale_qty,
                        }
                        before = dict(book.operation_counts)
                        sell_start = time.perf_counter()
                        result = book.process_event(sell)
                        sell_seconds = time.perf_counter() - sell_start
                        fills = result["fills"]
                        rows.append(
                            {
                                "version": book.version,
                                "seed": seed,
                                "initial_orders": args.initial_orders,
                                "available_prices": levels,
                                "sale_percent": percent,
                                "repeat": repeat,
                                "construction_seconds": f"{construction_seconds:.9f}",
                                "sell_seconds": f"{sell_seconds:.9f}",
                                "requested_qty_units": sale_qty,
                                "available_bid_qty_units": total_qty,
                                "fill_count": len(fills),
                                "makers_touched": book.operation_counts["maker_orders_touched"] - before["maker_orders_touched"],
                                "price_levels_visited": len({fill["price_ticks"] for fill in fills}),
                                "unfilled_qty_units": result["unfilled_qty_units"],
                            }
                        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(args.output)


if __name__ == "__main__":
    main()
