"""Version A vs Version B after every event, plus storage checks for stale entries.

Agreement is supporting evidence only; correctness comes from tests/test_spec.py and the
independent oracle. The full per-event book comparison over all five 10,000-event
samples is in bench/verify_correctness.py (slower; results saved to results/).
"""
import gzip
import json
import unittest
from pathlib import Path

from lob.book_a import BookA
from lob.book_b import BookB
from tests.streams import random_stream

DATA = Path(__file__).resolve().parent.parent / "data"


def read(path):
    with gzip.open(path, "rt") as fh:
        return [json.loads(line) for line in fh]


class TestEquivalence(unittest.TestCase):
    def test_random_streams_every_event(self):
        for seed in range(100, 200):
            with self.subTest(seed=seed):
                a, b = BookA(), BookB()
                for ev in random_stream(seed, n=300, prices=1 + seed % 6):
                    self.assertEqual(a.process(ev), b.process(ev), ev)
                    self.assertEqual(a.inspect_book(), b.inspect_book(), ev)

    def test_supplied_samples_results_every_event(self):
        for path in sorted(DATA.glob("*_10000.jsonl.gz")):
            with self.subTest(sample=path.name):
                a, b = BookA(), BookB()
                for i, ev in enumerate(read(path)):
                    self.assertEqual(a.process(ev), b.process(ev), ev)
                    if i % 1000 == 999:
                        self.assertEqual(a.inspect_book(), b.inspect_book())
                self.assertEqual(a.inspect_book(), b.inspect_book())


class TestVersionBStructure(unittest.TestCase):
    """Added after implementing B: its internal indexes must stay consistent."""

    def test_internal_invariants_random_streams(self):
        for seed in range(300, 340):
            with self.subTest(seed=seed):
                b = BookB()
                for ev in random_stream(seed, n=300, prices=1 + seed % 6):
                    b.process(ev)
                    b.check_internal()

    def test_internal_invariants_samples(self):
        for path in sorted(DATA.glob("*_10000.jsonl.gz")):
            with self.subTest(sample=path.name):
                b = BookB()
                for i, ev in enumerate(read(path)):
                    b.process(ev)
                    if i % 250 == 0:
                        b.check_internal()
                b.check_internal()


class _GenericB(BookB):
    """Version B data structures, but every event goes through the shared generic path."""

    def process(self, event):
        from lob.common import OrderBookBase
        return OrderBookBase.process(self, event)


class _StrSub(str):
    pass


class _DictSub(dict):
    pass


