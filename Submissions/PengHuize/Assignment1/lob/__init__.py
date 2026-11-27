"""Two equivalent limit-order-book implementations."""

from .baseline import ListOrderBook
from .common import gross_proceeds_tick_units
from .optimized import IndexedOrderBook


def make_book(version: str, *, instrument: bool = False):
    normalized = version.strip().upper()
    if normalized in {"A", "A-LIST", "BASELINE"}:
        return ListOrderBook(instrument=instrument)
    if normalized in {"B", "B-INDEXED", "OPTIMIZED"}:
        return IndexedOrderBook(instrument=instrument)
    raise ValueError(f"unknown implementation version: {version}")


__all__ = [
    "IndexedOrderBook",
    "ListOrderBook",
    "gross_proceeds_tick_units",
    "make_book",
]
