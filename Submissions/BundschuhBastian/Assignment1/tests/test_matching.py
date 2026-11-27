"""Hand-calculated matching cases. Every expected value was worked out on paper.

Small prices (100 = "100 ticks") keep the arithmetic readable; the rules do not depend on
the size of the numbers. Notation in comments: `b1 100x10 @1` = order b1, price 100,
quantity 10, arrival seq 1. Every event goes through step(), so invariants and conservation
are also checked after each event.
"""
from helpers import (BUY, SELL, fill, limit, msell, order, run, step, submitted)


# --- empty book and one order --------------------------------------------------------
def test_empty_book(book):
    assert book.snapshot() == []
    assert book.best_bid() is None and book.best_ask() is None


def test_market_sell_into_empty_book(book):
    assert step(book, msell(1, "s1", 5)) == submitted("e1", "s1", "unfilled", 5)
    assert book.snapshot() == []


def test_one_limit_buy_rests(book):
    assert step(book, limit(1, "b1", BUY, 100, 10)) == submitted("e1", "b1", "resting", 10)
    assert book.snapshot() == [order("b1", BUY, 100, 10, 1)]
    assert book.best_bid() == 100 and book.best_ask() is None


def test_one_limit_sell_rests(book):
    assert step(book, limit(1, "a1", SELL, 101, 10)) == submitted("e1", "a1", "resting", 10)
    assert book.best_bid() is None and book.best_ask() == 101


def test_market_sell_with_only_asks(book):
    # market sell only takes BIDS; the ask must stay untouched
    run(book, [limit(1, "a1", SELL, 101, 10)])
    assert step(book, msell(2, "s1", 5)) == submitted("e2", "s1", "unfilled", 5)
    assert book.snapshot() == [order("a1", SELL, 101, 10, 1)]


def test_minimum_values_price_1_qty_1(book):
    run(book, [limit(1, "b1", BUY, 1, 1)])
    assert step(book, msell(2, "s1", 1)) == submitted("e2", "s1", "filled", 0,
                                                     [fill("b1", "s1", 1, 1)])
    assert book.snapshot() == []


# --- sale smaller / equal / larger than depth --------------------------------------------
def test_sell_smaller_than_depth(book):
    # b1 100x10; sell 4 -> b1 gives 4 at 100, keeps 6 and its arrival 1
    run(book, [limit(1, "b1", BUY, 100, 10)])
    assert step(book, msell(2, "s1", 4)) == submitted("e2", "s1", "filled", 0,
                                                     [fill("b1", "s1", 100, 4)])
    assert book.snapshot() == [order("b1", BUY, 100, 6, 1)]


def test_sell_equal_to_depth_empties_book(book):
    run(book, [limit(1, "b1", BUY, 100, 10)])
    assert step(book, msell(2, "s1", 10)) == submitted("e2", "s1", "filled", 0,
                                                      [fill("b1", "s1", 100, 10)])
    assert book.snapshot() == [] and book.best_bid() is None


def test_sell_larger_than_depth_then_book_still_works(book):
    # sell 15 against 10 -> partial, 5 discarded (never rests)
    run(book, [limit(1, "b1", BUY, 100, 10)])
    assert step(book, msell(2, "s1", 15)) == submitted("e2", "s1", "partial", 5,
                                                      [fill("b1", "s1", 100, 10)])
    assert book.snapshot() == [] and book.best_bid() is None
    # a stale "best bid" would make this sell try to trade with a ghost order
    assert step(book, limit(3, "a1", SELL, 1, 3)) == submitted("e3", "a1", "resting", 3)
    assert book.snapshot() == [order("a1", SELL, 1, 3, 3)]


def test_market_sell_partial_leaves_asks_alone(book):
    run(book, [limit(1, "b1", BUY, 100, 1), limit(2, "a1", SELL, 101, 1)])
    assert step(book, msell(3, "s1", 3)) == submitted("e3", "s1", "partial", 2,
                                                     [fill("b1", "s1", 100, 1)])
    assert book.snapshot() == [order("a1", SELL, 101, 1, 2)]


# --- several makers at one price, several prices -----------------------------------------
def test_fifo_at_one_price(book):
    # b1 3, b2 4, b3 5 at 100; sell 8 -> b1 3 + b2 4 + b3 1 = 8; b3 keeps 4
    run(book, [limit(1, "b1", BUY, 100, 3), limit(2, "b2", BUY, 100, 4),
               limit(3, "b3", BUY, 100, 5)])
    assert step(book, msell(4, "s1", 8)) == submitted("e4", "s1", "filled", 0, [
        fill("b1", "s1", 100, 3), fill("b2", "s1", 100, 4), fill("b3", "s1", 100, 1)])
    assert book.snapshot() == [order("b3", BUY, 100, 4, 3)]


