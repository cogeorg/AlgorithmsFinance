"""Robustness: adversarial events and malformed input lines.

Expected behaviour comes from the specification and the validation rules
documented in 03_code/validation.py, not from the implementation:
  - an invalid event is rejected: status "rejected", a reason that names the
    cause, the book and last_seq unchanged, no exception;
  - unusual but valid events (huge quantity, extra fields, reuse of an id
    that is no longer live, cancel of a market-sell id) are processed
    normally;
  - all three versions give identical results and books;
  - replay.py turns a line that is not valid JSON into the result
    {"event_id": None, "status": "rejected", "reason": "malformed JSON line <n>"}
    and continues; empty lines are skipped.
Engine reason texts are not compared word for word (only the cause they
name). The malformed-line reason is compared exactly, because its wording is
part of the replay specification.
"""

import copy
import gzip
import importlib
import json

import pytest

import replay
from conftest import VERSIONS
from invariants import check_event

HUGE = 10 ** 30


def ev(seq, kind, **fields):
    return {"seq": seq, "event_id": f"e{seq}", "type": kind, **fields}


def limit(seq, order_id, side, price_ticks, qty_units):
    return ev(seq, "LIMIT", order_id=order_id, side=side, price_ticks=price_ticks,
              qty_units=qty_units)


def market(seq, order_id, qty_units):
    return ev(seq, "MARKET_SELL", order_id=order_id, qty_units=qty_units)


def cancel(seq, target):
    return ev(seq, "CANCEL", target_order_id=target)


def without(event, field):
    return {k: v for k, v in event.items() if k != field}


# Two bids and two asks, not crossed. Accepted seqs 1-4, so seq 5 is next.
BOOK_EVENTS = [limit(1, "b1", "BUY", 100, 5), limit(2, "b2", "BUY", 99, 7),
               limit(3, "a1", "SELL", 101, 4), limit(4, "a2", "SELL", 102, 6)]


def seeded_book(lob):
    book = lob.OrderBook()
    for e in BOOK_EVENTS:
        assert book.process_event(e)["status"] == "resting"
    return book


# (case, event, a word the reason must contain). Every event would be the
# next valid event (seq 5) if it were not broken.
REJECTS = [
    ("price as string", limit(5, "x", "BUY", "100", 1), "price"),
    ("price as float", limit(5, "x", "BUY", 100.0, 1), "price"),
    ("price as bool", limit(5, "x", "BUY", True, 1), "price"),
    ("price zero", limit(5, "x", "BUY", 0, 1), "price"),
    ("price negative", limit(5, "x", "BUY", -100, 1), "price"),
    ("qty as string", limit(5, "x", "BUY", 98, "1"), "qty"),
    ("qty as float", limit(5, "x", "BUY", 98, 1.5), "qty"),
    ("qty as bool", limit(5, "x", "BUY", 98, True), "qty"),
    ("qty zero", limit(5, "x", "BUY", 98, 0), "qty"),
    ("market qty as string", market(5, "m", "3"), "qty"),
    ("market qty as float", market(5, "m", 3.0), "qty"),
    ("market qty as bool", market(5, "m", True), "qty"),
    ("side lowercase", limit(5, "x", "buy", 98, 1), "side"),
    ("side unknown", limit(5, "x", "BID", 98, 1), "side"),
    ("type unknown", ev(5, "MARKET_BUY", order_id="x", qty_units=1), "type"),
    ("type lowercase", ev(5, "limit", order_id="x", side="BUY", price_ticks=98,
                          qty_units=1), "type"),
    ("type missing", without(limit(5, "x", "BUY", 98, 1), "type"), "type"),
    ("order_id missing", without(limit(5, "x", "BUY", 98, 1), "order_id"), "order_id"),
    ("order_id not a string", limit(5, 7, "BUY", 98, 1), "order_id"),
    ("side missing", without(limit(5, "x", "BUY", 98, 1), "side"), "side"),
    ("price missing", without(limit(5, "x", "BUY", 98, 1), "price_ticks"), "price"),
    ("qty missing", without(limit(5, "x", "BUY", 98, 1), "qty_units"), "qty"),
    ("market qty missing", without(market(5, "m", 3), "qty_units"), "qty"),
    ("market order_id missing", without(market(5, "m", 3), "order_id"), "order_id"),
    ("cancel target missing", without(cancel(5, "b1"), "target_order_id"),
     "target_order_id"),
    ("cancel target not a string", cancel(5, 1), "target_order_id"),
    ("seq missing", without(limit(5, "x", "BUY", 98, 1), "seq"), "seq"),
    ("seq as string", {**limit(5, "x", "BUY", 98, 1), "seq": "5"}, "seq"),
    ("seq as float", {**limit(5, "x", "BUY", 98, 1), "seq": 5.0}, "seq"),
    ("seq repeated", limit(4, "x", "BUY", 98, 1), "seq"),
    ("seq going back", limit(2, "x", "BUY", 98, 1), "seq"),
    ("event_id missing", without(limit(5, "x", "BUY", 98, 1), "event_id"), "event_id"),
    ("event is a list", [5, "e5", "LIMIT"], "object"),
    ("event is a string", "LIMIT", "object"),
    ("event is a number", 5, "object"),
    ("event is null", None, "object"),
    ("order_id still live", limit(5, "b1", "BUY", 98, 1), "duplicate"),
]


