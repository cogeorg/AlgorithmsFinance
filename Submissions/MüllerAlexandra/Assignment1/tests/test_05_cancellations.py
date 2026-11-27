"""Cancellations remove exactly the active residual, if any."""

from limit_order_book.interface import OrderBook

from helpers import cancel_event, limit_event, market_sell_event, resting


def test_cancel_active_order_removes_full_residual(book: OrderBook) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 100, 5))

    result = book.process_event(cancel_event(2, "b1"))

    assert result == {
        "event_id": "event2",
        "target_order_id": "b1",
        "status": "cancelled",
        "cancelled_qty_units": 5,
    }
    assert book.inspect_book() == []


def test_cancel_after_partial_fill_removes_only_remaining_quantity(
    book: OrderBook,
) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 100, 5))
    book.process_event(market_sell_event(2, "s1", 2))

    result = book.process_event(cancel_event(3, "b1"))

    assert result["status"] == "cancelled"
    assert result["cancelled_qty_units"] == 3
    assert book.inspect_book() == []


def test_cancel_after_complete_fill_is_not_found(book: OrderBook) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 100, 2))
    book.process_event(market_sell_event(2, "s1", 2))

    result = book.process_event(cancel_event(3, "b1"))

    assert result["status"] == "not_found"
    assert result["cancelled_qty_units"] == 0


def test_repeated_cancellation_is_not_found_second_time(book: OrderBook) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 100, 2))

    first = book.process_event(cancel_event(2, "b1"))
    second = book.process_event(cancel_event(3, "b1"))

    assert first["status"] == "cancelled"
    assert second["status"] == "not_found"
    assert second["cancelled_qty_units"] == 0


def test_cancelling_one_order_does_not_disturb_other_priority(book: OrderBook) -> None:
    book.process_event(limit_event(1, "first", "BUY", 100, 1))
    book.process_event(limit_event(2, "cancel-me", "BUY", 100, 1))
    book.process_event(limit_event(3, "third", "BUY", 100, 1))
    book.process_event(cancel_event(4, "cancel-me"))

    assert book.inspect_book() == [
        resting("first", "BUY", 100, 1, 1),
        resting("third", "BUY", 100, 1, 3),
    ]


def test_cancelling_head_of_queue_exposes_next_arrival(book: OrderBook) -> None:
    book.process_event(limit_event(1, "first", "BUY", 101, 1))
    book.process_event(limit_event(2, "second", "BUY", 101, 1))
    book.process_event(cancel_event(3, "first"))

    result = book.process_event(market_sell_event(4, "seller", 1))

    assert result["fills"] == [
        {
            "maker_id": "second",
            "taker_id": "seller",
            "price_ticks": 101,
            "qty_units": 1,
        }
    ]
    assert book.inspect_book() == []


def test_cancelled_empty_best_level_can_reopen_without_stale_priority(
    book: OrderBook,
) -> None:
    book.process_event(limit_event(1, "old-best", "BUY", 101, 1))
    book.process_event(limit_event(2, "lower", "BUY", 100, 1))
    book.process_event(cancel_event(3, "old-best"))
    book.process_event(limit_event(4, "new-best", "BUY", 101, 1))

    result = book.process_event(market_sell_event(5, "seller", 1))

    assert result["fills"] == [
        {
            "maker_id": "new-best",
            "taker_id": "seller",
            "price_ticks": 101,
            "qty_units": 1,
        }
    ]
    assert book.inspect_book() == [resting("lower", "BUY", 100, 1, 2)]

