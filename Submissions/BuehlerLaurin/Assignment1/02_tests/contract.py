"""Named contract checks: check_<rule>(impl) -> None, raise AssertionError on violation.

`impl` is a version class from lob.METHODS; `impl()` gives a fresh empty book.
Used by 02_tests/test_contract.py (real versions) and 02_tests/test_mutants.py (mutants).
Imported as `import contract` (02_tests is on pythonpath, not a package).

Layers (aif-tdd):
1. Hand-calculated expected results: the worked example (supplied), small inline
   scenarios below, and the OWN datasets in 06_data/own/ (one check_own_<case> each).
2. One suite for every version (this file).
4. Invariants and conservation: EVERY replay in this file goes through `run()`, which
   calls `step_check()` after each event. step_check derives what an accepted event
   must have done from the book BEFORE the event (snapshot) and the reported result:
   fills follow the canonical priority order of the opposite side, at the maker's
   price, min(remaining, resting) each, stop only when nothing crosses any more;
   the book AFTER equals the book before minus the fills / cancelled residual plus a
   rested limit residual. Rejections must leave the book unchanged.
Validation rules are shared by A and B, so each rule has its own check here
(an A/B comparison cannot catch a shared validation bug).
"""
import copy
import gzip
import json
from pathlib import Path

from datagen.own_cases import (C, INVALID_EVENTS, INVALID_SETUP, INVALID_SETUP_LAST_SEQ, L, M)

ROOT = Path(__file__).resolve().parents[1]
SUPPLIED = ROOT / "06_data" / "supplied"
OWN = ROOT / "06_data" / "own"
SUPPLIED_STREAMS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
SUPPLIED_PREFIX = 1000      # events per supplied stream replayed with the full step checker

# Fixed list (not discovered from disk), so a missing dataset file fails instead of
# silently dropping its check. test_own_datasets.py checks it equals own_cases.CASE_NAMES.
OWN_CASES = ("empty_book", "one_order", "fifo_one_price", "sweep_levels", "sell_sizes",
             "market_larger_than_book", "market_sell_empty_bid_side", "partial_then_another_sale",
             "cancel_cases", "interleaved_cancel_fill", "crossing_limit_buy", "crossing_limit_sell",
             "limit_at_touch", "noncrossing_residuals", "id_reuse", "huge_values", "long_queue",
             "invalid_fields")

SNAP_KEYS = {"order_id", "side", "price_ticks", "qty_units", "arrival_seq"}
FILL_KEYS = {"maker_id", "taker_id", "price_ticks", "qty_units"}
SUBMIT_KEYS = {"event_id", "order_id", "status", "unfilled_qty_units", "fills"}
CANCEL_KEYS = {"event_id", "target_order_id", "status", "cancelled_qty_units"}
REJECT_KEYS = {"event_id", "status", "reason"}


# =========================================================================================
# helpers
# =========================================================================================
def is_int(x) -> bool:
    """int but not bool (SPEC.md Q4)."""
    return isinstance(x, int) and not isinstance(x, bool)


def read_jsonl(path: Path, limit=None) -> list:
    opener = gzip.open if path.suffix == ".gz" else open
    out = []
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            if limit is not None and len(out) >= limit:
                break
            if line.strip():
                out.append(json.loads(line))
    return out


def canonical(rows: list) -> list:
    """Canonical book order: bids price desc then arrival, then asks price asc then arrival."""
    bids = sorted((r for r in rows if r["side"] == "BUY"), key=lambda r: (-r["price_ticks"], r["arrival_seq"]))
    asks = sorted((r for r in rows if r["side"] == "SELL"), key=lambda r: (r["price_ticks"], r["arrival_seq"]))
    return bids + asks


