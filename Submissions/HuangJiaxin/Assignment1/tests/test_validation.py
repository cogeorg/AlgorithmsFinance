"""Invalid events are rejected without changing the book or the last accepted seq."""
import copy

import pytest

from conftest import BTC, run, usd


def _base(book, stream):
    run(book, [stream.buy("b1", 60000, 1), stream.sell("a1", 60100, 1)])   # seq 1, 2


def _limit(seq=3, **over):
    e = {"seq": seq, "event_id": f"ev{seq}", "type": "LIMIT", "order_id": "x",
         "side": "BUY", "price_ticks": usd(59000), "qty_units": BTC}
    e.update(over)
    return e


def _market(seq=3, **over):
    e = {"seq": seq, "event_id": f"ev{seq}", "type": "MARKET_SELL", "order_id": "m", "qty_units": BTC}
    e.update(over)
    return e


DROP = object()

INVALID = {
    "unknown type": _limit(type="LIMITT"),
    "unknown side": _limit(side="HOLD"),
    "zero price": _limit(price_ticks=0),
    "negative price": _limit(price_ticks=-100),
    "float price": _limit(price_ticks=5900000.5),
    "string price": _limit(price_ticks="5900000"),
    "bool price": _limit(price_ticks=True),
    "zero quantity": _limit(qty_units=0),
    "negative quantity": _limit(qty_units=-1),
    "float quantity": _limit(qty_units=1.5),
    "string quantity": _limit(qty_units="100"),
    "bool quantity": _limit(qty_units=True),
    "missing price": _limit(price_ticks=DROP),
    "missing order_id": _limit(order_id=DROP),
    "missing side": _limit(side=DROP),
    "missing type": _limit(type=DROP),
    "missing seq": _limit(seq=DROP),
    "float seq": _limit(seq=3.0),
    "duplicate live limit id": _limit(order_id="b1"),
    "duplicate live id on market sell": _market(order_id="a1"),
    "market sell zero quantity": _market(qty_units=0),
    "market sell negative quantity": _market(qty_units=-5),
    "seq equal to last accepted": _limit(seq=2),
    "seq smaller than last accepted": _limit(seq=1),
    "cancel without target": {"seq": 3, "event_id": "ev3", "type": "CANCEL"},
    # found in an external review: JSON lists/objects are unhashable and used to crash
    "type is a JSON list": _limit(type=["LIMIT"]),
    "type is a JSON object": _limit(type={"name": "LIMIT"}),
    "side is a JSON list": _limit(side=["BUY"]),
}


def _clean(e):
    return {k: v for k, v in e.items() if v is not DROP}


@pytest.mark.parametrize("name", list(INVALID))
def test_invalid_event_is_rejected_without_change(book, stream, name):
    _base(book, stream)
    before = copy.deepcopy(book.snapshot())
    event = _clean(INVALID[name])
    r = book.process(event)
    assert r["status"] == "rejected", name
    assert isinstance(r.get("reason"), str) and r["reason"], name
    assert r["event_id"] == event.get("event_id")
    assert book.snapshot() == before, name
    # the rejected event did not advance the last accepted seq: seq 3 is still accepted
    ok = book.process(_limit(seq=3, order_id="later"))
    assert ok["status"] == "resting", name


def test_rejected_large_seq_does_not_advance(book, stream):
    _base(book, stream)
    assert book.process(_limit(seq=10, qty_units=0))["status"] == "rejected"
    assert book.process(_limit(seq=3))["status"] == "resting"


def test_seq_may_skip_numbers(book, stream):
    _base(book, stream)
    assert book.process(_limit(seq=100))["status"] == "resting"
    assert book.process(_limit(seq=50, order_id="y"))["status"] == "rejected"


def test_cancel_of_unknown_target_is_valid_and_advances_seq(book, stream):
    _base(book, stream)
    r = book.process({"seq": 3, "event_id": "ev3", "type": "CANCEL", "target_order_id": "zzz"})
    assert r["status"] == "not_found"
    assert book.process(_limit(seq=3, order_id="y"))["status"] == "rejected"


def test_rejected_crossing_order_does_not_trade(book, stream):
    _base(book, stream)
    r = book.process(_limit(side="BUY", price_ticks=usd(60100), qty_units=-1))
    assert r["status"] == "rejected"
    assert book.snapshot()["asks"][0]["qty_units"] == BTC