@pytest.mark.source("spec + validation rules: adversarial events are rejected")
@pytest.mark.parametrize("case, event, cause", REJECTS, ids=[c[0] for c in REJECTS])
def test_invalid_event_is_rejected_and_changes_nothing(lob, case, event, cause):
    book = seeded_book(lob)
    before, last_seq = book.inspect_book(), book.last_seq
    sent = copy.deepcopy(event)

    result = book.process_event(event)

    event_id = event.get("event_id") if isinstance(event, dict) else None
    assert result == {"event_id": event_id, "status": "rejected", "reason": result["reason"]}
    assert isinstance(result["reason"], str) and cause in result["reason"], result["reason"]
    assert book.inspect_book() == before
    assert book.last_seq == last_seq
    assert event == sent                      # the input is not modified
    book.assert_invariants()
    # The rejected event did not use up seq 5.
    assert book.process_event(limit(5, "next", "BUY", 98, 1))["status"] == "resting"


@pytest.mark.source("spec: huge quantity is a valid integer (rests in full)")
def test_huge_quantity_limit_rests(lob):
    book = seeded_book(lob)
    result = book.process_event(limit(5, "big", "SELL", 103, HUGE))
    assert result == {"event_id": "e5", "order_id": "big", "status": "resting",
                      "unfilled_qty_units": HUGE, "fills": []}
    assert book.inspect_book()[-1] == {"order_id": "big", "side": "SELL", "price_ticks": 103,
                                       "qty_units": HUGE, "arrival_seq": 5}
    book.assert_invariants()


@pytest.mark.source("spec: huge market sell takes every bid, the rest is discarded")
def test_huge_quantity_market_sell(lob):
    book = seeded_book(lob)
    result = book.process_event(market(5, "m", HUGE))
    assert result == {
        "event_id": "e5", "order_id": "m", "status": "partial",
        "unfilled_qty_units": HUGE - 12,
        "fills": [{"maker_id": "b1", "taker_id": "m", "price_ticks": 100, "qty_units": 5},
                  {"maker_id": "b2", "taker_id": "m", "price_ticks": 99, "qty_units": 7}]}
    assert [o["order_id"] for o in book.inspect_book()] == ["a1", "a2"]
    book.assert_invariants()


@pytest.mark.source("spec: a market sell never rests, so cancelling its id is not_found")
def test_cancel_of_market_sell_id_is_not_found(lob):
    book = seeded_book(lob)
    assert book.process_event(market(5, "m1", 3))["status"] == "filled"
    before = book.inspect_book()
    result = book.process_event(cancel(6, "m1"))
    assert result == {"event_id": "e6", "target_order_id": "m1", "status": "not_found",
                      "cancelled_qty_units": 0}
    assert book.inspect_book() == before
    assert book.last_seq == 6                 # a valid cancel, so seq 6 is used


@pytest.mark.source("spec: only LIVE ids are duplicates; a gone id may be reused")
def test_order_id_reuse_after_the_order_is_gone(lob):
    book = seeded_book(lob)
    # b1 (BUY 5 @ 100) is filled away; a2 is cancelled.
    assert book.process_event(market(5, "m", 5))["status"] == "filled"
    assert book.process_event(cancel(6, "a2"))["status"] == "cancelled"
    r1 = book.process_event(limit(7, "b1", "BUY", 98, 2))
    r2 = book.process_event(limit(8, "a2", "SELL", 105, 3))
    assert (r1["status"], r2["status"]) == ("resting", "resting")
    assert book.inspect_book() == [
        {"order_id": "b2", "side": "BUY", "price_ticks": 99, "qty_units": 7, "arrival_seq": 2},
        {"order_id": "b1", "side": "BUY", "price_ticks": 98, "qty_units": 2, "arrival_seq": 7},
        {"order_id": "a1", "side": "SELL", "price_ticks": 101, "qty_units": 4, "arrival_seq": 3},
        {"order_id": "a2", "side": "SELL", "price_ticks": 105, "qty_units": 3, "arrival_seq": 8}]
    # While the new b1 is live, a third b1 is a duplicate.
    assert book.process_event(limit(9, "b1", "BUY", 97, 1))["status"] == "rejected"
    book.assert_invariants()


@pytest.mark.source("spec: unknown extra fields are ignored")
def test_extra_fields_are_ignored(lob):
    plain = [limit(5, "x", "BUY", 101, 6), market(6, "m", 2), cancel(7, "x")]
    extra = [{**e, "note": "hello", "price_usd": "1.01", "nested": {"a": [1, 2]}}
             for e in plain]
    book_plain, book_extra = seeded_book(lob), seeded_book(lob)
    for p, x in zip(plain, extra):
        assert book_extra.process_event(x) == book_plain.process_event(p)
        assert book_extra.inspect_book() == book_plain.inspect_book()


