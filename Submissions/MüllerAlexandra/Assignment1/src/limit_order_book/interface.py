"""Shared public contract implemented by both order-book versions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, TypeAlias


Event: TypeAlias = Mapping[str, object]
EventResult: TypeAlias = dict[str, object]
BookSnapshot: TypeAlias = list[dict[str, object]]


class OrderBook(Protocol):
    """Structural interface used by tests, replay, and measurements."""

    def process_event(self, event: Event) -> EventResult:
        """Validate and process one event atomically."""

    def add_limit_order(self, event: Event) -> EventResult:
        """Process one validated limit-order submission."""

    def cancel_order(self, event: Event) -> EventResult:
        """Process one validated cancellation."""

    def fill_market_sell(self, event: Event) -> EventResult:
        """Process one validated market sell against live bids."""

    def inspect_book(self) -> BookSnapshot:
        """Return the canonical list of active individual orders."""

