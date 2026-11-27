"""Public names and result shapes shared by both implementations."""

from limit_order_book.interface import OrderBook

from helpers import cancel_event, limit_event, market_sell_event


def test_public_methods_exist(book: OrderBook) -> None:
    for name in (
        "process_event",
        "add_limit_order",
        "cancel_order",
        "fill_market_sell",
        "inspect_book",
    ):
        assert callable(getattr(book, name))


def test_fresh_book_is_empty(book: OrderBook) -> None:
    assert book.inspect_book() == []


def test_limit_result_has_required_fields(book: OrderBook) -> None:
    result = book.process_event(limit_event(1, "b1", "BUY", 100, 5))

    assert result == {
        "event_id": "event1",
        "order_id": "b1",
        "status": "resting",
        "unfilled_qty_units": 5,
        "fills": [],
    }


def test_market_sell_result_has_required_fields(book: OrderBook) -> None:
    result = book.process_event(market_sell_event(1, "s1", 5))

    assert result == {
        "event_id": "event1",
        "order_id": "s1",
        "status": "unfilled",
        "unfilled_qty_units": 5,
        "fills": [],
    }


def test_cancellation_result_has_required_fields(book: OrderBook) -> None:
    result = book.process_event(cancel_event(1, "missing"))

    assert result == {
        "event_id": "event1",
        "target_order_id": "missing",
        "status": "not_found",
        "cancelled_qty_units": 0,
    }

