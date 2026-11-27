"""Shared test helpers; this file contains no matching implementation."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
import unittest


IMPORT_ERRORS: dict[str, str] = {}
IMPLEMENTATION_CLASSES: dict[str, type[Any]] = {}

try:
    from orderbook.baseline import BaselineOrderBook
except Exception as error:  # The tests-first baseline intentionally reaches here.
    IMPORT_ERRORS["baseline"] = f"{type(error).__name__}: {error}"
else:
    IMPLEMENTATION_CLASSES["baseline"] = BaselineOrderBook

try:
    from orderbook.revised import RevisedOrderBook
except Exception as error:  # The tests-first baseline intentionally reaches here.
    IMPORT_ERRORS["revised"] = f"{type(error).__name__}: {error}"
else:
    IMPLEMENTATION_CLASSES["revised"] = RevisedOrderBook


def require_implementations(test_case: unittest.TestCase) -> dict[str, type[Any]]:
    test_case.assertEqual(
        IMPORT_ERRORS,
        {},
        "required implementations are missing or failed to import: "
        f"{IMPORT_ERRORS}",
    )
    test_case.assertEqual(set(IMPLEMENTATION_CLASSES), {"baseline", "revised"})
    return IMPLEMENTATION_CLASSES


def limit(
    seq: int,
    order_id: str,
    side: str,
    price_ticks: int,
    qty_units: int,
    *,
    event_id: str | None = None,
) -> dict[str, object]:
    return {
        "seq": seq,
        "event_id": event_id or f"event{seq}",
        "type": "LIMIT",
        "order_id": order_id,
        "side": side,
        "price_ticks": price_ticks,
        "qty_units": qty_units,
    }


def market_sell(
    seq: int,
    order_id: str,
    qty_units: int,
    *,
    event_id: str | None = None,
) -> dict[str, object]:
    return {
        "seq": seq,
        "event_id": event_id or f"event{seq}",
        "type": "MARKET_SELL",
        "order_id": order_id,
        "qty_units": qty_units,
    }


def cancel(
    seq: int,
    target_order_id: str,
    *,
    event_id: str | None = None,
) -> dict[str, object]:
    return {
        "seq": seq,
        "event_id": event_id or f"event{seq}",
        "type": "CANCEL",
        "target_order_id": target_order_id,
    }


def fill(
    maker_id: str,
    taker_id: str,
    price_ticks: int,
    qty_units: int,
) -> dict[str, object]:
    return {
        "maker_id": maker_id,
        "taker_id": taker_id,
        "price_ticks": price_ticks,
        "qty_units": qty_units,
    }


def resting_order(
    order_id: str,
    side: str,
    price_ticks: int,
    qty_units: int,
    arrival_seq: int,
) -> dict[str, object]:
    return {
        "order_id": order_id,
        "side": side,
        "price_ticks": price_ticks,
        "qty_units": qty_units,
        "arrival_seq": arrival_seq,
    }


def process_without_input_mutation(
    test_case: unittest.TestCase,
    book: Any,
    event: object,
) -> dict[str, object]:
    before = deepcopy(event)
    result = book.ProcessEvent(event)
    test_case.assertEqual(event, before)
    test_case.assertIs(type(result), dict)
    return result


def assert_book_invariants(test_case: unittest.TestCase, book: Any) -> None:
    orders = book.InspectBook()
    test_case.assertIs(type(orders), list)
    test_case.assertEqual(len({order["order_id"] for order in orders}), len(orders))
    test_case.assertTrue(all(type(order["qty_units"]) is int for order in orders))
    test_case.assertTrue(all(order["qty_units"] > 0 for order in orders))

    bids = [order for order in orders if order["side"] == "BUY"]
    asks = [order for order in orders if order["side"] == "SELL"]
    test_case.assertEqual(
        bids,
        sorted(bids, key=lambda order: (-order["price_ticks"], order["arrival_seq"])),
    )
    test_case.assertEqual(
        asks,
        sorted(asks, key=lambda order: (order["price_ticks"], order["arrival_seq"])),
    )
    if bids and asks:
        test_case.assertLess(bids[0]["price_ticks"], asks[0]["price_ticks"])
