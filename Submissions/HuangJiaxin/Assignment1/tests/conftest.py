"""Shared test helpers. Every test runs against BOTH versions (A and B).

Expected results in the tests are calculated by hand from the matching rules, not taken
from either implementation.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lob.book_a import OrderBookA  # noqa: E402
from lob.book_b import OrderBookB  # noqa: E402

BTC = 100_000_000          # quantity units per BTC
VERSIONS = [OrderBookA, OrderBookB]


def usd(dollars):
    """Price in ticks (cents) for a price in dollars."""
    return int(round(dollars * 100))


class Stream:
    """Builds events with strictly increasing seq numbers."""

    def __init__(self):
        self.seq = 0

    def _next(self):
        self.seq += 1
        return self.seq

    def limit(self, oid, side, dollars, btc):
        s = self._next()
        return {"seq": s, "event_id": f"ev{s}", "type": "LIMIT", "order_id": oid,
                "side": side, "price_ticks": usd(dollars), "qty_units": int(round(btc * BTC))}

    def buy(self, oid, dollars, btc):
        return self.limit(oid, "BUY", dollars, btc)

    def sell(self, oid, dollars, btc):
        return self.limit(oid, "SELL", dollars, btc)

    def market_sell(self, oid, btc=None, units=None):
        s = self._next()
        q = units if units is not None else int(round(btc * BTC))
        return {"seq": s, "event_id": f"ev{s}", "type": "MARKET_SELL", "order_id": oid,
                "qty_units": q}

    def cancel(self, target):
        s = self._next()
        return {"seq": s, "event_id": f"ev{s}", "type": "CANCEL", "target_order_id": target}


def fill(maker, taker, dollars, btc):
    return {"maker_id": maker, "taker_id": taker, "price_ticks": usd(dollars),
            "qty_units": int(round(btc * BTC))}


def order(oid, side, dollars, btc, arrival):
    return {"order_id": oid, "side": side, "price_ticks": usd(dollars),
            "qty_units": int(round(btc * BTC)), "arrival_seq": arrival}


def run(book, events):
    """Process events in order; return the list of results."""
    return [book.process(e) for e in events]


@pytest.fixture(params=VERSIONS, ids=lambda cls: f"version_{cls.name}")
def book(request):
    """A fresh, empty book of each version."""
    return request.param()


@pytest.fixture
def stream():
    return Stream()
