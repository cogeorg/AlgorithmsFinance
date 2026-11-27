"""OWN edge-case datasets (not supplied by the course): small hand-designed event streams
with hand-calculated expected results.

Usage (from the exercise root):
    python run.py datagen.own_cases            # (re)writes 06_data/own/
    python run.py datagen.own_cases --check    # exit 1 if 06_data/own/ differs from this file

For every case it writes
    06_data/own/<case>.jsonl           one event per line (JSON Lines, as the supplied files)
    06_data/own/<case>.expected.json   {"own": true, "results": [one result per event],
                                        "final_book": [...], "best_bid": .., "best_ask": ..}
Expected values are written out by hand below, from the rules in SPEC.md (no engine is
used). Only `long_queue` builds its expectation with a stated closed-form rule (FIFO =
arrival order; every maker holds 2 units). Deterministic: fixed seed 42 (`long_queue` ids
only), fixed key order, LF line endings.

Conventions: prices are small integer ticks (e.g. 100) so the arithmetic is easy to check
by hand; the units are those of SPEC.md. Valid events use event_id "e<seq>".
"""
import argparse
import json
import random
import sys
from pathlib import Path

SEED = 42
OUT = Path("06_data/own")


# ---- event builders -------------------------------------------------------------------
def L(seq, oid, side, price, qty, eid=None):
    return {"seq": seq, "event_id": eid or f"e{seq}", "type": "LIMIT", "order_id": oid,
            "side": side, "price_ticks": price, "qty_units": qty}


def M(seq, oid, qty, eid=None):
    return {"seq": seq, "event_id": eid or f"e{seq}", "type": "MARKET_SELL", "order_id": oid,
            "qty_units": qty}


def C(seq, target, eid=None):
    return {"seq": seq, "event_id": eid or f"e{seq}", "type": "CANCEL", "target_order_id": target}


# ---- expected-result builders (field names: README "Required results", worked_expected.json)
def F(maker, taker, price, qty):
    return {"maker_id": maker, "taker_id": taker, "price_ticks": price, "qty_units": qty}


def R_LIMIT(seq, oid, status, unfilled, *fills):
    assert status in ("filled", "resting")
    return {"event_id": f"e{seq}", "order_id": oid, "status": status,
            "unfilled_qty_units": unfilled, "fills": list(fills)}


def R_MKT(seq, oid, status, unfilled, *fills):
    assert status in ("filled", "partial", "unfilled")
    return {"event_id": f"e{seq}", "order_id": oid, "status": status,
            "unfilled_qty_units": unfilled, "fills": list(fills)}


def R_CXL(seq, target, status, qty, eid=None):
    assert status in ("cancelled", "not_found")
    return {"event_id": eid or f"e{seq}", "target_order_id": target, "status": status,
            "cancelled_qty_units": qty}


def R_REJ(eid, reason):
    return {"event_id": eid, "status": "rejected", "reason": reason}


def ROW(oid, side, price, qty, arrival):
    return {"order_id": oid, "side": side, "price_ticks": price, "qty_units": qty, "arrival_seq": arrival}


# ---- the shared table of invalid events (SPEC.md, Validation) ---------------------------
# Setup before every row: last accepted seq = 2; live orders b1 (BUY 100 x5, seq 1) and
# a1 (SELL 110 x5, seq 2). Each row is rejected; the expected reason is the FIRST failing
# rule in the fixed check order. Used by the `invalid_fields` case below, by the per-rule
# contract checks (02_tests/contract.py) and by 02_tests/test_validation.py.
INVALID_SETUP = [L(1, "b1", "BUY", 100, 5), L(2, "a1", "SELL", 110, 5)]
INVALID_SETUP_LAST_SEQ = 2
INVALID_SETUP_LIVE = ("b1", "a1")

_LIM = {"seq": 3, "type": "LIMIT", "order_id": "n1", "side": "BUY", "price_ticks": 99, "qty_units": 1}
_MKT = {"seq": 3, "type": "MARKET_SELL", "order_id": "n1", "qty_units": 1}
_CXL = {"seq": 3, "type": "CANCEL", "target_order_id": "b1"}
_DROP = object()          # marker: remove this key
_AUTO = object()          # marker: result event_id = the row's auto event_id


def _row(label, base, reason, changes=None, result_eid=_AUTO):
    """One invalid event: base template + auto event_id 'x-<label>' + changes (value _DROP removes the key)."""
    ev = {"seq": base["seq"], "event_id": f"x-{label}", **{k: v for k, v in base.items() if k != "seq"}}
    for k, v in (changes or {}).items():
        if v is _DROP:
            ev.pop(k, None)
        else:
            ev[k] = v
    eid = f"x-{label}" if result_eid is _AUTO else result_eid
    return {"label": label, "event": ev, "reason": reason, "result_event_id": eid}


