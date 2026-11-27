"""Internal structure of Version B (deque per price level + lazy cancel), after EVERY event.

Checks the claims in lob/version_b.py and REVISIONS.md step 9:
  - no empty price level is kept (a level whose last live order goes away is dropped at once)
  - per level: live == number of records with qty > 0, dead == number with qty == 0,
    len(queue) == live + dead, and dead * 2 <= len(queue)   (compaction rule)
    => len(queue) <= 2 * live, so memory is O(B), never O(number of submissions)
  - the order index and the queues describe the same live orders (same record object)
  - the sorted price list matches the occupied levels
These look at private attributes on purpose: a bug here would be silent in A-vs-B results
(a dead record that is never removed gives the same answers, only more memory).
"""
from lob.version_b import OrderBookB
from tools.gen_small import PROFILES, generate


def check_structure(book):
    index_ids = set(book._index)
    live_seen = set()
    for side in (book._bids, book._asks):
        assert side.keys == sorted(side.keys), "price list not sorted"
        assert side.keys == sorted(side.key(p) for p in side.levels), "price list != levels"
        for price, (queue, live, dead) in side.levels.items():
            assert live > 0, f"empty level kept at {price}"
            assert live == sum(1 for r in queue if r[0] > 0)
            assert dead == sum(1 for r in queue if r[0] == 0)
            assert len(queue) == live + dead
            assert dead * 2 <= len(queue), f"level {price}: {dead} dead of {len(queue)}"
            assert all(r[0] >= 0 for r in queue)
            for rec in queue:
                if rec[0] > 0:
                    is_bid, idx_price, idx_rec = book._index[rec[2]]
                    assert (is_bid, idx_price) == (side.is_bid, price) and idx_rec is rec
                    live_seen.add(rec[2])
    assert live_seen == index_ids, "index and queues disagree"


def total_records(book):
    return sum(len(lv[0]) for s in (book._bids, book._asks) for lv in s.levels.values())


def test_structure_after_every_event_on_generated_streams():
    for profile in PROFILES:
        for seed in range(40):
            book = OrderBookB()
            for event in generate(seed, 250, profile):
                book.process(event)
                check_structure(book)


def test_memory_bound_after_mass_cancels():
    """Cancel from the front, the back and every other order: records stay <= 2 * live."""
    n = 3000
    for pattern in ("tail", "front", "alternate"):
        book, seq = OrderBookB(), 0
        for i in range(n):
            seq += 1
            book.process({"seq": seq, "event_id": f"e{seq}", "type": "LIMIT", "order_id": f"o{i}",
                          "side": "BUY", "price_ticks": 100, "qty_units": 5})
        order = {"tail": range(n - 1, 0, -1), "front": range(0, n - 1),
                 "alternate": range(0, n, 2)}[pattern]
        for i in order:
            seq += 1
            r = book.process({"seq": seq, "event_id": f"e{seq}", "type": "CANCEL",
                              "target_order_id": f"o{i}"})
            assert r["status"] == "cancelled"
            assert total_records(book) <= 2 * len(book._index)
        check_structure(book)


def test_pinned_order_with_endless_add_cancel_does_not_grow():
    book = OrderBookB()
    book.process({"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "pin",
                  "side": "BUY", "price_ticks": 100, "qty_units": 5})
    seq = 1
    for i in range(5000):
        book.process({"seq": seq + 1, "event_id": f"a{i}", "type": "LIMIT", "order_id": f"o{i}",
                      "side": "BUY", "price_ticks": 100, "qty_units": 1})
        book.process({"seq": seq + 2, "event_id": f"c{i}", "type": "CANCEL",
                      "target_order_id": f"o{i}"})
        seq += 2
        assert total_records(book) <= 3
    check_structure(book)


def test_dead_head_is_skipped_by_matching():
    """Cancel the oldest order, then sell: the dead record at the front must be skipped."""
    book = OrderBookB()
    for n, oid in enumerate(("a", "b", "c"), start=1):
        book.process({"seq": n, "event_id": f"e{n}", "type": "LIMIT", "order_id": oid,
                      "side": "BUY", "price_ticks": 100, "qty_units": 2})
    book.process({"seq": 4, "event_id": "e4", "type": "CANCEL", "target_order_id": "a"})
    r = book.process({"seq": 5, "event_id": "e5", "type": "MARKET_SELL", "order_id": "s",
                      "qty_units": 3})
    assert [(f["maker_id"], f["qty_units"]) for f in r["fills"]] == [("b", 2), ("c", 1)]
    check_structure(book)
    assert book.snapshot() == [{"order_id": "c", "side": "BUY", "price_ticks": 100,
                                "qty_units": 1, "arrival_seq": 3}]
