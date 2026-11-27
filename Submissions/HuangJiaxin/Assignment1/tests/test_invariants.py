"""Conservation and price-time invariants after EVERY event, checked from the outside
(snapshots before and after each event), independently of the implementation."""
import pytest

from random_streams import random_stream


def _orders(snap):
    return {o["order_id"]: o for o in snap["bids"] + snap["asks"]}


def check_book_invariants(snap):
    bids, asks = snap["bids"], snap["asks"]
    all_orders = bids + asks
    ids = [o["order_id"] for o in all_orders]
    assert len(ids) == len(set(ids)), "an order is stored twice"
    assert all(o["qty_units"] > 0 for o in all_orders), "nonpositive resting quantity"
    assert all(o["side"] == "BUY" for o in bids) and all(o["side"] == "SELL" for o in asks)
    assert bids == sorted(bids, key=lambda o: (-o["price_ticks"], o["arrival_seq"]))
    assert asks == sorted(asks, key=lambda o: (o["price_ticks"], o["arrival_seq"]))
    if bids and asks:
        assert bids[0]["price_ticks"] < asks[0]["price_ticks"], "crossed book"


def check_event(event, result, before, after):
    b, a = _orders(before), _orders(after)
    status = result["status"]
    if status == "rejected":
        assert before == after
        return
    if event["type"] == "CANCEL":
        t = event["target_order_id"]
        if status == "cancelled":
            assert result["cancelled_qty_units"] == b[t]["qty_units"]      # exactly the residual
            assert t not in a
            assert {k: v for k, v in b.items() if k != t} == a
        else:
            assert status == "not_found" and result["cancelled_qty_units"] == 0
            assert t not in b and before == after
        return

    fills = result["fills"]
    q = event["qty_units"]
    filled = sum(f["qty_units"] for f in fills)
    assert filled + result["unfilled_qty_units"] == q                    # incoming conservation
    assert all(f["qty_units"] > 0 and f["taker_id"] == event["order_id"] for f in fills)

    # every maker loses exactly its fills, at its own (resting) price
    per_maker = {}
    for f in fills:
        m = b[f["maker_id"]]
        assert f["price_ticks"] == m["price_ticks"]
        per_maker[f["maker_id"]] = per_maker.get(f["maker_id"], 0) + f["qty_units"]
    for mid, qty in per_maker.items():
        left = a[mid]["qty_units"] if mid in a else 0
        assert b[mid]["qty_units"] - qty == left
        if mid in a:
            assert a[mid]["arrival_seq"] == b[mid]["arrival_seq"]        # priority kept
    for oid, o in b.items():
        if oid not in per_maker:
            assert a.get(oid) == o                                      # untouched orders

    # fills follow price-time priority of the opposite side
    opposite = before["bids"] if event.get("side", "SELL") == "SELL" else before["asks"]
    expected_makers = [o["order_id"] for o in opposite][:len(per_maker)]
    assert list(dict.fromkeys(f["maker_id"] for f in fills)) == expected_makers

    if event["type"] == "MARKET_SELL":
        assert event["order_id"] not in a                              # never rests
        want = "filled" if result["unfilled_qty_units"] == 0 else ("unfilled" if not fills else "partial")
        assert status == want
        if result["unfilled_qty_units"] > 0:
            assert after["bids"] == []                                  # only stops when bids run out
    else:
        rest = result["unfilled_qty_units"]
        assert status == ("resting" if rest else "filled")
        if rest:
            o = a[event["order_id"]]
            assert (o["qty_units"], o["price_ticks"], o["arrival_seq"]) == \
                (rest, event["price_ticks"], event["seq"])
        else:
            assert event["order_id"] not in a


@pytest.mark.parametrize("seed", range(20))
def test_invariants_on_random_streams(book, seed):
    before = book.snapshot()
    check_book_invariants(before)
    for event in random_stream(seed):
        result = book.process(event)
        after = book.snapshot()
        check_book_invariants(after)
        check_event(event, result, before, after)
        before = after

