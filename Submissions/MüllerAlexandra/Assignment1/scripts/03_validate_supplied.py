"""Replay every supplied workload and validate its final canonical book."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from limit_order_book import BaselineOrderBook, RevisedOrderBook
from limit_order_book.interface import OrderBook
from limit_order_book.stream_io import iter_events


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data" / "supplied"
IMPLEMENTATIONS = {
    "baseline": BaselineOrderBook,
    "revised": RevisedOrderBook,
}


def validate_snapshot(snapshot: list[dict[str, object]]) -> None:
    """Check representation invariants visible through the public interface."""

    identifiers = [order["order_id"] for order in snapshot]
    if len(identifiers) != len(set(identifiers)):
        raise AssertionError("an active identifier appears more than once")
    if any(order["qty_units"] <= 0 for order in snapshot):
        raise AssertionError("a resting order has nonpositive quantity")

    bids = [order["price_ticks"] for order in snapshot if order["side"] == "BUY"]
    asks = [order["price_ticks"] for order in snapshot if order["side"] == "SELL"]
    if bids and asks and max(bids) >= min(asks):
        raise AssertionError("the final resting book is crossed")


def replay_file(path: Path, book: OrderBook) -> dict[str, object]:
    """Replay one supplied stream and return its validation summary."""

    results = [book.process_event(event) for event in iter_events(path)]
    rejected = sum(result["status"] == "rejected" for result in results)
    snapshot = book.inspect_book()
    validate_snapshot(snapshot)
    if len(results) != 10_000:
        raise AssertionError(f"{path.name} contains {len(results)} events, expected 10000")
    if rejected:
        raise AssertionError(f"{path.name} produced {rejected} rejected valid events")
    return {
        "file": path.name,
        "events": len(results),
        "rejected": rejected,
        "active_orders_final": len(snapshot),
        "bid_orders_final": sum(order["side"] == "BUY" for order in snapshot),
        "ask_orders_final": sum(order["side"] == "SELL" for order in snapshot),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", choices=sorted(IMPLEMENTATIONS), default="baseline"
    )
    parser.add_argument(
        "--file",
        help="Validate one supplied filename instead of all *_10000.jsonl.gz files",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    factory = IMPLEMENTATIONS[args.version]
    paths = [DATA_DIR / args.file] if args.file else sorted(
        DATA_DIR.glob("*_10000.jsonl.gz")
    )
    summaries = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        print(f"validating {path.name}", flush=True)
        summary = replay_file(path, factory())
        summaries.append(summary)
        print(json.dumps(summary, sort_keys=True), flush=True)
    print(json.dumps({"version": args.version, "workloads": summaries}, indent=2))


if __name__ == "__main__":
    main()
