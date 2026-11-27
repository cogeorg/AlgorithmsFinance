"""Invalid input must be rejected, never crash, and never change the book (SPEC.md D1-D9).

Every bad event is sent into a book that already holds
    b1  BUY  100 x 10  (seq 1)
    a1  SELL 101 x 10  (seq 2)
Most bad events are built so that, if they were wrongly accepted, they WOULD trade
(e.g. a SELL priced at or below 100). So a missing check shows up as a changed book,
not only as a wrong status. After each rejection the next valid seq (3) must still work,
which proves the rejected event did not advance the last accepted seq.
"""
import pytest

from helpers import (BUY, SELL, cancel, cancelled, fill, limit, msell, not_found, order,
                     rejected, run, step, submitted)

START = [order("b1", BUY, 100, 10, 1), order("a1", SELL, 101, 10, 2)]


@pytest.fixture
def two_sided(book):
    run(book, [limit(1, "b1", BUY, 100, 10), limit(2, "a1", SELL, 101, 10)])
    assert book.snapshot() == START
    return book


def good_sell(seq=3, **overrides):
    """A SELL that crosses b1 if accepted. Override single fields to break it."""
    ev = {"seq": seq, "event_id": f"e{seq}", "type": "LIMIT", "order_id": "x",
          "side": SELL, "price_ticks": 100, "qty_units": 5}
    ev.update(overrides)
    return ev


def without(ev, key):
    ev = dict(ev)
    del ev[key]
    return ev


def assert_still_accepts_seq_3(book):
    """Last accepted seq must still be 2: a non-crossing seq-3 order is accepted."""
    res = step(book, limit(3, "probe", BUY, 50, 1))
    assert res == submitted("e3", "probe", "resting", 1)


