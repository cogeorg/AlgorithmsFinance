"""Independent checks derived from the specification (ASSIGNMENT.md), not from either version.

The oracle only sees the public outputs: the event, its result, and inspect_book()
before and after the event. From the *before* book it recomputes, independently of
the engine, which makers must trade (price-time priority), how much, at which price,
and what the book must look like afterwards.
"""

SUBMISSION_KEYS = {"event_id", "order_id", "status", "unfilled_qty_units", "fills"}
CANCEL_KEYS = {"event_id", "target_order_id", "status", "cancelled_qty_units"}
FILL_KEYS = {"maker_id", "taker_id", "price_ticks", "qty_units"}
ORDER_KEYS = {"order_id", "side", "price_ticks", "qty_units", "arrival_seq"}


def _is_pos_int(x):
    # bool is a subclass of int in Python, so check the exact type.
    return type(x) is int and x > 0


def _is_id(x):
    return isinstance(x, str) and x != ""


def expected_valid(event, last_seq, live_ids):
    """Independent restatement of the validation rules."""
    if not isinstance(event, dict):
        return False
    if not _is_pos_int(event.get("seq")) or event["seq"] <= last_seq:
        return False
    if not _is_id(event.get("event_id")):
        return False
    kind = event.get("type")
    if kind == "LIMIT":
        return (_is_id(event.get("order_id")) and event["order_id"] not in live_ids
                and event.get("side") in ("BUY", "SELL")
                and _is_pos_int(event.get("price_ticks"))
                and _is_pos_int(event.get("qty_units")))
    if kind == "MARKET_SELL":
        return (_is_id(event.get("order_id")) and event["order_id"] not in live_ids
                and _is_pos_int(event.get("qty_units")))
    if kind == "CANCEL":
        return _is_id(event.get("target_order_id"))
    return False


def book_map(orders):
    out = {}
    for o in orders:
        assert set(o) == ORDER_KEYS, f"unexpected order keys {sorted(o)}"
        assert o["order_id"] not in out, f"order {o['order_id']} stored twice"
        out[o["order_id"]] = (o["side"], o["price_ticks"], o["qty_units"], o["arrival_seq"])
    return out


def check_book_invariants(orders):
    """No crossed book, positive integer quantities, no duplicates, canonical order."""
    book_map(orders)
    for o in orders:
        assert o["side"] in ("BUY", "SELL")
        assert _is_pos_int(o["price_ticks"]), o
        assert _is_pos_int(o["qty_units"]), f"nonpositive resting quantity: {o}"
        assert _is_pos_int(o["arrival_seq"]), o
    bids = [o for o in orders if o["side"] == "BUY"]
    asks = [o for o in orders if o["side"] == "SELL"]
    canonical = (sorted(bids, key=lambda o: (-o["price_ticks"], o["arrival_seq"]))
                 + sorted(asks, key=lambda o: (o["price_ticks"], o["arrival_seq"])))
    assert orders == canonical, "inspect_book() is not in canonical price-time order"
    if bids and asks:
        assert bids[0]["price_ticks"] < asks[0]["price_ticks"], "crossed resting book"


def _priority_queue(book, side):
    rows = [(oid, v) for oid, v in book.items() if v[0] == side]
    if side == "BUY":
        rows.sort(key=lambda r: (-r[1][1], r[1][3]))
    else:
        rows.sort(key=lambda r: (r[1][1], r[1][3]))
    return rows


def check_event(before, event, result, after, last_seq):
    """Check one processed event. Returns the new last accepted seq."""
    b = book_map(before)
    a = book_map(after)
    check_book_invariants(after)
    valid = expected_valid(event, last_seq, set(b))
    status = result.get("status")

    if not valid:
        assert status == "rejected", f"invalid event accepted: {event} -> {result}"
        assert isinstance(result.get("reason"), str) and result["reason"], result
        if isinstance(event, dict) and "event_id" in event:
            assert result.get("event_id") == event["event_id"]
        assert a == b and before == after, "rejected event changed the book"
        return last_seq

    assert status != "rejected", f"valid event rejected: {event} -> {result}"
    kind = event["type"]
    assert result["event_id"] == event["event_id"]

    if kind == "CANCEL":
        assert set(result) == CANCEL_KEYS, sorted(result)
        target = event["target_order_id"]
        assert result["target_order_id"] == target
        if target in b:
            assert status == "cancelled"
            assert result["cancelled_qty_units"] == b[target][2], "cancel must remove exactly the residual"
            expected = dict(b)
            del expected[target]
        else:
            assert status == "not_found" and result["cancelled_qty_units"] == 0
            expected = b
        assert a == expected, "cancel changed other orders"
        return event["seq"]

    assert set(result) == SUBMISSION_KEYS, sorted(result)
    oid = event["order_id"]
    qty = event["qty_units"]
    side = "SELL" if kind == "MARKET_SELL" else event["side"]
    limit = event["price_ticks"] if kind == "LIMIT" else None
    assert result["order_id"] == oid

    def crosses(maker_price):
        if limit is None:
            return True
        return maker_price <= limit if side == "BUY" else maker_price >= limit

    queue = _priority_queue(b, "SELL" if side == "BUY" else "BUY")
    fills = result["fills"]
    assert len(fills) <= len(queue), "more fills than resting makers"
    expected = dict(b)
    executed = 0
    for i, f in enumerate(fills):
        assert set(f) == FILL_KEYS, sorted(f)
        maker_id, (m_side, m_price, m_qty, m_seq) = queue[i]
        assert f["maker_id"] == maker_id, (
            f"fill {i}: expected maker {maker_id} by price-time priority, got {f['maker_id']}")
        assert f["taker_id"] == oid
        assert f["price_ticks"] == m_price, "must execute at the resting order's price"
        assert crosses(m_price), "traded with a maker that does not cross"
        assert _is_pos_int(f["qty_units"]) and f["qty_units"] <= m_qty
        if i < len(fills) - 1:
            assert f["qty_units"] == m_qty, "only the last maker may be partially filled"
        executed += f["qty_units"]
        if f["qty_units"] == m_qty:
            del expected[maker_id]
        else:
            expected[maker_id] = (m_side, m_price, m_qty - f["qty_units"], m_seq)

    unfilled = qty - executed
    assert unfilled >= 0
    assert result["unfilled_qty_units"] == unfilled, "incoming qty != executed + residual"
    if fills and fills[-1]["qty_units"] < queue[len(fills) - 1][1][2]:
        assert unfilled == 0, "maker left partially filled while incoming still had quantity"
    if unfilled > 0 and len(fills) < len(queue):
        assert not crosses(queue[len(fills)][1][1]), "matching stopped while a crossing maker remained"

    if kind == "LIMIT":
        assert status == ("filled" if unfilled == 0 else "resting")
        if unfilled:
            expected[oid] = (side, limit, unfilled, event["seq"])
    else:
        assert status == ("filled" if unfilled == 0 else ("unfilled" if not fills else "partial"))
        assert oid not in a, "market residual must not rest"
    assert a == expected, "book after event differs from independently expected book"
    return event["seq"]
