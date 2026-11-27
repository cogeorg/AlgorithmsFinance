from orderbook.revised import OrderBook


def _limit(seq, order_id, side, price_ticks, qty_units=10):
    return {
        "seq": seq,
        "event_id": f"e{seq}",
        "type": "LIMIT",
        "order_id": order_id,
        "side": side,
        "price_ticks": price_ticks,
        "qty_units": qty_units,
    }


def _market_sell(seq, order_id, qty_units):
    return {
        "seq": seq,
        "event_id": f"e{seq}",
        "type": "MARKET_SELL",
        "order_id": order_id,
        "qty_units": qty_units,
    }


def _cancel(seq, target_order_id):
    return {
        "seq": seq,
        "event_id": f"e{seq}",
        "type": "CANCEL",
        "target_order_id": target_order_id,
    }


def _active_levels(book, side):
    return book._bids_by_price if side == "BUY" else book._asks_by_price


def _heap_parts(book, side):
    if side == "BUY":
        return book._bid_heap, book._bid_heap_members
    return book._ask_heap, book._ask_heap_members


def test_cancelling_middle_of_price_queue_preserves_fifo():
    book = OrderBook()
    for seq, order_id in enumerate(("first", "middle", "last"), start=1):
        assert book.process_event(_limit(seq, order_id, "BUY", 6000))[
            "status"
        ] == "resting"

    assert book.process_event(_cancel(4, "middle")) == {
        "event_id": "e4",
        "target_order_id": "middle",
        "status": "cancelled",
        "cancelled_qty_units": 10,
    }
    result = book.process_event(_market_sell(5, "sell", 20))

    assert result["fills"] == [
        {
            "maker_id": "first",
            "taker_id": "sell",
            "price_ticks": 6000,
            "qty_units": 10,
        },
        {
            "maker_id": "last",
            "taker_id": "sell",
            "price_ticks": 6000,
            "qty_units": 10,
        },
    ]
    assert book.inspect_book() == {"bids": [], "asks": []}
    assert book._orders_by_id == {}


def test_partial_maker_keeps_fifo_priority_across_events():
    book = OrderBook()
    book.process_event(_limit(1, "first", "BUY", 6000, 10))
    book.process_event(_limit(2, "second", "BUY", 6000, 10))

    first_sale = book.process_event(_market_sell(3, "sell-a", 4))
    second_sale = book.process_event(_market_sell(4, "sell-b", 8))

    assert first_sale["fills"] == [
        {
            "maker_id": "first",
            "taker_id": "sell-a",
            "price_ticks": 6000,
            "qty_units": 4,
        }
    ]
    assert second_sale["fills"] == [
        {
            "maker_id": "first",
            "taker_id": "sell-b",
            "price_ticks": 6000,
            "qty_units": 6,
        },
        {
            "maker_id": "second",
            "taker_id": "sell-b",
            "price_ticks": 6000,
            "qty_units": 2,
        },
    ]
    assert book.inspect_book()["bids"] == [
        {
            "order_id": "second",
            "side": "BUY",
            "price_ticks": 6000,
            "qty_units": 8,
            "seq": 2,
        }
    ]


def test_reactivated_price_reuses_its_stale_heap_entry():
    book = OrderBook()
    book.process_event(_limit(1, "old-low", "BUY", 5000))
    book.process_event(_limit(2, "high", "BUY", 6000))
    book.process_event(_cancel(3, "old-low"))

    heap, members = _heap_parts(book, "BUY")
    assert len(heap) == 2
    assert len(members) == 2
    assert _active_levels(book, "BUY").keys() == {6000}

    book.process_event(_limit(4, "new-low", "BUY", 5000))
    assert len(book._bid_heap) == 2
    assert len(book._bid_heap_members) == 2

    result = book.process_event(_market_sell(5, "sell", 20))
    assert [fill["maker_id"] for fill in result["fills"]] == ["high", "new-low"]
    assert book.inspect_book() == {"bids": [], "asks": []}
    assert book._bid_heap == []
    assert book._bid_heap_members == set()


def test_worse_price_cancellations_leave_bounded_stale_heap_entries():
    book = OrderBook()
    for seq, price in enumerate((7000, 6000, 5000), start=1):
        book.process_event(_limit(seq, f"bid-{price}", "BUY", price))

    book.process_event(_cancel(4, "bid-6000"))
    book.process_event(_cancel(5, "bid-5000"))

    assert set(_active_levels(book, "BUY")) == {7000}
    assert len(book._orders_by_id) == 1
    assert len(book._bid_heap) == 3
    assert len(book._bid_heap_members) == 3
    assert len(book._bid_heap) > len(_active_levels(book, "BUY"))


def test_repeated_churn_stays_bounded_while_another_price_is_active():
    book = OrderBook()
    book.process_event(_limit(1, "anchor", "BUY", 100))
    seq = 2

    for index in range(160):
        order_id = f"transient-{index}"
        price = 1000 + index
        book.process_event(_limit(seq, order_id, "BUY", price))
        seq += 1
        book.process_event(_cancel(seq, order_id))
        seq += 1

        levels = _active_levels(book, "BUY")
        heap, members = _heap_parts(book, "BUY")
        assert set(levels) == {100}
        assert len(book._orders_by_id) == 1
        assert len(heap) <= 2 * len(levels) + 32
        assert len(heap) == len(members)
        assert set(heap) == members


def test_each_side_clears_heap_when_it_becomes_empty():
    book = OrderBook()
    book.process_event(_limit(1, "bid-a", "BUY", 6000))
    book.process_event(_limit(2, "bid-b", "BUY", 5900))
    book.process_event(_limit(3, "ask-a", "SELL", 6100))
    book.process_event(_limit(4, "ask-b", "SELL", 6200))

    book.process_event(_cancel(5, "bid-a"))
    book.process_event(_cancel(6, "bid-b"))
    assert book._bid_heap == []
    assert book._bid_heap_members == set()
    assert book._bids_by_price == {}

    book.process_event(_cancel(7, "ask-a"))
    book.process_event(_cancel(8, "ask-b"))
    assert book._ask_heap == []
    assert book._ask_heap_members == set()
    assert book._asks_by_price == {}
    assert book._orders_by_id == {}


def test_cleanup_preserves_best_price_and_fifo_matching_order():
    book = OrderBook()
    book.process_event(_limit(1, "first-best", "BUY", 7000, 10))
    book.process_event(_limit(2, "second-best", "BUY", 7000, 10))
    for offset in range(40):
        book.process_event(
            _limit(3 + offset, f"worse-{offset}", "BUY", 6900 - offset)
        )

    seq = 43
    for offset in range(40):
        book.process_event(_cancel(seq, f"worse-{offset}"))
        seq += 1

    active_levels = _active_levels(book, "BUY")
    assert set(active_levels) == {7000}
    assert len(book._bid_heap) < 41
    assert len(book._bid_heap) <= 2 * len(active_levels) + 32
    result = book.process_event(_market_sell(seq, "sell", 15))

    assert result["fills"] == [
        {
            "maker_id": "first-best",
            "taker_id": "sell",
            "price_ticks": 7000,
            "qty_units": 10,
        },
        {
            "maker_id": "second-best",
            "taker_id": "sell",
            "price_ticks": 7000,
            "qty_units": 5,
        },
    ]
    assert book.inspect_book()["bids"] == [
        {
            "order_id": "second-best",
            "side": "BUY",
            "price_ticks": 7000,
            "qty_units": 5,
            "seq": 2,
        }
    ]
