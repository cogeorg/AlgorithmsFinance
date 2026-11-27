"""Independent limit-order outcomes establish price-time priority."""

from limit_order_book.interface import OrderBook

from helpers import fill, limit_event, resting


def test_noncrossing_orders_rest_in_canonical_order(book: OrderBook) -> None:
    buy = book.process_event(limit_event(1, "b1", "BUY", 100, 5))
    sell = book.process_event(limit_event(2, "a1", "SELL", 110, 3))

    assert buy["status"] == "resting"
    assert sell["status"] == "resting"
    assert book.inspect_book() == [
        resting("b1", "BUY", 100, 5, 1),
        resting("a1", "SELL", 110, 3, 2),
    ]


def test_crossing_buy_executes_at_resting_ask_and_rests_residual(
    book: OrderBook,
) -> None:
    book.process_event(limit_event(1, "a1", "SELL", 100, 2))

    result = book.process_event(limit_event(2, "b1", "BUY", 105, 3))

    assert result == {
        "event_id": "event2",
        "order_id": "b1",
        "status": "resting",
        "unfilled_qty_units": 1,
        "fills": [fill("a1", "b1", 100, 2)],
    }
    assert book.inspect_book() == [resting("b1", "BUY", 105, 1, 2)]


def test_crossing_sell_executes_at_resting_bid_and_rests_residual(
    book: OrderBook,
) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 100, 2))
    book.process_event(limit_event(2, "b2", "BUY", 90, 2))

    result = book.process_event(limit_event(3, "a1", "SELL", 95, 3))

    assert result == {
        "event_id": "event3",
        "order_id": "a1",
        "status": "resting",
        "unfilled_qty_units": 1,
        "fills": [fill("b1", "a1", 100, 2)],
    }
    assert book.inspect_book() == [
        resting("b2", "BUY", 90, 2, 2),
        resting("a1", "SELL", 95, 1, 3),
    ]


def test_crossing_limit_uses_best_price_then_fifo(book: OrderBook) -> None:
    book.process_event(limit_event(1, "a-low-first", "SELL", 101, 2))
    book.process_event(limit_event(2, "a-best-first", "SELL", 100, 1))
    book.process_event(limit_event(3, "a-best-second", "SELL", 100, 2))

    result = book.process_event(limit_event(4, "b1", "BUY", 101, 4))

    assert result == {
        "event_id": "event4",
        "order_id": "b1",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            fill("a-best-first", "b1", 100, 1),
            fill("a-best-second", "b1", 100, 2),
            fill("a-low-first", "b1", 101, 1),
        ],
    }
    assert book.inspect_book() == [resting("a-low-first", "SELL", 101, 1, 1)]


def test_identifier_spelling_does_not_override_arrival_priority(
    book: OrderBook,
) -> None:
    book.process_event(limit_event(1, "z-first", "SELL", 100, 1))
    book.process_event(limit_event(2, "a-second", "SELL", 100, 1))

    result = book.process_event(limit_event(3, "buyer", "BUY", 100, 2))

    assert [item["maker_id"] for item in result["fills"]] == ["z-first", "a-second"]


def test_crossing_limit_sell_uses_best_price_then_fifo_and_stops_at_limit(
    book: OrderBook,
) -> None:
    book.process_event(limit_event(1, "ineligible", "BUY", 99, 2))
    book.process_event(limit_event(2, "best-first", "BUY", 101, 1))
    book.process_event(limit_event(3, "best-second", "BUY", 101, 2))
    book.process_event(limit_event(4, "middle", "BUY", 100, 2))

    result = book.process_event(limit_event(5, "seller", "SELL", 100, 4))

    assert result == {
        "event_id": "event5",
        "order_id": "seller",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            fill("best-first", "seller", 101, 1),
            fill("best-second", "seller", 101, 2),
            fill("middle", "seller", 100, 1),
        ],
    }
    assert book.inspect_book() == [
        resting("middle", "BUY", 100, 1, 4),
        resting("ineligible", "BUY", 99, 2, 1),
    ]


def test_partial_ask_retains_priority_for_later_limit_buy(book: OrderBook) -> None:
    book.process_event(limit_event(1, "first", "SELL", 100, 5))
    book.process_event(limit_event(2, "second", "SELL", 100, 5))

    first_buy = book.process_event(limit_event(3, "b1", "BUY", 100, 3))
    second_buy = book.process_event(limit_event(4, "b2", "BUY", 100, 4))

    assert first_buy["fills"] == [fill("first", "b1", 100, 3)]
    assert second_buy["fills"] == [
        fill("first", "b2", 100, 2),
        fill("second", "b2", 100, 2),
    ]
    assert book.inspect_book() == [resting("second", "SELL", 100, 3, 2)]


def test_canonical_book_orders_both_sides_by_price_then_arrival(
    book: OrderBook,
) -> None:
    book.process_event(limit_event(1, "z-low-bid", "BUY", 100, 1))
    book.process_event(limit_event(2, "z-first-best-bid", "BUY", 102, 1))
    book.process_event(limit_event(3, "a-second-best-bid", "BUY", 102, 1))
    book.process_event(limit_event(4, "z-high-ask", "SELL", 105, 1))
    book.process_event(limit_event(5, "z-first-best-ask", "SELL", 104, 1))
    book.process_event(limit_event(6, "a-second-best-ask", "SELL", 104, 1))

    assert book.inspect_book() == [
        resting("z-first-best-bid", "BUY", 102, 1, 2),
        resting("a-second-best-bid", "BUY", 102, 1, 3),
        resting("z-low-bid", "BUY", 100, 1, 1),
        resting("z-first-best-ask", "SELL", 104, 1, 5),
        resting("a-second-best-ask", "SELL", 104, 1, 6),
        resting("z-high-ask", "SELL", 105, 1, 4),
    ]