class TestFastPath(unittest.TestCase):
    """Added with the fast path of Version B: it must behave exactly like the generic path."""

    def assertSame(self, events, book_every=1):
        fast, slow = BookB(), _GenericB()
        for i, ev in enumerate(events):
            self.assertEqual(fast.process(ev), slow.process(ev), ev)
            self.assertEqual(fast.last_seq, slow.last_seq, ev)
            if i % book_every == 0:
                self.assertEqual(fast.inspect_book(), slow.inspect_book(), ev)
        self.assertEqual(fast.inspect_book(), slow.inspect_book())
        fast.check_internal()

    def test_random_streams_with_invalid_events(self):
        for seed in range(400, 480):
            with self.subTest(seed=seed):
                self.assertSame(random_stream(seed, n=300, prices=1 + seed % 6, invalid_rate=0.15))

    def test_supplied_samples(self):
        for path in sorted(DATA.glob("*_10000.jsonl.gz")):
            with self.subTest(sample=path.name):
                self.assertSame(read(path), book_every=250)

    def test_edge_cases_fall_back_or_match(self):
        base = {"seq": 1, "event_id": "e1", "type": "LIMIT", "order_id": "b1", "side": "BUY",
                "price_ticks": 100, "qty_units": 5}
        cases = [
            [_DictSub(base)],                                         # dict subclass
            [{**base, "order_id": _StrSub("b1")}],                    # str subclass id
            [{**base, "event_id": _StrSub("e1")}],
            [{**base, "side": _StrSub("BUY")}],
            [{**base, "type": _StrSub("LIMIT")}],
            [{**base, "qty_units": True}], [{**base, "price_ticks": False}],
            [{**base, "seq": 0}], [{**base, "seq": -1}], [{**base, "event_id": ""}], [{**base, "order_id": ""}],
            [base, {"seq": 2, "event_id": "e2", "type": "CANCEL", "target_order_id": _StrSub("b1")}],
            [base, {"seq": 2, "event_id": "e2", "type": "CANCEL"}],
            [base, {"seq": 2, "event_id": "e2", "type": "MARKET_SELL", "order_id": "b1", "qty_units": 1}],
            [base, {"seq": 2, "event_id": "e2", "type": "MARKET_SELL", "order_id": "s", "qty_units": 99}],
            [base, {**base, "seq": 2, "event_id": "e2", "order_id": "a1", "side": "SELL", "price_ticks": 100}],
            [base, {**base, "seq": 2, "event_id": "e2", "order_id": "a1", "side": "SELL", "price_ticks": 101}],
            [{**base, "side": "SELL"}, {**base, "seq": 2, "event_id": "e2", "order_id": "b2", "price_ticks": 100}],
            [{**base, "side": "SELL"}, {**base, "seq": 2, "event_id": "e2", "order_id": "b2", "price_ticks": 99}],
            [{**base, "type": "MARKET_BUY"}], [{**base, "side": None}], [None], [[base]],
        ]
        for events in cases:
            with self.subTest(events=events):
                self.assertSame(events)


class TestSnapshotRestore(unittest.TestCase):
    """Added for the liquidation benchmark: a restored book must behave like the original."""

    def test_restore_then_sell_matches_original(self):
        events = read(DATA / "mixed_10000.jsonl.gz")[:4000]
        for impl in (BookA, BookB):
            with self.subTest(impl=impl.__name__):
                orig = impl()
                for ev in events:
                    orig.process(ev)
                snap = orig.inspect_book()
                copy = impl.from_snapshot(snap, orig.last_seq)
                self.assertEqual(copy.inspect_book(), snap)
                sell = {"seq": orig.last_seq + 1, "event_id": "big", "type": "MARKET_SELL",
                        "order_id": "big", "qty_units": 10**12}
                self.assertEqual(copy.process(sell), orig.process(sell))
                self.assertEqual(copy.inspect_book(), orig.inspect_book())
                if impl is BookB:
                    copy.check_internal()


class TestNoStaleStorage(unittest.TestCase):
    """Cancellation churn must not leave inactive entries behind (memory trap)."""

    def test_cancel_churn_storage_matches_active_book(self):
        events = read(DATA / "cancel_churn_10000.jsonl.gz")
        for impl in (BookA, BookB):
            with self.subTest(impl=impl.__name__):
                book = impl()
                for ev in events:
                    book.process(ev)
                active = len(book.inspect_book())
                counts = book.storage_counts()
                self.assertEqual(active, 0)  # every add is followed by its cancel
                self.assertEqual(counts["stored_orders"], active, counts)
                self.assertEqual(counts["stored_levels"], 0, counts)

    def test_storage_counts_after_mixed_flow(self):
        events = read(DATA / "mixed_10000.jsonl.gz")
        for impl in (BookA, BookB):
            with self.subTest(impl=impl.__name__):
                book = impl()
                for ev in events:
                    book.process(ev)
                orders = book.inspect_book()
                counts = book.storage_counts()
                self.assertEqual(counts["stored_orders"], len(orders), counts)
                levels = {(o["side"], o["price_ticks"]) for o in orders}
                if impl is BookB:
                    self.assertEqual(counts["stored_levels"], len(levels), counts)


if __name__ == "__main__":
    unittest.main()