# --- (event, expected event_id in the result, expected reason) --------------------------
BAD_EVENTS = [
    # 0: not a JSON object at all
    (None, None, "malformed_event"),
    ([], None, "malformed_event"),
    ([{"seq": 3}], None, "malformed_event"),
    ("LIMIT", None, "malformed_event"),
    (42, None, "malformed_event"),
    ({"_parse_error": 7}, None, "malformed_event"),          # reader marker
    # 1/2: seq
    ({}, None, "invalid_seq"),
    (without(good_sell(), "seq"), "e3", "invalid_seq"),
    (good_sell(seq=None), "eNone", "invalid_seq"),
    (good_sell(seq="3"), "e3", "invalid_seq"),
    (good_sell(seq=3.0), "e3.0", "invalid_seq"),
    (good_sell(seq=True), "eTrue", "invalid_seq"),            # True == 1, but a bool
    (good_sell(seq=False), "eFalse", "invalid_seq"),
    (good_sell(seq=0), "e0", "invalid_seq"),
    (good_sell(seq=-3), "e-3", "invalid_seq"),
    (good_sell(seq=[3]), "e[3]", "invalid_seq"),
    (good_sell(seq=2), "e2", "nonincreasing_seq"),            # equal to last accepted
    (good_sell(seq=1), "e1", "nonincreasing_seq"),
    # 3: event_id
    (without(good_sell(), "event_id"), None, "invalid_event_id"),
    (good_sell(event_id=""), None, "invalid_event_id"),
    (good_sell(event_id=None), None, "invalid_event_id"),
    (good_sell(event_id=3), None, "invalid_event_id"),
    (good_sell(event_id=["e3"]), None, "invalid_event_id"),
    # 4: type (lists/dicts are unhashable: a dict lookup on them would crash)
    (without(good_sell(), "type"), "e3", "unknown_type"),
    (good_sell(type="limit"), "e3", "unknown_type"),
    (good_sell(type="MARKET_BUY"), "e3", "unknown_type"),
    (good_sell(type=""), "e3", "unknown_type"),
    (good_sell(type=None), "e3", "unknown_type"),
    (good_sell(type=["LIMIT"]), "e3", "unknown_type"),
    (good_sell(type={"LIMIT": 1}), "e3", "unknown_type"),
    (good_sell(type=" LIMIT"), "e3", "unknown_type"),
    # 5: order_id
    (without(good_sell(), "order_id"), "e3", "invalid_order_id"),
    (good_sell(order_id=""), "e3", "invalid_order_id"),
    (good_sell(order_id=None), "e3", "invalid_order_id"),
    (good_sell(order_id=7), "e3", "invalid_order_id"),
    (good_sell(order_id=["x"]), "e3", "invalid_order_id"),
    (good_sell(order_id={"x": 1}), "e3", "invalid_order_id"),
    (without(msell(3, "s", 5), "order_id"), "e3", "invalid_order_id"),
    (msell(3, ["s"], 5), "e3", "invalid_order_id"),
    (msell(3, None, 5), "e3", "invalid_order_id"),
    # 6: side
    (without(good_sell(), "side"), "e3", "unknown_side"),
    (good_sell(side="sell"), "e3", "unknown_side"),
    (good_sell(side="Sell"), "e3", "unknown_side"),
    (good_sell(side=""), "e3", "unknown_side"),
    (good_sell(side=None), "e3", "unknown_side"),
    (good_sell(side=["SELL"]), "e3", "unknown_side"),
    (good_sell(side=1), "e3", "unknown_side"),
    # 7: price
    (without(good_sell(), "price_ticks"), "e3", "invalid_price"),
    (good_sell(price_ticks=0), "e3", "invalid_price"),
    (good_sell(price_ticks=-1), "e3", "invalid_price"),
    (good_sell(price_ticks=99.5), "e3", "invalid_price"),
    (good_sell(price_ticks=100.0), "e3", "invalid_price"),      # integral float
    (good_sell(price_ticks="100"), "e3", "invalid_price"),
    (good_sell(price_ticks=True), "e3", "invalid_price"),       # True == 1 would cross
    (good_sell(price_ticks=False), "e3", "invalid_price"),
    (good_sell(price_ticks=None), "e3", "invalid_price"),
    (good_sell(price_ticks=[100]), "e3", "invalid_price"),
    (good_sell(price_ticks=float("nan")), "e3", "invalid_price"),
    (good_sell(price_ticks=float("inf")), "e3", "invalid_price"),
    # 8: quantity (LIMIT and MARKET_SELL)
    (without(good_sell(), "qty_units"), "e3", "invalid_qty"),
    (good_sell(qty_units=0), "e3", "invalid_qty"),
    (good_sell(qty_units=-5), "e3", "invalid_qty"),
    (good_sell(qty_units=2.5), "e3", "invalid_qty"),
    (good_sell(qty_units=5.0), "e3", "invalid_qty"),
    (good_sell(qty_units="5"), "e3", "invalid_qty"),
    (good_sell(qty_units=True), "e3", "invalid_qty"),
    (good_sell(qty_units=None), "e3", "invalid_qty"),
    (without(msell(3, "s", 5), "qty_units"), "e3", "invalid_qty"),
    (msell(3, "s", 0), "e3", "invalid_qty"),
    (msell(3, "s", -1), "e3", "invalid_qty"),
    (msell(3, "s", True), "e3", "invalid_qty"),
    (msell(3, "s", 1.0), "e3", "invalid_qty"),
    (msell(3, "s", "5"), "e3", "invalid_qty"),
    (msell(3, "s", None), "e3", "invalid_qty"),
    (msell(3, "s", float("inf")), "e3", "invalid_qty"),
    # 9: cancel target
    (without(cancel(3, "b1"), "target_order_id"), "e3", "invalid_target_order_id"),
    (cancel(3, ""), "e3", "invalid_target_order_id"),
    (cancel(3, None), "e3", "invalid_target_order_id"),
    (cancel(3, 1), "e3", "invalid_target_order_id"),
    (cancel(3, ["b1"]), "e3", "invalid_target_order_id"),
    (cancel(3, {"b1": 1}), "e3", "invalid_target_order_id"),
    # 10: duplicate live order id (D5), all of these would trade if accepted
    (good_sell(order_id="b1"), "e3", "duplicate_live_order_id"),
    (good_sell(order_id="a1"), "e3", "duplicate_live_order_id"),
    (limit(3, "a1", BUY, 101, 5), "e3", "duplicate_live_order_id"),
    (msell(3, "b1", 5), "e3", "duplicate_live_order_id"),
    (msell(3, "a1", 5), "e3", "duplicate_live_order_id"),
]