def assert_book(book) -> list:
    """Invariants I1-I4 on the public inspection functions; returns the snapshot."""
    snap = book.snapshot()
    bb, ba = book.best_bid(), book.best_ask()
    assert isinstance(snap, list), f"snapshot must be a list, got {type(snap).__name__}"
    ids, seqs = set(), set()
    for r in snap:
        assert isinstance(r, dict) and set(r) == SNAP_KEYS, f"snapshot row has wrong fields: {r}"
        assert r["side"] in ("BUY", "SELL"), f"bad side in book: {r}"
        assert isinstance(r["order_id"], str) and r["order_id"], f"bad order_id in book: {r}"
        for k in ("price_ticks", "qty_units", "arrival_seq"):
            assert is_int(r[k]), f"{k} must be int in book: {r}"
        assert r["qty_units"] > 0, f"I2 violated, nonpositive resting qty: {r}"
        assert r["price_ticks"] > 0, f"nonpositive price in book: {r}"
        assert r["order_id"] not in ids, f"I3 violated, order stored twice: {r['order_id']}"
        assert r["arrival_seq"] not in seqs, f"two active orders with one arrival_seq: {r}"
        ids.add(r["order_id"]); seqs.add(r["arrival_seq"])
    assert snap == canonical(snap), f"I4 violated, snapshot not in canonical order: {snap}"
    bids = [r for r in snap if r["side"] == "BUY"]
    asks = [r for r in snap if r["side"] == "SELL"]
    assert bb == (bids[0]["price_ticks"] if bids else None), f"best_bid {bb} != book {bids[:1]}"
    assert ba == (asks[0]["price_ticks"] if asks else None), f"best_ask {ba} != book {asks[:1]}"
    assert bb is None or is_int(bb), f"best_bid must be int or None: {bb!r}"
    assert ba is None or is_int(ba), f"best_ask must be int or None: {ba!r}"
    if bids and asks:
        assert bids[0]["price_ticks"] < asks[0]["price_ticks"], f"I1 violated, crossed book: {bb} >= {ba}"
    return snap


def step_check(before: list, event, result, after: list) -> None:
    """Rules + conservation (C1-C6) for ONE event, from the book before and the result."""
    assert isinstance(result, dict), f"result must be a dict, got {result!r}"
    if result.get("status") == "rejected":
        assert set(result) == REJECT_KEYS, f"rejection has wrong fields: {result}"
        assert isinstance(result["reason"], str) and result["reason"], f"rejection needs a reason: {result}"
        assert after == before, f"rejected event changed the book: {event}"
        return
    assert isinstance(event, dict), f"non-object event was not rejected: {event!r} -> {result}"
    etype = event["type"]
    if etype == "CANCEL":
        assert set(result) == CANCEL_KEYS, f"cancel result has wrong fields: {result}"
        assert result["event_id"] == event["event_id"] and result["target_order_id"] == event["target_order_id"], result
        assert is_int(result["cancelled_qty_units"]), result
        live = {r["order_id"]: r for r in before}
        target = event["target_order_id"]
        if target in live:
            assert result["status"] == "cancelled", f"live target {target} not cancelled: {result}"
            assert result["cancelled_qty_units"] == live[target]["qty_units"], (
                f"C3 violated: cancel must remove exactly the residual {live[target]['qty_units']}: {result}")
            assert after == [r for r in before if r["order_id"] != target], f"C3 violated: book after cancel {target}"
        else:
            assert result["status"] == "not_found" and result["cancelled_qty_units"] == 0, (
                f"inactive/unknown target {target} must be not_found with 0: {result}")
            assert after == before, "not_found cancel changed the book"
        return

    assert etype in ("LIMIT", "MARKET_SELL"), f"unexpected accepted type {etype!r}"
    assert set(result) == SUBMIT_KEYS, f"submission result has wrong fields: {result}"
    assert result["event_id"] == event["event_id"] and result["order_id"] == event["order_id"], result
    fills, qty, taker = result["fills"], event["qty_units"], event["order_id"]
    assert isinstance(fills, list), result
    if etype == "LIMIT":
        side, limit = event["side"], event["price_ticks"]
        opp_side = "SELL" if side == "BUY" else "BUY"
        crosses = (lambda p: p <= limit) if side == "BUY" else (lambda p: p >= limit)
    else:
        side, limit, opp_side = "SELL", None, "BUY"
        crosses = lambda p: True  # noqa: E731 - a market sell accepts every bid
    opp = [r for r in before if r["side"] == opp_side]          # canonical = priority order
    remaining = qty
    for i, f in enumerate(fills):
        assert isinstance(f, dict) and set(f) == FILL_KEYS, f"fill has wrong fields: {f}"
        assert all(is_int(f[k]) for k in ("price_ticks", "qty_units")), f"fill numbers must be int: {f}"
        assert i < len(opp), f"more fills than resting opposite orders: {fills}"
        maker = opp[i]
        assert f["maker_id"] == maker["order_id"], (
            f"price-time priority violated: fill {i} hit {f['maker_id']}, expected {maker['order_id']} "
            f"(best price, then earliest arrival)")
        assert f["taker_id"] == taker, f"taker_id must be the incoming order: {f}"
        assert f["price_ticks"] == maker["price_ticks"], f"fill not at the resting (maker) price: {f}"
        assert crosses(maker["price_ticks"]), f"traded with a noncrossing maker: {f} limit={limit}"
        assert f["qty_units"] == min(remaining, maker["qty_units"]), (
            f"fill qty must be min(incoming remaining {remaining}, resting {maker['qty_units']}): {f}")
        assert f["qty_units"] > 0, f"zero-quantity fill: {f}"
        remaining -= f["qty_units"]
    assert result["unfilled_qty_units"] == remaining, (
        f"C1 violated: qty {qty} != fills {qty - remaining} + unfilled {result['unfilled_qty_units']}")
    if remaining > 0 and len(fills) < len(opp):
        assert not crosses(opp[len(fills)]["price_ticks"]), f"stopped matching while a crossing maker remained: {result}"
    if etype == "LIMIT":
        want = "filled" if remaining == 0 else "resting"
    else:
        want = "filled" if remaining == 0 else ("partial" if fills else "unfilled")
    assert result["status"] == want, f"status must be {want!r}: {result}"
    # expected book after: makers lose exactly their fills (C2); market residual never rests (C5)
    expect = [dict(r) for r in before]
    by_id = {r["order_id"]: r for r in expect}
    for f in fills:
        by_id[f["maker_id"]]["qty_units"] -= f["qty_units"]
    expect = [r for r in expect if r["qty_units"] > 0]
    if etype == "LIMIT" and remaining > 0:
        expect.append({"order_id": taker, "side": side, "price_ticks": limit, "qty_units": remaining,
                       "arrival_seq": event["seq"]})
    assert after == canonical(expect), (
        f"C2/C5/C6 violated: book after {event.get('event_id')} differs from before - fills (+ rested residual)")


