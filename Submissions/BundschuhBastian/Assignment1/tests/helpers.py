"""Test helpers: event builders and an independent checker that runs after EVERY event.

The checker uses only the public interface (process, snapshot, best_bid, best_ask) and the
rules in SPEC.md. It does not import anything from the engines' internals, and it does not
use lob.common (so a bug in shared code cannot hide itself here).

`step(book, event)` = process one event and then check:
  - the engine did not change the caller's event dict
  - book invariants I1-I3 (not crossed, all quantities > 0, every id once, canonical order,
    best_bid/best_ask agree with the snapshot)
  - result shape (exact keys per status, SPEC.md D10-D14)
  - conservation I4-I7: incoming = fills + residual, each maker loses exactly its fills,
    a cancel removes exactly the residual, rejected / not_found leave the book unchanged
  - priority: fills walk the opposite side from the best price, FIFO inside a price,
    every fill at the maker's price and within the taker's limit
"""
from __future__ import annotations

import copy

BUY, SELL = "BUY", "SELL"
ORDER_KEYS = {"order_id", "side", "price_ticks", "qty_units", "arrival_seq"}
FILL_KEYS = {"maker_id", "taker_id", "price_ticks", "qty_units"}
SUBMIT_KEYS = {"event_id", "order_id", "status", "unfilled_qty_units", "fills"}
CANCEL_KEYS = {"event_id", "target_order_id", "status", "cancelled_qty_units", "fills"}
REJECT_KEYS = {"event_id", "status", "reason", "fills"}


# --- event and expected-value builders (plain dicts, nothing hidden) -----------------
def limit(seq, order_id, side, price, qty, event_id=None):
    return {"seq": seq, "event_id": event_id or f"e{seq}", "type": "LIMIT",
            "order_id": order_id, "side": side, "price_ticks": price, "qty_units": qty}


def msell(seq, order_id, qty, event_id=None):
    return {"seq": seq, "event_id": event_id or f"e{seq}", "type": "MARKET_SELL",
            "order_id": order_id, "qty_units": qty}


def cancel(seq, target, event_id=None):
    return {"seq": seq, "event_id": event_id or f"e{seq}", "type": "CANCEL",
            "target_order_id": target}


def order(order_id, side, price, qty, arrival):
    """One expected line of snapshot()."""
    return {"order_id": order_id, "side": side, "price_ticks": price,
            "qty_units": qty, "arrival_seq": arrival}


def fill(maker, taker, price, qty):
    return {"maker_id": maker, "taker_id": taker, "price_ticks": price, "qty_units": qty}


def submitted(event_id, order_id, status, unfilled, fills=()):
    return {"event_id": event_id, "order_id": order_id, "status": status,
            "unfilled_qty_units": unfilled, "fills": list(fills)}


def cancelled(event_id, target, qty):
    return {"event_id": event_id, "target_order_id": target, "status": "cancelled",
            "cancelled_qty_units": qty, "fills": []}


def not_found(event_id, target):
    return {"event_id": event_id, "target_order_id": target, "status": "not_found",
            "cancelled_qty_units": 0, "fills": []}


def rejected(event_id, reason):
    return {"event_id": event_id, "status": "rejected", "reason": reason, "fills": []}


# --- running events ----------------------------------------------------------------------
def step(book, event):
    """Process one event through `book` and run every check. Returns the result."""
    before = book.snapshot()
    event_before = copy.deepcopy(event)
    result = book.process(event)
    assert event == event_before, "engine changed the caller's event"
    after = book.snapshot()
    check_book(book, after)
    check_result(event, result, before, after)
    return result


def run(book, events):
    """step() every event; return the list of results."""
    return [step(book, ev) for ev in events]


# --- book invariants (I1-I3) -------------------------------------------------------------
def _is_int(x):
    return type(x) is int


def canonical_key(o):
    if o["side"] == BUY:
        return (0, -o["price_ticks"], o["arrival_seq"])
    return (1, o["price_ticks"], o["arrival_seq"])


def check_book(book, snap):
    assert isinstance(snap, list)
    ids = [o["order_id"] for o in snap]
    assert len(ids) == len(set(ids)), f"order stored twice: {ids}"
    for o in snap:
        assert set(o) == ORDER_KEYS, f"bad snapshot keys {set(o)}"
        assert o["side"] in (BUY, SELL)
        for k in ("price_ticks", "qty_units", "arrival_seq"):
            assert _is_int(o[k]) and o[k] > 0, f"{k} not a positive int in {o}"
    assert snap == sorted(snap, key=canonical_key), "snapshot not in canonical order"
    bids = [o["price_ticks"] for o in snap if o["side"] == BUY]
    asks = [o["price_ticks"] for o in snap if o["side"] == SELL]
    assert book.best_bid() == (max(bids) if bids else None)
    assert book.best_ask() == (min(asks) if asks else None)
    if bids and asks:
        assert max(bids) < min(asks), f"crossed book: bid {max(bids)} >= ask {min(asks)}"


