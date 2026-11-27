import json
from pathlib import Path
import os
if os.environ.get("ORDERBOOK_VERSION", "A") == "B":
    from orderbook.version_b import OrderBook
else:
    from orderbook.version_a import OrderBook

BTC = 100_000_000
DATA = Path(__file__).parent.parent / "data"

def test_one_limit_buy_rests_on_empty_book():
    book = OrderBook()

    event = {"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
             "side": "BUY", "price_ticks": 6_000_000, "qty_units": 100_000_000}

    result = book.process_event(event)

    assert result["status"] == "resting"
    assert result["unfilled_qty_units"] == 1 * BTC
    assert result["fills"] == []
    assert book.snapshot() == [
        {"order_id": "b1", "side": "BUY", "price_ticks": 6_000_000,
         "qty_units": 100_000_000, "arrival_seq": 1}
    ]
def test_limit_sell_crosses_resting_buy():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})

    result = book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "a1",
                                 "side": "SELL", "price_ticks": 5_990_000, "qty_units": 1 * BTC})

    assert result["status"] == "filled"
    assert result["unfilled_qty_units"] == 0
    assert result["fills"] == [
        {"maker_id": "b1", "taker_id": "a1", "price_ticks": 6_000_000, "qty_units": 100_000_000}
    ]
    assert book.snapshot() == []
def test_limit_sell_does_not_cross():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    result = book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "a1",
                                 "side": "SELL", "price_ticks": 6_010_000, "qty_units": 2 * BTC})
    assert result["status"] == "resting"
    assert result["unfilled_qty_units"] == 2 * BTC
    assert result["fills"] == []
    assert book.snapshot() == [
        {"order_id": "b1", "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC, "arrival_seq": 1},
        {"order_id": "a1", "side": "SELL", "price_ticks": 6_010_000, "qty_units": 2 * BTC, "arrival_seq": 2},
    ]
def test_one_limit_sell_rests_on_empty_book():
    book = OrderBook()

    event = {"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "a1",
             "side": "SELL", "price_ticks": 6_000_000, "qty_units": 100_000_000}

    result = book.process_event(event)

    assert result["status"] == "resting"
    assert result["unfilled_qty_units"] == 1 * BTC
    assert result["fills"] == []
    assert book.snapshot() == [
        {"order_id": "a1", "side": "SELL", "price_ticks": 6_000_000,
         "qty_units": 100_000_000, "arrival_seq": 1}]
def test_market_sell_on_empty_book():
    book = OrderBook()
    event = {"seq": 1, "event_id": "e1", "type": "MARKET_SELL",
             "order_id": "s1", "qty_units": 1 * BTC}
    result = book.process_event(event)
    assert result["status"] == "unfilled"
    assert result["unfilled_qty_units"] == 1 * BTC
    assert result["fills"] == []
    assert book.snapshot() == []
def test_market_sell_smaller_resting_buy():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 2 * BTC})

    result = book.process_event({"seq": 2, "event_id": "e2", "type": "MARKET_SELL", "order_id": "s1", "qty_units": 1 * BTC})

    assert result["status"] == "filled"
    assert result["unfilled_qty_units"] == 0
    assert result["fills"] == [
        {"maker_id": "b1", "taker_id": "s1", "price_ticks": 6_000_000, "qty_units": 1 * BTC}
    ]
    assert book.snapshot() == [
        {"order_id": "b1", "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC, "arrival_seq": 1}
    ]
def test_market_sell_equal_to_depth():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 2 * BTC})

    result = book.process_event({"seq": 2, "event_id": "e2", "type": "MARKET_SELL", "order_id": "s1", "qty_units": 2 * BTC})

    assert result["status"] == "filled"
    assert result["unfilled_qty_units"] == 0
    assert result["fills"] == [
        {"maker_id": "b1", "taker_id": "s1", "price_ticks": 6_000_000, "qty_units": 2 * BTC}
    ]
    assert book.snapshot() == []
