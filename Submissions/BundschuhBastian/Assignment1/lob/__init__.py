"""Limit order book, Assignment 1 (Algorithms in Finance). See SPEC.md."""
from lob.version_a import OrderBookA
from lob.version_b import OrderBookB

VERSIONS = {"A": OrderBookA, "B": OrderBookB}

__all__ = ["OrderBookA", "OrderBookB", "VERSIONS"]
