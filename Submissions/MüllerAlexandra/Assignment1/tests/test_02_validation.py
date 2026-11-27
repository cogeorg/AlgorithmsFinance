"""Invalid events are rejected atomically and do not consume sequence rank."""

from copy import deepcopy

import pytest

from limit_order_book.interface import OrderBook

from helpers import cancel_event, limit_event, market_sell_event, resting


@pytest.mark.parametrize(
    "invalid_event",
    [
        {"event_id": "missing-sequence", "type": "CANCEL", "target_order_id": "b1"},
        {"seq": 2, "event_id": "bad-type", "type": "UNKNOWN"},
        {"seq": 2, "event_id": "empty-type", "type": ""},
        {"seq": 2, "event_id": "nonstring-type", "type": 7},
        {"seq": 2, "event_id": "", "type": "CANCEL", "target_order_id": "b1"},
        {"seq": 2, "event_id": 7, "type": "CANCEL", "target_order_id": "b1"},
        limit_event(2, "bad-side", "HOLD", 99, 1, event_id="bad-side-event"),
        {
            "seq": 2,
            "event_id": "missing-order-id",
            "type": "LIMIT",
            "side": "BUY",
            "price_ticks": 99,
            "qty_units": 1,
        },
        limit_event(2, "", "BUY", 99, 1, event_id="empty-order-id"),
        {
            "seq": 2,
            "event_id": "missing-price",
            "type": "LIMIT",
            "order_id": "x",
            "side": "BUY",
            "qty_units": 1,
        },
        {
            "seq": 2,
            "event_id": "missing-limit-quantity",
            "type": "LIMIT",
            "order_id": "x",
            "side": "BUY",
            "price_ticks": 99,
        },
        limit_event(2, "bad-price-zero", "BUY", 0, 1),
        limit_event(2, "bad-price-negative", "BUY", -1, 1),
        limit_event(2, "bad-price-float", "BUY", 99.5, 1),
        limit_event(2, "bad-price-bool", "BUY", True, 1),
        limit_event(2, "bad-qty-zero", "BUY", 99, 0),
        limit_event(2, "bad-qty-negative", "BUY", 99, -1),
        limit_event(2, "bad-qty-float", "BUY", 99, 1.5),
        limit_event(2, "bad-qty-bool", "BUY", 99, True),
        market_sell_event(2, "bad-market-zero", 0),
        market_sell_event(2, "bad-market-negative", -1),
        market_sell_event(2, "bad-market-float", 1.5),
        market_sell_event(2, "bad-market-bool", True),
        {"seq": 2, "event_id": "missing-quantity", "type": "MARKET_SELL", "order_id": "s"},
        {"seq": 2, "event_id": "missing-target", "type": "CANCEL"},
        {"seq": 2, "event_id": "empty-target", "type": "CANCEL", "target_order_id": ""},
        {"seq": 2, "event_id": "nonstring-target", "type": "CANCEL", "target_order_id": 7},
        {
            "seq": 2,
            "event_id": "missing-side",
            "type": "LIMIT",
            "order_id": "x",
            "price_ticks": 99,
            "qty_units": 1,
        },
    ],
    ids=[
        "missing-sequence",
        "unknown-type",
        "empty-type",
        "nonstring-type",
        "empty-event-id",
        "nonstring-event-id",
        "unknown-side",
        "missing-order-id",
        "empty-order-id",
        "missing-price",
        "missing-limit-quantity",
        "zero-price",
        "negative-price",
        "noninteger-price",
        "boolean-price-is-not-integer",
        "zero-quantity",
        "negative-quantity",
        "noninteger-quantity",
        "boolean-is-not-integer",
        "zero-market-quantity",
        "negative-market-quantity",
        "noninteger-market-quantity",
        "boolean-market-quantity",
        "missing-quantity",
        "missing-cancel-target",
        "empty-cancel-target",
        "nonstring-cancel-target",
        "missing-limit-side",
    ],
)
def test_invalid_event_is_rejected_without_state_change(
    book: OrderBook, invalid_event: dict[str, object]
) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 100, 5))
    before = deepcopy(book.inspect_book())

    result = book.process_event(invalid_event)

    assert result["event_id"] == invalid_event["event_id"]
    assert result["status"] == "rejected"
    assert isinstance(result["reason"], str) and result["reason"]
    assert book.inspect_book() == before


def test_missing_event_id_is_rejected_without_adding_one(book: OrderBook) -> None:
    event = {
        "seq": 1,
        "type": "LIMIT",
        "order_id": "b1",
        "side": "BUY",
        "price_ticks": 100,
        "qty_units": 1,
    }

    result = book.process_event(event)

    assert result["status"] == "rejected"
    assert "event_id" not in result
    assert book.inspect_book() == []


def test_sequence_must_be_positive_integer(book: OrderBook) -> None:
    result = book.process_event(limit_event(0, "b0", "BUY", 100, 1))

    assert result["status"] == "rejected"
    assert book.inspect_book() == []


@pytest.mark.parametrize("invalid_seq", [1.5, True], ids=["float", "boolean"])
def test_sequence_must_not_accept_nonintegers(
    book: OrderBook, invalid_seq: object
) -> None:
    event = limit_event(1, "b1", "BUY", 100, 1)
    event["seq"] = invalid_seq

    result = book.process_event(event)

    assert result["status"] == "rejected"
    assert book.inspect_book() == []


def test_rejected_event_does_not_advance_last_accepted_sequence(book: OrderBook) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 100, 1))
    rejected = book.process_event(
        limit_event(3, "invalid", "HOLD", 99, 1, event_id="invalid-event")
    )
    accepted = book.process_event(limit_event(2, "b2", "BUY", 99, 1))

    assert rejected["status"] == "rejected"
    assert accepted["status"] == "resting"
    assert [order["order_id"] for order in book.inspect_book()] == ["b1", "b2"]


@pytest.mark.parametrize("invalid_seq", [2, 1], ids=["equal", "decreasing"])
def test_sequence_must_be_strictly_increasing_without_state_change(
    book: OrderBook, invalid_seq: int
) -> None:
    book.process_event(limit_event(2, "b1", "BUY", 100, 1))
    before = deepcopy(book.inspect_book())

    rejected = book.process_event(
        limit_event(invalid_seq, "invalid", "BUY", 99, 1, event_id="invalid-seq")
    )
    accepted = book.process_event(limit_event(3, "b2", "BUY", 99, 1))

    assert rejected["status"] == "rejected"
    assert book.inspect_book() == [
        resting("b1", "BUY", 100, 1, 2),
        resting("b2", "BUY", 99, 1, 3),
    ]
    assert before == [resting("b1", "BUY", 100, 1, 2)]
    assert accepted["status"] == "resting"


def test_duplicate_live_order_identifier_is_rejected(book: OrderBook) -> None:
    book.process_event(limit_event(1, "same", "BUY", 100, 2))
    before = book.inspect_book()

    result = book.process_event(market_sell_event(2, "same", 1))

    assert result["status"] == "rejected"
    assert book.inspect_book() == before


def test_unknown_cancellation_is_valid_and_advances_sequence(book: OrderBook) -> None:
    missing = book.process_event(cancel_event(1, "unknown"))
    later = book.process_event(limit_event(2, "b2", "BUY", 100, 1))

    assert missing == {
        "event_id": "event1",
        "target_order_id": "unknown",
        "status": "not_found",
        "cancelled_qty_units": 0,
    }
    assert later["status"] == "resting"
    assert book.inspect_book() == [resting("b2", "BUY", 100, 1, 2)]

