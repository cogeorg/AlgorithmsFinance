"""Per-event checks that work for every version (they only use inspect_book()).

check_event(before, event, result, after) raises AssertionError when one
accepted event breaks conservation or price-time priority. `before` and
`after` are inspect_book() snapshots taken around process_event(event).

The structural invariants (no crossed book, positive quantities, no order
stored twice) live in each version's own assert_invariants(), because they
must look at the version's internal storage.
"""


def _qty_by_id(book):
    return {o["order_id"]: o["qty_units"] for o in book}


def _expected_fills(before, taker_id, taker_side, qty, limit_price):
    """Fills implied by the canonical `before` book (oracle for priority)."""
    maker_side = "SELL" if taker_side == "BUY" else "BUY"
    makers = [o for o in before if o["side"] == maker_side]  # already canonical
    fills = []
    for m in makers:
        if qty == 0:
            break
        p = m["price_ticks"]
        if limit_price is not None:
            if taker_side == "BUY" and limit_price < p:
                break
            if taker_side == "SELL" and limit_price > p:
                break
        traded = min(qty, m["qty_units"])
        fills.append({"maker_id": m["order_id"], "taker_id": taker_id,
                      "price_ticks": p, "qty_units": traded})
        qty -= traded
    return fills


def check_event(before, event, result, after):
    status = result["status"]

    if status == "rejected":
        assert before == after, "rejected event changed the book"
        return

    if event["type"] == "CANCEL":
        b, a = _qty_by_id(before), _qty_by_id(after)
        target = event["target_order_id"]
        if status == "cancelled":
            # A cancel removes exactly the residual and nothing else.
            assert target in b and target not in a
            assert result["cancelled_qty_units"] == b[target]
            del b[target]
        else:
            assert status == "not_found", status
            assert target not in b
            assert result["cancelled_qty_units"] == 0
        assert b == a, "cancel changed other orders"
        return

    # LIMIT or MARKET_SELL
    order_id = event["order_id"]
    qty = event["qty_units"]
    fills = result["fills"]
    unfilled = result["unfilled_qty_units"]
    if event["type"] == "LIMIT":
        side, limit = event["side"], event["price_ticks"]
    else:
        side, limit = "SELL", None

    # Incoming quantity = sum of fills + returned residual.
    assert all(f["qty_units"] > 0 for f in fills)
    assert qty == sum(f["qty_units"] for f in fills) + unfilled

    # Fills follow price-time priority of the book before the event.
    assert fills == _expected_fills(before, order_id, side, qty, limit), \
        "fills differ from price-time priority"

    # Each maker loses exactly its filled quantity.
    b, a = _qty_by_id(before), _qty_by_id(after)
    for f in fills:
        b[f["maker_id"]] -= f["qty_units"]
    b = {k: v for k, v in b.items() if v > 0}

    # Only a limit residual may rest; a market residual is discarded.
    if event["type"] == "LIMIT" and unfilled > 0:
        assert result["status"] == "resting"
        b[order_id] = unfilled
        rested = [o for o in after if o["order_id"] == order_id]
        assert rested and rested[0]["arrival_seq"] == event["seq"]
        assert rested[0]["price_ticks"] == limit and rested[0]["side"] == side
    elif event["type"] == "LIMIT":
        assert result["status"] == "filled"
    else:
        expected = "filled" if unfilled == 0 else ("partial" if fills else "unfilled")
        assert result["status"] == expected
    assert b == a, "book after the event does not match fills + residual"
