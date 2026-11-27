"""Later evidence will compare ordered fills and canonical state after every event."""

from limit_order_book import BaselineOrderBook, RevisedOrderBook

from helpers import cancel_event, limit_event, market_sell_event


def test_versions_agree_after_every_event_on_small_mixed_stream() -> None:
    events = [
        limit_event(1, "b1", "BUY", 100, 4),
        limit_event(2, "b2", "BUY", 100, 2),
        limit_event(3, "a1", "SELL", 105, 3),
        market_sell_event(4, "s1", 5),
        cancel_event(5, "b2"),
        limit_event(6, "b3", "BUY", 106, 4),
        limit_event(7, "a2", "SELL", 104, 6),
        cancel_event(8, "unknown"),
    ]
    baseline = BaselineOrderBook()
    revised = RevisedOrderBook()

    for event in events:
        assert baseline.process_event(event) == revised.process_event(event)
        assert baseline.inspect_book() == revised.inspect_book()

