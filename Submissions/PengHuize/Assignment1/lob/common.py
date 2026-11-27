"""Shared contract and matching rules for both order-book implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterable, Mapping


BUY = "BUY"
SELL = "SELL"


@dataclass
class Order:
    order_id: str
    side: str
    price_ticks: int
    qty_units: int
    arrival_seq: int


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


class BaseLimitOrderBook(ABC):
    """Validate events and apply the common continuous-matching contract.

    Subclasses differ only in how active orders are organized and located.
    Instrumentation is disabled by default so operation counters do not affect
    primary timing or memory measurements.
    """

    version = "base"

    def __init__(self, *, instrument: bool = False) -> None:
        self.last_accepted_seq = 0
        self.instrument = instrument
        self.operation_counts: dict[str, int] = {
            "best_order_calls": 0,
            "maker_scans": 0,
            "maker_orders_touched": 0,
            "price_level_visits": 0,
            "fills": 0,
        }
        self.active_order_peak = 0
        self.price_level_peak = 0

    def process_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Validate and dispatch one event; rejected events are atomic."""
        reason = self._validation_error(event)
        if reason is not None:
            return self._rejected(event, reason)

        event_type = event["type"]
        if event_type == "LIMIT":
            result = self.AddLimitOrder(event)
        elif event_type == "MARKET_SELL":
            result = self.FillMarketSell(event)
        else:
            result = self.CancelOrder(event)

        self.last_accepted_seq = event["seq"]
        if self.instrument:
            self.active_order_peak = max(
                self.active_order_peak, self.active_order_count()
            )
            self.price_level_peak = max(
                self.price_level_peak, self.price_level_count()
            )
        return result

    def AddLimitOrder(self, event: Mapping[str, Any]) -> dict[str, Any]:
        incoming = Order(
            order_id=event["order_id"],
            side=event["side"],
            price_ticks=event["price_ticks"],
            qty_units=event["qty_units"],
            arrival_seq=event["seq"],
        )
        fills = self._match_limit(incoming)
        residual = incoming.qty_units
        if residual:
            self._rest(incoming)
        return {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "status": "filled" if residual == 0 else "resting",
            "unfilled_qty_units": residual,
            "fills": fills,
        }

    def FillMarketSell(self, event: Mapping[str, Any]) -> dict[str, Any]:
        remaining = event["qty_units"]
        fills: list[dict[str, Any]] = []
        previous_price: int | None = None
        while remaining:
            maker = self._best_order(BUY)
            if maker is None:
                break
            previous_price = self._record_match_work(maker, previous_price)
            traded = min(remaining, maker.qty_units)
            fills.append(self._fill_record(maker, event["order_id"], traded))
            remaining -= traded
            maker.qty_units -= traded
            if maker.qty_units == 0:
                self._remove(maker)

        if remaining == 0:
            status = "filled"
        elif fills:
            status = "partial"
        else:
            status = "unfilled"
        return {
            "event_id": event["event_id"],
            "order_id": event["order_id"],
            "status": status,
            "unfilled_qty_units": remaining,
            "fills": fills,
        }

    def CancelOrder(self, event: Mapping[str, Any]) -> dict[str, Any]:
        cancelled = self._cancel(event["target_order_id"])
        return {
            "event_id": event["event_id"],
            "target_order_id": event["target_order_id"],
            "status": "cancelled" if cancelled else "not_found",
            "cancelled_qty_units": cancelled,
        }

    def _match_limit(self, incoming: Order) -> list[dict[str, Any]]:
        resting_side = SELL if incoming.side == BUY else BUY
        fills: list[dict[str, Any]] = []
        previous_price: int | None = None
        while incoming.qty_units:
            maker = self._best_order(resting_side)
            if maker is None or not self._crosses(incoming, maker):
                break
            previous_price = self._record_match_work(maker, previous_price)
            traded = min(incoming.qty_units, maker.qty_units)
            fills.append(self._fill_record(maker, incoming.order_id, traded))
            incoming.qty_units -= traded
            maker.qty_units -= traded
            if maker.qty_units == 0:
                self._remove(maker)
        return fills

    @staticmethod
    def _crosses(incoming: Order, maker: Order) -> bool:
        if incoming.side == BUY:
            return incoming.price_ticks >= maker.price_ticks
        return incoming.price_ticks <= maker.price_ticks

    def _record_match_work(self, maker: Order, previous_price: int | None) -> int:
        if self.instrument:
            self.operation_counts["maker_orders_touched"] += 1
            self.operation_counts["fills"] += 1
            if maker.price_ticks != previous_price:
                self.operation_counts["price_level_visits"] += 1
        return maker.price_ticks

    @staticmethod
    def _fill_record(maker: Order, taker_id: str, quantity: int) -> dict[str, Any]:
        return {
            "maker_id": maker.order_id,
            "taker_id": taker_id,
            "price_ticks": maker.price_ticks,
            "qty_units": quantity,
        }

    def inspect_book(self) -> list[dict[str, Any]]:
        """Return the canonical active book: bids then asks, each price-time sorted."""
        orders = list(self._iter_active_orders())
        bids = sorted(
            (order for order in orders if order.side == BUY),
            key=lambda order: (-order.price_ticks, order.arrival_seq),
        )
        asks = sorted(
            (order for order in orders if order.side == SELL),
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
            for order in (*bids, *asks)
        ]

    def validate_invariants(self) -> None:
        orders = self.inspect_book()
        identifiers = [row["order_id"] for row in orders]
        if len(identifiers) != len(set(identifiers)):
            raise AssertionError("an active order is stored more than once")
        if any(row["qty_units"] <= 0 for row in orders):
            raise AssertionError("nonpositive resting quantity")
        bids = [row["price_ticks"] for row in orders if row["side"] == BUY]
        asks = [row["price_ticks"] for row in orders if row["side"] == SELL]
        if bids and asks and max(bids) >= min(asks):
            raise AssertionError("crossed resting book")

    def metrics(self) -> dict[str, Any]:
        return {
            "active_orders": self.active_order_count(),
            "price_levels": self.price_level_count(),
            "active_order_peak": self.active_order_peak,
            "price_level_peak": self.price_level_peak,
            **self.operation_counts,
        }

    def _validation_error(self, event: Mapping[str, Any]) -> str | None:
        if not isinstance(event, Mapping):
            return "event must be a mapping"
        seq = event.get("seq")
        if not _positive_int(seq):
            return "seq must be a positive integer"
        if seq <= self.last_accepted_seq:
            return "seq must be strictly increasing"
        if not isinstance(event.get("event_id"), str) or not event["event_id"]:
            return "event_id must be a nonempty string"
        event_type = event.get("type")
        if event_type not in {"LIMIT", "MARKET_SELL", "CANCEL"}:
            return "unknown event type"

        if event_type == "CANCEL":
            target = event.get("target_order_id")
            if not isinstance(target, str) or not target:
                return "target_order_id must be a nonempty string"
            return None

        order_id = event.get("order_id")
        if not isinstance(order_id, str) or not order_id:
            return "order_id must be a nonempty string"
        if self._is_live(order_id):
            return "duplicate live order_id"
        if not _positive_int(event.get("qty_units")):
            return "qty_units must be a positive integer"
        if event_type == "MARKET_SELL":
            return None
        if event.get("side") not in {BUY, SELL}:
            return "side must be BUY or SELL"
        if not _positive_int(event.get("price_ticks")):
            return "price_ticks must be a positive integer"
        return None

    @staticmethod
    def _rejected(event: Mapping[str, Any], reason: str) -> dict[str, Any]:
        result: dict[str, Any] = {"status": "rejected", "reason": reason}
        if isinstance(event, Mapping) and "event_id" in event:
            result["event_id"] = event["event_id"]
        return result

    @abstractmethod
    def _best_order(self, side: str) -> Order | None:
        raise NotImplementedError

    @abstractmethod
    def _rest(self, order: Order) -> None:
        raise NotImplementedError

    @abstractmethod
    def _remove(self, order: Order) -> None:
        raise NotImplementedError

    @abstractmethod
    def _cancel(self, order_id: str) -> int:
        raise NotImplementedError

    @abstractmethod
    def _is_live(self, order_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def _iter_active_orders(self) -> Iterable[Order]:
        raise NotImplementedError

    @abstractmethod
    def active_order_count(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def price_level_count(self) -> int:
        raise NotImplementedError


def gross_proceeds_tick_units(fills: Iterable[Mapping[str, int]]) -> int:
    return sum(fill["price_ticks"] * fill["qty_units"] for fill in fills)