# --- result shape and conservation (I4-I7) ----------------------------------------------
def check_result(event, result, before, after):
    assert isinstance(result, dict), f"result is not a dict: {result!r}"
    assert isinstance(result.get("fills"), list), "result has no fills list"
    status = result.get("status")
    before_by_id = {o["order_id"]: o for o in before}
    after_by_id = {o["order_id"]: o for o in after}

    if status == "rejected":
        assert set(result) == REJECT_KEYS
        assert result["fills"] == []
        assert isinstance(result["reason"], str) and result["reason"]
        assert after == before, "rejected event changed the book"
        return

    if status in ("cancelled", "not_found"):
        assert set(result) == CANCEL_KEYS
        assert result["fills"] == []
        assert result["target_order_id"] == event["target_order_id"]
        target = event["target_order_id"]
        if status == "not_found":
            assert result["cancelled_qty_units"] == 0
            assert after == before, "not_found cancel changed the book"
        else:
            assert target in before_by_id and target not in after_by_id
            assert result["cancelled_qty_units"] == before_by_id[target]["qty_units"]
            assert after == [o for o in before if o["order_id"] != target]
        return

    # accepted LIMIT or MARKET_SELL
    assert set(result) == SUBMIT_KEYS, f"bad result keys {set(result)}"
    typ, taker = event["type"], event["order_id"]
    assert result["order_id"] == taker and result["event_id"] == event["event_id"]
    incoming_side = event["side"] if typ == "LIMIT" else SELL
    maker_side = SELL if incoming_side == BUY else BUY
    fills = result["fills"]

    filled_by_maker = {}
    prev_key = None
    for f in fills:
        assert set(f) == FILL_KEYS
        assert f["taker_id"] == taker
        assert _is_int(f["qty_units"]) and f["qty_units"] > 0
        maker = before_by_id.get(f["maker_id"])
        assert maker is not None, f"maker {f['maker_id']} was not resting before"
        assert maker["side"] == maker_side
        assert f["price_ticks"] == maker["price_ticks"], "fill not at the maker's price"
        if typ == "LIMIT":
            if incoming_side == BUY:
                assert f["price_ticks"] <= event["price_ticks"], "buy filled above its limit"
            else:
                assert f["price_ticks"] >= event["price_ticks"], "sell filled below its limit"
        key = canonical_key(maker)          # walk from the best price, FIFO inside a price
        assert prev_key is None or key > prev_key, "fills out of price-time order"
        prev_key = key
        filled_by_maker[f["maker_id"]] = filled_by_maker.get(f["maker_id"], 0) + f["qty_units"]

    # I4: incoming = fills + residual
    total = sum(f["qty_units"] for f in fills)
    assert total + result["unfilled_qty_units"] == event["qty_units"]
    assert _is_int(result["unfilled_qty_units"]) and result["unfilled_qty_units"] >= 0

    # I5: each maker loses exactly its fills; untouched orders unchanged
    for oid, o in before_by_id.items():
        lost = filled_by_maker.get(oid, 0)
        if lost == o["qty_units"]:
            assert oid not in after_by_id, f"exhausted maker {oid} still in book"
        else:
            assert after_by_id.get(oid) == dict(o, qty_units=o["qty_units"] - lost)

    # residual handling and status
    new_ids = set(after_by_id) - set(before_by_id)
    if typ == "LIMIT":
        if result["unfilled_qty_units"] == 0:
            assert result["status"] == "filled" and not new_ids
        else:
            assert result["status"] == "resting" and new_ids == {taker}
            assert after_by_id[taker] == order(taker, incoming_side, event["price_ticks"],
                                               result["unfilled_qty_units"], event["seq"])
    else:
        assert not new_ids, "market sell residual rests in the book"
        if result["unfilled_qty_units"] == 0:
            assert result["status"] == "filled"
        elif fills:
            assert result["status"] == "partial"
        else:
            assert result["status"] == "unfilled"
        if result["unfilled_qty_units"] > 0:
            assert not any(o["side"] == BUY for o in after), "market sell stopped with bids left"
