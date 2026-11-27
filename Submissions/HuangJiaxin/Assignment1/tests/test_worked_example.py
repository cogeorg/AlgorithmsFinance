"""The course's worked example: six BTC sold into four resting buyers."""
import json
from pathlib import Path

from lob.events_io import read_events

DATA = Path(__file__).resolve().parents[1] / "data" / "supplied"


def test_worked_example_matches_expected(book):
    events = read_events(DATA / "worked_example.jsonl")
    expected = json.loads((DATA / "worked_expected.json").read_text())
    results = [book.process(e) for e in events]

    assert [r["status"] for r in results[:5]] == ["resting"] * 5
    sell = results[-1]
    want = expected["market_sell_result"]
    for key in ["event_id", "order_id", "status", "unfilled_qty_units", "fills"]:
        assert sell[key] == want[key], key

    snap = book.snapshot()
    assert snap["bids"] + snap["asks"] == expected["remaining_orders"]


def test_worked_example_proceeds(book):
    events = read_events(DATA / "worked_example.jsonl")
    sell = [book.process(e) for e in events][-1]
    gross = sum(f["price_ticks"] * f["qty_units"] for f in sell["fills"])
    assert gross == 3_594_000_000_000_000          # tick x unit
    assert gross / 10_000_000_000 == 359_400.0      # dollars
