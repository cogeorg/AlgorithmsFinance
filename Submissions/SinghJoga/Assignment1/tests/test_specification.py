import json
from pathlib import Path

import pytest

from orderbook.baseline import OrderBook as BaselineOrderBook
from orderbook.revised import OrderBook as RevisedOrderBook


OrderBook = BaselineOrderBook


@pytest.fixture(
    autouse=True,
    params=[
        pytest.param(BaselineOrderBook, id="baseline"),
        pytest.param(RevisedOrderBook, id="revised"),
    ],
)
def _select_orderbook_implementation(request, monkeypatch):
    monkeypatch.setattr(request.module, "OrderBook", request.param)


def _limit(seq, event_id, order_id, side, price_ticks, qty_units):
    return {
        "seq": seq,
        "event_id": event_id,
        "type": "LIMIT",
        "order_id": order_id,
        "side": side,
        "price_ticks": price_ticks,
        "qty_units": qty_units,
    }


def _market_sell(seq, event_id, order_id, qty_units):
    return {
        "seq": seq,
        "event_id": event_id,
        "type": "MARKET_SELL",
        "order_id": order_id,
        "qty_units": qty_units,
    }


def _cancel(seq, event_id, target_order_id):
    return {
        "seq": seq,
        "event_id": event_id,
        "type": "CANCEL",
        "target_order_id": target_order_id,
    }


def _assert_submission_conservation(result, submitted_qty_units):
    assert all(fill["qty_units"] > 0 for fill in result["fills"])
    assert (
        sum(fill["qty_units"] for fill in result["fills"])
        + result["unfilled_qty_units"]
        == submitted_qty_units
    )


def _assert_book_invariants(book):
    snapshot = book.inspect_book()
    bids = snapshot["bids"]
    asks = snapshot["asks"]
    active_ids = [order["order_id"] for order in bids + asks]

    assert len(active_ids) == len(set(active_ids))
    assert all(order["qty_units"] > 0 for order in bids + asks)
    if bids and asks:
        assert max(order["price_ticks"] for order in bids) < min(
            order["price_ticks"] for order in asks
        )
    return snapshot


def _book_with_seed_bid():
    book = OrderBook()
    book.process_event(
        _limit(1, "seed-event", "seed-bid", "BUY", 6000000, 100000000)
    )
    expected_book = {
        "bids": [
            {
                "order_id": "seed-bid",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 100000000,
                "seq": 1,
            }
        ],
        "asks": [],
    }
    return book, expected_book


def _valid_event(event_type, seq=2):
    event = {
        "seq": seq,
        "event_id": f"event-{seq}",
        "type": event_type,
    }
    if event_type == "LIMIT":
        event.update(
            {
                "order_id": "new-order",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 25000000,
            }
        )
    elif event_type == "MARKET_SELL":
        event.update({"order_id": "new-market-sell", "qty_units": 25000000})
    elif event_type == "CANCEL":
        event["target_order_id"] = "missing-target"
    return event


def _assert_rejection_preserves_state(book, event, expected_book, accepted_seq):
    result = book.process_event(event)

    assert result["status"] == "rejected"
    assert result["reason"]
    if "event_id" in event:
        assert result["event_id"] == event["event_id"]
    else:
        assert "event_id" not in result
    assert book.inspect_book() == expected_book
    assert book.last_accepted_seq == accepted_seq


def test_empty_book_inspection_and_initial_sequence():
    book = OrderBook()

    assert book.inspect_book() == {"bids": [], "asks": []}
    assert book.last_accepted_seq is None


def test_market_sell_against_empty_book_is_unfilled_and_does_not_rest():
    book = OrderBook()
    result = book.process_event(_market_sell(1, "e1", "sell_1", 75000000))

    assert result == {
        "event_id": "e1",
        "order_id": "sell_1",
        "status": "unfilled",
        "unfilled_qty_units": 75000000,
        "fills": [],
    }
    assert book.inspect_book() == {"bids": [], "asks": []}
    assert book.last_accepted_seq == 1
    _assert_submission_conservation(result, 75000000)