def adversarial_stream():
    """The seeded book, every reject case, and the valid edge cases, in one
    stream with increasing seqs (rejected events do not use their seq)."""
    stream = list(BOOK_EVENTS)
    for _, event, _ in REJECTS:
        stream.append(copy.deepcopy(event))
    stream += [limit(5, "big", "SELL", 103, HUGE), market(6, "m1", 3), cancel(7, "m1"),
               market(8, "m2", 2), limit(9, "b1", "BUY", 98, 2),
               {**limit(10, "x", "BUY", 97, 1), "note": "extra"},
               market(11, "m3", HUGE), cancel(12, "nobody"), limit(13, "b1", "BUY", 96, 1)]
    return stream


@pytest.mark.source("differential: A vs B-sorted vs B-heap on the adversarial stream")
@pytest.mark.cross_version
def test_versions_agree_on_adversarial_stream():
    outputs = {}
    for name in VERSIONS:
        book = importlib.import_module(name).OrderBook()
        results, books = [], []
        before = book.inspect_book()
        for event in adversarial_stream():
            result = book.process_event(event)
            after = book.inspect_book()
            book.assert_invariants()
            check_event(before, event, result, after)
            results.append(result)
            books.append(after)
            before = after
        outputs[name] = (results, books, book.last_seq)
    first = outputs[VERSIONS[0]]
    for name in VERSIONS[1:]:
        assert outputs[name] == first, name
    statuses = [r["status"] for r in first[0]]
    assert statuses.count("rejected") == len(REJECTS)
    assert {"resting", "filled", "partial", "not_found"} <= set(statuses)


# ----- replay.py: malformed lines ---------------------------------------------------

def write_lines(path, lines):
    data = b"\n".join(lines) + b"\n"
    if path.suffix == ".gz":
        with gzip.open(path, "wb") as fh:
            fh.write(data)
    else:
        path.write_bytes(data)


def j(event):
    return json.dumps(event).encode()


GOOD = [limit(1, "b1", "BUY", 100, 5), limit(2, "a1", "SELL", 101, 4), market(3, "m1", 2)]
FILE_LINES = [
    j(GOOD[0]),                                   # line 1
    b"",                                          # line 2: empty, skipped
    b'{"seq": 2, "event_id": "e2", "type": "LIM',  # line 3: cut off
    b"   \t ",                                    # line 4: whitespace only, skipped
    j(GOOD[1]),                                   # line 5 (seq 2 is still free)
    b"not json at all",                           # line 6
    b'{"seq": 3, "event_id": "e\xff"}',            # line 7: invalid UTF-8
    b"[" * 100_000 + b"]" * 100_000,              # line 8: too deeply nested
    j(GOOD[2]),                                   # line 9
    b"[1, 2]",                                    # line 10: valid JSON, not an object
]


def malformed(n):
    return {"event_id": None, "status": "rejected", "reason": f"malformed JSON line {n}"}


@pytest.mark.source("spec: malformed JSON lines are rejected, the replay continues")
@pytest.mark.parametrize("suffix", [".jsonl", ".jsonl.gz"])
@pytest.mark.parametrize("check", [False, True], ids=["timed", "checked"])
def test_replay_survives_malformed_lines(lob, tmp_path, suffix, check):
    version = lob.__name__.removeprefix("lob_")
    src = tmp_path / f"broken{suffix}"
    write_lines(src, FILE_LINES)
    out = tmp_path / "results.jsonl"

    args = [str(src), "--version", version, "--results", str(out)]
    assert replay.main(args + (["--check"] if check else [])) == 0

    results = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    clean = lob.OrderBook()
    good = [clean.process_event(e) for e in GOOD]   # the same events in a clean file
    assert len(results) == 8                        # 10 lines minus 2 empty ones
    assert results[:7] == [good[0], malformed(3), good[1], malformed(6), malformed(7),
                           malformed(8), good[2]]
    assert results[7]["event_id"] is None and results[7]["status"] == "rejected"
    assert "object" in results[7]["reason"]


@pytest.mark.source("spec: --print-book prints the final book, one order per line")
def test_replay_prints_final_book(lob, tmp_path, capsys):
    version = lob.__name__.removeprefix("lob_")
    src = tmp_path / "events.jsonl"
    write_lines(src, [j(e) for e in GOOD])
    assert replay.main([str(src), "--version", version, "--print-book"]) == 0
    lines = capsys.readouterr().out.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("final book"))
    printed = [json.loads(line) for line in lines[start + 1:]]
    clean = lob.OrderBook()
    for e in GOOD:
        clean.process_event(e)
    assert printed == clean.inspect_book()
    assert [o["qty_units"] for o in printed] == [3, 4]     # b1 lost 2 to the sale
