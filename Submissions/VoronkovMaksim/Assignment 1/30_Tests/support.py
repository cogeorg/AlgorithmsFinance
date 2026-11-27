"""Shared Phase 1 contract for both future order-book versions."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ("order_book_v1", "order_book_v2")


def load_book(version):
    """Load OrderBook from 20_Code/<version>.py without changing sys.path."""
    path = ROOT / "20_Code" / f"{version}.py"
    if not path.is_file():
        raise AssertionError(f"Phase 2 pending: create {path.name} with an OrderBook class")
    spec = importlib.util.spec_from_file_location(version, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.OrderBook()


def event(seq, kind, **fields):
    return {"seq": seq, "event_id": f"e{seq}", "type": kind, **fields}


def limit(seq, order_id, side, price, quantity):
    return event(seq, "LIMIT", order_id=order_id, side=side,
                 price_ticks=price, qty_units=quantity)


def sell(seq, order_id, quantity):
    return event(seq, "MARKET_SELL", order_id=order_id, qty_units=quantity)


def cancel(seq, target):
    return event(seq, "CANCEL", target_order_id=target)


def order(order_id, side, price, quantity, arrival):
    return {"order_id": order_id, "side": side, "price_ticks": price,
            "qty_units": quantity, "arrival_seq": arrival}


def fill(maker, taker, price, quantity):
    return {"maker_id": maker, "taker_id": taker,
            "price_ticks": price, "qty_units": quantity}


def submission(event_id, order_id, status, residual, fills=()):
    return {"event_id": event_id, "order_id": order_id, "status": status,
            "unfilled_qty_units": residual, "fills": list(fills)}


def cancellation(event_id, target, status, quantity):
    return {"event_id": event_id, "target_order_id": target,
            "status": status, "cancelled_qty_units": quantity}


def assert_step(test, book, incoming, expected_result, expected_book):
    """Check this event's outcome and the entire canonical live book."""
    before = dict(incoming)
    result = book.process_event(incoming)
    test.assertEqual(incoming, before, "processing changed its input event")
    for key, value in expected_result.items():
        test.assertIn(key, result)
        test.assertEqual(result[key], value, key)
    if incoming.get("type") in ("LIMIT", "MARKET_SELL"):
        fills = result["fills"]
        test.assertEqual(incoming["qty_units"],
                         sum(f["qty_units"] for f in fills) + result["unfilled_qty_units"])
        test.assertTrue(all(f["qty_units"] > 0 for f in fills))
    actual = book.inspect_book()
    test.assertEqual(actual, expected_book)
    test.assertEqual(len({o["order_id"] for o in actual}), len(actual))
    test.assertTrue(all(o["qty_units"] > 0 for o in actual))
    bids = [o["price_ticks"] for o in actual if o["side"] == "BUY"]
    asks = [o["price_ticks"] for o in actual if o["side"] == "SELL"]
    if bids and asks:
        test.assertLess(max(bids), min(asks), "resting book is crossed")
    return result


def assert_case(test, steps):
    for version in VERSIONS:
        with test.subTest(version=version):
            book = load_book(version)
            test.assertEqual(book.inspect_book(), [])
            for incoming, expected_result, expected_book in steps:
                with test.subTest(version=version, seq=incoming.get("seq")):
                    assert_step(test, book, incoming, expected_result, expected_book)