@pytest.mark.parametrize(
    ("sell_qty_units", "expected_result", "expected_book"),
    [
        pytest.param(
            50000000,
            {
                "event_id": "e2",
                "order_id": "sell_1",
                "status": "filled",
                "unfilled_qty_units": 0,
                "fills": [
                    {
                        "maker_id": "bid_1",
                        "taker_id": "sell_1",
                        "price_ticks": 6000000,
                        "qty_units": 50000000,
                    }
                ],
            },
            {
                "bids": [
                    {
                        "order_id": "bid_1",
                        "side": "BUY",
                        "price_ticks": 6000000,
                        "qty_units": 150000000,
                        "seq": 1,
                    }
                ],
                "asks": [],
            },
            id="smaller-than-depth",
        ),
        pytest.param(
            200000000,
            {
                "event_id": "e2",
                "order_id": "sell_1",
                "status": "filled",
                "unfilled_qty_units": 0,
                "fills": [
                    {
                        "maker_id": "bid_1",
                        "taker_id": "sell_1",
                        "price_ticks": 6000000,
                        "qty_units": 200000000,
                    }
                ],
            },
            {"bids": [], "asks": []},
            id="equal-to-depth",
        ),
        pytest.param(
            300000000,
            {
                "event_id": "e2",
                "order_id": "sell_1",
                "status": "partial",
                "unfilled_qty_units": 100000000,
                "fills": [
                    {
                        "maker_id": "bid_1",
                        "taker_id": "sell_1",
                        "price_ticks": 6000000,
                        "qty_units": 200000000,
                    }
                ],
            },
            {"bids": [], "asks": []},
            id="larger-than-depth-market-residual-does-not-rest",
        ),
    ],
)
def test_one_bid_market_sell_depth_cases(
    sell_qty_units, expected_result, expected_book
):
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "bid_1", "BUY", 6000000, 200000000)
    )

    result = book.process_event(_market_sell(2, "e2", "sell_1", sell_qty_units))

    assert result == expected_result
    assert book.inspect_book() == expected_book
    assert book.last_accepted_seq == 2
    _assert_submission_conservation(result, sell_qty_units)
    _assert_book_invariants(book)


def test_partial_fill_then_next_sell_keeps_maker_fifo_priority():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "z_first", "BUY", 6000000, 100000000)
    )
    book.process_event(
        _limit(2, "e2", "a_second", "BUY", 6000000, 100000000)
    )

    first_result = book.process_event(_market_sell(3, "e3", "sell_1", 50000000))
    assert first_result == {
        "event_id": "e3",
        "order_id": "sell_1",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            {
                "maker_id": "z_first",
                "taker_id": "sell_1",
                "price_ticks": 6000000,
                "qty_units": 50000000,
            }
        ],
    }
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "z_first",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 50000000,
                "seq": 1,
            },
            {
                "order_id": "a_second",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 100000000,
                "seq": 2,
            },
        ],
        "asks": [],
    }

    second_result = book.process_event(
        _market_sell(4, "e4", "sell_2", 75000000)
    )
    assert second_result == {
        "event_id": "e4",
        "order_id": "sell_2",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            {
                "maker_id": "z_first",
                "taker_id": "sell_2",
                "price_ticks": 6000000,
                "qty_units": 50000000,
            },
            {
                "maker_id": "a_second",
                "taker_id": "sell_2",
                "price_ticks": 6000000,
                "qty_units": 25000000,
            },
        ],
    }
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "a_second",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 75000000,
                "seq": 2,
            }
        ],
        "asks": [],
    }
    _assert_submission_conservation(first_result, 50000000)
    _assert_submission_conservation(second_result, 75000000)
    _assert_book_invariants(book)


