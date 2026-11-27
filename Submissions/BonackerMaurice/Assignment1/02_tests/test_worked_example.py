"""Hand-calculated test 1: the worked example.

Expected values come from Maurice's independent hand calculation in
01_my_notes/OrderBookTests.xlsx (Sheet1), summarised in AGENTS.md section 8.
They are NOT derived from any implementation. The Excel works in BTC and
dollars; here they are written in integer units:
    1 BTC = 100_000_000 qty_units, $1 = 100 price_ticks.

A second, separate check compares against the supplied
00_instructions/data/worked_expected.json.

Every version listed in conftest.VERSIONS must pass the same tests.
"""

import json
from pathlib import Path

import pytest

# Expected values typed from the Excel tab "Base" (formerly Sheet1).
pytestmark = pytest.mark.source("my Excel tab Base")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "00_instructions" / "data"

BTC = 100_000_000  # qty_units per BTC
USD = 100          # price_ticks per dollar
TICK_UNITS_PER_USD = 10**10  # proceeds in dollars = sum(p * q) / 10**10

# --- Maurice's hand calculation (OrderBookTests.xlsx) -----------------------

# Rows 2-6, column J "Executes on Arrival" = 0 for every limit:
# none of the five limits trades on arrival, so each rests in full.
EXPECTED_LIMIT_RESULTS = [
    {"event_id": "event1", "order_id": "b1", "status": "resting",
     "unfilled_qty_units": 1 * BTC, "fills": []},
    {"event_id": "event2", "order_id": "b2", "status": "resting",
     "unfilled_qty_units": 1 * BTC, "fills": []},
    {"event_id": "event3", "order_id": "b3", "status": "resting",
     "unfilled_qty_units": 3 * BTC, "fills": []},
    {"event_id": "event4", "order_id": "b4", "status": "resting",
     "unfilled_qty_units": 5 * BTC, "fills": []},
    {"event_id": "event5", "order_id": "a1", "status": "resting",
     "unfilled_qty_units": 2 * BTC, "fills": []},
]

# Column M "Fill in from Market Sell" (BTC) at column I prices (dollars),
# queue order from column K. Summary row 10: 4 steps, 6 sold, 0 unfilled,
# status "filled".
EXPECTED_SELL_RESULT = {
    "event_id": "event6",
    "order_id": "s1",
    "status": "filled",
    "unfilled_qty_units": 0,
    "fills": [
        {"maker_id": "b1", "taker_id": "s1",
         "price_ticks": 60_000 * USD, "qty_units": 1 * BTC},
        {"maker_id": "b2", "taker_id": "s1",
         "price_ticks": 60_000 * USD, "qty_units": 1 * BTC},
        {"maker_id": "b3", "taker_id": "s1",
         "price_ticks": 59_900 * USD, "qty_units": 3 * BTC},
        {"maker_id": "b4", "taker_id": "s1",
         "price_ticks": 59_700 * USD, "qty_units": 1 * BTC},
    ],
}

# Column N "Remaining Order": b4 keeps 4 BTC, a1 keeps 2 BTC; arrival seq
# from column A. Bids (price desc, seq) first, then asks (price asc, seq).
EXPECTED_BOOK = [
    {"order_id": "b4", "side": "BUY", "price_ticks": 59_700 * USD,
     "qty_units": 4 * BTC, "arrival_seq": 4},
    {"order_id": "a1", "side": "SELL", "price_ticks": 60_100 * USD,
     "qty_units": 2 * BTC, "arrival_seq": 5},
]

EXPECTED_PROCEEDS_USD = 359_400    # F10 / B20
EXPECTED_AVERAGE_PRICE_USD = 59_900  # G10
EXPECTED_STEPS = 4                 # B10 / B13
EXPECTED_SUBMITTED_BUY_BTC = 10    # B15
EXPECTED_TRADED_BTC = 6            # B14
EXPECTED_REMAINING_BID_BTC = 4     # B16
EXPECTED_REMAINING_ASK_BTC = 2     # B17
EXPECTED_OPEN_ORDERS = 2           # B18
EXPECTED_DISCARDED_BTC = 0         # B19


# --- helpers -----------------------------------------------------------------

