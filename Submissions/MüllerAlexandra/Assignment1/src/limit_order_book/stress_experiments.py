"""Deterministic liquidation and correctness-diagnostic experiments."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from math import ceil
from statistics import median
from time import perf_counter
import tracemalloc
from typing import Any

from .interface import Event, OrderBook


BookFactory = Callable[[], OrderBook]
Clock = Callable[[], float]


def build_liquidation_events(
    *,
    order_count: int,
    price_levels: int,
    base_price_ticks: int = 6_000_000,
    quantity_cycle: Sequence[int] = (1_000_000, 2_000_000, 3_000_000),
) -> tuple[Event, ...]:
    """Build an identical deterministic bid book for every liquidation run."""

    if isinstance(order_count, bool) or not isinstance(order_count, int) or order_count <= 0:
        raise ValueError("order_count must be a positive integer")
    if isinstance(price_levels, bool) or not isinstance(price_levels, int) or price_levels <= 0:
        raise ValueError("price_levels must be a positive integer")
    if price_levels > order_count:
        raise ValueError("price_levels must not exceed order_count")
    if (
        isinstance(base_price_ticks, bool)
        or not isinstance(base_price_ticks, int)
        or base_price_ticks < price_levels
    ):
        raise ValueError("base_price_ticks must be a sufficiently large integer")
    if not quantity_cycle or any(
        isinstance(quantity, bool)
        or not isinstance(quantity, int)
        or quantity <= 0
        for quantity in quantity_cycle
    ):
        raise ValueError("quantity_cycle must contain positive integers")

    return tuple(
        {
            "seq": index + 1,
            "event_id": f"liquidation-build-{index + 1}",
            "type": "LIMIT",
            "order_id": f"maker-{index + 1:06d}",
            "side": "BUY",
            "price_ticks": base_price_ticks - index % price_levels,
            "qty_units": quantity_cycle[index % len(quantity_cycle)],
        }
        for index in range(order_count)
    )


def liquidation_quantities(available_qty_units: int) -> dict[str, int]:
    if (
        isinstance(available_qty_units, bool)
        or not isinstance(available_qty_units, int)
        or available_qty_units <= 0
    ):
        raise ValueError("available_qty_units must be a positive integer")
    return {
        "10_percent": max(1, ceil(available_qty_units / 10)),
        "100_percent": available_qty_units,
        "200_percent": 2 * available_qty_units,
    }


def _build_book(book_factory: BookFactory, build_events: Sequence[Event]) -> OrderBook:
    book = book_factory()
    for event in build_events:
        result = book.process_event(event)
        if result.get("status") == "rejected":
            raise ValueError(f"build event was rejected: {result}")
    return book


def _sale_event(build_events: Sequence[Event], requested: int) -> Event:
    return {
        "seq": len(build_events) + 1,
        "event_id": "liquidation-sale",
        "type": "MARKET_SELL",
        "order_id": "liquidation-seller",
        "qty_units": requested,
    }


def _sale_metrics(result: dict[str, object], requested: int) -> dict[str, int]:
    fills = result["fills"]
    unfilled = result["unfilled_qty_units"]
    assert isinstance(fills, list)
    assert isinstance(unfilled, int)
    executed = sum(int(fill["qty_units"]) for fill in fills)
    return {
        "requested_qty_units": requested,
        "executed_qty_units": executed,
        "unfilled_qty_units": unfilled,
        "fill_count": len(fills),
        "makers_touched": len({str(fill["maker_id"]) for fill in fills}),
        "price_levels_visited": len({int(fill["price_ticks"]) for fill in fills}),
        "proceeds_tick_qty": sum(
            int(fill["price_ticks"]) * int(fill["qty_units"]) for fill in fills
        ),
    }


def measure_liquidation_scenarios(
    book_factory: BookFactory,
    build_events: Sequence[Event],
    *,
    warmups: int = 1,
    repeats: int = 5,
    clock: Clock = perf_counter,
) -> dict[str, Any]:
    if not build_events:
        raise ValueError("build_events must not be empty")
    if isinstance(warmups, bool) or not isinstance(warmups, int) or warmups < 0:
        raise ValueError("warmups must be a nonnegative integer")
    if isinstance(repeats, bool) or not isinstance(repeats, int) or repeats <= 0:
        raise ValueError("repeats must be a positive integer")
    available = sum(int(event["qty_units"]) for event in build_events)
    quantities = liquidation_quantities(available)
    records: list[dict[str, int | float | str]] = []
    for sale_size, requested in quantities.items():
        for _ in range(warmups):
            warmup_book = _build_book(book_factory, build_events)
            warmup_book.process_event(_sale_event(build_events, requested))
        for repeat in range(1, repeats + 1):
            construction_started = clock()
            book = _build_book(book_factory, build_events)
            construction_seconds = clock() - construction_started
            sale_started = clock()
            result = book.process_event(_sale_event(build_events, requested))
            sale_seconds = clock() - sale_started
            if construction_seconds < 0 or sale_seconds < 0:
                raise ValueError("clock produced negative elapsed time")
            metrics = _sale_metrics(result, requested)
            if metrics["executed_qty_units"] + metrics["unfilled_qty_units"] != requested:
                raise ValueError("liquidation quantity was not conserved")
            records.append(
                {
                    "sale_size": sale_size,
                    "repeat": repeat,
                    "construction_seconds": construction_seconds,
                    "sale_seconds": sale_seconds,
                    **metrics,
                }
            )
    summaries = {
        sale_size: {
            "repeat_count": repeats,
            "median_construction_seconds": median(
                float(record["construction_seconds"])
                for record in records
                if record["sale_size"] == sale_size
            ),
            "median_sale_seconds": median(
                float(record["sale_seconds"])
                for record in records
                if record["sale_size"] == sale_size
            ),
        }
        for sale_size in quantities
    }
    return {
        "order_count": len(build_events),
        "available_qty_units": available,
        "quantities": quantities,
        "warmups": warmups,
        "repeats": repeats,
        "records": records,
        "summaries": summaries,
    }


def measure_liquidation_sale_memory(
    book_factory: BookFactory,
    build_events: Sequence[Event],
    *,
    sale_size: str,
) -> dict[str, Any]:
    if not build_events:
        raise ValueError("build_events must not be empty")
    available = sum(int(event["qty_units"]) for event in build_events)
    quantities = liquidation_quantities(available)
    if sale_size not in quantities:
        raise ValueError(f"unknown sale_size: {sale_size}")
    requested = quantities[sale_size]
    book = _build_book(book_factory, build_events)
    tracemalloc.start()
    try:
        result = book.process_event(_sale_event(build_events, requested))
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    metrics = _sale_metrics(result, requested)
    return {
        "sale_size": sale_size,
        "available_qty_units": available,
        **metrics,
        "current_bytes": current_bytes,
        "peak_bytes": peak_bytes,
        "inclusions": {
            "prebuilt_book_allocations": False,
            "sale_matching_temporaries": True,
            "retained_sale_result_and_fills": True,
            "python_tracemalloc_only": True,
        },
    }


def diagnose_replay(
    book_factory: BookFactory, events: Sequence[Event]
) -> dict[str, Any]:
    if not events:
        raise ValueError("events must not be empty")
    book = book_factory()
    event_type_counts: dict[str, int] = {}
    total_fills = 0
    rejected_events = 0
    peak_active_orders = 0
    peak_levels = 0
    for event in events:
        event_type = str(event.get("type"))
        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
        result = book.process_event(event)
        if result.get("status") == "rejected":
            rejected_events += 1
        fills = result.get("fills", [])
        assert isinstance(fills, list)
        total_fills += len(fills)
        snapshot = book.inspect_book()
        peak_active_orders = max(peak_active_orders, len(snapshot))
        peak_levels = max(
            peak_levels,
            len({(order["side"], order["price_ticks"]) for order in snapshot}),
        )

    final_snapshot = book.inspect_book()
    final_levels = {
        (order["side"], order["price_ticks"]) for order in final_snapshot
    }
    order_ids = [order["order_id"] for order in final_snapshot]
    bids = [int(order["price_ticks"]) for order in final_snapshot if order["side"] == "BUY"]
    asks = [int(order["price_ticks"]) for order in final_snapshot if order["side"] == "SELL"]
    return {
        "event_count": len(events),
        "event_type_counts": dict(sorted(event_type_counts.items())),
        "total_fills": total_fills,
        "rejected_events": rejected_events,
        "peak_active_orders": peak_active_orders,
        "peak_occupied_price_levels": peak_levels,
        "final_active_orders": len(final_snapshot),
        "final_occupied_price_levels": len(final_levels),
        "final_unique_order_ids": len(order_ids) == len(set(order_ids)),
        "final_positive_quantities": all(
            int(order["qty_units"]) > 0 for order in final_snapshot
        ),
        "final_uncrossed": not bids or not asks or max(bids) < min(asks),
    }