NAN, INF = float("nan"), float("inf")
INVALID_EVENTS = [
    # not a JSON object -> event_id unavailable
    {"label": "list", "event": [1, 2, 3], "reason": "not_an_object", "result_event_id": None},
    {"label": "string", "event": "LIMIT", "reason": "not_an_object", "result_event_id": None},
    {"label": "null", "event": None, "reason": "not_an_object", "result_event_id": None},
    {"label": "number", "event": 7, "reason": "not_an_object", "result_event_id": None},
    # seq
    _row("seq-missing", _LIM, "missing_field:seq", {"seq": _DROP}),
    _row("seq-zero", _LIM, "bad_seq", {"seq": 0}),
    _row("seq-negative", _LIM, "bad_seq", {"seq": -3}),
    _row("seq-bool", _LIM, "bad_seq", {"seq": True}),
    _row("seq-float", _LIM, "bad_seq", {"seq": 3.0}),
    _row("seq-string", _LIM, "bad_seq", {"seq": "3"}),
    _row("seq-null", _LIM, "bad_seq", {"seq": None}),
    _row("seq-equal-limit", _LIM, "nonincreasing_seq", {"seq": 2}),
    _row("seq-lower-limit", _LIM, "nonincreasing_seq", {"seq": 1}),
    _row("seq-equal-market", _MKT, "nonincreasing_seq", {"seq": 2}),
    _row("seq-lower-cancel", _CXL, "nonincreasing_seq", {"seq": 1}),
    # type (exact, case-sensitive spelling, Q14)
    _row("type-missing", _LIM, "missing_field:type", {"type": _DROP}),
    _row("type-market-buy", _LIM, "unknown_type", {"type": "MARKET_BUY"}),
    _row("type-lowercase", _LIM, "unknown_type", {"type": "limit"}),
    _row("type-empty", _LIM, "unknown_type", {"type": ""}),
    _row("type-null", _LIM, "unknown_type", {"type": None}),
    _row("type-number", _LIM, "unknown_type", {"type": 5}),
    # missing required fields (Q3), reported in REQUIRED_FIELDS order
    _row("limit-no-event-id", _LIM, "missing_field:event_id", {"event_id": _DROP}, result_eid=None),
    _row("limit-no-order-id", _LIM, "missing_field:order_id", {"order_id": _DROP}),
    _row("limit-no-side", _LIM, "missing_field:side", {"side": _DROP}),
    _row("limit-no-price", _LIM, "missing_field:price_ticks", {"price_ticks": _DROP}),
    _row("limit-no-qty", _LIM, "missing_field:qty_units", {"qty_units": _DROP}),
    _row("market-no-event-id", _MKT, "missing_field:event_id", {"event_id": _DROP}, result_eid=None),
    _row("market-no-order-id", _MKT, "missing_field:order_id", {"order_id": _DROP}),
    _row("market-no-qty", _MKT, "missing_field:qty_units", {"qty_units": _DROP}),
    _row("cancel-no-event-id", _CXL, "missing_field:event_id", {"event_id": _DROP}, result_eid=None),
    _row("cancel-no-target", _CXL, "missing_field:target_order_id", {"target_order_id": _DROP}),
    # identifiers must be non-empty strings (Q3); a present null is a bad id, not a missing field
    _row("event-id-empty", _LIM, "bad_id:event_id", {"event_id": ""}, result_eid=None),
    _row("event-id-number", _LIM, "bad_id:event_id", {"event_id": 7}, result_eid=None),
    _row("event-id-null", _CXL, "bad_id:event_id", {"event_id": None}, result_eid=None),
    _row("order-id-empty", _LIM, "bad_id:order_id", {"order_id": ""}),
    _row("order-id-number", _LIM, "bad_id:order_id", {"order_id": 12}),
    _row("order-id-null", _LIM, "bad_id:order_id", {"order_id": None}),
    _row("market-order-id-number", _MKT, "bad_id:order_id", {"order_id": 5}),
    _row("target-empty", _CXL, "bad_id:target_order_id", {"target_order_id": ""}),
    _row("target-number", _CXL, "bad_id:target_order_id", {"target_order_id": 5}),
    _row("target-null", _CXL, "bad_id:target_order_id", {"target_order_id": None}),
    # side (exact spelling)
    _row("side-lowercase", _LIM, "unknown_side", {"side": "buy"}),
    _row("side-hold", _LIM, "unknown_side", {"side": "HOLD"}),
    _row("side-empty", _LIM, "unknown_side", {"side": ""}),
    _row("side-null", _LIM, "unknown_side", {"side": None}),
    _row("side-number", _LIM, "unknown_side", {"side": 1}),
    # price_ticks: only int, not bool, > 0 (Q4)
    _row("price-zero", _LIM, "bad_price", {"price_ticks": 0}),
    _row("price-negative", _LIM, "bad_price", {"price_ticks": -100}),
    _row("price-integral-float", _LIM, "bad_price", {"price_ticks": 99.0}),
    _row("price-float", _LIM, "bad_price", {"price_ticks": 99.5}),
    _row("price-true", _LIM, "bad_price", {"price_ticks": True}),
    _row("price-false", _LIM, "bad_price", {"price_ticks": False}),
    _row("price-string", _LIM, "bad_price", {"price_ticks": "99"}),
    _row("price-null", _LIM, "bad_price", {"price_ticks": None}),
    _row("price-nan", _LIM, "bad_price", {"price_ticks": NAN}),
    _row("price-inf", _LIM, "bad_price", {"price_ticks": INF}),
    # qty_units: only int, not bool, > 0 (Q4)
    _row("qty-zero", _LIM, "bad_qty", {"qty_units": 0}),
    _row("qty-negative", _LIM, "bad_qty", {"qty_units": -1}),
    _row("qty-integral-float", _LIM, "bad_qty", {"qty_units": 1.0}),
    _row("qty-float", _LIM, "bad_qty", {"qty_units": 1.5}),
    _row("qty-true", _LIM, "bad_qty", {"qty_units": True}),
    _row("qty-false", _LIM, "bad_qty", {"qty_units": False}),
    _row("qty-string", _LIM, "bad_qty", {"qty_units": "1"}),
    _row("qty-null", _LIM, "bad_qty", {"qty_units": None}),
    _row("qty-nan", _LIM, "bad_qty", {"qty_units": NAN}),
    _row("qty-inf", _LIM, "bad_qty", {"qty_units": INF}),
    _row("market-qty-zero", _MKT, "bad_qty", {"qty_units": 0}),
    _row("market-qty-true", _MKT, "bad_qty", {"qty_units": True}),
    _row("market-qty-integral-float", _MKT, "bad_qty", {"qty_units": 2.0}),
    # duplicate live submission id (Q5: also for MARKET_SELL)
    _row("dup-live-bid-id", _LIM, "duplicate_live_order_id", {"order_id": "b1"}),
    _row("dup-live-ask-id", _LIM, "duplicate_live_order_id", {"order_id": "a1", "side": "SELL", "price_ticks": 120}),
    _row("dup-market-bid-id", _MKT, "duplicate_live_order_id", {"order_id": "b1"}),
    _row("dup-market-ask-id", _MKT, "duplicate_live_order_id", {"order_id": "a1"}),
    # several faults at once: the FIRST rule in the fixed check order wins (Q2)
    _row("order-seq-before-type", _LIM, "bad_seq", {"seq": 0, "type": "X"}),
    _row("order-seq-before-fields", _LIM, "nonincreasing_seq", {"seq": 2, "event_id": _DROP}, result_eid=None),
    _row("order-type-before-fields", _LIM, "unknown_type", {"type": "X", "event_id": _DROP}, result_eid=None),
    _row("order-missing-before-side", _LIM, "missing_field:qty_units", {"qty_units": _DROP, "side": "buy"}),
    _row("order-event-id-before-order-id", _LIM, "bad_id:event_id", {"event_id": 7, "order_id": ""}, result_eid=None),
    _row("order-side-before-price", _LIM, "unknown_side", {"side": "buy", "price_ticks": 0}),
    _row("order-price-before-qty", _LIM, "bad_price", {"price_ticks": 0, "qty_units": 0}),
    _row("order-qty-before-duplicate", _LIM, "bad_qty", {"qty_units": 0, "order_id": "b1"}),
]


