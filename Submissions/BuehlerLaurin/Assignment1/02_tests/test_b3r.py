"""B3r thresholds, per-side/list-scan traps and work credits; no timing tests."""
from pathlib import Path
import runpy

import pytest
from datagen.own_cases import C, L, M
from lob import METHODS

ATTACK = runpy.run_path(str(Path(__file__).resolve().parents[1]/"07_attack/gen_attack.py"))


class NoLevelIteration(dict):
    """Membership/length work; iterating retained dict slots is forbidden."""
    def __iter__(self):
        raise AssertionError("rebuild iterated the levels dict")

    def keys(self):
        raise AssertionError("rebuild iterated levels.keys")

    def items(self):
        raise AssertionError("rebuild iterated levels.items")

    def values(self):
        raise AssertionError("rebuild iterated levels.values")


@pytest.mark.parametrize("scenario,n", [("dead_slot_rebuild", 512), ("two_side_thrash", 128)])
def test_rebuild_scan_work_per_cancel_is_amortized_at_most_two(scenario, n):
    book = METHODS[("lob", "B3r")](count_operations=True)
    pre, attack = ATTACK[scenario](n)
    for event in pre:
        assert book.process(event)["status"] != "rejected"
    for side in (book.bids, book.asks):
        side.levels = NoLevelIteration(side.levels)
    # Include prefill credits, since a rebuild can spend keys staled there.
    for event in attack:
        assert book.process(event)["status"] != "rejected"
    c = book.counters
    assert c.heap_rebuilds > 0
    assert c.heap_rebuild_keys_scanned <= 2*c.cancel_events
    assert c.heap_rebuild_keys_scanned <= 2*c.heap_rebuild_stale_removed


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_heap_bound_and_strict_thresholds_on_drift(side):
    book = METHODS[("lob", "B3r")](count_operations=True)
    best = 10000 if side == "BUY" else 1
    book.process(L(1, "keep", side, best, 1))
    for i in range(250):
        book.process(L(2+2*i, "x", side, 100+i, 1))
        book.process(C(3+2*i, "x"))
        for data in (book.bids, book.asks):
            assert len(data.heap) <= 2*len(data.levels)+32
            assert set(data.heap) == data.in_heap and len(data.heap) == len(data.in_heap)
        assert (book.best_bid() if side == "BUY" else book.best_ask()) == best
        if i == 31:
            assert book.counters.heap_rebuilds == 0  # stale==32
        if i == 32:
            assert book.counters.heap_rebuilds == 1
    assert book.counters.heap_rebuild_keys_scanned <= 2*book.counters.cancel_events


def test_equal_live_does_not_rebuild_and_matching_can_trigger_rebuild():
    book = METHODS[("lob", "B3r")](count_operations=True)
    for i in range(66):
        book.process(L(i+1, f"o{i}", "BUY", 100+i, 1))
    for i in range(33):
        book.process(C(67+i, f"o{i}"))
    assert book.counters.heap_rebuilds == 0  # live==stale==33
    book.process(M(100, "take-best", 1))
    assert book.counters.heap_rebuilds == 1
    assert len(book.bids.heap) == len(book.bids.levels) == 32


def test_b3r_reactivated_key_and_quotes_remain_counter_neutral():
    book = METHODS[("lob", "B3r")](count_operations=True)
    for event in (L(1, "same", "BUY", 100, 2), C(2, "same"), L(3, "same", "BUY", 100, 2)):
        book.process(event)
    assert book.counters.heap_pushes == 1 and len(book.bids.heap) == 1
    before = book.counters.as_dict()
    assert book.best_bid() == 100 and book.best_ask() is None
    assert book.counters.as_dict() == before