def test_market_sell_larger_than_depth():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})

    result = book.process_event({"seq": 2, "event_id": "e2", "type": "MARKET_SELL", "order_id": "s1", "qty_units": 2 * BTC})

    assert result["status"] == "partial"
    assert result["unfilled_qty_units"] == 1 * BTC
    assert result["fills"] == [
        {"maker_id": "b1", "taker_id": "s1", "price_ticks": 6_000_000, "qty_units": 1 * BTC}
    ]
    assert book.snapshot() == []
def test_two_limit_buys_same_price_rest_in_arrival_order():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    result = book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "b2",
                                 "side": "BUY", "price_ticks": 6_000_000, "qty_units": 2 * BTC})

    assert result["status"] == "resting"
    assert result["unfilled_qty_units"] == 2 * BTC
    assert result["fills"] == []
    assert book.snapshot() == [
        {"order_id": "b1", "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC, "arrival_seq": 1},
        {"order_id": "b2", "side": "BUY", "price_ticks": 6_000_000, "qty_units": 2 * BTC, "arrival_seq": 2},
    ]
def test_two_limit_buys_same_price_rest_in_arrival_order():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    result = book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "b2",
                                 "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})

    assert result["status"] == "resting"
    assert result["unfilled_qty_units"] == 1 * BTC
    assert result["fills"] == []
    assert book.snapshot() == [
        {"order_id": "b1", "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC, "arrival_seq": 1},
        {"order_id": "b2", "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC, "arrival_seq": 2},
    ]
def test_multiple_makers_at_one_price_fifo():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "b2",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    result = book.process_event({"seq": 3, "event_id": "e3", "type": "MARKET_SELL",
                                 "order_id": "s1", "qty_units": 1 * BTC})

    assert result["status"] == "filled"
    assert result["unfilled_qty_units"] == 0
    assert result["fills"] == [
        {"maker_id": "b1", "taker_id": "s1", "price_ticks": 6_000_000, "qty_units": 1 * BTC}
    ]
    assert book.snapshot() == [
        {"order_id": "b2", "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC, "arrival_seq": 2},
    ]
def test_limit_sell_fills_limit_buy_order():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "b2",
                        "side": "BUY", "price_ticks": 5_990_000, "qty_units": 1 * BTC})
    result = book.process_event({"seq": 3, "event_id": "e3", "type": "LIMIT",
                                 "order_id": "a1","side": "SELL", "price_ticks": 6_000_000, "qty_units": 1 * BTC})

    assert result["status"] == "filled"
    assert result["unfilled_qty_units"] == 0
    assert result["fills"] == [
        {"maker_id": "b1", "taker_id": "a1", "price_ticks": 6_000_000, "qty_units": 1 * BTC}
    ]
    assert book.snapshot() == [
        {"order_id": "b2", "side": "BUY", "price_ticks": 5_990_000, "qty_units": 1 * BTC, "arrival_seq": 2},
    ]
def test_market_sell_sweep_price_levels_order():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "b2",
                            "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    book.process_event({"seq": 3, "event_id": "e3", "type": "LIMIT", "order_id": "b3",
                        "side": "BUY", "price_ticks": 5_990_000, "qty_units": 3 * BTC})
    result = book.process_event({"seq": 4, "event_id": "e4", "type": "MARKET_SELL",
                                 "order_id": "s1", "qty_units": 3 * BTC})

    assert result["status"] == "filled"
    assert result["unfilled_qty_units"] == 0
    assert result["fills"] == [
        {"maker_id": "b1", "taker_id": "s1", "price_ticks": 6_000_000, "qty_units": 1 * BTC},
        {"maker_id": "b2", "taker_id": "s1", "price_ticks": 6_000_000, "qty_units": 1 * BTC},
        {"maker_id": "b3", "taker_id": "s1", "price_ticks": 5_990_000, "qty_units": 1 * BTC}
    ]
    assert book.snapshot() == [
        {"order_id": "b3", "side": "BUY", "price_ticks": 5_990_000, "qty_units": 2 * BTC, "arrival_seq": 3},
    ]