def run(book, events: list) -> list:
    """Replay through process(); check invariants + conservation after EVERY event."""
    results = []
    before = assert_book(book)
    for ev in events:
        sent = copy.deepcopy(ev)
        res = book.process(sent)
        # (NaN fields still compare equal here: deepcopy keeps the same float object, and
        #  container equality checks identity first)
        assert sent == ev, f"process() mutated its input event: {ev} -> {sent}"
        after = assert_book(book)
        step_check(before, ev, res, after)
        results.append(res)
        before = after
    return results


def row(oid, side, price, qty, arrival):
    return {"order_id": oid, "side": side, "price_ticks": price, "qty_units": qty, "arrival_seq": arrival}


def fill(maker, taker, price, qty):
    return {"maker_id": maker, "taker_id": taker, "price_ticks": price, "qty_units": qty}


# =========================================================================================
# worked example (supplied, README "Worked example and tests first", slide 3)
# =========================================================================================
def _worked():
    events = read_jsonl(SUPPLIED / "worked_example.jsonl")
    expected = json.loads((SUPPLIED / "worked_expected.json").read_text(encoding="utf-8"))
    return events, expected


def check_worked_example_market_sell(impl):
    events, expected = _worked()
    res = run(impl(), events)
    # events 1-5 rest completely (hand: nothing crosses; ask 60,100 > best bid 60,000)
    for ev, r in zip(events[:5], res[:5]):
        assert r == {"event_id": ev["event_id"], "order_id": ev["order_id"], "status": "resting",
                     "unfilled_qty_units": ev["qty_units"], "fills": []}, r
    assert res[5] == expected["market_sell_result"], f"worked example sell:\n{res[5]}\n!=\n{expected['market_sell_result']}"


