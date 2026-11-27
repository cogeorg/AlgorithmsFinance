"""Phase 4: Version A and Version B must agree after EVERY event.

Small generated streams (tools/gen_small.py) run in lock step. For each event, both books
go through tests/helpers.py::step() (independent invariant checker I1-I7), and then we require
  - identical result dicts (status, reason, ordered fills, quantities),
  - identical canonical snapshots (ids, prices, remaining quantity, arrival seq),
  - identical best_bid() / best_ask().
Neither "A equals B" nor one example replaces the hand-calculated tests; this only finds
differences between the two implementations (shared validation bugs stay invisible here).
"""
from collections import Counter
from pathlib import Path

import pytest

from lob.common import load_events
from lob.version_a import OrderBookA
from lob.version_b import OrderBookB
from tests.helpers import step
from tools.gen_small import PROFILES, generate

SEEDS = range(40)
EVENTS_PER_STREAM = 250
DATA = Path(__file__).resolve().parent.parent / "data"


def run_lockstep(events):
    """Return the list of A's results; fail at the first event where A and B differ."""
    a, b = OrderBookA(), OrderBookB()
    results = []
    for n, event in enumerate(events):
        ra, rb = step(a, event), step(b, event)
        assert ra == rb, f"event #{n} {event!r}: results differ\nA: {ra}\nB: {rb}"
        assert a.snapshot() == b.snapshot(), f"event #{n} {event!r}: books differ"
        assert (a.best_bid(), a.best_ask()) == (b.best_bid(), b.best_ask())
        results.append(ra)
    return results


@pytest.mark.parametrize("profile", sorted(PROFILES))
def test_generated_streams_agree_after_every_event(profile):
    for seed in SEEDS:
        run_lockstep(generate(seed, EVENTS_PER_STREAM, profile))


def test_generator_is_deterministic():
    for profile in PROFILES:
        assert generate(7, 100, profile) == generate(7, 100, profile)
    assert generate(1, 100, "tight") != generate(2, 100, "tight")


def test_generated_streams_exercise_the_hard_cases():
    """Guard against a vacuous comparison: the streams must reach the interesting paths."""
    seen = Counter()
    for profile in PROFILES:
        for seed in SEEDS:
            for r in run_lockstep(generate(seed, EVENTS_PER_STREAM, profile)):
                seen["status:" + r["status"]] += 1
                if r["status"] == "rejected":
                    seen["reason:" + r["reason"]] += 1
                if len(r["fills"]) >= 3:
                    seen["three_or_more_fills"] += 1
                if len({f["price_ticks"] for f in r["fills"]}) >= 2:
                    seen["fills_over_two_price_levels"] += 1
                if len({f["maker_id"] for f in r["fills"] if f["price_ticks"] == (
                        r["fills"][0]["price_ticks"])}) >= 2:
                    seen["two_makers_one_price"] += 1
    for status in ("filled", "resting", "partial", "unfilled", "cancelled", "not_found",
                   "rejected"):
        assert seen["status:" + status] > 20, (status, seen)
    for reason in ("malformed_event", "invalid_seq", "nonincreasing_seq", "invalid_event_id",
                   "unknown_type", "invalid_order_id", "unknown_side", "invalid_price",
                   "invalid_qty", "invalid_target_order_id", "duplicate_live_order_id"):
        assert seen["reason:" + reason] > 0, (reason, seen)
    for key in ("three_or_more_fills", "fills_over_two_price_levels", "two_makers_one_price"):
        assert seen[key] > 20, (key, seen)


SUPPLIED = sorted(DATA.glob("*_10000.jsonl.gz"))


@pytest.mark.parametrize("path", SUPPLIED, ids=[p.name for p in SUPPLIED])
def test_supplied_files_agree(path):
    """10,000 events: results and best prices after every event; full book every 200 events
    (a full snapshot per event would cost O(M*B) for the big books) and at the end."""
    assert SUPPLIED, "supplied data files not found"
    a, b = OrderBookA(), OrderBookB()
    for n, event in enumerate(load_events(path), start=1):
        ra, rb = a.process(event), b.process(event)
        assert ra == rb, f"{path.name} event #{n}: results differ\nA: {ra}\nB: {rb}"
        assert (a.best_bid(), a.best_ask()) == (b.best_bid(), b.best_ask()), (path.name, n)
        if n % 200 == 0:
            assert a.snapshot() == b.snapshot(), f"{path.name} after event #{n}"
    assert a.snapshot() == b.snapshot()


def test_supplied_file_list_is_complete():
    assert len(SUPPLIED) == 5
