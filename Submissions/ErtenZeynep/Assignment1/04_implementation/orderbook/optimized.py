"""Independent indexed price-level limit order book."""

from __future__ import annotations

import heapq
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from .contracts import EVENT_CANCEL, EVENT_LIMIT, EVENT_MARKET_SELL
from .validation import rejected_result, validate_event


@dataclass(slots=True)
class _Order:
    order_id: str
    side: str
    price_ticks: int
    qty_units: int
    arrival_seq: int


@dataclass(slots=True)
class _PriceLevel:
    price_ticks: int
    generation: int
    orders: OrderedDict[str, _Order] = field(default_factory=OrderedDict)


_HeapEntry = tuple[int, int, int]


class OptimizedOrderBook:
    """Price-level book with direct ID lookup and FIFO level queues."""

    _COMPACTION_MULTIPLIER = 2
    _COMPACTION_SLACK = 64

    def __init__(self) -> None:
        self._last_accepted_seq: int | None = None
        self._active_by_id: dict[str, _Order] = {}
        self._bid_levels: dict[int, _PriceLevel] = {}
        self._ask_levels: dict[int, _PriceLevel] = {}
        self._bid_heap: list[_HeapEntry] = []
        self._ask_heap: list[_HeapEntry] = []
        self._next_generation = 1

    @property
    def last_accepted_seq(self) -> int | None:
        return self._last_accepted_seq

    def canonical_snapshot(self) -> list[dict[str, Any]]:
        ordered = sorted(
            self._active_by_id.values(),
            key=lambda order: (
                0 if order.side == "BUY" else 1,
                -order.price_ticks if order.side == "BUY" else order.price_ticks,
                order.arrival_seq,
            ),
        )
        return [
            {
                "order_id": order.order_id,
                "side": order.side,
                "price_ticks": order.price_ticks,
                "qty_units": order.qty_units,
                "arrival_seq": order.arrival_seq,
            }
            for order in ordered
        ]

    def process_event(self, event: Any) -> dict[str, Any]:
        return self._process(event, required_type=None)

    def AddLimitOrder(self, event: Any) -> dict[str, Any]:
        return self._process(event, required_type=EVENT_LIMIT)

    def CancelOrder(self, event: Any) -> dict[str, Any]:
        return self._process(event, required_type=EVENT_CANCEL)

    def FillMarketSell(self, event: Any) -> dict[str, Any]:
        return self._process(event, required_type=EVENT_MARKET_SELL)

    def _process(self, event: Any, required_type: str | None) -> dict[str, Any]:
        rejection = validate_event(event)
        if rejection is not None:
            return rejection
        if required_type is not None and event["type"] != required_type:
            return rejected_result(event, "invalid_event_type")
        if self._last_accepted_seq is not None and event["seq"] <= self._last_accepted_seq:
            return rejected_result(event, "nonincreasing_sequence")
        if (
            event["type"] in {EVENT_LIMIT, EVENT_MARKET_SELL}
            and event["order_id"] in self._active_by_id
        ):
            return rejected_result(event, "duplicate_live_order_id")

        if event["type"] == EVENT_LIMIT:
            result = self._apply_limit(event)
        elif event["type"] == EVENT_MARKET_SELL:
            result = self._apply_market_sell(event)
        else:
            result = self._apply_cancel(event)
        self._last_accepted_seq = event["seq"]
        return result

    def _apply_limit(self, event: dict[str, Any]) -> dict[str, Any]:
        fills, residual = self._match(
            taker_id=event["order_id"],
            incoming_side=event["side"],
            incoming_qty=event["qty_units"],
            limit_price=event["price_ticks"],
        )
        if residual:
            self._insert_order(
                _Order(
                    order_id=event["order_id"],
                    side=event["side"],
                    price_ticks=event["price_ticks"],
                    qty_units=residual,
                    arrival_seq=event["seq"],
                )
            )
            status = "resting"
        else:
            status = "filled"
        return {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "fills": fills,
            "status": status,
            "unfilled_qty_units": residual,
        }

    def _apply_market_sell(self, event: dict[str, Any]) -> dict[str, Any]:
        fills, residual = self._match(
            taker_id=event["order_id"],
            incoming_side="SELL",
            incoming_qty=event["qty_units"],
            limit_price=None,
        )
        if residual == 0:
            status = "filled"
        elif fills:
            status = "partial"
        else:
            status = "unfilled"
        return {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "fills": fills,
            "status": status,
            "unfilled_qty_units": residual,
        }

    def _apply_cancel(self, event: dict[str, Any]) -> dict[str, Any]:
        target = event["target_order_id"]
        order = self._active_by_id.get(target)
        if order is None:
            return {
                "event_id": event["event_id"],
                "target_order_id": target,
                "status": "not_found",
                "cancelled_qty_units": 0,
            }

        level = self._levels_for_side(order.side)[order.price_ticks]
        del level.orders[target]
        del self._active_by_id[target]
        self._delete_level_if_empty(order.side, order.price_ticks)
        return {
            "event_id": event["event_id"],
            "target_order_id": target,
            "status": "cancelled",
            "cancelled_qty_units": order.qty_units,
        }

    def _match(
        self,
        taker_id: str,
        incoming_side: str,
        incoming_qty: int,
        limit_price: int | None,
    ) -> tuple[list[dict[str, Any]], int]:
        maker_side = "SELL" if incoming_side == "BUY" else "BUY"
        residual = incoming_qty
        fills: list[dict[str, Any]] = []

        while residual:
            level = self._best_level(maker_side)
            if level is None or not self._crosses(incoming_side, limit_price, level.price_ticks):
                break

            maker_id, maker = next(iter(level.orders.items()))
            executed = min(residual, maker.qty_units)
            fills.append(
                {
                    "maker_id": maker_id,
                    "taker_id": taker_id,
                    "price_ticks": maker.price_ticks,
                    "qty_units": executed,
                }
            )
            maker.qty_units -= executed
            residual -= executed

            if maker.qty_units == 0:
                level.orders.popitem(last=False)
                del self._active_by_id[maker_id]
                self._delete_level_if_empty(maker_side, level.price_ticks)

        return fills, residual

    @staticmethod
    def _crosses(incoming_side: str, limit_price: int | None, maker_price: int) -> bool:
        if limit_price is None:
            return True
        if incoming_side == "BUY":
            return maker_price <= limit_price
        return maker_price >= limit_price

    def _insert_order(self, order: _Order) -> None:
        levels = self._levels_for_side(order.side)
        level = levels.get(order.price_ticks)
        if level is None:
            level = _PriceLevel(order.price_ticks, self._allocate_generation())
            levels[order.price_ticks] = level
            heapq.heappush(self._heap_for_side(order.side), self._entry_for_level(order.side, level))
            self._maybe_compact(order.side)
        level.orders[order.order_id] = order
        self._active_by_id[order.order_id] = order

    def _delete_level_if_empty(self, side: str, price_ticks: int) -> None:
        levels = self._levels_for_side(side)
        level = levels.get(price_ticks)
        if level is not None and not level.orders:
            del levels[price_ticks]
            self._maybe_compact(side)

    def _best_level(self, side: str) -> _PriceLevel | None:
        heap = self._heap_for_side(side)
        self._discard_stale_heap_top(side)
        if not heap:
            return None
        return self._levels_for_side(side)[heap[0][2]]

    def _discard_stale_heap_top(self, side: str) -> None:
        heap = self._heap_for_side(side)
        while heap and not self._is_heap_entry_valid(side, heap[0]):
            heapq.heappop(heap)

    def _is_heap_entry_valid(self, side: str, entry: _HeapEntry) -> bool:
        level = self._levels_for_side(side).get(entry[2])
        return level is not None and level.generation == entry[1]

    def _maybe_compact(self, side: str) -> None:
        heap = self._heap_for_side(side)
        levels = self._levels_for_side(side)
        threshold = self._COMPACTION_MULTIPLIER * len(levels) + self._COMPACTION_SLACK
        if len(heap) > threshold:
            heap[:] = [self._entry_for_level(side, level) for level in levels.values()]
            heapq.heapify(heap)

    def _allocate_generation(self) -> int:
        generation = self._next_generation
        self._next_generation += 1
        return generation

    def _levels_for_side(self, side: str) -> dict[int, _PriceLevel]:
        return self._bid_levels if side == "BUY" else self._ask_levels

    def _heap_for_side(self, side: str) -> list[_HeapEntry]:
        return self._bid_heap if side == "BUY" else self._ask_heap

    @staticmethod
    def _entry_for_level(side: str, level: _PriceLevel) -> _HeapEntry:
        key = -level.price_ticks if side == "BUY" else level.price_ticks
        return (key, level.generation, level.price_ticks)