def check_worked_example_book_and_proceeds(impl):
    events, expected = _worked()
    book = impl()
    res = run(book, events)
    assert book.snapshot() == expected["remaining_orders"], book.snapshot()
    total = sum(f["price_ticks"] * f["qty_units"] for f in res[5]["fills"])
    assert total == expected["gross_proceeds_tick_units"] == 3_594_000_000_000_000, total
    assert total % 10**10 == 0 and total // 10**10 == 359_400, "proceeds must be exactly 359,400.00 USD"


# =========================================================================================
# own datasets: one check per file in 06_data/own/ (hand-calculated expected files)
# =========================================================================================
def _replay_own_dataset(impl, name: str) -> None:
    """Helper (not a check itself: no check_ prefix). Used by the generated check_own_<case>."""
    events = read_jsonl(OWN / f"{name}.jsonl")
    exp = json.loads((OWN / f"{name}.expected.json").read_text(encoding="utf-8"))
    assert exp["own"] is True and exp["case"] == name
    assert len(events) == len(exp["results"]), f"{name}: events and expected results differ in length"
    book = impl()
    res = run(book, events)
    for i, (got, want) in enumerate(zip(res, exp["results"])):
        assert got == want, f"{name}: event #{i + 1} {events[i]!r}\n got: {got}\nwant: {want}"
    assert book.snapshot() == exp["final_book"], f"{name}: final book\n got: {book.snapshot()}\nwant: {exp['final_book']}"
    assert (book.best_bid(), book.best_ask()) == (exp["best_bid"], exp["best_ask"]), name


def _make_own_check(name):
    def check(impl):
        _replay_own_dataset(impl, name)
    check.__name__ = check.__qualname__ = f"check_own_{name}"
    check.__doc__ = f"Replay 06_data/own/{name}.jsonl and compare with {name}.expected.json (own, hand-calculated)."
    return check


for _name in OWN_CASES:
    globals()[f"check_own_{_name}"] = _make_own_check(_name)
del _name


# =========================================================================================
# matching rules (small inline scenarios, expected values by hand)
# =========================================================================================
def check_empty_book_inspection(impl):
    book = impl()
    assert book.snapshot() == [] and book.best_bid() is None and book.best_ask() is None


def check_one_limit_rests(impl):
    book = impl()
    r = run(book, [L(1, "b1", "BUY", 100, 10)])[0]
    assert r == {"event_id": "e1", "order_id": "b1", "status": "resting", "unfilled_qty_units": 10, "fills": []}, r
    assert book.snapshot() == [row("b1", "BUY", 100, 10, 1)]
    assert (book.best_bid(), book.best_ask()) == (100, None)


def check_fifo_within_price(impl):
    """Same price: earliest arrival first, regardless of id spelling (x, a, m)."""
    book = impl()
    r = run(book, [L(1, "x", "BUY", 100, 2), L(2, "a", "BUY", 100, 2), L(3, "m", "BUY", 100, 2), M(4, "s", 3)])[3]
    assert r["fills"] == [fill("x", "s", 100, 2), fill("a", "s", 100, 1)], r
    assert book.snapshot() == [row("a", "BUY", 100, 1, 2), row("m", "BUY", 100, 2, 3)]


def check_best_price_first(impl):
    """Bids arrive at 100, 102, 101: a sell takes 102, then 101, then 100."""
    book = impl()
    r = run(book, [L(1, "b1", "BUY", 100, 1), L(2, "b2", "BUY", 102, 1), L(3, "b3", "BUY", 101, 1), M(4, "s", 3)])[3]
    assert r["fills"] == [fill("b2", "s", 102, 1), fill("b3", "s", 101, 1), fill("b1", "s", 100, 1)], r
    assert r["status"] == "filled" and book.snapshot() == []


def check_fill_at_maker_price(impl):
    """A buy limit at 105 against an ask at 100 trades at 100 (the resting price)."""
    book = impl()
    r = run(book, [L(1, "a1", "SELL", 100, 1), L(2, "t", "BUY", 105, 1)])[1]
    assert r == {"event_id": "e2", "order_id": "t", "status": "filled", "unfilled_qty_units": 0,
                 "fills": [fill("a1", "t", 100, 1)]}, r