@pytest.mark.parametrize("event,event_id,reason", BAD_EVENTS,
                         ids=[f"{i:02d}-{r}" for i, (_, _, r) in enumerate(BAD_EVENTS)])
def test_bad_event_rejected_book_and_seq_unchanged(two_sided, event, event_id, reason):
    res = step(two_sided, event)
    assert res == rejected(event_id, reason)
    assert two_sided.snapshot() == START
    assert_still_accepts_seq_3(two_sided)


# --- D9: with several errors, the FIRST check in the fixed order wins ------------------
ORDER_CASES = [
    (good_sell(seq=0, type="nope"), "invalid_seq"),
    (good_sell(seq=2, event_id=""), "nonincreasing_seq"),
    (good_sell(event_id=5, type="nope"), "invalid_event_id"),
    (good_sell(type="nope", price_ticks=-1), "unknown_type"),
    (good_sell(order_id=None, side="x", price_ticks=0, qty_units=0), "invalid_order_id"),
    (good_sell(side="x", price_ticks=0, qty_units=0), "unknown_side"),
    (good_sell(price_ticks=0, qty_units=0), "invalid_price"),
    (good_sell(order_id="b1", qty_units=0), "invalid_qty"),     # duplicate check is last
    (good_sell(order_id="b1", price_ticks=1.5), "invalid_price"),
    (cancel(0, None), "invalid_seq"),
]


@pytest.mark.parametrize("event,reason", ORDER_CASES,
                         ids=[r for _, r in ORDER_CASES])
def test_first_failing_check_is_the_reason(two_sided, event, reason):
    res = step(two_sided, event)
    assert res["status"] == "rejected" and res["reason"] == reason
    assert two_sided.snapshot() == START


# --- seq bookkeeping -----------------------------------------------------------------
def test_first_event_seq_zero_rejected_seq_one_accepted(book):
    assert step(book, limit(0, "b1", BUY, 100, 1)) == rejected("e0", "invalid_seq")
    assert step(book, limit(1, "b1", BUY, 100, 1)) == submitted("e1", "b1", "resting", 1)


def test_rejected_high_seq_does_not_block_lower_seq(two_sided):
    # seq 10 is rejected (bad price) -> last accepted stays 2 -> seq 4 is fine
    assert step(two_sided, good_sell(seq=10, price_ticks=0)) == rejected("e10", "invalid_price")
    res = step(two_sided, limit(4, "b2", BUY, 99, 1))
    assert res == submitted("e4", "b2", "resting", 1)


def test_seq_gaps_allowed_and_huge_seq(book):
    run(book, [limit(1, "b1", BUY, 100, 1), limit(1000, "b2", BUY, 100, 1)])
    huge = 10**30
    assert step(book, limit(huge, "b3", BUY, 100, 1)) == submitted(f"e{huge}", "b3", "resting", 1)
    assert step(book, limit(huge, "b4", BUY, 100, 1)) == rejected(f"e{huge}", "nonincreasing_seq")
    assert [o["order_id"] for o in book.snapshot()] == ["b1", "b2", "b3"]


def test_not_found_cancel_advances_seq(book):
    assert step(book, cancel(1, "ghost")) == not_found("e1", "ghost")
    assert step(book, limit(1, "b1", BUY, 100, 1)) == rejected("e1", "nonincreasing_seq")


def test_same_event_object_twice(book):
    ev = limit(1, "b1", BUY, 100, 1)
    assert step(book, ev) == submitted("e1", "b1", "resting", 1)
    assert step(book, ev) == rejected("e1", "nonincreasing_seq")
    assert book.snapshot() == [order("b1", BUY, 100, 1, 1)]


def test_duplicate_event_id_is_not_checked(book):
    """D3: event_id uniqueness is not validated."""
    run(book, [limit(1, "b1", BUY, 100, 1, event_id="same"),
               limit(2, "b2", BUY, 100, 1, event_id="same")])
    assert len(book.snapshot()) == 2


# --- D5: when an order id is "live" ------------------------------------------------------
def test_id_reusable_after_full_fill(book):
    run(book, [limit(1, "b1", BUY, 100, 5), msell(2, "s1", 5)])
    assert step(book, limit(3, "b1", BUY, 90, 2)) == submitted("e3", "b1", "resting", 2)
    assert book.snapshot() == [order("b1", BUY, 90, 2, 3)]


