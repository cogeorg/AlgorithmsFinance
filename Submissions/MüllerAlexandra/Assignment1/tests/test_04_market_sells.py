"""Market sells mutate bids, preserve FIFO, and never rest residuals."""

import pytest

from limit_order_book.interface import OrderBook

from helpers import fill, limit_event, market_sell_event, resting


@pytest.mark.parametrize(
    ("requested", "expected_status", "expected_unfilled"),
    [
        (2, "filled", 0),
        (5, "filled", 0),
        (7, "partial", 2),
    ],
    ids=["smaller-than-depth", "equal-to-depth", "larger-than-depth"],
)
def test_market_sell_relative_to_available_depth(
    book: OrderBook,
    requested: int,
    expected_status: str,
    expected_unfilled: int,
) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 100, 5))

    result = book.process_event(market_sell_event(2, "s1", requested))

    executed = min(requested, 5)
    assert result == {
        "event_id": "event2",
        "order_id": "s1",
        "status": expected_status,
        "unfilled_qty_units": expected_unfilled,
        "fills": [fill("b1", "s1", 100, executed)],
    }
    expected_book = [] if executed == 5 else [resting("b1", "BUY", 100, 3, 1)]
    assert book.inspect_book() == expected_book
    assert all(order["order_id"] != "s1" for order in book.inspect_book())


def test_market_sell_uses_best_bid_then_fifo(book: OrderBook) -> None:
    book.process_event(limit_event(1, "low", "BUY", 99, 4))
    book.process_event(limit_event(2, "best-first", "BUY", 101, 2))
    book.process_event(limit_event(3, "best-second", "BUY", 101, 3))
    book.process_event(limit_event(4, "middle", "BUY", 100, 2))

    result = book.process_event(market_sell_event(5, "seller", 8))

    assert result["fills"] == [
        fill("best-first", "seller", 101, 2),
        fill("best-second", "seller", 101, 3),
        fill("middle", "seller", 100, 2),
        fill("low", "seller", 99, 1),
    ]
    assert book.inspect_book() == [resting("low", "BUY", 99, 3, 1)]


def test_partial_maker_retains_priority_for_later_sale(book: OrderBook) -> None:
    book.process_event(limit_event(1, "first", "BUY", 100, 5))
    book.process_event(limit_event(2, "second", "BUY", 100, 5))

    first_sale = book.process_event(market_sell_event(3, "s1", 3))
    second_sale = book.process_event(market_sell_event(4, "s2", 4))

    assert first_sale["fills"] == [fill("first", "s1", 100, 3)]
    assert second_sale["fills"] == [
        fill("first", "s2", 100, 2),
        fill("second", "s2", 100, 2),
    ]
    assert book.inspect_book() == [resting("second", "BUY", 100, 3, 2)]


def test_long_equal_price_queue_preserves_all_arrivals(book: OrderBook) -> None:
    queue_length = 50
    for seq in range(1, queue_length + 1):
        book.process_event(limit_event(seq, f"maker-{seq:02d}", "BUY", 100, 1))

    result = book.process_event(
        market_sell_event(queue_length + 1, "seller", queue_length)
    )

    assert [item["maker_id"] for item in result["fills"]] == [
        f"maker-{seq:02d}" for seq in range(1, queue_length + 1)
    ]
    assert book.inspect_book() == []