def test_limit_sell_stops_at_limit_then_next_sell_order():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "b2",
                        "side": "BUY", "price_ticks": 5_990_000, "qty_units": 2 * BTC})
    result_a1 = book.process_event({"seq": 3, "event_id": "e3", "type": "LIMIT", "order_id": "a1",
                                    "side": "SELL", "price_ticks": 6_000_000, "qty_units": 2 * BTC})
    result = book.process_event({"seq": 4, "event_id": "e4", "type": "LIMIT", "order_id": "a2",
                                 "side": "SELL", "price_ticks": 5_990_000, "qty_units": 1 * BTC})

    # a1: trades 1 BTC with b1, stops at its limit (60,000 > b2's 59,900), rest of a1 rests
    assert result_a1["status"] == "resting"
    assert result_a1["unfilled_qty_units"] == 1 * BTC
    assert result_a1["fills"] == [
        {"maker_id": "b1", "taker_id": "a1", "price_ticks": 6_000_000, "qty_units": 1 * BTC}
    ]

    # a2: trades 1 BTC with b2 at 59,900, fully filled
    assert result["status"] == "filled"
    assert result["unfilled_qty_units"] == 0
    assert result["fills"] == [
        {"maker_id": "b2", "taker_id": "a2", "price_ticks": 5_990_000, "qty_units": 1 * BTC}
    ]

    # book: b2 has 1 BTC left (bid), a1 has 1 BTC resting (ask)
    assert book.snapshot() == [
        {"order_id": "b2", "side": "BUY", "price_ticks": 5_990_000, "qty_units": 1 * BTC, "arrival_seq": 2},
        {"order_id": "a1", "side": "SELL", "price_ticks": 6_000_000, "qty_units": 1 * BTC, "arrival_seq": 3},
    ]
def test_cancel_after_partial_fill_then_repeat_cancel():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 2 * BTC})
    book.process_event({"seq": 2, "event_id": "e2", "type": "MARKET_SELL", "order_id": "s1",
                        "qty_units": 1 * BTC})
    result1 = book.process_event({"seq": 3, "event_id": "e3", "type": "CANCEL", "target_order_id": "b1"})
    result2 = book.process_event({"seq": 4, "event_id": "e4", "type": "CANCEL", "target_order_id": "b1"})

    # 1st cancel: b1 still active with 1 BTC left (after partial fill) -> removes exactly that
    assert result1["status"] == "cancelled"
    assert result1["cancelled_qty_units"] == 1 * BTC
    # 2nd cancel: b1 already gone -> harmless no-op
    assert result2["status"] == "not_found"
    assert result2["cancelled_qty_units"] == 0
    # book is empty
    assert book.snapshot() == []
def test_worked_example():
    book = OrderBook()

    # replay every event from the file, in order
    lines = (DATA / "worked_example.jsonl").read_text().splitlines()
    for line in lines:
        event = json.loads(line)
        result = book.process_event(event)   # after the loop: the last event's result (the 6 BTC sell)

    # load the expected answer supplied with the assignment
    expected = json.loads((DATA / "worked_expected.json").read_text())
    exp_sell = expected["market_sell_result"]

    assert result["status"] == exp_sell["status"]
    assert result["unfilled_qty_units"] == exp_sell["unfilled_qty_units"]
    assert result["fills"] == exp_sell["fills"]
    assert book.snapshot() == expected["remaining_orders"]

    # conservation: proceeds = sum of price * quantity over the fills
    proceeds = sum(f["price_ticks"] * f["qty_units"] for f in result["fills"])
    assert proceeds == expected["gross_proceeds_tick_units"]