def test_long_same_price_queue_uses_arrival_not_identifier_order():
    book = OrderBook()
    book.process_event(_limit(1, "e1", "z_first", "BUY", 6000000, 10000000))
    book.process_event(_limit(2, "e2", "a_second", "BUY", 6000000, 10000000))
    book.process_event(_limit(3, "e3", "m_third", "BUY", 6000000, 10000000))
    book.process_event(_limit(4, "e4", "b_fourth", "BUY", 6000000, 10000000))
    book.process_event(_limit(5, "e5", "x_fifth", "BUY", 6000000, 10000000))

    result = book.process_event(_market_sell(6, "e6", "sell_1", 45000000))

    assert result == {
        "event_id": "e6",
        "order_id": "sell_1",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            {"maker_id": "z_first", "taker_id": "sell_1", "price_ticks": 6000000, "qty_units": 10000000},
            {"maker_id": "a_second", "taker_id": "sell_1", "price_ticks": 6000000, "qty_units": 10000000},
            {"maker_id": "m_third", "taker_id": "sell_1", "price_ticks": 6000000, "qty_units": 10000000},
            {"maker_id": "b_fourth", "taker_id": "sell_1", "price_ticks": 6000000, "qty_units": 10000000},
            {"maker_id": "x_fifth", "taker_id": "sell_1", "price_ticks": 6000000, "qty_units": 5000000},
        ],
    }
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "x_fifth",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 5000000,
                "seq": 5,
            }
        ],
        "asks": [],
    }
    _assert_submission_conservation(result, 45000000)
    _assert_book_invariants(book)


def test_cancel_before_execution_removes_remaining_order():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "bid_1", "BUY", 6000000, 100000000)
    )

    result = book.process_event(_cancel(2, "e2", "bid_1"))
    assert result == {
        "event_id": "e2",
        "target_order_id": "bid_1",
        "status": "cancelled",
        "cancelled_qty_units": 100000000,
    }
    assert book.inspect_book() == {"bids": [], "asks": []}
    sell_result = book.process_event(_market_sell(3, "e3", "sell_1", 25000000))
    assert sell_result == {
        "event_id": "e3",
        "order_id": "sell_1",
        "status": "unfilled",
        "unfilled_qty_units": 25000000,
        "fills": [],
    }
    assert book.last_accepted_seq == 3
    _assert_submission_conservation(sell_result, 25000000)
    _assert_book_invariants(book)


def test_cancel_after_partial_execution_removes_only_the_residual():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "bid_1", "BUY", 6000000, 100000000)
    )
    result = book.process_event(_market_sell(2, "e2", "sell_1", 40000000))
    assert result == {
        "event_id": "e2",
        "order_id": "sell_1",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            {
                "maker_id": "bid_1",
                "taker_id": "sell_1",
                "price_ticks": 6000000,
                "qty_units": 40000000,
            }
        ],
    }

    cancel_result = book.process_event(_cancel(3, "e3", "bid_1"))

    assert cancel_result == {
        "event_id": "e3",
        "target_order_id": "bid_1",
        "status": "cancelled",
        "cancelled_qty_units": 60000000,
    }
    assert book.inspect_book() == {"bids": [], "asks": []}
    assert result["fills"][0]["qty_units"] + cancel_result["cancelled_qty_units"] == 100000000


def test_cancel_after_full_execution_returns_not_found():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "bid_1", "BUY", 6000000, 100000000)
    )
    fill_result = book.process_event(_market_sell(2, "e2", "sell_1", 100000000))
    assert fill_result["fills"] == [
        {
            "maker_id": "bid_1",
            "taker_id": "sell_1",
            "price_ticks": 6000000,
            "qty_units": 100000000,
        }
    ]

    result = book.process_event(_cancel(3, "e3", "bid_1"))

    assert result == {
        "event_id": "e3",
        "target_order_id": "bid_1",
        "status": "not_found",
        "cancelled_qty_units": 0,
    }
    assert book.inspect_book() == {"bids": [], "asks": []}


def test_repeated_cancellation_is_not_found_after_first_cancel():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "bid_1", "BUY", 6000000, 100000000)
    )
    assert book.process_event(_cancel(2, "e2", "bid_1")) == {
        "event_id": "e2",
        "target_order_id": "bid_1",
        "status": "cancelled",
        "cancelled_qty_units": 100000000,
    }

    result = book.process_event(_cancel(3, "e3", "bid_1"))

    assert result == {
        "event_id": "e3",
        "target_order_id": "bid_1",
        "status": "not_found",
        "cancelled_qty_units": 0,
    }
    assert book.last_accepted_seq == 3


def test_valid_unknown_cancel_advances_accepted_sequence():
    book = OrderBook()

    result = book.process_event(_cancel(1, "e1", "never-seen"))

    assert result == {
        "event_id": "e1",
        "target_order_id": "never-seen",
        "status": "not_found",
        "cancelled_qty_units": 0,
    }
    assert book.inspect_book() == {"bids": [], "asks": []}
    assert book.last_accepted_seq == 1


