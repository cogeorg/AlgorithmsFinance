"""Deterministic small streams compare each engine with an independent oracle."""

import random

import pytest

from conftest import BookFactory
from reference_model import ReferenceBook


def generated_events(seed: int, count: int = 60) -> list[dict[str, object]]:
    """Generate a small valid mix without consulting either implementation."""

    rng = random.Random(seed)
    events: list[dict[str, object]] = []
    limit_ids: list[str] = []
    for seq in range(1, count + 1):
        event_id = f"generated-event-{seq}"
        draw = rng.random()
        if seq <= 16 or draw < 0.55:
            side = rng.choice(["BUY", "SELL"])
            if seq <= 16:
                price = rng.randint(95, 99) if side == "BUY" else rng.randint(101, 105)
            else:
                price = rng.randint(94, 106)
            order_id = f"limit-{seq}"
            limit_ids.append(order_id)
            events.append(
                {
                    "seq": seq,
                    "event_id": event_id,
                    "type": "LIMIT",
                    "order_id": order_id,
                    "side": side,
                    "price_ticks": price,
                    "qty_units": rng.randint(1, 6),
                }
            )
        elif draw < 0.80:
            events.append(
                {
                    "seq": seq,
                    "event_id": event_id,
                    "type": "MARKET_SELL",
                    "order_id": f"market-{seq}",
                    "qty_units": rng.randint(1, 10),
                }
            )
        else:
            target = rng.choice(limit_ids) if rng.random() < 0.8 else f"unknown-{seq}"
            events.append(
                {
                    "seq": seq,
                    "event_id": event_id,
                    "type": "CANCEL",
                    "target_order_id": target,
                }
            )
    return events


def assert_visible_invariants(snapshot: list[dict[str, object]]) -> None:
    identifiers = [order["order_id"] for order in snapshot]
    assert len(identifiers) == len(set(identifiers))
    assert all(order["qty_units"] > 0 for order in snapshot)
    bids = [order["price_ticks"] for order in snapshot if order["side"] == "BUY"]
    asks = [order["price_ticks"] for order in snapshot if order["side"] == "SELL"]
    assert not bids or not asks or max(bids) < min(asks)


@pytest.mark.parametrize("seed", [3, 17, 42, 99])
def test_small_generated_stream_matches_independent_oracle_after_every_event(
    book_factory: BookFactory, seed: int
) -> None:
    book = book_factory()
    oracle = ReferenceBook()

    for event in generated_events(seed):
        expected_result = oracle.process_event(event)
        actual_result = book.process_event(event)
        assert actual_result == expected_result
        assert book.inspect_book() == oracle.inspect_book()
        assert_visible_invariants(book.inspect_book())