# ---- the cases --------------------------------------------------------------------------
def _long_queue():
    """300 buys at price 100 with 2 units each (random ids, so id order != arrival order)
    and one deeper buy at 99. Closed-form expectation: a sell of 401 units fills the first
    200 makers completely (400 units) and takes 1 unit from maker 201 (arrival 201)."""
    rng = random.Random(SEED)
    ids = []
    while len(ids) < 300:
        oid = "q" + "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(6))
        if oid not in ids:
            ids.append(oid)
    assert ids != sorted(ids), "ids must not already be in arrival order"
    ev = [L(i + 1, ids[i], "BUY", 100, 2) for i in range(300)] + [L(301, "deep", "BUY", 99, 7)]
    res = [R_LIMIT(i + 1, ids[i], "resting", 2) for i in range(300)] + [R_LIMIT(301, "deep", "resting", 7)]
    # s1 = 401 units: makers ids[0..199] x 2 units, then ids[200] x 1 unit
    ev.append(M(302, "s1", 401))
    res.append(R_MKT(302, "s1", "filled", 0, *[F(ids[i], "s1", 100, 2) for i in range(200)], F(ids[200], "s1", 100, 1)))
    # cancel in the middle of the queue: ids[249] (arrival 250) still has 2 units
    ev.append(C(303, ids[249]))
    res.append(R_CXL(303, ids[249], "cancelled", 2))
    # s2 = 3 units: ids[200] keeps its priority with 1 unit left, then ids[201] x 2
    ev.append(M(304, "s2", 3))
    res.append(R_MKT(304, "s2", "filled", 0, F(ids[200], "s2", 100, 1), F(ids[201], "s2", 100, 2)))
    book = [ROW(ids[i], "BUY", 100, 2, i + 1) for i in range(202, 300) if i != 249] + [ROW("deep", "BUY", 99, 7, 301)]
    return ev, res, book, 100, None