def load_events():
    path = DATA / "worked_example.jsonl"
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def load_supplied_expected():
    with (DATA / "worked_expected.json").open(encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def replayed(lob):
    """Replay the worked example on a fresh book; return (events, results, book)."""
    book = lob.OrderBook()
    events = load_events()
    results = [book.process_event(event) for event in events]
    return events, results, book


# --- check 1: Maurice's hand calculation ------------------------------------

def test_limits_rest_without_trading(replayed):
    _, results, _ = replayed
    assert results[:5] == EXPECTED_LIMIT_RESULTS


def test_market_sell_result(replayed):
    _, results, _ = replayed
    assert results[5] == EXPECTED_SELL_RESULT


def test_remaining_book(replayed):
    _, _, book = replayed
    assert book.inspect_book() == EXPECTED_BOOK


def test_proceeds_and_average_price(replayed):
    _, results, _ = replayed
    fills = results[5]["fills"]
    gross = sum(f["price_ticks"] * f["qty_units"] for f in fills)
    sold = sum(f["qty_units"] for f in fills)
    # Integer check: proceeds in tick-units, no floats.
    assert gross == EXPECTED_PROCEEDS_USD * TICK_UNITS_PER_USD
    # Average price = gross / sold, exact in ticks.
    assert gross % sold == 0
    assert gross // sold == EXPECTED_AVERAGE_PRICE_USD * USD


def test_book_level_conservation(replayed):
    """Maurice's Excel conservation check (B21) plus the summary counts."""
    events, results, book = replayed
    sell = results[5]
    fills = sell["fills"]
    remaining = book.inspect_book()

    submitted_buy = sum(e["qty_units"] for e in events
                        if e["type"] == "LIMIT" and e["side"] == "BUY")
    traded = sum(f["qty_units"] for f in fills)
    resting_bids = sum(o["qty_units"] for o in remaining if o["side"] == "BUY")
    resting_asks = sum(o["qty_units"] for o in remaining if o["side"] == "SELL")

    assert submitted_buy == EXPECTED_SUBMITTED_BUY_BTC * BTC
    assert traded == EXPECTED_TRADED_BTC * BTC
    assert resting_bids == EXPECTED_REMAINING_BID_BTC * BTC
    assert resting_asks == EXPECTED_REMAINING_ASK_BTC * BTC
    # 10 BTC of limit buys = 6 traded + 4 still resting on the bids.
    assert submitted_buy == traded + resting_bids

    # Market sell 6 BTC = 6 sold + 0 discarded; the residual never rests.
    market_qty = events[5]["qty_units"]
    assert market_qty == traded + sell["unfilled_qty_units"]
    assert sell["unfilled_qty_units"] == EXPECTED_DISCARDED_BTC * BTC
    assert all(o["order_id"] != "s1" for o in remaining)

    assert len(fills) == EXPECTED_STEPS
    assert len(remaining) == EXPECTED_OPEN_ORDERS
    assert [o["order_id"] for o in remaining] == ["b4", "a1"]


# --- check 2: the supplied worked_expected.json -----------------------------

@pytest.mark.source("my Excel tab Base vs professor JSON")
def test_hand_values_agree_with_supplied_json():
    """Excel and JSON must agree; this needs no implementation."""
    supplied = load_supplied_expected()
    assert supplied["market_sell_result"] == EXPECTED_SELL_RESULT
    assert supplied["remaining_orders"] == EXPECTED_BOOK
    assert supplied["gross_proceeds_tick_units"] == (
        EXPECTED_PROCEEDS_USD * TICK_UNITS_PER_USD)
    assert supplied["gross_proceeds_usd"] == f"{EXPECTED_PROCEEDS_USD}.00"


@pytest.mark.source("professor JSON")
def test_matches_supplied_json(replayed):
    _, results, book = replayed
    supplied = load_supplied_expected()
    assert results[5] == supplied["market_sell_result"]
    assert book.inspect_book() == supplied["remaining_orders"]
    gross = sum(f["price_ticks"] * f["qty_units"] for f in results[5]["fills"])
    assert gross == supplied["gross_proceeds_tick_units"]
    assert f"{gross / TICK_UNITS_PER_USD:.2f}" == supplied["gross_proceeds_usd"]
