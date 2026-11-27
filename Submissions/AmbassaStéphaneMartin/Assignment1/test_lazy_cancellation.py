"""Lazy-cancellation regressions, compared against the unchanged Baseline.

Run from Assignment1:
    python -B -m unittest -v test_lazy_cancellation
"""

from collections import deque
from copy import deepcopy
import unittest

from order_book import ComparedOrderBook
from test_order_book import (
    BTC_UNITS, cancel_event, limit_event, market_sell_event,
)


class NoScanDeque(deque):
    """Detect a cancellation scan when queue compaction is not due."""

    def __iter__(self):
        raise AssertionError("Logical cancellation must not iterate its deque.")

    def remove(self, value):
        raise AssertionError("Logical cancellation must not call deque.remove().")


class TestLazyCancellation(unittest.TestCase):
    def setUp(self):
        self.reset_book()

    def reset_book(self):
        self.engine = ComparedOrderBook()
        self.book = self.engine.revised
        self.seq = 0

    def levels(self, side):
        return self.book.bids_by_price if side == "BUY" else self.book.asks_by_price

    def is_live(self, order):
        return self.book.orders_by_id.get(order["order_id"]) is order

    def submit(self, event):
        result = self.engine.process_event(event)
        if result["status"] != "rejected":
            self.seq = event["seq"]
        self.check_storage()
        return result

    def add(self, order_id, side, price=6_000_000, quantity=BTC_UNITS):
        return self.submit(limit_event(self.seq + 1, order_id, side, price, quantity))

    def cancel(self, order_id):
        return self.submit(cancel_event(self.seq + 1, order_id))

    def take(self, side, quantity, price=10_000_000):
        order_id = f"take-{self.seq + 1}"
        if side == "BUY":
            return self.submit(market_sell_event(self.seq + 1, order_id, quantity))
        return self.add(order_id, "BUY", price, quantity)

    def check_storage(self):
        live_ids = set()
        for side in ("BUY", "SELL"):
            levels = self.levels(side)
            heap = self.book.bid_price_heap if side == "BUY" else self.book.ask_price_heap
            retained = self.book._bid_heap_keys if side == "BUY" else self.book._ask_heap_keys
            self.assertEqual(set(heap), retained)
            self.assertEqual(len(heap), len(retained))
            self.assertLessEqual(len(heap), 2 * len(levels) + 32)
            counts = {}
            for price, queue in levels.items():
                self.assertIs(type(price), int)
                self.assertGreater(price, 0)
                self.assertIsInstance(queue, deque)
                self.assertTrue(queue)
                live_count = 0
                previous_seq = 0
                for order in queue:
                    self.assertEqual(order["side"], side)
                    self.assertEqual(order["price_ticks"], price)
                    self.assertIs(type(order["price_ticks"]), int)
                    self.assertIs(type(order["qty_units"]), int)
                    self.assertGreaterEqual(order["qty_units"], 0)
                    self.assertIs(type(order["arrival_seq"]), int)
                    self.assertGreater(order["arrival_seq"], previous_seq)
                    previous_seq = order["arrival_seq"]
                    if self.is_live(order):
                        self.assertNotIn(order["order_id"], live_ids)
                        live_ids.add(order["order_id"])
                        live_count += 1
                        self.assertGreater(order["qty_units"], 0)
                self.assertGreater(live_count, 0)
                self.assertLessEqual(len(queue), 2 * live_count + 32)
                counts[price] = live_count
                self.assertIn(-price if side == "BUY" else price, retained)
            actual_counts = getattr(
                self.book, "_bid_live_counts" if side == "BUY" else "_ask_live_counts", None
            )
            if actual_counts is not None:
                self.assertEqual(actual_counts, counts)
            if not levels:
                self.assertEqual(heap, [])
                self.assertEqual(retained, set())
        self.assertEqual(live_ids, set(self.book.orders_by_id))
        snapshot = self.book.inspect_book()
        self.assertEqual(
            self.book.orders_by_id,
            {order["order_id"]: order for order in snapshot["bids"] + snapshot["asks"]},
        )

    def raw_state(self):
        return (
            self.book._last_seq,
            deepcopy(self.book.orders_by_id),
            {key: id(value) for key, value in self.book.orders_by_id.items()},
            {
                side: {
                    price: (id(queue), [(id(order), dict(order)) for order in queue])
                    for price, queue in self.levels(side).items()
                }
                for side in ("BUY", "SELL")
            },
            list(self.book.bid_price_heap), list(self.book.ask_price_heap),
            set(self.book._bid_heap_keys), set(self.book._ask_heap_keys),
            deepcopy(getattr(self.book, "_bid_live_counts", None)),
            deepcopy(getattr(self.book, "_ask_live_counts", None)),
        )

    def test_logical_cancellation_does_not_scan_the_deque(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                for order_id in ("Z", "M", "A"):
                    self.add(order_id, side)
                guarded = NoScanDeque(self.levels(side)[6_000_000])
                removed = self.book.orders_by_id["M"]
                self.levels(side)[6_000_000] = guarded

                # Compare's snapshots use the live index and do not iterate queues.
                result = self.engine.process_event(cancel_event(self.seq + 1, "M"))
                self.seq += 1
                self.assertEqual(result["status"], "cancelled")
                self.assertEqual(result["cancelled_qty_units"], BTC_UNITS)
                self.assertNotIn("M", self.book.orders_by_id)
                self.assertIs(guarded[1], removed)
                self.levels(side)[6_000_000] = deque(deque.__iter__(guarded))
                self.check_storage()

    def test_cancelled_makers_never_execute_or_appear_in_snapshots(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                self.add("Z", side, quantity=2 * BTC_UNITS)
                self.add("M", side, quantity=3 * BTC_UNITS)
                self.add("A", side)
                self.take(side, BTC_UNITS)
                result = self.cancel("M")
                self.assertEqual(result["cancelled_qty_units"], 3 * BTC_UNITS)
                rows = self.book.inspect_book()["bids" if side == "BUY" else "asks"]
                self.assertEqual([order["order_id"] for order in rows], ["Z", "A"])
                self.assertEqual(self.cancel("M")["status"], "not_found")
                result = self.take(side, 2 * BTC_UNITS)
                self.assertEqual([fill["maker_id"] for fill in result["fills"]], ["Z", "A"])
                self.assertEqual([fill["price_ticks"] for fill in result["fills"]], [6_000_000] * 2)
                self.assertEqual(self.book.orders_by_id, {})

    def test_old_active_head_churn_is_bounded_and_cleanup_preserves_fifo(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                self.add("Z", side, quantity=2 * BTC_UNITS)
                self.add("M", side)
                self.add("A", side)
                original = self.book.orders_by_id["Z"]
                saw_inactive = saw_compaction = False
                for rank in range(200):
                    order_id = f"temporary-{rank}"
                    self.add(order_id, side)
                    size_before = len(self.levels(side)[6_000_000])
                    self.cancel(order_id)
                    size_after = len(self.levels(side)[6_000_000])
                    saw_inactive |= size_after > len(self.book.orders_by_id)
                    saw_compaction |= size_after < size_before - 1
                    self.assertIs(self.book.orders_by_id["Z"], original)
                self.assertTrue(saw_inactive)
                self.assertTrue(saw_compaction)
                self.assertEqual(self.take(side, BTC_UNITS)["fills"][0]["maker_id"], "Z")
                self.assertEqual(self.book.orders_by_id["Z"]["arrival_seq"], original["arrival_seq"])
                result = self.take(side, 3 * BTC_UNITS)
                self.assertEqual([fill["maker_id"] for fill in result["fills"]], ["Z", "M", "A"])

    def test_retained_storage_is_bounded_separately_at_each_price(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                prices = [6_000_000 + rank for rank in range(5)]
                for rank, price in enumerate(prices):
                    self.add(f"anchor-{rank}", side, price)
                saw_inactive = False
                for rank in range(300):
                    price = prices[rank % len(prices)]
                    order_id = f"temporary-{rank}"
                    self.add(order_id, side, price)
                    self.cancel(order_id)
                    queue = self.levels(side)[price]
                    saw_inactive |= len(queue) > 1
                    self.assertLessEqual(len(queue), 34)
                self.assertTrue(saw_inactive)
                for rank in range(5):
                    self.cancel(f"anchor-{rank}")
                self.assertEqual(self.levels(side), {})
                self.assertEqual(self.book.orders_by_id, {})

    def test_inactive_level_removal_and_recreation_keep_price_heaps_correct(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                better = 6_100_000 if side == "BUY" else 5_900_000
                self.add("better", side, better)
                self.add("old-head", side)
                self.add("old-tail", side)
                old_queue = self.levels(side)[6_000_000]
                self.cancel("old-tail")
                self.cancel("old-head")
                self.assertFalse(old_queue)
                self.assertNotIn(6_000_000, self.levels(side))
                heap = self.book.bid_price_heap if side == "BUY" else self.book.ask_price_heap
                key = -6_000_000 if side == "BUY" else 6_000_000
                self.assertIn(key, heap)
                self.add("Z", side)
                self.add("A", side)
                self.assertEqual(heap.count(key), 1)
                self.assertEqual(self.take(side, BTC_UNITS)["fills"][0]["maker_id"], "better")
                result = self.take(side, 2 * BTC_UNITS)
                self.assertEqual([fill["maker_id"] for fill in result["fills"]], ["Z", "A"])

    def test_reused_identifier_does_not_reactivate_an_old_queue_entry(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                self.add("head", side)
                self.add("reused", side)
                old_order = self.book.orders_by_id["reused"]
                self.cancel("reused")
                self.assertTrue(any(order is old_order for order in self.levels(side)[6_000_000]))
                self.add("reused", side, quantity=2 * BTC_UNITS)
                new_order = self.book.orders_by_id["reused"]
                self.assertIsNot(old_order, new_order)
                result = self.take(side, 2 * BTC_UNITS)
                self.assertEqual([fill["maker_id"] for fill in result["fills"]], ["head", "reused"])
                self.assertEqual(new_order["qty_units"], BTC_UNITS)
                self.assertIs(self.levels(side)[6_000_000][0], new_order)

    def test_partial_head_cancellation_and_not_found_results_are_preserved(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                self.add("Z", side, quantity=2 * BTC_UNITS)
                self.add("A", side)
                self.take(side, BTC_UNITS)
                result = self.cancel("Z")
                self.assertEqual(result["cancelled_qty_units"], BTC_UNITS)
                self.assertEqual(self.cancel("Z")["status"], "not_found")
                result = self.take(side, BTC_UNITS)
                self.assertEqual(result["fills"][0]["maker_id"], "A")
                self.assertEqual(self.cancel("A")["status"], "not_found")
                self.assertEqual(self.cancel("unknown")["cancelled_qty_units"], 0)

    def test_filled_heads_and_inactive_prefixes_leave_only_live_makers(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                for order_id in ("Z", "M", "A"):
                    self.add(order_id, side)
                self.cancel("M")
                self.assertEqual(self.take(side, BTC_UNITS)["fills"][0]["maker_id"], "Z")
                self.assertNotIn("Z", self.book.orders_by_id)
                self.assertEqual(self.take(side, BTC_UNITS)["fills"][0]["maker_id"], "A")
                self.assertEqual(self.levels(side), {})
                self.assertEqual(self.book.orders_by_id, {})

    def test_rejections_preserve_inactive_entries_and_all_internal_indexes(self):
        self.add("bid-head", "BUY")
        self.add("bid-dead", "BUY")
        self.add("ask-head", "SELL", 6_010_000)
        self.add("ask-dead", "SELL", 6_010_000)
        self.cancel("bid-dead")
        self.cancel("ask-dead")
        bad_events = []
        for value in (True, False, 0, -1, 1.0):
            bad_events.append(market_sell_event(self.seq + 1, "bad", value))
            bad_events.append(limit_event(self.seq + 1, "bad", "BUY", value, BTC_UNITS))
        for seq in (True, False, 0, -1, self.seq, float(self.seq + 1)):
            bad_events.append(market_sell_event(seq, "bad", BTC_UNITS))
        missing = cancel_event(self.seq + 1, "bid-head")
        del missing["target_order_id"]
        bad_events.extend([
            missing,
            market_sell_event(self.seq + 1, "bid-head", BTC_UNITS),
            {"seq": self.seq + 1, "event_id": "unknown", "type": "UNKNOWN"},
            None,
        ])
        for event in bad_events:
            with self.subTest(event=event):
                before = self.raw_state()
                self.assertEqual(self.submit(event)["status"], "rejected")
                self.assertEqual(self.raw_state(), before)
        self.assertEqual(self.cancel("bid-head")["status"], "cancelled")

    def test_large_integer_quantities_survive_queue_cleanup(self):
        price, quantity = 2**60 + 3, 2**60 + 7
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                self.add("huge", side, price, quantity)
                for rank in range(100):
                    order_id = f"temporary-{rank}"
                    self.add(order_id, side, price)
                    self.cancel(order_id)
                result = self.take(side, quantity - 1, price)
                self.assertEqual(result["fills"][0]["price_ticks"], price)
                self.assertEqual(result["fills"][0]["qty_units"], quantity - 1)
                self.assertIs(type(result["fills"][0]["price_ticks"]), int)
                self.assertIs(type(result["fills"][0]["qty_units"]), int)
                self.assertEqual(self.cancel("huge")["cancelled_qty_units"], 1)


if __name__ == "__main__":
    unittest.main()
