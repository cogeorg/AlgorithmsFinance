"""Revision regressions: stale prices, queue identity, bounded cleanup, parity."""
import copy
import random
import unittest
from unittest.mock import patch
from lob.version_a import OrderBook as VersionA
from lob.version_b import OrderBook as VersionB
from tests import test_version_a_validation as boundary_tests
from tests.test_orderbook import limit, cancel, sell, order, fill


class TestVersionBBoundaries(boundary_tests.TestVersionAValidation):
    """Reuse every baseline boundary assertion unchanged against Version B."""

    def setUp(self):
        replacement = patch.object(boundary_tests, "OrderBook", VersionB)
        replacement.start()
        self.addCleanup(replacement.stop)


class TestVersionBStructure(unittest.TestCase):
    def check_storage(self, book):
        for side in ("BUY", "SELL"):
            levels = book._levels[side]
            heap = book._heaps[side]
            keys = book._heap_keys[side]
            self.assertEqual(len(heap), len(keys))
            self.assertEqual(set(heap), keys)
            self.assertLessEqual(len(heap), 2 * len(levels) + 64)
            if not levels:
                self.assertEqual(heap, [])
            for index in range(1, len(heap)):
                self.assertLessEqual(heap[(index - 1) // 2], heap[index])
            for price, queue in levels.items():
                self.assertTrue(queue)
                self.assertIn(-price if side == "BUY" else price, keys)
                for oid, record in queue.items():
                    self.assertIs(book._orders[oid], record)
        self.assertEqual(len(book._orders), sum(len(q) for levels in book._levels.values() for q in levels.values()))

    def test_reactivated_price_uses_current_queue_once(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                book = VersionB()
                best, second = (200, 100) if side == "BUY" else (100, 200)
                book.process_event(limit(1, "best", side, best, 1))
                book.process_event(limit(2, "old", side, second, 1))
                book.process_event(cancel(3, "old"))
                book.process_event(limit(4, "new", side, second, 2))
                self.check_storage(book)
                event = sell(5, qty=3) if side == "BUY" else limit(5, "t", "BUY", 200, 3)
                result = book.process_event(event)
                self.assertEqual(result["fills"], [fill("best", price=best, qty=1), fill("new", price=second, qty=2)])
                self.assertEqual(book.inspect_book(), [])
                self.check_storage(book)

    def test_churn_with_live_anchor_bounds_heap_storage(self):
        book = VersionB()
        book.process_event(limit(1, "anchor", price=10000, qty=1))
        for i in range(1000):
            seq = 2 + 2 * i
            book.process_event(limit(seq, f"b{i}", price=i + 1, qty=1))
            book.process_event(cancel(seq + 1, f"b{i}"))
            self.check_storage(book)
        self.assertEqual(book.inspect_book(), [order("anchor", price=10000, qty=1)])
        book.process_event(cancel(2002, "anchor"))
        self.check_storage(book)
        self.assertEqual(book._orders, {})

    def test_compaction_retains_live_levels_and_fifo(self):
        book = VersionB()
        for i in range(160):
            book.process_event(limit(i + 1, f"p{i}", price=i + 1, qty=1))
        for i in range(120):
            book.process_event(cancel(161 + i, f"p{i}"))
            self.check_storage(book)
        book.process_event(limit(281, "last", price=160, qty=2))
        result = book.process_event(sell(282, qty=42))
        expected = [fill("p159", price=160, qty=1), fill("last", price=160, qty=2)]
        expected += [fill(f"p{i}", price=i + 1, qty=1) for i in range(158, 119, -1)]
        self.assertEqual(result["fills"], expected)
        self.assertEqual(book.inspect_book(), [])
        self.check_storage(book)

    def test_rejection_does_not_even_clean_internal_heaps(self):
        book = VersionB()
        book.process_event(limit(1, "best", price=200))
        book.process_event(limit(2, "stale", price=100))
        book.process_event(cancel(3, "stale"))
        before = copy.deepcopy(book.__dict__)
        self.assertEqual(book.process_event(limit(4, "best", "SELL", 100, 2))["status"], "rejected")
        self.assertEqual(book.__dict__, before)


class TestGeneratedParity(unittest.TestCase):
    def test_mixed_streams_compare_every_event(self):
        for seed in (42, 43, 44):
            rng = random.Random(seed)
            a, b = VersionA(), VersionB()
            submitted = []
            for seq in range(1, 601):
                choice = rng.random()
                if choice < 0.60:
                    oid = f"o{seq}"
                    event = limit(seq, oid, rng.choice(("BUY", "SELL")), rng.randint(95, 105), rng.randint(1, 20))
                    submitted.append(oid)
                elif choice < 0.82:
                    event = cancel(seq, rng.choice(submitted) if submitted else "unknown")
                else:
                    event = sell(seq, f"m{seq}", rng.randint(1, 60))
                if seq % 71 == 0:
                    bad = limit(seq, f"bad{seq}", qty=0)
                    before = a.inspect_book()
                    self.assertEqual(a.process_event(bad), b.process_event(bad))
                    self.assertEqual(a.inspect_book(), before)
                    self.assertEqual(b.inspect_book(), before)
                self.assertEqual(a.process_event(event), b.process_event(event), (seed, seq))
                self.assertEqual(a.inspect_book(), b.inspect_book(), (seed, seq))
                self.assertEqual(a.last_seq, b.last_seq)