def check_crossing_sell_at_maker_price(impl):
    """A sell limit at 90 against a bid at 100 trades at 100 and rests its residual at 90."""
    book = impl()
    r = run(book, [L(1, "b1", "BUY", 100, 1), L(2, "t", "SELL", 90, 3)])[1]
    assert r == {"event_id": "e2", "order_id": "t", "status": "resting", "unfilled_qty_units": 2,
                 "fills": [fill("b1", "t", 100, 1)]}, r
    assert book.snapshot() == [row("t", "SELL", 90, 2, 2)]


def check_limit_at_touch_crosses(impl):
    """Buy exactly at the best ask crosses; one tick lower does not."""
    book = impl()
    res = run(book, [L(1, "a1", "SELL", 101, 2), L(2, "b1", "BUY", 100, 1), L(3, "b2", "BUY", 101, 1)])
    assert res[1]["status"] == "resting" and res[1]["fills"] == [], res[1]
    assert res[2]["fills"] == [fill("a1", "b2", 101, 1)] and res[2]["status"] == "filled", res[2]
    assert book.snapshot() == [row("b1", "BUY", 100, 1, 2), row("a1", "SELL", 101, 1, 1)]


def check_partial_maker_keeps_priority(impl):
    book = impl()
    res = run(book, [L(1, "b1", "BUY", 100, 5), L(2, "b2", "BUY", 100, 5), M(3, "s1", 2),
                     L(4, "b3", "BUY", 100, 1), M(5, "s2", 4)])
    assert res[2]["fills"] == [fill("b1", "s1", 100, 2)], res[2]
    assert res[4]["fills"] == [fill("b1", "s2", 100, 3), fill("b2", "s2", 100, 1)], res[4]
    assert book.snapshot() == [row("b2", "BUY", 100, 4, 2), row("b3", "BUY", 100, 1, 4)]


def check_market_sell_on_empty_book_is_unfilled(impl):
    r = run(impl(), [M(1, "s", 5)])[0]
    assert r == {"event_id": "e1", "order_id": "s", "status": "unfilled", "unfilled_qty_units": 5, "fills": []}, r


def check_market_sell_equal_to_depth_is_filled(impl):
    book = impl()
    r = run(book, [L(1, "b1", "BUY", 100, 2), L(2, "b2", "BUY", 99, 3), M(3, "s", 5)])[2]
    assert r["status"] == "filled" and r["unfilled_qty_units"] == 0, r
    assert book.snapshot() == [] and book.best_bid() is None


def check_market_sell_larger_than_depth_is_partial(impl):
    r = run(impl(), [L(1, "b1", "BUY", 100, 2), M(2, "s", 5)])[1]
    assert r == {"event_id": "e2", "order_id": "s", "status": "partial", "unfilled_qty_units": 3,
                 "fills": [fill("b1", "s", 100, 2)]}, r


def check_market_residual_discarded(impl):
    """The 3 unfilled units never rest: no ask appears, and a later buy at any price rests."""
    book = impl()
    res = run(book, [L(1, "b1", "BUY", 100, 2), M(2, "s", 5), L(3, "b2", "BUY", 10**9, 1)])
    assert res[1]["unfilled_qty_units"] == 3
    assert res[2] == {"event_id": "e3", "order_id": "b2", "status": "resting", "unfilled_qty_units": 1, "fills": []}, res[2]
    assert book.best_ask() is None and book.snapshot() == [row("b2", "BUY", 10**9, 1, 3)]


def check_market_sell_ignores_asks(impl):
    book = impl()
    r = run(book, [L(1, "a1", "SELL", 50, 4), L(2, "b1", "BUY", 40, 1), M(3, "s", 3)])[2]
    assert r["fills"] == [fill("b1", "s", 40, 1)] and r["status"] == "partial", r
    assert book.snapshot() == [row("a1", "SELL", 50, 4, 1)]


def check_long_queue_fifo(impl):
    """1000 one-unit buys at one price with ids in REVERSE spelling order; a 999-unit sell
    fills them in arrival order and leaves the last one."""
    ids = [f"o{999 - i:04d}" for i in range(1000)]          # o0999, o0998, ..., o0000
    book = impl()
    res = run(book, [L(i + 1, ids[i], "BUY", 100, 1) for i in range(1000)] + [M(1001, "s", 999)])
    assert [f["maker_id"] for f in res[-1]["fills"]] == ids[:999], "long queue not filled in arrival order"
    assert book.snapshot() == [row(ids[999], "BUY", 100, 1, 1000)]


