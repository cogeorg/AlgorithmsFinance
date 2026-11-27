"""Hand-calculated matching cases (expected values written before any implementation)."""
from conftest import BTC, fill, order, run, usd


# ---------------------------------------------------------------- empty book, one order
def test_empty_book(book):
    assert book.snapshot() == {"bids": [], "asks": []}
    assert book.best_bid() is None and book.best_ask() is None


def test_market_sell_on_empty_book(book, stream):
    r = book.process(stream.market_sell("s1", 1))
    assert r == {"event_id": "ev1", "order_id": "s1", "status": "unfilled",
                 "unfilled_qty_units": BTC, "fills": []}
    assert book.snapshot() == {"bids": [], "asks": []}


def test_one_limit_order_rests(book, stream):
    r = book.process(stream.buy("b1", 60000, 1))
    assert r == {"event_id": "ev1", "order_id": "b1", "status": "resting",
                 "unfilled_qty_units": BTC, "fills": []}
    assert book.snapshot() == {"bids": [order("b1", "BUY", 60000, 1, 1)], "asks": []}
    assert book.best_bid() == usd(60000) and book.best_ask() is None


# ---------------------------------------------------------------- market sell sizes
def _two_bids_one_ask(book, stream):
    run(book, [stream.buy("b1", 60000, 1), stream.buy("b2", 60000, 1),
               stream.sell("a1", 60100, 2)])


def test_sell_smaller_than_depth(book, stream):
    _two_bids_one_ask(book, stream)
    r = book.process(stream.market_sell("s1", 0.5))
    assert r["fills"] == [fill("b1", "s1", 60000, 0.5)]
    assert r["status"] == "filled" and r["unfilled_qty_units"] == 0
    assert book.snapshot()["bids"] == [order("b1", "BUY", 60000, 0.5, 1),
                                       order("b2", "BUY", 60000, 1, 2)]


def test_sell_equal_to_depth(book, stream):
    _two_bids_one_ask(book, stream)
    r = book.process(stream.market_sell("s1", 2))
    assert r["fills"] == [fill("b1", "s1", 60000, 1), fill("b2", "s1", 60000, 1)]
    assert r["status"] == "filled" and r["unfilled_qty_units"] == 0
    assert book.snapshot() == {"bids": [], "asks": [order("a1", "SELL", 60100, 2, 3)]}


def test_sell_larger_than_depth_discards_residual(book, stream):
    _two_bids_one_ask(book, stream)
    r = book.process(stream.market_sell("s1", 3))
    assert r["fills"] == [fill("b1", "s1", 60000, 1), fill("b2", "s1", 60000, 1)]
    assert r["status"] == "partial" and r["unfilled_qty_units"] == BTC
    # the unfilled residual never rests; the ask side is untouched
    assert book.snapshot() == {"bids": [], "asks": [order("a1", "SELL", 60100, 2, 3)]}
    assert book.process(stream.cancel("s1"))["status"] == "not_found"


def test_market_sell_with_only_asks_is_unfilled(book, stream):
    book.process(stream.sell("a1", 60100, 1))
    r = book.process(stream.market_sell("s1", 1))
    assert r["status"] == "unfilled" and r["fills"] == [] and r["unfilled_qty_units"] == BTC
    assert book.snapshot()["asks"] == [order("a1", "SELL", 60100, 1, 1)]


# ---------------------------------------------------------------- priority
def test_fifo_at_one_price_ignores_id_spelling(book, stream):
    # "z" arrives before "a": arrival decides, not the identifier
    run(book, [stream.buy("z", 60000, 1), stream.buy("a", 60000, 1)])
    r = book.process(stream.market_sell("s1", 1.5))
    assert r["fills"] == [fill("z", "s1", 60000, 1), fill("a", "s1", 60000, 0.5)]
    assert book.snapshot()["bids"] == [order("a", "BUY", 60000, 0.5, 2)]


def test_numeric_looking_ids_are_not_sorted(book, stream):
    run(book, [stream.buy("b10", 60000, 1), stream.buy("b2", 60000, 1),
               stream.buy("b1", 60000, 1)])
    r = book.process(stream.market_sell("s1", 3))
    assert [f["maker_id"] for f in r["fills"]] == ["b10", "b2", "b1"]