def _invalid_fields():
    ev = list(INVALID_SETUP)
    res = [R_LIMIT(1, "b1", "resting", 5), R_LIMIT(2, "a1", "resting", 5)]
    for row in INVALID_EVENTS:
        ev.append(row["event"])
        res.append(R_REJ(row["result_event_id"], row["reason"]))
    # none of the rejections advanced the last accepted seq (2): seq 3 is still accepted
    ev.append(L(3, "b2", "BUY", 99, 1)); res.append(R_LIMIT(3, "b2", "resting", 1))
    ev.append(C(3, "b1", eid="x-seq3-again")); res.append(R_REJ("x-seq3-again", "nonincreasing_seq"))
    ev.append(C(4, "b1")); res.append(R_CXL(4, "b1", "cancelled", 5))
    book = [ROW("b2", "BUY", 99, 1, 3), ROW("a1", "SELL", 110, 5, 2)]
    return ev, res, book, 99, 110


CASES = {
    "empty_book": dict(
        description="Market sell and cancels on a completely empty book; the accepted cancel advances seq.",
        covers=["empty book", "market sell on empty book", "cancel unknown target is valid", "nonincreasing seq after accepted cancel"],
        events=[M(1, "s1", 5), C(2, "x1"), M(3, "s2", 1), C(2, "x2", eid="r4")],
        results=[R_MKT(1, "s1", "unfilled", 5), R_CXL(2, "x1", "not_found", 0), R_MKT(3, "s2", "unfilled", 1),
                 R_REJ("r4", "nonincreasing_seq")],
        final_book=[], best_bid=None, best_ask=None),

    "one_order": dict(
        description="A single limit buy rests; ask side empty.",
        covers=["one order", "one side empty"],
        events=[L(1, "b1", "BUY", 100, 10)],
        results=[R_LIMIT(1, "b1", "resting", 10)],
        final_book=[ROW("b1", "BUY", 100, 10, 1)], best_bid=100, best_ask=None),

    "fifo_one_price": dict(
        description="Three buys at one price, ids z9/a1/m5 (id order != arrival order), seq with gaps; "
                    "a 9-unit sell fills them in arrival order, the last one partially.",
        covers=["FIFO at one price", "multiple makers at one price", "identifier order differs from arrival order",
                "seq gaps allowed", "partial fill keeps remainder"],
        events=[L(10, "z9", "BUY", 100, 3), L(20, "a1", "BUY", 100, 4), L(30, "m5", "BUY", 100, 5), M(40, "s1", 9)],
        results=[R_LIMIT(10, "z9", "resting", 3), R_LIMIT(20, "a1", "resting", 4), R_LIMIT(30, "m5", "resting", 5),
                 R_MKT(40, "s1", "filled", 0, F("z9", "s1", 100, 3), F("a1", "s1", 100, 4), F("m5", "s1", 100, 2))],
        final_book=[ROW("m5", "BUY", 100, 3, 30)], best_bid=100, best_ask=None),

    "sweep_levels": dict(
        description="Bids on three levels (two orders at the best); an 8-unit sell takes 105 (b1, b3), "
                    "then 103 (b2), then 1 unit at 101 (b4). The ask is untouched.",
        covers=["sweep through several levels", "best price first", "market sell ignores asks"],
        events=[L(1, "b1", "BUY", 105, 2), L(2, "b2", "BUY", 103, 4), L(3, "b3", "BUY", 105, 1),
                L(4, "b4", "BUY", 101, 5), L(5, "a1", "SELL", 110, 7), M(6, "s1", 8)],
        results=[R_LIMIT(1, "b1", "resting", 2), R_LIMIT(2, "b2", "resting", 4), R_LIMIT(3, "b3", "resting", 1),
                 R_LIMIT(4, "b4", "resting", 5), R_LIMIT(5, "a1", "resting", 7),
                 R_MKT(6, "s1", "filled", 0, F("b1", "s1", 105, 2), F("b3", "s1", 105, 1),
                       F("b2", "s1", 103, 4), F("b4", "s1", 101, 1))],
        final_book=[ROW("b4", "BUY", 101, 4, 4), ROW("a1", "SELL", 110, 7, 5)], best_bid=101, best_ask=110),

    "sell_sizes": dict(
        description="Market sells smaller than, equal to and larger than the bid depth; then a sell with "
                    "no bids but an ask present.",
        covers=["sale smaller than depth", "sale equal to depth", "sale larger than depth", "residual discarded",
                "market sell with empty bid side"],
        events=[L(1, "b1", "BUY", 100, 5), L(2, "b2", "BUY", 99, 5),
                M(3, "s1", 3),                       # smaller: b1 3 -> b1 keeps 2
                M(4, "s2", 7),                       # equal to the remaining 7: b1 2, b2 5
                L(5, "b3", "BUY", 98, 4), L(6, "a1", "SELL", 101, 6),
                M(7, "s3", 10),                      # larger: b3 4, 6 discarded
                M(8, "s4", 2)],                      # no bids at all
        results=[R_LIMIT(1, "b1", "resting", 5), R_LIMIT(2, "b2", "resting", 5),
                 R_MKT(3, "s1", "filled", 0, F("b1", "s1", 100, 3)),
                 R_MKT(4, "s2", "filled", 0, F("b1", "s2", 100, 2), F("b2", "s2", 99, 5)),
                 R_LIMIT(5, "b3", "resting", 4), R_LIMIT(6, "a1", "resting", 6),
                 R_MKT(7, "s3", "partial", 6, F("b3", "s3", 98, 4)),
                 R_MKT(8, "s4", "unfilled", 2)],
        final_book=[ROW("a1", "SELL", 101, 6, 6)], best_bid=None, best_ask=101),

    "market_larger_than_book": dict(
        description="A 1000-unit sell against 6 units of bids: partial, 994 discarded. A later buy at 149 "
                    "rests, which shows that no residual ask was left behind.",
        covers=["market sell larger than the whole book", "unfilled residual never rests"],
        events=[L(1, "b1", "BUY", 200, 1), L(2, "b2", "BUY", 150, 2), L(3, "b3", "BUY", 150, 3),
                L(4, "a1", "SELL", 250, 9), M(5, "s1", 1000), L(6, "b4", "BUY", 149, 1)],
        results=[R_LIMIT(1, "b1", "resting", 1), R_LIMIT(2, "b2", "resting", 2), R_LIMIT(3, "b3", "resting", 3),
                 R_LIMIT(4, "a1", "resting", 9),
                 R_MKT(5, "s1", "partial", 994, F("b1", "s1", 200, 1), F("b2", "s1", 150, 2), F("b3", "s1", 150, 3)),
                 R_LIMIT(6, "b4", "resting", 1)],
        final_book=[ROW("b4", "BUY", 149, 1, 6), ROW("a1", "SELL", 250, 9, 4)], best_bid=149, best_ask=250),

    "market_sell_empty_bid_side": dict(
        description="Only an ask rests; a market sell finds no bids and returns unfilled; the ask is unchanged.",
        covers=["market sell on empty bid side", "one side empty"],
        events=[L(1, "a1", "SELL", 100, 5), M(2, "s1", 3)],
        results=[R_LIMIT(1, "a1", "resting", 5), R_MKT(2, "s1", "unfilled", 3)],
        final_book=[ROW("a1", "SELL", 100, 5, 1)], best_bid=None, best_ask=100),

    "partial_then_another_sale": dict(
        description="b1 is partly filled and keeps its place before b2 and the later b3 at the same price.",
        covers=["partial fill followed by another sale", "partially filled maker keeps priority"],
        events=[L(1, "b1", "BUY", 100, 5), L(2, "b2", "BUY", 100, 5), M(3, "s1", 3),
                L(4, "b3", "BUY", 100, 1), M(5, "s2", 4)],
        results=[R_LIMIT(1, "b1", "resting", 5), R_LIMIT(2, "b2", "resting", 5),
                 R_MKT(3, "s1", "filled", 0, F("b1", "s1", 100, 3)),
                 R_LIMIT(4, "b3", "resting", 1),
                 R_MKT(5, "s2", "filled", 0, F("b1", "s2", 100, 2), F("b2", "s2", 100, 2))],
        final_book=[ROW("b2", "BUY", 100, 3, 2), ROW("b3", "BUY", 100, 1, 4)], best_bid=100, best_ask=None),

    "cancel_cases": dict(
        description="Cancel before any fill, after a full fill, after a partial fill, twice, unknown, "
                    "a market-sell id, and an ask.",
        covers=["cancel before fill", "cancel after full fill -> not_found", "cancel after partial fill",
                "repeated cancel -> not_found", "unknown cancel -> not_found", "cancel of a market-sell id",
                "cancel removes exactly the residual"],
        events=[L(1, "b1", "BUY", 100, 5), L(2, "b2", "BUY", 100, 5), L(3, "b3", "BUY", 99, 4),
                C(4, "b3"), M(5, "s1", 7), C(6, "b1"), C(7, "b2"), C(8, "b2"), C(9, "zz"), C(10, "s1"),
                L(11, "a1", "SELL", 105, 2), C(12, "a1")],
        results=[R_LIMIT(1, "b1", "resting", 5), R_LIMIT(2, "b2", "resting", 5), R_LIMIT(3, "b3", "resting", 4),
                 R_CXL(4, "b3", "cancelled", 4),
                 R_MKT(5, "s1", "filled", 0, F("b1", "s1", 100, 5), F("b2", "s1", 100, 2)),
                 R_CXL(6, "b1", "not_found", 0), R_CXL(7, "b2", "cancelled", 3), R_CXL(8, "b2", "not_found", 0),
                 R_CXL(9, "zz", "not_found", 0), R_CXL(10, "s1", "not_found", 0),
                 R_LIMIT(11, "a1", "resting", 2), R_CXL(12, "a1", "cancelled", 2)],
        final_book=[], best_bid=None, best_ask=None),

    "interleaved_cancel_fill": dict(
        description="Four buys in one queue; cancels and sells alternate at the same level; queue order "
                    "of the survivors is preserved.",
        covers=["interleaved cancel and fill at the same level", "cancel in the middle of a queue",
                "cancel after partial fill"],
        events=[L(1, "b1", "BUY", 100, 2), L(2, "b2", "BUY", 100, 3), L(3, "b3", "BUY", 100, 4),
                L(4, "b4", "BUY", 100, 5), C(5, "b2"), M(6, "s1", 4), C(7, "b3"), L(8, "b5", "BUY", 100, 1),
                M(9, "s2", 6), C(10, "b4"), L(11, "b6", "BUY", 100, 7)],
        results=[R_LIMIT(1, "b1", "resting", 2), R_LIMIT(2, "b2", "resting", 3), R_LIMIT(3, "b3", "resting", 4),
                 R_LIMIT(4, "b4", "resting", 5), R_CXL(5, "b2", "cancelled", 3),
                 R_MKT(6, "s1", "filled", 0, F("b1", "s1", 100, 2), F("b3", "s1", 100, 2)),
                 R_CXL(7, "b3", "cancelled", 2), R_LIMIT(8, "b5", "resting", 1),
                 R_MKT(9, "s2", "filled", 0, F("b4", "s2", 100, 5), F("b5", "s2", 100, 1)),
                 R_CXL(10, "b4", "not_found", 0), R_LIMIT(11, "b6", "resting", 7)],
        final_book=[ROW("b6", "BUY", 100, 7, 11)], best_bid=100, best_ask=None),

    "crossing_limit_buy": dict(
        description="A buy at 103 for 10 crosses asks at 101 (a1, a3) and 102 (a2) at the MAKER prices, "
                    "then rests 4 at 103; the 104 ask stays; the book is not crossed afterwards.",
        covers=["crossing limit buy", "execute at the resting price (taker price improvement)",
                "residual of a crossing limit rests at its limit", "several levels"],
        events=[L(1, "a1", "SELL", 101, 2), L(2, "a2", "SELL", 102, 3), L(3, "a3", "SELL", 101, 1),
                L(4, "a4", "SELL", 104, 5), L(5, "b1", "BUY", 99, 4), L(6, "t1", "BUY", 103, 10)],
        results=[R_LIMIT(1, "a1", "resting", 2), R_LIMIT(2, "a2", "resting", 3), R_LIMIT(3, "a3", "resting", 1),
                 R_LIMIT(4, "a4", "resting", 5), R_LIMIT(5, "b1", "resting", 4),
                 R_LIMIT(6, "t1", "resting", 4, F("a1", "t1", 101, 2), F("a3", "t1", 101, 1), F("a2", "t1", 102, 3))],
        final_book=[ROW("t1", "BUY", 103, 4, 6), ROW("b1", "BUY", 99, 4, 5), ROW("a4", "SELL", 104, 5, 4)],
        best_bid=103, best_ask=104),

    "crossing_limit_sell": dict(
        description="A sell at 99 for 4 is filled at 100 (b1, then b3 partly); a sell at 97 for 5 takes "
                    "b3's rest and b2 at 98, then rests 2 at 97.",
        covers=["crossing limit sell", "limit sell fully filled -> status filled", "residual limit sell rests",
                "partially filled maker keeps priority"],
        events=[L(1, "b1", "BUY", 100, 3), L(2, "b2", "BUY", 98, 2), L(3, "b3", "BUY", 100, 2),
                L(4, "a1", "SELL", 105, 1), L(5, "t1", "SELL", 99, 4), L(6, "t2", "SELL", 97, 5)],
        results=[R_LIMIT(1, "b1", "resting", 3), R_LIMIT(2, "b2", "resting", 2), R_LIMIT(3, "b3", "resting", 2),
                 R_LIMIT(4, "a1", "resting", 1),
                 R_LIMIT(5, "t1", "filled", 0, F("b1", "t1", 100, 3), F("b3", "t1", 100, 1)),
                 R_LIMIT(6, "t2", "resting", 2, F("b3", "t2", 100, 1), F("b2", "t2", 98, 2))],
        final_book=[ROW("t2", "SELL", 97, 2, 6), ROW("a1", "SELL", 105, 1, 4)], best_bid=None, best_ask=97),

    "limit_at_touch": dict(
        description="Limits one tick away do not cross; a buy exactly at the best ask and a sell exactly "
                    "at the best bid do cross (>= and <=).",
        covers=["limit at the touch crosses", "noncrossing residual limits", "crossing on both sides"],
        events=[L(1, "b1", "BUY", 100, 5), L(2, "a1", "SELL", 102, 5),
                L(3, "s1", "SELL", 101, 1),          # 101 > best bid 100: rests
                L(4, "b2", "BUY", 100, 1),           # 100 < best ask 101: rests behind b1
                L(5, "x1", "BUY", 101, 2),           # = best ask 101: takes s1, rests 1 at 101
                L(6, "x2", "SELL", 101, 3)],         # = best bid 101: takes x1, rests 2 at 101
        results=[R_LIMIT(1, "b1", "resting", 5), R_LIMIT(2, "a1", "resting", 5), R_LIMIT(3, "s1", "resting", 1),
                 R_LIMIT(4, "b2", "resting", 1),
                 R_LIMIT(5, "x1", "resting", 1, F("s1", "x1", 101, 1)),
                 R_LIMIT(6, "x2", "resting", 2, F("x1", "x2", 101, 1))],
        final_book=[ROW("b1", "BUY", 100, 5, 1), ROW("b2", "BUY", 100, 1, 4),
                    ROW("x2", "SELL", 101, 2, 6), ROW("a1", "SELL", 102, 5, 2)],
        best_bid=100, best_ask=101),

    "noncrossing_residuals": dict(
        description="Eight resting limits on both sides; checks the canonical book order "
                    "(bids price desc, asks price asc, then arrival).",
        covers=["noncrossing residual limits", "canonical snapshot order", "several levels on both sides"],
        events=[L(1, "a1", "SELL", 105, 1), L(2, "b1", "BUY", 100, 1), L(3, "a2", "SELL", 103, 2),
                L(4, "b2", "BUY", 102, 2), L(5, "a3", "SELL", 105, 3), L(6, "b3", "BUY", 100, 3),
                L(7, "b4", "BUY", 102, 4), L(8, "a4", "SELL", 103, 4)],
        results=[R_LIMIT(1, "a1", "resting", 1), R_LIMIT(2, "b1", "resting", 1), R_LIMIT(3, "a2", "resting", 2),
                 R_LIMIT(4, "b2", "resting", 2), R_LIMIT(5, "a3", "resting", 3), R_LIMIT(6, "b3", "resting", 3),
                 R_LIMIT(7, "b4", "resting", 4), R_LIMIT(8, "a4", "resting", 4)],
        final_book=[ROW("b2", "BUY", 102, 2, 4), ROW("b4", "BUY", 102, 4, 7), ROW("b1", "BUY", 100, 1, 2),
                    ROW("b3", "BUY", 100, 3, 6), ROW("a2", "SELL", 103, 2, 3), ROW("a4", "SELL", 103, 4, 8),
                    ROW("a1", "SELL", 105, 1, 1), ROW("a3", "SELL", 105, 3, 5)],
        best_bid=102, best_ask=103),

    "id_reuse": dict(
        description="Duplicate LIVE ids are rejected (limit and market sell); re-using an id after it was "
                    "filled or cancelled is accepted as a new order (historical reuse is out of scope).",
        covers=["duplicate live id rejected", "market sell with a live id rejected", "id reuse after fill",
                "id reuse after cancel", "market-sell id reuse"],
        events=[L(1, "b1", "BUY", 100, 2), L(2, "b1", "BUY", 101, 1), M(3, "b1", 1), M(4, "s1", 2),
                L(5, "b1", "BUY", 99, 3), C(6, "b1"), L(7, "b1", "SELL", 120, 1), M(8, "s1", 1), C(9, "s1")],
        results=[R_LIMIT(1, "b1", "resting", 2), R_REJ("e2", "duplicate_live_order_id"),
                 R_REJ("e3", "duplicate_live_order_id"),
                 R_MKT(4, "s1", "filled", 0, F("b1", "s1", 100, 2)),
                 R_LIMIT(5, "b1", "resting", 3), R_CXL(6, "b1", "cancelled", 3),
                 R_LIMIT(7, "b1", "resting", 1), R_MKT(8, "s1", "unfilled", 1), R_CXL(9, "s1", "not_found", 0)],
        final_book=[ROW("b1", "SELL", 120, 1, 7)], best_bid=None, best_ask=120),

    "huge_values": dict(
        description="Prices and quantities far beyond 64-bit-safe float precision; integers must stay exact.",
        covers=["huge integers", "exact integer arithmetic"],
        events=[L(1, "b1", "BUY", 10**15, 10**18), L(2, "a1", "SELL", 10**15 + 1, 10**18),
                M(3, "s1", 10**18 - 1), L(4, "t1", "BUY", 10**15 + 1, 2 * 10**18)],
        results=[R_LIMIT(1, "b1", "resting", 10**18), R_LIMIT(2, "a1", "resting", 10**18),
                 R_MKT(3, "s1", "filled", 0, F("b1", "s1", 10**15, 10**18 - 1)),
                 R_LIMIT(4, "t1", "resting", 10**18, F("a1", "t1", 10**15 + 1, 10**18))],
        final_book=[ROW("t1", "BUY", 10**15 + 1, 10**18, 4), ROW("b1", "BUY", 10**15, 1, 1)],
        best_bid=10**15 + 1, best_ask=None),
}