def test_invalid_events_rejected_book_unchanged():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})

    # zero price
    r = book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "x1",
                            "side": "BUY", "price_ticks": 0, "qty_units": 1 * BTC})
    assert r["status"] == "rejected"
    # negative quantity
    r = book.process_event({"seq": 3, "event_id": "e3", "type": "LIMIT", "order_id": "x2",
                            "side": "BUY", "price_ticks": 6_000_000, "qty_units": -5})
    assert r["status"] == "rejected"
    # unknown side
    r = book.process_event({"seq": 4, "event_id": "e4", "type": "LIMIT", "order_id": "x3",
                            "side": "HOLD", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    assert r["status"] == "rejected"
    # unknown type
    r = book.process_event({"seq": 5, "event_id": "e5", "type": "FOO"})
    assert r["status"] == "rejected"
    # duplicate live order id (b1 is still resting)
    r = book.process_event({"seq": 6, "event_id": "e6", "type": "LIMIT", "order_id": "b1",
                            "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    assert r["status"] == "rejected"
    # seq not increasing (1 was already used)
    r = book.process_event({"seq": 1, "event_id": "e7", "type": "LIMIT", "order_id": "x4",
                            "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    assert r["status"] == "rejected"
    # decimal price (not a whole number of ticks)
    r = book.process_event({"seq": 7, "event_id": "e8", "type": "LIMIT", "order_id": "x5",
                            "side": "BUY", "price_ticks": 6_000_000.5, "qty_units": 1 * BTC})
    assert r["status"] == "rejected"

    # after all that, the book must be exactly as before: only b1
    assert book.snapshot() == [
        {"order_id": "b1", "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC, "arrival_seq": 1}
    ]

    # rejected events do NOT advance seq: so seq 2 is still allowed now
    r = book.process_event({"seq": 2, "event_id": "e9", "type": "LIMIT", "order_id": "b2",
                            "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    assert r["status"] == "resting"
    # cancelling an unknown order is VALID, just not found
    r = book.process_event({"seq": 3, "event_id": "e10", "type": "CANCEL", "target_order_id": "zzz"})
    assert r["status"] == "not_found"
def test_priority_by_arrival_not_by_id_spelling():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "z9",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "a1",
                        "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    result = book.process_event({"seq": 3, "event_id": "e3", "type": "MARKET_SELL",
                                 "order_id": "s1", "qty_units": 1 * BTC})

    assert result["fills"] == [
        {"maker_id": "z9", "taker_id": "s1", "price_ticks": 6_000_000, "qty_units": 1 * BTC}
    ]
    assert book.snapshot() == [
        {"order_id": "a1", "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC, "arrival_seq": 2}
    ]
def test_long_queue_at_one_price():
    book = OrderBook()
    for i in range(1, 51):                       # i = 1, 2, ..., 50
        book.process_event({"seq": i, "event_id": f"e{i}", "type": "LIMIT", "order_id": f"b{i}",
                            "side": "BUY", "price_ticks": 6_000_000, "qty_units": 1 * BTC})
    result = book.process_event({"seq": 51, "event_id": "e51", "type": "MARKET_SELL",
                                 "order_id": "s1", "qty_units": 30 * BTC})

    makers = [f["maker_id"] for f in result["fills"]]   # list of maker ids, in fill order
    assert len(result["fills"]) == 30
    assert makers == [f"b{i}" for i in range(1, 31)]    # b1, b2, ... b30 in arrival order
    remaining = book.snapshot()
    assert len(remaining) == 20
    assert remaining[0]["order_id"] == "b31"             # b31 is now first in the queue
def test_limit_buy_crosses_resting_ask():
    book = OrderBook()
    book.process_event({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "a1",
                        "side": "SELL", "price_ticks": 6_010_000, "qty_units": 1 * BTC})
    result = book.process_event({"seq": 2, "event_id": "e2", "type": "LIMIT", "order_id": "b1",
                                 "side": "BUY", "price_ticks": 6_020_000, "qty_units": 2 * BTC})

    assert result["status"] == "resting"
    assert result["unfilled_qty_units"] == 1 * BTC
    assert result["fills"] == [
        {"maker_id": "a1", "taker_id": "b1", "price_ticks": 6_010_000, "qty_units": 1 * BTC}
    ]
    assert book.snapshot() == [
        {"order_id": "b1", "side": "BUY", "price_ticks": 6_020_000, "qty_units": 1 * BTC, "arrival_seq": 2}
    ]