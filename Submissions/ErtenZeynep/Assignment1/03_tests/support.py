"""Implementation-independent events, oracles, and transition verification."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from orderbook import BaselineOrderBook, OptimizedOrderBook
from orderbook.contracts import FILL_FIELDS, SNAPSHOT_FIELDS


ENGINE_CLASSES = (BaselineOrderBook, OptimizedOrderBook)


def limit(seq: int, event_id: str, order_id: str, side: str, price: int, qty: int) -> dict[str, Any]:
    return {
        "seq": seq,
        "event_id": event_id,
        "type": "LIMIT",
        "order_id": order_id,
        "side": side,
        "price_ticks": price,
        "qty_units": qty,
    }


def market_sell(seq: int, event_id: str, order_id: str, qty: int) -> dict[str, Any]:
    return {
        "seq": seq,
        "event_id": event_id,
        "type": "MARKET_SELL",
        "order_id": order_id,
        "qty_units": qty,
    }


def cancel(seq: int, event_id: str, target_order_id: str) -> dict[str, Any]:
    return {
        "seq": seq,
        "event_id": event_id,
        "type": "CANCEL",
        "target_order_id": target_order_id,
    }


def fill(maker: str, taker: str, price: int, qty: int) -> dict[str, Any]:
    return {
        "maker_id": maker,
        "taker_id": taker,
        "price_ticks": price,
        "qty_units": qty,
    }


def order(order_id: str, side: str, price: int, qty: int, arrival_seq: int) -> dict[str, Any]:
    return {
        "order_id": order_id,
        "side": side,
        "price_ticks": price,
        "qty_units": qty,
        "arrival_seq": arrival_seq,
    }


def submission_result(
    event_id: str,
    order_id: str,
    status: str,
    unfilled: int,
    fills: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "order_id": order_id,
        "fills": list(fills),
        "status": status,
        "unfilled_qty_units": unfilled,
    }


def _validate_snapshot(snapshot: list[dict[str, Any]]) -> None:
    assert type(snapshot) is list, "canonical snapshot must be a list"
    identifiers: set[str] = set()
    for entry in snapshot:
        assert type(entry) is dict
        assert set(entry) == SNAPSHOT_FIELDS
        assert type(entry["order_id"]) is str and entry["order_id"]
        assert entry["order_id"] not in identifiers, "duplicate active order"
        identifiers.add(entry["order_id"])
        assert entry["side"] in {"BUY", "SELL"}
        for field in ("price_ticks", "qty_units", "arrival_seq"):
            assert type(entry[field]) is int and entry[field] > 0

    expected = sorted(
        snapshot,
        key=lambda item: (
            0 if item["side"] == "BUY" else 1,
            -item["price_ticks"] if item["side"] == "BUY" else item["price_ticks"],
            item["arrival_seq"],
        ),
    )
    assert snapshot == expected, "snapshot is not in canonical price-time order"
    bids = [entry["price_ticks"] for entry in snapshot if entry["side"] == "BUY"]
    asks = [entry["price_ticks"] for entry in snapshot if entry["side"] == "SELL"]
    if bids and asks:
        assert max(bids) < min(asks), "resting book is crossed"


def _assert_sequence(event: dict[str, Any], before_seq: int | None, after_seq: int | None) -> None:
    assert type(event["seq"]) is int and event["seq"] > 0
    assert after_seq == event["seq"]
    if before_seq is not None:
        assert event["seq"] > before_seq


def verify_transition(
    before_snapshot: list[dict[str, Any]],
    event: dict[str, Any],
    result: dict[str, Any],
    after_snapshot: list[dict[str, Any]],
    before_last_seq: int | None,
    after_last_seq: int | None,
) -> None:
    """Reconcile one observed transition without inspecting engine internals."""

    _validate_snapshot(before_snapshot)
    _validate_snapshot(after_snapshot)
    assert type(result) is dict and type(result.get("status")) is str

    if result["status"] == "rejected":
        assert before_snapshot == after_snapshot
        assert before_last_seq == after_last_seq
        assert type(result.get("reason")) is str and result["reason"]
        return

    _assert_sequence(event, before_last_seq, after_last_seq)
    before_by_id = {entry["order_id"]: entry for entry in before_snapshot}
    after_by_id = {entry["order_id"]: entry for entry in after_snapshot}

    if event["type"] == "CANCEL":
        target = event["target_order_id"]
        assert result["event_id"] == event["event_id"]
        assert result["target_order_id"] == target
        if result["status"] == "not_found":
            assert result["cancelled_qty_units"] == 0
            assert target not in before_by_id
            assert before_snapshot == after_snapshot
            return
        assert result["status"] == "cancelled"
        assert target in before_by_id
        assert result["cancelled_qty_units"] == before_by_id[target]["qty_units"]
        expected = {key: value for key, value in before_by_id.items() if key != target}
        assert after_by_id == expected
        return

    assert event["type"] in {"LIMIT", "MARKET_SELL"}
    assert result["event_id"] == event["event_id"]
    assert result["order_id"] == event["order_id"]
    fills = result["fills"]
    assert type(fills) is list
    incoming_side = event.get("side", "SELL")
    maker_side = "SELL" if incoming_side == "BUY" else "BUY"
    eligible = [entry for entry in before_snapshot if entry["side"] == maker_side]
    if event["type"] == "LIMIT":
        if incoming_side == "BUY":
            eligible = [entry for entry in eligible if entry["price_ticks"] <= event["price_ticks"]]
        else:
            eligible = [entry for entry in eligible if entry["price_ticks"] >= event["price_ticks"]]

    remaining = {entry["order_id"]: entry["qty_units"] for entry in before_snapshot}
    filled_by_maker: dict[str, int] = defaultdict(int)
    cursor = 0
    total_filled = 0
    for execution in fills:
        assert type(execution) is dict and set(execution) == FILL_FIELDS
        assert type(execution["qty_units"]) is int and execution["qty_units"] > 0
        while cursor < len(eligible) and remaining[eligible[cursor]["order_id"]] == 0:
            cursor += 1
        assert cursor < len(eligible), "fill has no eligible maker"
        maker = eligible[cursor]
        assert execution["maker_id"] == maker["order_id"]
        assert execution["taker_id"] == event["order_id"]
        assert execution["price_ticks"] == maker["price_ticks"]
        assert execution["qty_units"] <= remaining[maker["order_id"]]
        remaining[maker["order_id"]] -= execution["qty_units"]
        filled_by_maker[maker["order_id"]] += execution["qty_units"]
        total_filled += execution["qty_units"]

    assert total_filled <= event["qty_units"]
    residual = event["qty_units"] - total_filled
    assert result["unfilled_qty_units"] == residual
    expected_after = {key: dict(value) for key, value in before_by_id.items()}
    for maker_id, executed in filled_by_maker.items():
        expected_after[maker_id]["qty_units"] -= executed
        if expected_after[maker_id]["qty_units"] == 0:
            del expected_after[maker_id]

    if event["type"] == "MARKET_SELL":
        expected_status = "filled" if residual == 0 else ("partial" if total_filled else "unfilled")
        assert result["status"] == expected_status
        assert event["order_id"] not in after_by_id, "market residual rested"
        if residual > 0:
            assert not any(remaining[entry["order_id"]] > 0 for entry in eligible)
    else:
        expected_status = "filled" if residual == 0 else "resting"
        assert result["status"] == expected_status
        if residual:
            assert event["order_id"] not in expected_after
            expected_after[event["order_id"]] = order(
                event["order_id"], event["side"], event["price_ticks"], residual, event["seq"]
            )

    assert after_by_id == expected_after, "snapshot delta does not reconcile with fills/residual"


def run_expected_sequence(
    engine: Any,
    events: list[dict[str, Any]],
    expected_results: list[dict[str, Any]],
    expected_snapshots: list[list[dict[str, Any]]],
    expected_sequences: list[int],
) -> None:
    verify_expected_sequence(events, expected_results, expected_snapshots, expected_sequences)
    for event, expected_result, expected_snapshot, expected_seq in zip(
        events, expected_results, expected_snapshots, expected_sequences, strict=True
    ):
        before = engine.canonical_snapshot()
        before_seq = engine.last_accepted_seq
        actual = engine.process_event(event)
        after = engine.canonical_snapshot()
        assert actual == expected_result
        assert after == expected_snapshot
        assert engine.last_accepted_seq == expected_seq
        verify_transition(before, event, actual, after, before_seq, engine.last_accepted_seq)


def verify_expected_sequence(
    events: list[dict[str, Any]],
    expected_results: list[dict[str, Any]],
    expected_snapshots: list[list[dict[str, Any]]],
    expected_sequences: list[int],
) -> None:
    """Validate hand-calculated transitions before consulting either engine."""

    before_snapshot: list[dict[str, Any]] = []
    before_seq: int | None = None
    for event, result, after_snapshot, after_seq in zip(
        events, expected_results, expected_snapshots, expected_sequences, strict=True
    ):
        verify_transition(before_snapshot, event, result, after_snapshot, before_seq, after_seq)
        before_snapshot = after_snapshot
        before_seq = after_seq

