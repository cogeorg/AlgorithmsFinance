"""Small event constructors used only to make expected-result tests readable."""

from __future__ import annotations


def limit_event(
    seq: int,
    order_id: str,
    side: str,
    price_ticks: object,
    qty_units: object,
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


def market_sell_event(
    seq: int,
    order_id: str,
    qty_units: object,
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


def cancel_event(
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


def resting(
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

