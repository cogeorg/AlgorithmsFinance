from orderbook.baseline import OrderBook


def test_market_sell_fills_same_price_orders_fifo_and_preserves_residual():
    book = OrderBook()

    book.process_event(
        {
            "seq": 1,
            "event_id": "e1",
            "type": "LIMIT",
            "order_id": "z_buyer",
            "side": "BUY",
            "price_ticks": 6000000,
            "qty_units": 200000000,
        }
    )
    book.process_event(
        {
            "seq": 2,
            "event_id": "e2",
            "type": "LIMIT",
            "order_id": "a_buyer",
            "side": "BUY",
            "price_ticks": 6000000,
            "qty_units": 300000000,
        }
    )
    result = book.process_event(
        {
            "seq": 3,
            "event_id": "e3",
            "type": "MARKET_SELL",
            "order_id": "sell_1",
            "qty_units": 300000000,
        }
    )

    assert result == {
        "event_id": "e3",
        "order_id": "sell_1",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            {
                "maker_id": "z_buyer",
                "taker_id": "sell_1",
                "price_ticks": 6000000,
                "qty_units": 200000000,
            },
            {
                "maker_id": "a_buyer",
                "taker_id": "sell_1",
                "price_ticks": 6000000,
                "qty_units": 100000000,
            },
        ],
    }
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "a_buyer",
                "side": "BUY",
                "price_ticks": 6000000,
                "qty_units": 200000000,
                "seq": 2,
            }
        ],
        "asks": [],
    }


def test_market_sell_prioritizes_higher_bid_before_earlier_lower_bid():
    book = OrderBook()

    book.process_event(
        {
            "seq": 1,
            "event_id": "e1",
            "type": "LIMIT",
            "order_id": "early_buyer",
            "side": "BUY",
            "price_ticks": 5990000,
            "qty_units": 200000000,
        }
    )
    book.process_event(
        {
            "seq": 2,
            "event_id": "e2",
            "type": "LIMIT",
            "order_id": "later_buyer",
            "side": "BUY",
            "price_ticks": 6000000,
            "qty_units": 100000000,
        }
    )
    result = book.process_event(
        {
            "seq": 3,
            "event_id": "e3",
            "type": "MARKET_SELL",
            "order_id": "sell_1",
            "qty_units": 200000000,
        }
    )

    assert result == {
        "event_id": "e3",
        "order_id": "sell_1",
        "status": "filled",
        "unfilled_qty_units": 0,
        "fills": [
            {
                "maker_id": "later_buyer",
                "taker_id": "sell_1",
                "price_ticks": 6000000,
                "qty_units": 100000000,
            },
            {
                "maker_id": "early_buyer",
                "taker_id": "sell_1",
                "price_ticks": 5990000,
                "qty_units": 100000000,
            },
        ],
    }
    assert book.inspect_book() == {
        "bids": [
            {
                "order_id": "early_buyer",
                "side": "BUY",
                "price_ticks": 5990000,
                "qty_units": 100000000,
                "seq": 1,
            }
        ],
        "asks": [],
    }