def test_id_reusable_after_cancel_and_goes_to_back_of_queue(book):
    run(book, [limit(1, "b1", BUY, 100, 1), limit(2, "b2", BUY, 100, 1), cancel(3, "b1"),
               limit(4, "b1", BUY, 100, 1)])
    assert book.snapshot() == [order("b2", BUY, 100, 1, 2), order("b1", BUY, 100, 1, 4)]
    assert step(book, msell(5, "s", 1))["fills"] == [fill("b2", "s", 100, 1)]


def test_partially_filled_order_is_still_live(book):
    run(book, [limit(1, "b1", BUY, 100, 5), msell(2, "s1", 2)])
    assert step(book, limit(3, "b1", BUY, 50, 1)) == rejected("e3", "duplicate_live_order_id")
    assert book.snapshot() == [order("b1", BUY, 100, 3, 1)]


def test_market_sell_id_never_becomes_live(book):
    run(book, [limit(1, "b1", BUY, 100, 5), msell(2, "s1", 2)])
    assert step(book, msell(3, "s1", 1)) == submitted("e3", "s1", "filled", 0,
                                                     [fill("b1", "s1", 100, 1)])
    assert step(book, limit(4, "s1", SELL, 200, 1)) == submitted("e4", "s1", "resting", 1)


def test_fully_filled_incoming_limit_id_reusable(book):
    run(book, [limit(1, "a1", SELL, 101, 5)])
    assert step(book, limit(2, "t", BUY, 101, 5))["status"] == "filled"
    assert step(book, limit(3, "t", BUY, 90, 1)) == submitted("e3", "t", "resting", 1)


def test_rejected_order_id_does_not_become_live(book):
    assert step(book, limit(1, "x", BUY, 0, 1)) == rejected("e1", "invalid_price")
    assert step(book, cancel(2, "x")) == not_found("e2", "x")
    assert step(book, limit(3, "x", BUY, 100, 1)) == submitted("e3", "x", "resting", 1)


# --- D7: extra fields are ignored -----------------------------------------------------
def test_extra_fields_ignored_on_limit(book):
    ev = dict(limit(1, "b1", BUY, 100, 3), comment=[1, 2], target_order_id="zzz")
    assert step(book, ev) == submitted("e1", "b1", "resting", 3)


def test_market_sell_ignores_side_and_price_fields(book):
    run(book, [limit(1, "b1", BUY, 100, 10)])
    ev = dict(msell(2, "s1", 4), side=BUY, price_ticks=999)   # still a market SELL
    assert step(book, ev) == submitted("e2", "s1", "filled", 0, [fill("b1", "s1", 100, 4)])
    assert book.snapshot() == [order("b1", BUY, 100, 6, 1)]


def test_cancel_ignores_extra_order_id_field(book):
    run(book, [limit(1, "b1", BUY, 100, 10), limit(2, "b2", BUY, 100, 10)])
    ev = dict(cancel(3, "b1"), order_id="b2", price_ticks=5)
    assert step(book, ev) == cancelled("e3", "b1", 10)
    assert book.snapshot() == [order("b2", BUY, 100, 10, 2)]


# --- the engine must not share objects with the caller -------------------------------
def test_editing_returned_snapshot_does_not_change_book(book):
    run(book, [limit(1, "b1", BUY, 100, 10)])
    snap = book.snapshot()
    snap[0]["qty_units"] = 999
    snap.append(order("fake", BUY, 1, 1, 9))
    assert book.snapshot() == [order("b1", BUY, 100, 10, 1)]


def test_editing_returned_fills_does_not_change_book(book):
    run(book, [limit(1, "b1", BUY, 100, 10)])
    res = step(book, msell(2, "s1", 3))
    res["fills"][0]["qty_units"] = 10
    res["fills"].clear()
    assert book.snapshot() == [order("b1", BUY, 100, 7, 1)]


def test_editing_the_event_after_submit_does_not_change_book(book):
    ev = limit(1, "b1", BUY, 100, 10)
    step(book, ev)
    ev["qty_units"] = 1
    ev["price_ticks"] = 5
    assert book.snapshot() == [order("b1", BUY, 100, 10, 1)]