# =========================================================================================
# cancellation
# =========================================================================================
def check_cancel_removes_exact_residual(impl):
    """Cancel after a partial fill removes exactly the 3 remaining units; b2 then trades first."""
    book = impl()
    res = run(book, [L(1, "b1", "BUY", 100, 5), L(2, "b2", "BUY", 100, 3), M(3, "s1", 2), C(4, "b1"), M(5, "s2", 3)])
    assert res[3] == {"event_id": "e4", "target_order_id": "b1", "status": "cancelled", "cancelled_qty_units": 3}, res[3]
    assert res[4]["fills"] == [fill("b2", "s2", 100, 3)], res[4]
    assert book.snapshot() == []


def check_cancel_before_fill_removes_full_qty(impl):
    book = impl()
    r = run(book, [L(1, "a1", "SELL", 100, 7), C(2, "a1")])[1]
    assert r == {"event_id": "e2", "target_order_id": "a1", "status": "cancelled", "cancelled_qty_units": 7}, r
    assert book.snapshot() == []


def check_cancel_not_found_cases(impl):
    """Filled, twice cancelled, unknown and market-sell ids are not_found with 0."""
    book = impl()
    res = run(book, [L(1, "b1", "BUY", 100, 1), L(2, "b2", "BUY", 100, 1), M(3, "s1", 1),
                     C(4, "b1"), C(5, "b2"), C(6, "b2"), C(7, "nope"), C(8, "s1")])
    nf = lambda s, t: {"event_id": f"e{s}", "target_order_id": t, "status": "not_found", "cancelled_qty_units": 0}  # noqa: E731
    assert res[3] == nf(4, "b1"), res[3]
    assert res[4]["status"] == "cancelled" and res[4]["cancelled_qty_units"] == 1, res[4]
    assert res[5:] == [nf(6, "b2"), nf(7, "nope"), nf(8, "s1")], res[5:]


def check_cancel_keeps_queue_order_of_others(impl):
    book = impl()
    run(book, [L(1, "b1", "BUY", 100, 1), L(2, "b2", "BUY", 100, 1), L(3, "b3", "BUY", 100, 1), C(4, "b2")])
    assert book.snapshot() == [row("b1", "BUY", 100, 1, 1), row("b3", "BUY", 100, 1, 3)]


# =========================================================================================
# validation and rejection (shared module: one check per rule family, SPEC.md)
# =========================================================================================
def _setup_invalid_base(impl):
    book = impl()
    run(book, INVALID_SETUP)
    return book


def _check_invalid_rows(impl, rows):
    assert rows, "no invalid rows selected: the table filter is wrong"
    for r in rows:
        book = _setup_invalid_base(impl)
        before = book.snapshot()
        ev = copy.deepcopy(r["event"])
        got = book.process(ev)
        want = {"event_id": r["result_event_id"], "status": "rejected", "reason": r["reason"]}
        assert got == want, f"[{r['label']}] {r['event']!r}\n got: {got}\nwant: {want}"
        assert book.snapshot() == before, f"[{r['label']}] rejected event changed the book"
        # the rejection did not advance the last accepted seq: seq 3 is still accepted
        ok = book.process(L(INVALID_SETUP_LAST_SEQ + 1, "ok", "BUY", 99, 1))
        assert ok.get("status") == "resting", f"[{r['label']}] valid seq-3 event after the rejection: {ok}"


def _rows(pred):
    return [r for r in INVALID_EVENTS if pred(r)]


def check_rejects_not_an_object(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["reason"] == "not_an_object"))


def check_rejects_bad_seq(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["reason"] in ("bad_seq", "missing_field:seq")))


def check_rejects_nonincreasing_seq(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["reason"] == "nonincreasing_seq"))


def check_rejects_unknown_type(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["reason"] in ("unknown_type", "missing_field:type")))


def check_rejects_missing_fields(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["reason"].startswith("missing_field:")))


def check_rejects_bad_ids(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["reason"].startswith("bad_id:")))


def check_rejects_unknown_side(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["reason"] == "unknown_side"))