def test_crossing_limit_buy_uses_best_asks_then_fifo_and_maker_prices():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "ask_later", "SELL", 6010000, 100000000)
    )
    book.process_event(
        _limit(2, "e2", "ask_early_1", "SELL", 6000000, 100000000)
    )
    book.process_event(
        _limit(3, "e3", "ask_early_2", "SELL", 6000000, 100000000)
    )

    result = book.process_event(
        _limit(4, "e4", "buy_taker", "BUY", 6010000, 250000000)
    )

    assert result == {
        "event_id": "e4",
        "order_id": "buy_taker",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            {
                "maker_id": "ask_early_1",
                "taker_id": "buy_taker",
                "price_ticks": 6000000,
                "qty_units": 100000000,
            },
            {
                "maker_id": "ask_early_2",
                "taker_id": "buy_taker",
                "price_ticks": 6000000,
                "qty_units": 100000000,
            },
            {
                "maker_id": "ask_later",
                "taker_id": "buy_taker",
                "price_ticks": 6010000,
                "qty_units": 50000000,
            },
        ],
    }
    assert book.inspect_book() == {
        "bids": [],
        "asks": [
            {
                "order_id": "ask_later",
                "side": "SELL",
                "price_ticks": 6010000,
                "qty_units": 50000000,
                "seq": 1,
            }
        ],
    }
    assert sum(
        fill["price_ticks"] * fill["qty_units"] for fill in result["fills"]
    ) == 1500500000000000
    _assert_submission_conservation(result, 250000000)
    _assert_book_invariants(book)


def test_crossing_limit_sell_uses_best_bids_then_fifo():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "bid_high", "BUY", 6010000, 100000000)
    )
    book.process_event(
        _limit(2, "e2", "bid_mid_1", "BUY", 6000000, 100000000)
    )
    book.process_event(
        _limit(3, "e3", "bid_mid_2", "BUY", 6000000, 100000000)
    )

    result = book.process_event(
        _limit(4, "e4", "sell_taker", "SELL", 6000000, 250000000)
    )

    assert result == {
        "event_id": "e4",
        "order_id": "sell_taker",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            {
                "maker_id": "bid_high",
                "taker_id": "sell_taker",
                "price_ticks": 6010000,
                "qty_units": 100000000,
            },
            {
                "maker_id": "bid_mid_1",
                "taker_id": "sell_taker",
                "price_ticks": 6000000,
                "qty_units": 100000000,
            },
            {
                "maker_id": "bid_mid_2",
                "taker_id": "sell_taker",
                "price_ticks": 6000000,
                "qty_units": 50000000,
            },
        ],
    }
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "bid_mid_2",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 50000000,
                "seq": 3,
            }
        ],
        "asks": [],
    }
    _assert_submission_conservation(result, 250000000)
    _assert_book_invariants(book)


def test_limit_buy_crosses_at_price_equality():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "ask_1", "SELL", 6000000, 50000000)
    )

    result = book.process_event(
        _limit(2, "e2", "buy_taker", "BUY", 6000000, 50000000)
    )

    assert result == {
        "event_id": "e2",
        "order_id": "buy_taker",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            {
                "maker_id": "ask_1",
                "taker_id": "buy_taker",
                "price_ticks": 6000000,
                "qty_units": 50000000,
            }
        ],
    }
    assert book.inspect_book() == {"bids": [], "asks": []}
    _assert_submission_conservation(result, 50000000)


def test_limit_sell_crosses_at_price_equality():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "bid_1", "BUY", 6000000, 50000000)
    )

    result = book.process_event(
        _limit(2, "e2", "sell_taker", "SELL", 6000000, 50000000)
    )

    assert result == {
        "event_id": "e2",
        "order_id": "sell_taker",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            {
                "maker_id": "bid_1",
                "taker_id": "sell_taker",
                "price_ticks": 6000000,
                "qty_units": 50000000,
            }
        ],
    }
    assert book.inspect_book() == {"bids": [], "asks": []}
    _assert_submission_conservation(result, 50000000)