def test_best_price_first_across_levels(book, stream):
    run(book, [stream.buy("low", 59900, 1), stream.buy("high", 60000, 1),
               stream.buy("mid", 59950, 1)])
    r = book.process(stream.market_sell("s1", 2.5))
    assert r["fills"] == [fill("high", "s1", 60000, 1), fill("mid", "s1", 59950, 1),
                          fill("low", "s1", 59900, 0.5)]
    assert book.snapshot()["bids"] == [order("low", "BUY", 59900, 0.5, 1)]


def test_partial_fill_keeps_priority_for_next_sale(book, stream):
    run(book, [stream.buy("b1", 60000, 1), stream.buy("b2", 60000, 1)])
    r1 = book.process(stream.market_sell("s1", 0.5))
    r2 = book.process(stream.market_sell("s2", 1))
    assert r1["fills"] == [fill("b1", "s1", 60000, 0.5)]
    assert r2["fills"] == [fill("b1", "s2", 60000, 0.5), fill("b2", "s2", 60000, 0.5)]
    assert book.snapshot()["bids"] == [order("b2", "BUY", 60000, 0.5, 2)]


def test_long_queue_at_one_price(book, stream):
    unit = 1_000_000                      # 0.01 BTC each
    ids = [f"q{999 - i:03d}" for i in range(1000)]     # spelling runs backwards
    run(book, [stream.limit(oid, "BUY", 60000, 0.01) for oid in ids])
    r = book.process(stream.market_sell("s1", units=500 * unit))
    assert [f["maker_id"] for f in r["fills"]] == ids[:500]
    assert all(f["qty_units"] == unit for f in r["fills"])
    bids = book.snapshot()["bids"]
    assert [o["order_id"] for o in bids] == ids[500:]
    assert [o["arrival_seq"] for o in bids] == list(range(501, 1001))


# ---------------------------------------------------------------- cancellation
def test_cancel_before_any_fill(book, stream):
    book.process(stream.buy("b1", 60000, 1))
    r = book.process(stream.cancel("b1"))
    assert r == {"event_id": "ev2", "target_order_id": "b1", "status": "cancelled",
                 "cancelled_qty_units": BTC}
    assert book.snapshot() == {"bids": [], "asks": []}


def test_cancel_after_partial_fill_removes_only_residual(book, stream):
    book.process(stream.buy("b1", 60000, 1))
    book.process(stream.market_sell("s1", 0.4))
    r = book.process(stream.cancel("b1"))
    assert r["status"] == "cancelled" and r["cancelled_qty_units"] == int(round(0.6 * BTC))
    assert book.snapshot()["bids"] == []


def test_cancel_after_full_fill_is_not_found(book, stream):
    book.process(stream.buy("b1", 60000, 1))
    book.process(stream.market_sell("s1", 1))
    r = book.process(stream.cancel("b1"))
    assert r == {"event_id": "ev3", "target_order_id": "b1", "status": "not_found",
                 "cancelled_qty_units": 0}


def test_repeated_and_unknown_cancel(book, stream):
    book.process(stream.buy("b1", 60000, 1))
    assert book.process(stream.cancel("b1"))["status"] == "cancelled"
    again = book.process(stream.cancel("b1"))
    unknown = book.process(stream.cancel("nobody"))
    for r in (again, unknown):
        assert r["status"] == "not_found" and r["cancelled_qty_units"] == 0
    assert book.snapshot() == {"bids": [], "asks": []}


def test_cancel_removes_order_from_priority(book, stream):
    run(book, [stream.buy("b1", 60000, 1), stream.buy("b2", 60000, 1), stream.cancel("b1")])
    r = book.process(stream.market_sell("s1", 0.5))
    assert r["fills"] == [fill("b2", "s1", 60000, 0.5)]


def test_cancel_ask(book, stream):
    run(book, [stream.sell("a1", 60100, 1), stream.sell("a2", 60100, 2)])
    r = book.process(stream.cancel("a1"))
    assert r["status"] == "cancelled" and r["cancelled_qty_units"] == BTC
    assert book.snapshot()["asks"] == [order("a2", "SELL", 60100, 2, 2)]