def check_rejects_bad_price(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["reason"] == "bad_price"))


def check_rejects_bad_qty(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["reason"] == "bad_qty"))


def check_rejects_bool_quantity(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["label"] in ("qty-true", "qty-false", "market-qty-true")))


def check_rejects_integral_float_quantity(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["label"] in ("qty-integral-float", "market-qty-integral-float")))


def check_rejects_duplicate_live_id(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["reason"] == "duplicate_live_order_id"))


def check_validation_check_order(impl):
    _check_invalid_rows(impl, _rows(lambda r: r["label"].startswith("order-")))


def check_rejected_event_does_not_advance_seq(impl):
    book = impl()
    res = run(book, [L(1, "b1", "BUY", 100, 1),
                     L(2, "x", "BUY", 100, 0),             # rejected (bad_qty)
                     L(2, "b2", "BUY", 100, 1),            # seq 2 is still free -> accepted
                     L(2, "b3", "BUY", 100, 1, eid="r")])  # now 2 is taken -> nonincreasing
    assert res[1] == {"event_id": "e2", "status": "rejected", "reason": "bad_qty"}, res[1]
    assert res[2]["status"] == "resting", res[2]
    assert res[3] == {"event_id": "r", "status": "rejected", "reason": "nonincreasing_seq"}, res[3]


def check_accepted_cancel_and_market_advance_seq(impl):
    """A not_found cancel and an unfilled market sell are VALID events: they advance seq."""
    res = run(impl(), [C(1, "ghost"), L(1, "b1", "BUY", 100, 1, eid="r1"), M(2, "s", 1),
                       L(2, "b2", "BUY", 100, 1, eid="r2")])
    assert res[0]["status"] == "not_found" and res[2]["status"] == "unfilled", res
    assert res[1] == {"event_id": "r1", "status": "rejected", "reason": "nonincreasing_seq"}, res[1]
    assert res[3] == {"event_id": "r2", "status": "rejected", "reason": "nonincreasing_seq"}, res[3]


def check_reuse_of_inactive_ids_is_accepted(impl):
    """Historical id reuse is out of scope: filled / cancelled ids may be submitted again."""
    book = impl()
    res = run(book, [L(1, "b1", "BUY", 100, 1), M(2, "s", 1), L(3, "b1", "BUY", 90, 2), C(4, "b1"),
                     L(5, "b1", "SELL", 95, 1)])
    assert [r["status"] for r in res] == ["resting", "filled", "resting", "cancelled", "resting"], res
    assert book.snapshot() == [row("b1", "SELL", 95, 1, 5)]


# =========================================================================================
# interface and outputs
# =========================================================================================
_API_STREAM = [L(1, "b1", "BUY", 100, 5), L(2, "b2", "BUY", 99, 5), L(3, "a1", "SELL", 101, 2),
               M(4, "s1", 7), C(5, "b2"), C(6, "b2"), L(7, "t1", "BUY", 102, 3), M(8, "s2", 9),
               C(9, "zz"), L(10, "a2", "SELL", 105, 1)]


def check_direct_methods_match_process(impl):
    """AddLimitOrder / FillMarketSell / CancelOrder return exactly what process() returns."""
    via_process, direct = impl(), impl()
    route = {"LIMIT": direct.AddLimitOrder, "MARKET_SELL": direct.FillMarketSell, "CANCEL": direct.CancelOrder}
    for ev in _API_STREAM:
        a = via_process.process(copy.deepcopy(ev))
        b = route[ev["type"]](copy.deepcopy(ev))
        assert a == b, f"{ev}: process {a} != direct {b}"
        assert via_process.snapshot() == direct.snapshot(), f"books differ after {ev}"


def check_direct_methods_validate(impl):
    """The direct methods validate like process() (same shared validator)."""
    book = impl()
    assert book.AddLimitOrder(L(1, "b", "BUY", 100, 0)) == {"event_id": "e1", "status": "rejected", "reason": "bad_qty"}
    assert book.FillMarketSell(M(1, "s", True)) == {"event_id": "e1", "status": "rejected", "reason": "bad_qty"}
    assert book.CancelOrder(C(0, "b")) == {"event_id": "e0", "status": "rejected", "reason": "bad_seq"}
    assert book.snapshot() == []


