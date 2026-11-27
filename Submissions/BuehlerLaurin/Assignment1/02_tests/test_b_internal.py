"""Internal B-variant checks ported from lob/check_b.py in Phase 3b.

Run: python -m pytest 02_tests/test_b_internal.py -q
Checks B's internal invariants, compaction thresholds and counter/plain parity.
Own expected files are read only; A is the event-by-event oracle.
"""
import copy
import json
from collections import OrderedDict
from pathlib import Path

from datagen.own_cases import C, L, M, CASE_NAMES
import pytest

from lob import METHODS, OrderBookA
from lob.replay import read_events

ROOT = Path(__file__).resolve().parents[1]


B_VARIANTS = [(key, impl) for key, impl in sorted(METHODS.items()) if key[1] != "A"]
LAZY_VARIANTS = [(key, impl) for key, impl in B_VARIANTS if key[1] != "B2"]


@pytest.fixture(params=[impl for key, impl in B_VARIANTS], ids=[key[1] for key, impl in B_VARIANTS])
def b_impl(request):
    return request.param


def assert_internal(book):
    """Index bijection, live/stale counts, FIFO and the post-event stale bound."""
    found = {}
    for side, name in ((book.bids, "BUY"), (book.asks, "SELL")):
        if hasattr(side, "heap"):
            assert len(side.heap) == len(set(side.heap))
            assert set(side.heap) == side.in_heap
            assert {side.sign * p for p in side.levels} <= side.in_heap
            assert all(side.heap[(i - 1) // 2] <= value for i, value in enumerate(side.heap) if i)
        else:
            assert side.prices == sorted(set(side.prices))
            assert set(side.prices) == {side.sign * p for p in side.levels}
        for price, level in side.levels.items():
            if isinstance(level.queue, OrderedDict):
                live = list(level.queue.values())
                assert live and all(record.alive for record in live)
                assert list(level.queue) == [record.order_id for record in live]
                assert not hasattr(level, "stale"), "B2 has no tombstones"
            else:
                live = [order for order in level.queue if order.alive]
                dead = [order for order in level.queue if not order.alive]
                assert len(live) == level.live > 0
                assert len(dead) == level.stale
                assert level.stale <= max(level.live, 32)
            assert [r.arrival_seq for r in live] == sorted(r.arrival_seq for r in live)
            for record in live:
                assert record.side == name and record.price_ticks == price and record.qty_units > 0
                assert record.order_id not in found
                found[record.order_id] = record
    assert found == book.orders
    assert all(book.orders[key] is record for key, record in found.items())


def books(b_impl):
    plain = b_impl()
    # This is also the first red diagnostic against the original B stub.
    assert plain.snapshot() == []
    counted = b_impl(count_operations=True)
    assert plain.counters is None
    assert counted.counters is not None
    return OrderBookA(), plain, counted


def send(engines, event, *, inspect_quotes=True):
    """Compare all results/books; show the exact event on the first divergence."""
    a, plain, counted = engines
    before = counted.counters.as_dict()
    results = []
    for engine in engines:
        sent = copy.deepcopy(event)
        results.append(engine.process(sent))
        assert sent == event, ("input mutated", event)
    assert results[0] == results[1] == results[2], ("result divergence", event, results)
    snapshots = [engine.snapshot() for engine in engines]
    assert snapshots[0] == snapshots[1] == snapshots[2], ("book divergence", event, snapshots)
    assert a.last_seq == plain.last_seq == counted.last_seq
    counters_after_event = counted.counters.as_dict()
    if inspect_quotes:
        assert (a.best_bid(), a.best_ask()) == (plain.best_bid(), plain.best_ask()) == (
            counted.best_bid(), counted.best_ask()), event
    assert counted.counters.as_dict() == counters_after_event, "inspection changed counters"
    for engine in (plain, counted):
        assert_internal(engine)
    if results[0]["status"] == "rejected":
        assert counted.counters.as_dict() == before, ("rejection changed counters", event)
    return results[0]


def test_own_cases(b_impl):
    for name in CASE_NAMES:
        engines = books(b_impl)
        expected = json.loads((ROOT / "06_data/own" / f"{name}.expected.json").read_text(encoding="utf-8"))
        events = list(read_events(ROOT / "06_data/own" / f"{name}.jsonl"))
        assert len(events) == len(expected["results"])
        for event, want in zip(events, expected["results"]):
            assert send(engines, event) == want, (name, event, want)
        assert engines[1].snapshot() == expected["final_book"], name
    print("18 own cases: A == B plain == B counted after every event; original expectations match")


@pytest.mark.parametrize("b_impl", [impl for key, impl in LAZY_VARIANTS],
                         ids=[key[1] for key, impl in LAZY_VARIANTS], indirect=True)
def test_cancel_compaction(b_impl):
    for side in ("BUY", "SELL"):
        engines = books(b_impl)
        for i in range(65):
            send(engines, L(i + 1, f"o{i}", side, 100, 2))
        for i in range(32):
            send(engines, C(66 + i, f"o{i}"))
        levels = engines[1].bids.levels if side == "BUY" else engines[1].asks.levels
        level = levels[100]
        assert (level.live, level.stale, len(level.queue)) == (33, 32, 65)
        assert engines[2].counters.compactions == 0
        send(engines, C(98, "o32"))
        assert (level.live, level.stale, len(level.queue)) == (32, 0, 32)
        counters = engines[2].counters
        assert (counters.compactions, counters.stale_compacted, counters.compaction_records_scanned) == (1, 33, 65)
        # Delete every survivor, then recreate the same level and reuse an id.
        for i in range(33, 65):
            send(engines, C(99 + i, f"o{i}"))
        assert not levels and engines[1].best_bid() is None and engines[1].best_ask() is None
        send(engines, L(200, "o0", side, 100, 3))
    print("Cancel compaction: both sides, strict >32 and >live thresholds, complete deletion and recreation")


@pytest.mark.parametrize("b_impl", [impl for key, impl in LAZY_VARIANTS],
                         ids=[key[1] for key, impl in LAZY_VARIANTS], indirect=True)
def test_match_compaction(b_impl):
    engines = books(b_impl)
    for i in range(96):
        send(engines, L(i + 1, f"o{i}", "BUY", 100, 2))
    for j, i in enumerate(range(63, 96)):
        send(engines, C(97 + j, f"o{i}"))
    level = engines[1].bids.levels[100]
    assert (level.live, level.stale) == (63, 33)
    assert engines[2].counters.compactions == 0
    send(engines, M(130, "s", 62))
    assert (level.live, level.stale, len(level.queue)) == (32, 0, 32)
    c = engines[2].counters
    assert (c.compactions, c.stale_compacted, c.compaction_records_scanned) == (1, 33, 65)
    print("Matching compaction: fills can trigger the same stale/live threshold")


def test_hand_counted_counters(b_impl):
    engines = books(b_impl)
    for event in (L(1, "b1", "BUY", 100, 5), L(2, "b2", "BUY", 100, 5),
                  C(3, "b1"), M(4, "s", 3)):
        send(engines, event)
    c = engines[2].counters
    assert (c.accepted_events, c.limit_events, c.market_sell_events, c.cancel_events) == (4, 2, 1, 1)
    assert (c.levels_visited, c.makers_touched, c.fills, c.unfilled_qty_units) == (1, 1, 1, 10)
    skipped = 0 if isinstance(engines[1].bids.levels[100].queue, OrderedDict) else 1
    assert (c.stale_skipped, c.stale_compacted, c.stale_discarded, c.compactions) == (skipped, 0, 0, 0)
    assert (c.active_order_peak, c.price_level_peak) == (2, 1)
    # Reusing a cancelled id must not revive an old tombstone.
    send(engines, L(5, "b1", "BUY", 100, 1))
    send(engines, M(6, "s2", 10))
    assert engines[1].snapshot() == []
    print("Hand-counted counters and cancelled-id reuse: exact; counters default off")


@pytest.mark.parametrize("b_impl", [impl for key, impl in LAZY_VARIANTS],
                         ids=[key[1] for key, impl in LAZY_VARIANTS], indirect=True)
def test_compaction_equal_live_does_not_rebuild(b_impl):
    engines = books(b_impl)
    for i in range(66):
        send(engines, L(i + 1, f"o{i}", "BUY", 100, 1))
    for i in range(33):
        send(engines, C(67 + i, f"o{i}"))
    level = engines[1].bids.levels[100]
    assert (level.live, level.stale, len(level.queue)) == (33, 33, 66)
    assert engines[2].counters.compactions == 0
    send(engines, C(100, "o33"))
    assert (level.live, level.stale, len(level.queue)) == (32, 0, 32)
    assert engines[2].counters.compactions == 1


def test_b2_cancel_removes_physical_middle_entry():
    engines = books(METHODS[("lob", "B2")])
    for i in range(70):
        send(engines, L(i + 1, f"o{i}", "BUY", 100, 2))
    for i in range(1, 69):
        send(engines, C(70 + i, f"o{i}"))
    level = engines[1].bids.levels[100]
    assert isinstance(level.queue, OrderedDict)
    assert list(level.queue) == ["o0", "o69"] and len(level.queue) == 2
    send(engines, M(140, "s", 1))
    assert list(level.queue) == ["o0", "o69"], "partial maker moved"
    send(engines, C(141, "o0"))
    send(engines, C(142, "o69"))
    assert not engines[1].bids.levels and engines[1].best_bid() is None
    c = engines[2].counters
    assert c.compactions == c.stale_skipped == c.stale_compacted == c.stale_discarded == 0


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_b3_reactivated_price_is_not_pushed_twice(side):
    engines = books(METHODS[("lob", "B3")])
    for event in (L(1, "same", side, 100, 2), C(2, "same"), L(3, "same", side, 100, 2)):
        send(engines, event, inspect_quotes=False)
    heap_side = engines[1].bids if side == "BUY" else engines[1].asks
    assert len(heap_side.heap) == len(heap_side.in_heap) == 1
    assert engines[2].counters.heap_pushes == 1
    opposite = "SELL" if side == "BUY" else "BUY"
    send(engines, L(4, "t", opposite, 100, 2), inspect_quotes=False)
    assert not heap_side.levels and len(heap_side.heap) == 1
    before = engines[2].counters.as_dict()
    for book in engines[1:]:
        assert book.best_bid() is None and book.best_ask() is None
    assert not heap_side.heap and not heap_side.in_heap
    assert engines[2].counters.as_dict() == before


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_b3_stale_heap_prices_wait_until_they_reach_the_root(side):
    engines = books(METHODS[("lob", "B3")])
    best = 1000 if side == "BUY" else 1
    send(engines, L(1, "keep", side, best, 1), inspect_quotes=False)
    for i in range(40):
        send(engines, L(2 + 2*i, f"gone{i}", side, 100 + i, 1), inspect_quotes=False)
        send(engines, C(3 + 2*i, f"gone{i}"), inspect_quotes=False)
    heap_side = engines[1].bids if side == "BUY" else engines[1].asks
    assert len(heap_side.levels) == 1 and len(heap_side.heap) == len(heap_side.in_heap) == 41
    send(engines, C(82, "keep"), inspect_quotes=False)
    before = engines[2].counters.as_dict()
    for book in engines[1:]:
        assert book.best_bid() is None and book.best_ask() is None
    assert not heap_side.heap and not heap_side.in_heap and not heap_side.levels
    assert engines[2].counters.as_dict() == before