def _add_computed_cases():
    for name, build, desc, covers in [
        ("long_queue", _long_queue,
         "300 makers at one price with random ids, a 401-unit sell, a cancel in the middle of the queue "
         "and a second sell (closed-form expectation, seed 42).",
         ["long queue at one price", "identifier order differs from arrival order", "cancel in the middle of a queue",
          "partially filled maker keeps priority"]),
        ("invalid_fields", _invalid_fields,
         "Every invalid-event row of INVALID_EVENTS after a two-order setup; none changes the book or the "
         "last accepted seq; seq 3 is still accepted afterwards.",
         ["every invalid-field case", "rejection leaves book unchanged", "rejected events do not advance seq",
          "check order of validation rules"]),
    ]:
        ev, res, book, bb, ba = build()
        CASES[name] = dict(description=desc, covers=covers, events=ev, results=res,
                           final_book=book, best_bid=bb, best_ask=ba)


_add_computed_cases()
CASE_NAMES = tuple(CASES)


def _texts(name: str, case: dict) -> tuple[str, str]:
    assert len(case["events"]) == len(case["results"]), name
    events = "".join(json.dumps(e, separators=(",", ":")) + "\n" for e in case["events"])
    expected = {"own": True, "synthetic": True, "case": name, "description": case["description"],
                "covers": case["covers"], "generator": "01_code/datagen/own_cases.py", "seed": SEED,
                "results": case["results"], "final_book": case["final_book"],
                "best_bid": case["best_bid"], "best_ask": case["best_ask"]}
    return events, json.dumps(expected, indent=1) + "\n"