def check_direct_methods_reject_wrong_type(impl):
    """N2: type mismatch follows unknown_type and precedes required-field checks."""
    methods = {"LIMIT": "AddLimitOrder", "MARKET_SELL": "FillMarketSell", "CANCEL": "CancelOrder"}
    for expected, method in methods.items():
        for actual in methods:
            if actual == expected:
                continue
            book = impl()
            run(book, [L(1, "b1", "BUY", 100, 5)])
            before = book.snapshot()
            # Missing event_id must lose to wrong_type_for_method.
            event = {"seq": 2, "type": actual}
            sent = copy.deepcopy(event)
            result = getattr(book, method)(sent)
            assert result == {"event_id": None, "status": "rejected", "reason": "wrong_type_for_method"}, result
            assert sent == event and book.snapshot() == before
            unknown = getattr(book, method)({"seq": 2, "type": "UNKNOWN"})
            assert unknown == {"event_id": None, "status": "rejected", "reason": "unknown_type"}, unknown
            assert book.process(C(2, "b1"))["status"] == "cancelled", "rejection advanced seq"


def check_unknown_extra_fields_ignored(impl):
    """N3: irrelevant fields do not affect validation, matching, results or state."""
    plain, extra = impl(), impl()
    events = [L(1, "b1", "BUY", 100, 3), M(2, "s", 2), C(3, "b1")]
    extras = [{"comment": "own contract case", "target_order_id": []},
              {"side": "HOLD", "price_ticks": False, "comment": "ignored on market sell"},
              {"side": [], "price_ticks": None, "qty_units": False, "order_id": [], "comment": "cancel"}]
    for event, fields in zip(events, extras):
        want = run(plain, [event])[0]
        got = run(extra, [{**event, **fields}])[0]
        assert got == want and extra.snapshot() == plain.snapshot()


def check_result_types_are_exact_ints(impl):
    for r in run(impl(), _API_STREAM):
        for k in ("unfilled_qty_units", "cancelled_qty_units"):
            if k in r:
                assert is_int(r[k]), f"{k} must be int: {r}"
        for f in r.get("fills", []):
            assert all(isinstance(f[k], str) for k in ("maker_id", "taker_id")), f


def check_input_event_not_mutated(impl):
    run(impl(), _API_STREAM)          # run() asserts each event is unchanged after process()


def check_fresh_instances_independent(impl):
    first = impl()
    run(first, [L(1, "b1", "BUY", 100, 1)])
    second = impl()
    assert second.snapshot() == [] and second.best_bid() is None, "a new book shares state with another one"
    assert second.process(L(1, "b1", "BUY", 100, 1))["status"] == "resting", "seq/id state shared between books"


def check_snapshot_is_a_copy(impl):
    book = impl()
    run(book, [L(1, "b1", "BUY", 100, 5)])
    snap = book.snapshot()
    snap[0]["qty_units"] = 999
    snap.append(row("ghost", "BUY", 1, 1, 99))
    assert book.snapshot() == [row("b1", "BUY", 100, 5, 1)], "editing a snapshot changed the book"


def check_snapshot_canonical_order(impl):
    book = impl()
    run(book, [L(1, "a1", "SELL", 105, 1), L(2, "b1", "BUY", 100, 1), L(3, "a2", "SELL", 103, 1),
               L(4, "b2", "BUY", 102, 1), L(5, "a3", "SELL", 103, 1), L(6, "b3", "BUY", 102, 1)])
    assert [r["order_id"] for r in book.snapshot()] == ["b2", "b3", "b1", "a2", "a3", "a1"], book.snapshot()


# =========================================================================================
# invariants on the supplied streams (valid data: nothing may be rejected)
# =========================================================================================
def check_invariants_on_supplied_stream_prefixes(impl):
    for sc in SUPPLIED_STREAMS:
        events = read_jsonl(SUPPLIED / f"{sc}_10000.jsonl.gz", limit=SUPPLIED_PREFIX)
        assert len(events) == SUPPLIED_PREFIX, sc
        res = run(impl(), events)
        rejected = [r for r in res if r.get("status") == "rejected"]
        assert not rejected, f"{sc}: supplied valid events were rejected: {rejected[:3]}"