def test_worse_limit_buy_does_not_cross_and_rests():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "ask_1", "SELL", 6000000, 50000000)
    )

    result = book.process_event(
        _limit(2, "e2", "buy_taker", "BUY", 5999999, 25000000)
    )

    assert result == {
        "event_id": "e2",
        "order_id": "buy_taker",
        "status": "resting",
        "unfilled_qty_units": 25000000,
        "fills": [],
    }
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "buy_taker",
                "side": "BUY",
                "price_ticks": 5999999,
                "qty_units": 25000000,
                "seq": 2,
            }
        ],
        "asks": [
            {
                "order_id": "ask_1",
                "side": "SELL",
                "price_ticks": 6000000,
                "qty_units": 50000000,
                "seq": 1,
            }
        ],
    }
    _assert_submission_conservation(result, 25000000)
    _assert_book_invariants(book)


def test_worse_limit_sell_does_not_cross_and_rests():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "bid_1", "BUY", 6000000, 50000000)
    )

    result = book.process_event(
        _limit(2, "e2", "sell_taker", "SELL", 6000001, 25000000)
    )

    assert result == {
        "event_id": "e2",
        "order_id": "sell_taker",
        "status": "resting",
        "unfilled_qty_units": 25000000,
        "fills": [],
    }
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "bid_1",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 50000000,
                "seq": 1,
            }
        ],
        "asks": [
            {
                "order_id": "sell_taker",
                "side": "SELL",
                "price_ticks": 6000001,
                "qty_units": 25000000,
                "seq": 2,
            }
        ],
    }
    _assert_submission_conservation(result, 25000000)
    _assert_book_invariants(book)


def test_partially_filled_limit_buy_rests_its_residual():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "ask_1", "SELL", 6000000, 100000000)
    )

    result = book.process_event(
        _limit(2, "e2", "buy_taker", "BUY", 6000000, 150000000)
    )

    assert result == {
        "event_id": "e2",
        "order_id": "buy_taker",
        "status": "resting",
        "unfilled_qty_units": 50000000,
        "fills": [
            {
                "maker_id": "ask_1",
                "taker_id": "buy_taker",
                "price_ticks": 6000000,
                "qty_units": 100000000,
            }
        ],
    }
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "buy_taker",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 50000000,
                "seq": 2,
            }
        ],
        "asks": [],
    }
    _assert_submission_conservation(result, 150000000)
    _assert_book_invariants(book)


def test_partially_filled_limit_sell_rests_its_residual():
    book = OrderBook()
    book.process_event(
        _limit(1, "e1", "bid_1", "BUY", 6000000, 50000000)
    )

    result = book.process_event(
        _limit(2, "e2", "sell_taker", "SELL", 6000000, 100000000)
    )

    assert result == {
        "event_id": "e2",
        "order_id": "sell_taker",
        "status": "resting",
        "unfilled_qty_units": 50000000,
        "fills": [
            {
                "maker_id": "bid_1",
                "taker_id": "sell_taker",
                "price_ticks": 6000000,
                "qty_units": 50000000,
            }
        ],
    }
    assert book.inspect_book() == {
        "bids": [],
        "asks": [
            {
                "order_id": "sell_taker",
                "side": "SELL",
                "price_ticks": 6000000,
                "qty_units": 50000000,
                "seq": 2,
            }
        ],
    }
    _assert_submission_conservation(result, 100000000)
    _assert_book_invariants(book)


def test_supplied_worked_example_matches_supplied_expected_result():
    assignment_root = Path(__file__).resolve().parents[1]
    data_dir = assignment_root / "data"
    events = [
        json.loads(line)
        for line in (data_dir / "worked_example.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    expected = json.loads(
        (data_dir / "worked_expected.json").read_text(encoding="utf-8")
    )
    book = OrderBook()

    for event in events:
        result = book.process_event(event)

    assert result == expected["market_sell_result"]
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "b4",
                "side": "BUY",
                "price_ticks": 5970000,
                "qty_units": 400000000,
                "seq": 4,
            }
        ],
        "asks": [
            {
                "order_id": "a1",
                "side": "SELL",
                "price_ticks": 6010000,
                "qty_units": 200000000,
                "seq": 5,
            }
        ],
    }
    assert sum(
        fill["price_ticks"] * fill["qty_units"]
        for fill in result["fills"]
    ) == int(expected["gross_proceeds_tick_units"])
    _assert_submission_conservation(result, 600000000)
    _assert_book_invariants(book)