def _index_text() -> str:
    lines = ["# OWN edge-case datasets (not supplied by the course)", "",
             "Generated by `python run.py datagen.own_cases` from hand-calculated expectations in "
             "`01_code/datagen/own_cases.py`. Each `<case>.jsonl` has a `<case>.expected.json` with one "
             "expected result per event and the final canonical book. Replayed by the contract checks "
             "`check_own_<case>` in `02_tests/contract.py`.", "",
             "| Case | Events | Covers |", "|---|---|---|"]
    for name, case in CASES.items():
        lines.append(f"| `{name}` | {len(case['events'])} | {'; '.join(case['covers'])} |")
    return "\n".join(lines) + "\n"


def all_texts() -> dict[str, str]:
    """{relative file name: text} for every file this generator writes."""
    out = {"INDEX.md": _index_text()}
    for name, case in CASES.items():
        ev, exp = _texts(name, case)
        out[f"{name}.jsonl"] = ev
        out[f"{name}.expected.json"] = exp
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true", help="compare with existing files instead of writing")
    a = ap.parse_args()
    texts = all_texts()
    if a.check:
        bad = [n for n, t in texts.items()
               if not (a.out / n).exists() or (a.out / n).read_text(encoding="utf-8").splitlines() != t.splitlines()]
        print("RESULT:", "FAIL" if bad else "PASS", f"({len(texts)} files compared)", *bad)
        return 1 if bad else 0
    a.out.mkdir(parents=True, exist_ok=True)
    for n, t in texts.items():
        with (a.out / n).open("w", encoding="utf-8", newline="\n") as f:
            f.write(t)
    print(f"wrote {len(texts)} files to {a.out} ({len(CASES)} cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