# ---------------------------------------------------------------- crossing limits
def test_crossing_buy_trades_at_resting_prices(book, stream):
    run(book, [stream.sell("a1", 60100, 1), stream.sell("a2", 60200, 2)])
    r = book.process(stream.buy("t", 60200, 2))
    assert r["fills"] == [fill("a1", "t", 60100, 1), fill("a2", "t", 60200, 1)]
    assert r["status"] == "filled" and r["unfilled_qty_units"] == 0
    assert book.snapshot() == {"bids": [], "asks": [order("a2", "SELL", 60200, 1, 2)]}


def test_crossing_buy_rests_residual_at_its_limit(book, stream):
    run(book, [stream.sell("a1", 60100, 1), stream.sell("a2", 60200, 2)])
    r = book.process(stream.buy("t", 60150, 4))
    assert r["fills"] == [fill("a1", "t", 60100, 1)]
    assert r["status"] == "resting" and r["unfilled_qty_units"] == 3 * BTC
    assert book.snapshot() == {"bids": [order("t", "BUY", 60150, 3, 3)],
                               "asks": [order("a2", "SELL", 60200, 2, 2)]}
    assert book.best_bid() < book.best_ask()


def test_crossing_sell_trades_at_resting_prices(book, stream):
    run(book, [stream.buy("b1", 60000, 1), stream.buy("b2", 59900, 1)])
    r = book.process(stream.sell("t", 59950, 1.5))
    assert r["fills"] == [fill("b1", "t", 60000, 1)]
    assert r["status"] == "resting" and r["unfilled_qty_units"] == int(round(0.5 * BTC))
    assert book.snapshot() == {"bids": [order("b2", "BUY", 59900, 1, 2)],
                               "asks": [order("t", "SELL", 59950, 0.5, 3)]}


def test_crossing_sell_sweeps_several_levels(book, stream):
    run(book, [stream.buy("b1", 60000, 1), stream.buy("b2", 59900, 1)])
    r = book.process(stream.sell("t", 59000, 3))
    assert r["fills"] == [fill("b1", "t", 60000, 1), fill("b2", "t", 59900, 1)]
    assert r["status"] == "resting" and r["unfilled_qty_units"] == BTC
    assert book.snapshot() == {"bids": [], "asks": [order("t", "SELL", 59000, 1, 3)]}


def test_limit_at_equal_price_crosses(book, stream):
    book.process(stream.sell("a1", 60100, 1))
    r = book.process(stream.buy("t", 60100, 1))
    assert r["fills"] == [fill("a1", "t", 60100, 1)] and r["status"] == "filled"
    assert book.snapshot() == {"bids": [], "asks": []}


def test_noncrossing_limits_rest(book, stream):
    run(book, [stream.sell("a1", 60100, 1)])
    r = book.process(stream.buy("b1", 60000, 1))
    assert r["fills"] == [] and r["status"] == "resting"
    assert book.best_bid() == usd(60000) and book.best_ask() == usd(60100)


def test_residual_keeps_its_own_arrival_rank(book, stream):
    run(book, [stream.sell("a1", 60100, 1), stream.buy("y", 60100, 2),
               stream.buy("z", 60100, 1)])
    r = book.process(stream.market_sell("s1", 1.5))
    assert r["fills"] == [fill("y", "s1", 60100, 1), fill("z", "s1", 60100, 0.5)]
    assert book.snapshot()["bids"] == [order("z", "BUY", 60100, 0.5, 3)]


# ---------------------------------------------------------------- named functions
def test_named_functions_exist_and_work(book, stream):
    book.AddLimitOrder(stream.buy("b1", 60000, 1))
    r = book.FillMarketSell(stream.market_sell("s1", 0.25))
    assert r["fills"] == [fill("b1", "s1", 60000, 0.25)]
    c = book.CancelOrder(stream.cancel("b1"))
    assert c["status"] == "cancelled" and c["cancelled_qty_units"] == int(round(0.75 * BTC))