@pytest.mark.parametrize(
    ("event_type", "missing_field"),
    [
        ("LIMIT", "seq"),
        ("LIMIT", "event_id"),
        ("LIMIT", "type"),
        ("LIMIT", "order_id"),
        ("LIMIT", "side"),
        ("LIMIT", "price_ticks"),
        ("LIMIT", "qty_units"),
        ("MARKET_SELL", "seq"),
        ("MARKET_SELL", "event_id"),
        ("MARKET_SELL", "type"),
        ("MARKET_SELL", "order_id"),
        ("MARKET_SELL", "qty_units"),
        ("CANCEL", "seq"),
        ("CANCEL", "event_id"),
        ("CANCEL", "type"),
        ("CANCEL", "target_order_id"),
    ],
)
def test_missing_required_fields_are_rejected_without_state_change(
    event_type, missing_field
):
    book, expected_book = _book_with_seed_bid()
    event = _valid_event(event_type)
    del event[missing_field]

    _assert_rejection_preserves_state(book, event, expected_book, 1)


@pytest.mark.parametrize(
    ("field", "invalid_value"),
    [
        pytest.param("type", "UNKNOWN", id="unknown-event-type"),
        pytest.param("side", "HOLD", id="unknown-side"),
        pytest.param("price_ticks", 0, id="zero-price"),
        pytest.param("price_ticks", -1, id="negative-price"),
        pytest.param("price_ticks", 6000000.5, id="fractional-price"),
        pytest.param("price_ticks", "6000000", id="string-price"),
        pytest.param("price_ticks", True, id="boolean-price"),
        pytest.param("qty_units", 0, id="zero-quantity"),
        pytest.param("qty_units", -1, id="negative-quantity"),
        pytest.param("qty_units", 25.5, id="fractional-quantity"),
        pytest.param("qty_units", "25000000", id="string-quantity"),
        pytest.param("qty_units", False, id="boolean-quantity"),
        pytest.param("seq", 0, id="zero-sequence"),
        pytest.param("seq", -1, id="negative-sequence"),
        pytest.param("seq", 2.5, id="fractional-sequence"),
        pytest.param("seq", "2", id="string-sequence"),
        pytest.param("seq", True, id="boolean-sequence"),
    ],
)
def test_invalid_values_are_rejected_without_mutating_book_or_sequence(
    field, invalid_value
):
    book, expected_book = _book_with_seed_bid()
    event = _valid_event("LIMIT")
    event[field] = invalid_value

    _assert_rejection_preserves_state(book, event, expected_book, 1)


def test_duplicate_live_submission_id_is_rejected_without_mutation():
    book, expected_book = _book_with_seed_bid()
    event = _limit(2, "duplicate-event", "seed-bid", "BUY", 5990000, 25000000)

    _assert_rejection_preserves_state(book, event, expected_book, 1)


@pytest.mark.parametrize("nonincreasing_seq", [1, 0], ids=["equal", "lower"])
def test_nonincreasing_sequence_is_rejected_without_mutation(nonincreasing_seq):
    book, expected_book = _book_with_seed_bid()
    event = _valid_event("LIMIT", seq=nonincreasing_seq)

    _assert_rejection_preserves_state(book, event, expected_book, 1)


def test_rejected_sequence_can_be_used_by_a_later_valid_event():
    book = OrderBook()
    invalid_event = _limit(1, "bad-event", "bad-order", "BUY", 6000000, 0)
    rejected = book.process_event(invalid_event)

    assert rejected["status"] == "rejected"
    assert book.inspect_book() == {"bids": [], "asks": []}
    assert book.last_accepted_seq is None

    accepted = book.process_event(
        _limit(1, "good-event", "good-order", "BUY", 6000000, 25000000)
    )

    assert accepted == {
        "event_id": "good-event",
        "order_id": "good-order",
        "status": "resting",
        "unfilled_qty_units": 25000000,
        "fills": [],
    }
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "good-order",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 25000000,
                "seq": 1,
            }
        ],
        "asks": [],
    }
    assert book.last_accepted_seq == 1
    _assert_submission_conservation(accepted, 25000000)
    _assert_book_invariants(book)
