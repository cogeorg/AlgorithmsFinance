"""Canonical state representation shared by tests and both implementations."""

from __future__ import annotations

from collections.abc import Iterable

from .interface import BookSnapshot
from .models import RestingOrder


def canonical_snapshot(orders: Iterable[RestingOrder]) -> BookSnapshot:
    """Return bids then asks in the assignment's canonical order."""

    order_list = list(orders)
    bids = sorted(
        (order for order in order_list if order.side == "BUY"),
        key=lambda order: (-order.price_ticks, order.arrival_seq),
    )
    asks = sorted(
        (order for order in order_list if order.side == "SELL"),
        key=lambda order: (order.price_ticks, order.arrival_seq),
    )
    return [
        {
            "order_id": order.order_id,
            "side": order.side,
            "price_ticks": order.price_ticks,
            "qty_units": order.qty_units,
            "arrival_seq": order.arrival_seq,
        }
        for order in [*bids, *asks]
    ]

