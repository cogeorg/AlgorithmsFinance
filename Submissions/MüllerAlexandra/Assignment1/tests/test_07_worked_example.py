"""The supplied six-BTC example is checked without deriving it from either engine."""

import json
from pathlib import Path

from limit_order_book.interface import OrderBook
from limit_order_book.stream_io import iter_events


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA = PROJECT_ROOT / "data" / "supplied"


def test_supplied_worked_example(book: OrderBook) -> None:
    expected = json.loads((DATA / "worked_expected.json").read_text(encoding="utf-8"))

    results = [book.process_event(event) for event in iter_events(DATA / "worked_example.jsonl")]
    sell_result = results[-1]

    assert sell_result == expected["market_sell_result"]
    assert book.inspect_book() == expected["remaining_orders"]
    proceeds = sum(
        item["price_ticks"] * item["qty_units"] for item in sell_result["fills"]
    )
    assert proceeds == expected["gross_proceeds_tick_units"]

