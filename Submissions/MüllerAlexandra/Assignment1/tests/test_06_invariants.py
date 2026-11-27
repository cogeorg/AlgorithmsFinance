"""Conservation and canonical-state checks use independently known quantities."""

from limit_order_book.interface import OrderBook

from helpers import cancel_event, limit_event, market_sell_event


def test_incoming_quantity_equals_fills_plus_returned_residual(
    book: OrderBook,
) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 101, 2))
    book.process_event(limit_event(2, "b2", "BUY", 100, 3))

    requested = 7
    result = book.process_event(market_sell_event(3, "s1", requested))

    executed = sum(item["qty_units"] for item in result["fills"])
    assert requested == executed + result["unfilled_qty_units"]


def test_maker_loses_exactly_its_fill_quantity(book: OrderBook) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 100, 10))

    result = book.process_event(market_sell_event(2, "s1", 4))

    maker_fill = sum(
        item["qty_units"] for item in result["fills"] if item["maker_id"] == "b1"
    )
    remaining = book.inspect_book()[0]["qty_units"]
    assert 10 == maker_fill + remaining


def test_cancellation_quantity_equals_removed_residual(book: OrderBook) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 100, 10))
    book.process_event(market_sell_event(2, "s1", 4))

    result = book.process_event(cancel_event(3, "b1"))

    assert result["cancelled_qty_units"] == 6
    assert book.inspect_book() == []


def test_proceeds_equal_sum_of_fill_price_times_quantity(book: OrderBook) -> None:
    book.process_event(limit_event(1, "b1", "BUY", 101, 2))
    book.process_event(limit_event(2, "b2", "BUY", 99, 3))

    result = book.process_event(market_sell_event(3, "s1", 4))

    proceeds = sum(
        item["price_ticks"] * item["qty_units"] for item in result["fills"]
    )
    assert proceeds == 101 * 2 + 99 * 2


def test_resting_book_is_uncrossed_positive_and_unique(book: OrderBook) -> None:
    events = [
        limit_event(1, "b1", "BUY", 100, 3),
        limit_event(2, "a1", "SELL", 105, 2),
        limit_event(3, "b2", "BUY", 106, 1),
        limit_event(4, "a2", "SELL", 99, 1),
    ]
    for event in events:
        result = book.process_event(event)
        assert result["status"] != "rejected"
        snapshot = book.inspect_book()
        ids = [order["order_id"] for order in snapshot]
        assert len(ids) == len(set(ids))
        assert all(order["qty_units"] > 0 for order in snapshot)
        bids = [order["price_ticks"] for order in snapshot if order["side"] == "BUY"]
        asks = [order["price_ticks"] for order in snapshot if order["side"] == "SELL"]
        assert not bids or not asks or max(bids) < min(asks)

