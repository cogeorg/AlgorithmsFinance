"""Hand-calculated cancellation cases (SPEC.md rule 7, D6, D13).

Cancels in the middle of a queue, of the only order at the best price, and add/cancel
churn are where index structures go stale: the order is gone from one place but still
referenced from another.
"""
from helpers import (BUY, SELL, cancel, cancelled, fill, limit, msell, not_found, order,
                     run, step, submitted)


def test_cancel_on_empty_book(book):
    assert step(book, cancel(1, "b1")) == not_found("e1", "b1")


def test_cancel_before_any_fill(book):
    run(book, [limit(1, "b1", BUY, 100, 10)])
    assert step(book, cancel(2, "b1")) == cancelled("e2", "b1", 10)
    assert book.snapshot() == [] and book.best_bid() is None


def test_cancel_after_partial_fill_removes_only_residual(book):
    # 10 - 4 sold = 6 left -> cancel removes 6, not 10
    run(book, [limit(1, "b1", BUY, 100, 10), msell(2, "s1", 4)])
    assert step(book, cancel(3, "b1")) == cancelled("e3", "b1", 6)
    assert book.snapshot() == []


def test_cancel_after_full_fill_is_not_found(book):
    run(book, [limit(1, "b1", BUY, 100, 10), msell(2, "s1", 10)])
    assert step(book, cancel(3, "b1")) == not_found("e3", "b1")


def test_cancel_incoming_limit_that_filled_on_arrival(book):
    run(book, [limit(1, "a1", SELL, 101, 5), limit(2, "t", BUY, 101, 5)])
    assert step(book, cancel(3, "t")) == not_found("e3", "t")


def test_repeat_cancel(book):
    run(book, [limit(1, "b1", BUY, 100, 10)])
    assert step(book, cancel(2, "b1")) == cancelled("e2", "b1", 10)
    assert step(book, cancel(3, "b1")) == not_found("e3", "b1")
    assert step(book, cancel(4, "b1")) == not_found("e4", "b1")


def test_unknown_and_near_miss_targets(book):
    run(book, [limit(1, "b1", BUY, 100, 1), limit(2, "b10", BUY, 100, 1)])
    assert step(book, cancel(3, "nope")) == not_found("e3", "nope")
    assert step(book, cancel(4, "b1 ")) == not_found("e4", "b1 ")
    assert step(book, cancel(5, "B1")) == not_found("e5", "B1")
    assert step(book, cancel(6, "b1")) == cancelled("e6", "b1", 1)     # only exact id
    assert book.snapshot() == [order("b10", BUY, 100, 1, 2)]


def test_cancel_market_sell_id_is_not_found(book):
    run(book, [limit(1, "b1", BUY, 100, 1), msell(2, "s1", 5)])
    assert step(book, cancel(3, "s1")) == not_found("e3", "s1")


def test_cancel_ask(book):
    run(book, [limit(1, "a1", SELL, 101, 7), limit(2, "a2", SELL, 102, 1)])
    assert step(book, cancel(3, "a1")) == cancelled("e3", "a1", 7)
    assert book.best_ask() == 102


def three_at_100(book):
    run(book, [limit(1, "b1", BUY, 100, 1), limit(2, "b2", BUY, 100, 1),
               limit(3, "b3", BUY, 100, 1)])


def test_cancel_head_of_queue(book):
    three_at_100(book)
    step(book, cancel(4, "b1"))
    assert step(book, msell(5, "s", 1))["fills"] == [fill("b2", "s", 100, 1)]


def test_cancel_middle_of_queue(book):
    three_at_100(book)
    step(book, cancel(4, "b2"))
    assert step(book, msell(5, "s", 2))["fills"] == [fill("b1", "s", 100, 1),
                                                     fill("b3", "s", 100, 1)]


def test_cancel_tail_of_queue(book):
    three_at_100(book)
    step(book, cancel(4, "b3"))
    assert step(book, msell(5, "s", 3)) == submitted("e5", "s", "partial", 1, [
        fill("b1", "s", 100, 1), fill("b2", "s", 100, 1)])


def test_cancel_only_order_at_best_price_moves_best(book):
    run(book, [limit(1, "b1", BUY, 100, 1), limit(2, "b2", BUY, 99, 1),
               limit(3, "a1", SELL, 105, 1), limit(4, "a2", SELL, 106, 1)])
    step(book, cancel(5, "b1"))
    step(book, cancel(6, "a1"))
    assert book.best_bid() == 99 and book.best_ask() == 106
    # a stale level 100 would be hit here
    assert step(book, msell(7, "s", 1))["fills"] == [fill("b2", "s", 99, 1)]
    # a stale level 105 would be hit here
    assert step(book, limit(8, "t", BUY, 105, 1)) == submitted("e8", "t", "resting", 1)
    assert book.snapshot() == [order("t", BUY, 105, 1, 8), order("a2", SELL, 106, 1, 4)]


def test_cancel_everything_then_reuse_same_price(book):
    three_at_100(book)
    run(book, [cancel(4, "b2"), cancel(5, "b1"), cancel(6, "b3")])
    assert book.snapshot() == [] and book.best_bid() is None
    step(book, limit(7, "b4", BUY, 100, 2))
    assert step(book, msell(8, "s", 5)) == submitted("e8", "s", "partial", 3,
                                                    [fill("b4", "s", 100, 2)])


def test_cancel_then_crossing_order_skips_cancelled(book):
    run(book, [limit(1, "a1", SELL, 101, 5), limit(2, "a2", SELL, 101, 5), cancel(3, "a1")])
    assert step(book, limit(4, "t", BUY, 101, 7)) == submitted("e4", "t", "resting", 2,
                                                              [fill("a2", "t", 101, 5)])


def test_churn_add_cancel_keeps_book_tiny(book):
    # one order stays all the time; 300 add/cancel pairs around it
    step(book, limit(1, "keep", BUY, 50, 3))
    seq = 2
    for i in range(300):
        price = 100 - (i % 7)                      # reuse a few price levels
        assert step(book, limit(seq, f"c{i}", BUY, price, i + 1))["status"] == "resting"
        assert step(book, cancel(seq + 1, f"c{i}")) == cancelled(f"e{seq + 1}", f"c{i}", i + 1)
        seq += 2
    assert book.snapshot() == [order("keep", BUY, 50, 3, 1)]
    assert book.best_bid() == 50
    assert step(book, msell(seq, "s", 3))["fills"] == [fill("keep", "s", 50, 3)]
    assert book.snapshot() == [] and book.best_bid() is None