def test_several_prices_best_first_not_arrival_first(book):
    # arrival order 100, 98, 99 -> execution order must be 100, 99, 98
    # sell 5: b1 100x2 (200) + b3 99x2 (198) + b2 98x1 (98); proceeds 496
    run(book, [limit(1, "b1", BUY, 100, 2), limit(2, "b2", BUY, 98, 2),
               limit(3, "b3", BUY, 99, 2)])
    res = step(book, msell(4, "s1", 5))
    assert res == submitted("e4", "s1", "filled", 0, [
        fill("b1", "s1", 100, 2), fill("b3", "s1", 99, 2), fill("b2", "s1", 98, 1)])
    assert sum(f["price_ticks"] * f["qty_units"] for f in res["fills"]) == 496
    assert book.snapshot() == [order("b2", BUY, 98, 1, 2)]


def test_partial_fill_keeps_priority_over_later_order(book):
    # b1 100x10 @1, b2 100x10 @2; sell 3 -> b1 left 7 (still first)
    # b3 100x10 @4 arrives; sell 12 -> b1 7 + b2 5; b2 left 5, b3 untouched
    run(book, [limit(1, "b1", BUY, 100, 10), limit(2, "b2", BUY, 100, 10)])
    assert step(book, msell(3, "s1", 3))["fills"] == [fill("b1", "s1", 100, 3)]
    step(book, limit(4, "b3", BUY, 100, 10))
    assert step(book, msell(5, "s2", 12)) == submitted("e5", "s2", "filled", 0, [
        fill("b1", "s2", 100, 7), fill("b2", "s2", 100, 5)])
    assert book.snapshot() == [order("b2", BUY, 100, 5, 2), order("b3", BUY, 100, 10, 4)]


def test_identifier_spelling_never_decides_priority(book):
    # arrival: "z9", "a1", "10", "9" (string sort would give "10","9","a1","z9")
    run(book, [limit(1, "z9", BUY, 100, 1), limit(2, "a1", BUY, 100, 1),
               limit(3, "10", BUY, 100, 1), limit(4, "9", BUY, 100, 1)])
    assert [o["order_id"] for o in book.snapshot()] == ["z9", "a1", "10", "9"]
    assert step(book, msell(5, "s1", 3))["fills"] == [
        fill("z9", "s1", 100, 1), fill("a1", "s1", 100, 1), fill("10", "s1", 100, 1)]
    assert book.snapshot() == [order("9", BUY, 100, 1, 4)]


def test_long_queue_at_one_price(book):
    # 1000 orders, qty 2 each, ids counting DOWN (o0999 arrives first)
    # sell 501 -> 250 full fills (500) + 1 unit from the 251st order
    events = [limit(i, f"o{1000 - i:04d}", BUY, 100, 2) for i in range(1, 1001)]
    run(book, events)
    res = step(book, msell(1001, "s1", 501))
    expected = [fill(f"o{1000 - i:04d}", "s1", 100, 2) for i in range(1, 251)]
    expected.append(fill("o0749", "s1", 100, 1))           # arrival 251 -> id o0749
    assert res == submitted("e1001", "s1", "filled", 0, expected)
    snap = book.snapshot()
    assert len(snap) == 750
    assert snap[0] == order("o0749", BUY, 100, 1, 251)
    assert snap[-1] == order("o0000", BUY, 100, 2, 1000)
    assert [o["arrival_seq"] for o in snap] == list(range(251, 1001))


def test_fills_only_for_current_event(book):
    run(book, [limit(1, "b1", BUY, 100, 5)])
    assert step(book, msell(2, "s1", 2))["fills"] == [fill("b1", "s1", 100, 2)]
    assert step(book, msell(3, "s2", 1))["fills"] == [fill("b1", "s2", 100, 1)]
    assert step(book, limit(4, "b2", BUY, 90, 1))["fills"] == []


# --- crossing limit orders ----------------------------------------------------------------
def test_crossing_limit_buy_sweeps_levels_at_resting_prices_and_rests(book):
    # asks: a1 101x2 @1, a2 102x3 @2, a3 101x1 @3, a4 105x5 @4
    # buy 103 x 7: 101 queue (a1 2, a3 1) then 102 (a2 3) = 6; 105 > 103 stop; 1 rests at 103
    run(book, [limit(1, "a1", SELL, 101, 2), limit(2, "a2", SELL, 102, 3),
               limit(3, "a3", SELL, 101, 1), limit(4, "a4", SELL, 105, 5)])
    assert step(book, limit(5, "B", BUY, 103, 7)) == submitted("e5", "B", "resting", 1, [
        fill("a1", "B", 101, 2), fill("a3", "B", 101, 1), fill("a2", "B", 102, 3)])
    assert book.snapshot() == [order("B", BUY, 103, 1, 5), order("a4", SELL, 105, 5, 4)]


