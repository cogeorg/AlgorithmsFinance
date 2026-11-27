"""Version B groups FIFO orders by price and indexes active identifiers."""

from __future__ import annotations

from bisect import bisect_left, insort
from collections import OrderedDict
from typing import cast

from .interface import BookSnapshot, Event, EventResult
from .models import Fill, RestingOrder, Side
from .validation import EventValidationError, validate_event


PriceLevel = OrderedDict[str, RestingOrder]


class RevisedOrderBook:
    """Indexed active orders with FIFO queues and sorted occupied prices."""

    def __init__(self) -> None:
        self._orders: dict[str, RestingOrder] = {}
        self._levels: dict[Side, dict[int, PriceLevel]] = {
            "BUY": {},
            "SELL": {},
        }
        self._bid_prices: list[int] = []
        self._ask_prices: list[int] = []
        self._last_accepted_seq = 0

    def process_event(self, event: Event) -> EventResult:
        try:
            validate_event(event, self._last_accepted_seq, self._orders.keys())
        except EventValidationError as error:
            result: EventResult = {
                "status": "rejected",
                "reason": str(error),
            }
            if "event_id" in event:
                result["event_id"] = event["event_id"]
            return result

        event_type = cast(str, event["type"])
        if event_type == "LIMIT":
            result = self.add_limit_order(event)
        elif event_type == "MARKET_SELL":
            result = self.fill_market_sell(event)
        else:
            result = self.cancel_order(event)
        self._last_accepted_seq = cast(int, event["seq"])
        return result

    def add_limit_order(self, event: Event) -> EventResult:
        order_id = cast(str, event["order_id"])
        side = cast(Side, event["side"])
        price_ticks = cast(int, event["price_ticks"])
        remaining = cast(int, event["qty_units"])
        fills: list[Fill] = []

        opposite: Side = "SELL" if side == "BUY" else "BUY"
        while remaining > 0 and self._crosses(side, price_ticks):
            maker_price = self._best_price(opposite)
            level = self._levels[opposite][maker_price]
            maker = next(iter(level.values()))
            executed = min(remaining, maker.qty_units)
            fills.append(Fill(maker.order_id, order_id, maker.price_ticks, executed))
            maker.qty_units -= executed
            remaining -= executed
            if maker.qty_units == 0:
                level.popitem(last=False)
                del self._orders[maker.order_id]
                if not level:
                    self._remove_level(opposite, maker_price)

        if remaining > 0:
            self._rest_order(
                RestingOrder(
                    order_id,
                    side,
                    price_ticks,
                    remaining,
                    cast(int, event["seq"]),
                )
            )

        return {
            "event_id": event["event_id"],
            "order_id": order_id,
            "status": "filled" if remaining == 0 else "resting",
            "unfilled_qty_units": remaining,
            "fills": [self._fill_dict(fill) for fill in fills],
        }

    def cancel_order(self, event: Event) -> EventResult:
        target = cast(str, event["target_order_id"])
        order = self._orders.pop(target, None)
        if order is None:
            return {
                "event_id": event["event_id"],
                "target_order_id": target,
                "status": "not_found",
                "cancelled_qty_units": 0,
            }

        level = self._levels[order.side][order.price_ticks]
        del level[target]
        if not level:
            self._remove_level(order.side, order.price_ticks)
        return {
            "event_id": event["event_id"],
            "target_order_id": target,
            "status": "cancelled",
            "cancelled_qty_units": order.qty_units,
        }

    def fill_market_sell(self, event: Event) -> EventResult:
        order_id = cast(str, event["order_id"])
        requested = cast(int, event["qty_units"])
        remaining = requested
        fills: list[Fill] = []

        while remaining > 0 and self._bid_prices:
            maker_price = self._best_price("BUY")
            level = self._levels["BUY"][maker_price]
            maker = next(iter(level.values()))
            executed = min(remaining, maker.qty_units)
            fills.append(Fill(maker.order_id, order_id, maker.price_ticks, executed))
            maker.qty_units -= executed
            remaining -= executed
            if maker.qty_units == 0:
                level.popitem(last=False)
                del self._orders[maker.order_id]
                if not level:
                    self._remove_level("BUY", maker_price)

        if remaining == 0:
            status = "filled"
        elif remaining == requested:
            status = "unfilled"
        else:
            status = "partial"
        return {
            "event_id": event["event_id"],
            "order_id": order_id,
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": [self._fill_dict(fill) for fill in fills],
        }

    def inspect_book(self) -> BookSnapshot:
        ordered: list[RestingOrder] = []
        for price in reversed(self._bid_prices):
            ordered.extend(self._levels["BUY"][price].values())
        for price in self._ask_prices:
            ordered.extend(self._levels["SELL"][price].values())
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

    def _rest_order(self, order: RestingOrder) -> None:
        levels = self._levels[order.side]
        if order.price_ticks not in levels:
            levels[order.price_ticks] = OrderedDict()
            insort(self._prices(order.side), order.price_ticks)
        levels[order.price_ticks][order.order_id] = order
        self._orders[order.order_id] = order

    def _crosses(self, incoming_side: Side, limit_price: int) -> bool:
        if incoming_side == "BUY":
            return bool(self._ask_prices and limit_price >= self._ask_prices[0])
        return bool(self._bid_prices and limit_price <= self._bid_prices[-1])

    def _best_price(self, side: Side) -> int:
        prices = self._prices(side)
        return prices[-1] if side == "BUY" else prices[0]

    def _remove_level(self, side: Side, price: int) -> None:
        del self._levels[side][price]
        prices = self._prices(side)
        index = bisect_left(prices, price)
        if index >= len(prices) or prices[index] != price:
            raise RuntimeError("occupied-price index is inconsistent")
        prices.pop(index)

    def _prices(self, side: Side) -> list[int]:
        return self._bid_prices if side == "BUY" else self._ask_prices

    @staticmethod
    def _fill_dict(fill: Fill) -> dict[str, object]:
        return {
            "maker_id": fill.maker_id,
            "taker_id": fill.taker_id,
            "price_ticks": fill.price_ticks,
            "qty_units": fill.qty_units,
        }