def test_crossing_limit_sell_gets_the_better_bid_prices(book):
    # bids: b1 100x2 @1, b2 99x2 @2, b3 100x1 @3; sell 99 x 4
    # -> b1 100x2, b3 100x1, b2 99x1; proceeds 200 + 100 + 99 = 399 (not 4 x 99 = 396)
    run(book, [limit(1, "b1", BUY, 100, 2), limit(2, "b2", BUY, 99, 2),
               limit(3, "b3", BUY, 100, 1)])
    res = step(book, limit(4, "S", SELL, 99, 4))
    assert res == submitted("e4", "S", "filled", 0, [
        fill("b1", "S", 100, 2), fill("b3", "S", 100, 1), fill("b2", "S", 99, 1)])
    assert sum(f["price_ticks"] * f["qty_units"] for f in res["fills"]) == 399
    assert book.snapshot() == [order("b2", BUY, 99, 1, 2)]


def test_cross_at_exact_equality_and_one_tick_below_does_not(book):
    run(book, [limit(1, "a1", SELL, 101, 5)])
    assert step(book, limit(2, "t1", BUY, 101, 2)) == submitted("e2", "t1", "filled", 0,
                                                               [fill("a1", "t1", 101, 2)])
    assert step(book, limit(3, "t2", BUY, 100, 2)) == submitted("e3", "t2", "resting", 2)
    assert book.snapshot() == [order("t2", BUY, 100, 2, 3), order("a1", SELL, 101, 3, 1)]
    # sell one tick above the bid: no cross
    assert step(book, limit(4, "t3", SELL, 101, 1)) == submitted("e4", "t3", "resting", 1)
    # sell exactly at the bid: crosses
    assert step(book, limit(5, "t4", SELL, 100, 1)) == submitted("e5", "t4", "filled", 0,
                                                                [fill("t2", "t4", 100, 1)])


def test_crossing_buy_does_not_touch_own_side(book):
    run(book, [limit(1, "b1", BUY, 99, 1), limit(2, "a1", SELL, 101, 1)])
    assert step(book, limit(3, "t", BUY, 101, 1))["fills"] == [fill("a1", "t", 101, 1)]
    assert book.snapshot() == [order("b1", BUY, 99, 1, 1)]


def test_buy_stops_at_its_limit_inside_the_ask_ladder(book):
    # asks 101, 102, 103 (1 each); buy 102 x 10 -> 101, 102 fill; 8 rest at 102; 103 stays
    run(book, [limit(1, "a1", SELL, 101, 1), limit(2, "a2", SELL, 102, 1),
               limit(3, "a3", SELL, 103, 1)])
    assert step(book, limit(4, "B", BUY, 102, 10)) == submitted("e4", "B", "resting", 8, [
        fill("a1", "B", 101, 1), fill("a2", "B", 102, 1)])
    assert book.snapshot() == [order("B", BUY, 102, 8, 4), order("a3", SELL, 103, 1, 3)]


def test_limit_eats_whole_side_rests_and_book_flips(book):
    # asks a1 101x1, a2 102x1; buy 200 x 5 -> both asks, 3 rest at 200 (not at 102)
    run(book, [limit(1, "a1", SELL, 101, 1), limit(2, "a2", SELL, 102, 1)])
    assert step(book, limit(3, "B", BUY, 200, 5)) == submitted("e3", "B", "resting", 3, [
        fill("a1", "B", 101, 1), fill("a2", "B", 102, 1)])
    assert book.best_ask() is None and book.best_bid() == 200
    # market sell 1 -> B at 200; B left 2
    assert step(book, msell(4, "s1", 1))["fills"] == [fill("B", "s1", 200, 1)]
    # sell 150 x 5 crosses B (200): 2 at 200, 3 rest as an ASK at 150
    assert step(book, limit(5, "S", SELL, 150, 5)) == submitted("e5", "S", "resting", 3,
                                                               [fill("B", "S", 200, 2)])
    assert book.snapshot() == [order("S", SELL, 150, 3, 5)]
    assert book.best_bid() is None and book.best_ask() == 150


def test_emptied_level_is_recreated_cleanly(book):
    # bids 100x2, 99x2; sell 2 empties level 100 -> best bid 99
    run(book, [limit(1, "b1", BUY, 100, 2), limit(2, "b2", BUY, 99, 2)])
    step(book, msell(3, "s1", 2))
    assert book.best_bid() == 99
    # new order at 100 again: price beats the older 99 order
    step(book, limit(4, "b3", BUY, 100, 1))
    assert book.best_bid() == 100
    assert step(book, msell(5, "s2", 2))["fills"] == [fill("b3", "s2", 100, 1),
                                                      fill("b2", "s2", 99, 1)]
    assert book.snapshot() == [order("b2", BUY, 99, 1, 2)]


def test_huge_integers_stay_exact(book):
    # Python ints have no overflow; a float would lose the last digits here
    p, q = 10**15 + 1, 10**18 + 3
    run(book, [limit(1, "b1", BUY, p, q)])
    res = step(book, msell(2, "s1", 10**20))
    assert res == submitted("e2", "s1", "partial", 10**20 - q, [fill("b1", "s1", p, q)])
    assert res["fills"][0]["price_ticks"] * res["fills"][0]["qty_units"] == p * q
