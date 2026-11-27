"""Focused price-heap regressions, compared with the unchanged Baseline.

Run from Assignment1:
    python -B -m unittest -v test_price_heaps

The original 49 behavioral tests remain in test_order_book.py.
"""

from collections import deque
from copy import deepcopy
import unittest

from order_book import ComparedOrderBook
from test_order_book import (
    BTC_UNITS, cancel_event, limit_event, market_sell_event,
)


class TestPriceHeaps(unittest.TestCase):
    def setUp(self):
        self.reset_book()

    def reset_book(self):
        self.engine = ComparedOrderBook()
        self.book = self.engine.revised
        self.seq = 0

    def price_index(self, side):
        if side == "BUY":
            return self.book.bids_by_price, self.book.bid_price_heap, self.book._bid_heap_keys
        return self.book.asks_by_price, self.book.ask_price_heap, self.book._ask_heap_keys

    @staticmethod
    def heap_key(side, price):
        return -price if side == "BUY" else price

    def submit(self, event):
        result = self.engine.process_event(event)
        if result["status"] != "rejected":
            self.seq = event["seq"]
        self.check_indexes()
        return result

    def add(self, order_id, side, price, quantity=BTC_UNITS):
        return self.submit(limit_event(self.seq + 1, order_id, side, price, quantity))

    def cancel(self, order_id):
        return self.submit(cancel_event(self.seq + 1, order_id))

    def take(self, resting_side, quantity):
        order_id = f"take-{self.seq + 1}"
        if resting_side == "BUY":
            return self.submit(market_sell_event(self.seq + 1, order_id, quantity))
        return self.add(order_id, "BUY", 10_000_000, quantity)

    def check_indexes(self):
        live_ids = set()
        for side in ("BUY", "SELL"):
            levels, heap, retained = self.price_index(side)
            self.assertEqual(len(heap), len(set(heap)))
            self.assertEqual(set(heap), retained)
            self.assertLessEqual(len(heap), 2 * len(levels) + 32)
            if not levels:
                self.assertEqual(heap, [])
                self.assertEqual(retained, set())
            for index, key in enumerate(heap):
                self.assertIs(type(key), int)
                self.assertTrue(key < 0 if side == "BUY" else key > 0)
                if index:
                    self.assertLessEqual(heap[(index - 1) // 2], key)
            counts = {}
            for price, queue in levels.items():
                self.assertIs(type(price), int)
                self.assertGreater(price, 0)
                self.assertIn(self.heap_key(side, price), retained)
                self.assertIsInstance(queue, deque)
                self.assertTrue(queue)
                previous_seq = 0
                live_count = 0
                for order in queue:
                    self.assertEqual(order["side"], side)
                    self.assertIs(type(order["price_ticks"]), int)
                    self.assertEqual(order["price_ticks"], price)
                    self.assertIs(type(order["qty_units"]), int)
                    self.assertGreaterEqual(order["qty_units"], 0)
                    self.assertIs(type(order["arrival_seq"]), int)
                    self.assertGreater(order["arrival_seq"], previous_seq)
                    previous_seq = order["arrival_seq"]
                    if self.book.orders_by_id.get(order["order_id"]) is order:
                        self.assertNotIn(order["order_id"], live_ids)
                        live_ids.add(order["order_id"])
                        self.assertGreater(order["qty_units"], 0)
                        live_count += 1
                self.assertGreater(live_count, 0)
                self.assertLessEqual(len(queue), 2 * live_count + 32)
                counts[price] = live_count
            actual_counts = getattr(
                self.book, "_bid_live_counts" if side == "BUY" else "_ask_live_counts", None
            )
            if actual_counts is not None:
                self.assertEqual(actual_counts, counts)
        self.assertEqual(live_ids, set(self.book.orders_by_id))

    def raw_state(self):
        queues = {
            side: {
                price: (id(queue), [(id(order), dict(order)) for order in queue])
                for price, queue in self.price_index(side)[0].items()
            }
            for side in ("BUY", "SELL")
        }
        return (
            self.book._last_seq, deepcopy(self.book.orders_by_id), queues,
            list(self.book.bid_price_heap), list(self.book.ask_price_heap),
            set(self.book._bid_heap_keys), set(self.book._ask_heap_keys),
            deepcopy(getattr(self.book, "_bid_live_counts", None)),
            deepcopy(getattr(self.book, "_ask_live_counts", None)),
        )

    def test_bid_heap_skips_cancelled_best_price(self):
        self.add("low", "BUY", 5_990_000)
        self.add("high", "BUY", 6_010_000)
        self.add("middle", "BUY", 6_000_000)
        self.cancel("high")
        self.assertIn(-6_010_000, self.book.bid_price_heap)

        result = self.take("BUY", BTC_UNITS)
        self.assertEqual(
            [(fill["maker_id"], fill["price_ticks"]) for fill in result["fills"]],
            [("middle", 6_000_000)],
        )
        self.assertNotIn(-6_010_000, self.book._bid_heap_keys)
        result = self.take("BUY", BTC_UNITS)
        self.assertEqual(result["fills"][0]["maker_id"], "low")

    def test_ask_heap_skips_cancelled_best_price(self):
        self.add("high", "SELL", 6_010_000)
        self.add("low", "SELL", 5_990_000)
        self.add("middle", "SELL", 6_000_000)
        self.cancel("low")
        self.assertIn(5_990_000, self.book.ask_price_heap)

        result = self.take("SELL", BTC_UNITS)
        self.assertEqual(
            [(fill["maker_id"], fill["price_ticks"]) for fill in result["fills"]],
            [("middle", 6_000_000)],
        )
        self.assertNotIn(5_990_000, self.book._ask_heap_keys)
        result = self.take("SELL", BTC_UNITS)
        self.assertEqual(result["fills"][0]["maker_id"], "high")

    def test_heap_signs_do_not_change_large_original_integers(self):
        price, quantity = 2**60 + 3, 2**60 + 7
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                self.add("huge", side, price, quantity)
                self.assertEqual(self.price_index(side)[1], [self.heap_key(side, price)])
                snapshot = self.book.inspect_book()
                resting = snapshot["bids"] if side == "BUY" else snapshot["asks"]
                self.assertEqual(resting[0]["price_ticks"], price)
                if side == "BUY":
                    result = self.take(side, quantity - 1)
                else:
                    result = self.add("buyer", "BUY", price, quantity - 1)
                fill = result["fills"][0]
                self.assertIs(type(fill["price_ticks"]), int)
                self.assertIs(type(fill["qty_units"]), int)
                self.assertEqual(fill["price_ticks"], price)
                self.assertEqual(fill["qty_units"], quantity - 1)
                self.assertEqual(self.book.orders_by_id["huge"]["qty_units"], 1)
                self.cancel("huge")

    def test_recreation_reuses_retained_key_and_new_fifo_queue(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                price = 6_000_000
                anchor = 6_100_000 if side == "BUY" else 5_900_000
                self.add("anchor", side, anchor)
                self.add("old", side, price)
                old_queue = self.price_index(side)[0][price]
                self.cancel("old")
                key = self.heap_key(side, price)
                self.assertIn(key, self.price_index(side)[2])
                self.assertFalse(old_queue)

                self.add("Z", side, price, 2 * BTC_UNITS)
                self.add("A", side, price)
                queue = self.price_index(side)[0][price]
                self.assertIsNot(queue, old_queue)
                self.assertEqual(self.price_index(side)[1].count(key), 1)
                self.assertEqual(
                    [order["order_id"] for order in queue
                     if self.book.orders_by_id.get(order["order_id"]) is order],
                    ["Z", "A"],
                )
                self.assertEqual(self.take(side, BTC_UNITS)["fills"][0]["maker_id"], "anchor")
                self.assertEqual(self.take(side, BTC_UNITS)["fills"][0]["maker_id"], "Z")
                self.assertIs(queue[0], self.book.orders_by_id["Z"])
                self.assertEqual(queue[0]["qty_units"], BTC_UNITS)
                result = self.take(side, 2 * BTC_UNITS)
                self.assertEqual([fill["maker_id"] for fill in result["fills"]], ["Z", "A"])

    def test_recreation_after_stale_root_pop_pushes_a_fresh_key(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                price = 6_000_000
                fallback = 5_900_000 if side == "BUY" else 6_100_000
                self.add("fallback", side, fallback, 2 * BTC_UNITS)
                self.add("old", side, price)
                self.cancel("old")
                result = self.take(side, BTC_UNITS)
                self.assertEqual(result["fills"][0]["maker_id"], "fallback")
                key = self.heap_key(side, price)
                self.assertNotIn(key, self.price_index(side)[2])

                self.add("new", side, price)
                self.assertIn(key, self.price_index(side)[2])
                result = self.take(side, BTC_UNITS)
                self.assertEqual(result["fills"][0]["maker_id"], "new")
                self.assertEqual(self.book.orders_by_id["fallback"]["qty_units"], BTC_UNITS)

    def test_churn_rebuild_preserves_live_prices_and_allows_recreation(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                prices = (
                    (6_100_000, 6_090_000, 6_080_000)
                    if side == "BUY" else (5_900_000, 5_910_000, 5_920_000)
                )
                for order_id, price in zip(("Z", "M", "A"), prices):
                    self.add(order_id, side, price)
                saw_rebuild = False
                for rank in range(150):
                    price = 6_000_000 - rank if side == "BUY" else 6_000_000 + rank
                    order_id = f"temporary-{rank}"
                    self.add(order_id, side, price)
                    size_before = len(self.price_index(side)[1])
                    self.cancel(order_id)
                    saw_rebuild |= len(self.price_index(side)[1]) < size_before
                    self.assertEqual(set(self.price_index(side)[0]), set(prices))
                self.assertTrue(saw_rebuild)
                self.assertNotIn(self.heap_key(side, 6_000_000), self.price_index(side)[2])

                self.add("reborn", side, 6_000_000)
                result = self.take(side, 3 * BTC_UNITS)
                self.assertEqual([fill["maker_id"] for fill in result["fills"]], ["Z", "M", "A"])
                self.assertEqual([fill["price_ticks"] for fill in result["fills"]], list(prices))
                result = self.take(side, BTC_UNITS)
                self.assertEqual(result["fills"][0]["maker_id"], "reborn")

    def test_same_price_cancellation_churn_does_not_duplicate_keys(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                anchor = 6_100_000 if side == "BUY" else 5_900_000
                self.add("anchor", side, anchor)
                key = self.heap_key(side, 6_000_000)
                for rank in range(200):
                    order_id = f"temporary-{rank}"
                    self.add(order_id, side, 6_000_000)
                    self.cancel(order_id)
                    self.assertEqual(self.price_index(side)[1].count(key), 1)
                    self.assertLessEqual(len(self.price_index(side)[1]), 2)
                    self.assertEqual(set(self.book.orders_by_id), {"anchor"})
                self.cancel("anchor")

    def test_cancelling_every_level_clears_both_price_indexes(self):
        order_ids = []
        for rank in range(40):
            for side, price in (("BUY", 5_990_000 + rank), ("SELL", 6_010_000 + rank)):
                order_id = f"{side}-{rank}"
                self.add(order_id, side, price)
                order_ids.append(order_id)
        for order_id in reversed(order_ids):
            self.cancel(order_id)
        self.assertEqual(self.book.orders_by_id, {})
        for side in ("BUY", "SELL"):
            self.assertEqual(self.price_index(side), ({}, [], set()))

    def test_rejected_events_leave_stale_heaps_and_queues_unchanged(self):
        self.add("bid", "BUY", 6_000_000)
        self.add("ask", "SELL", 6_010_000)
        self.add("stale-bid", "BUY", 5_990_000)
        self.add("stale-ask", "SELL", 6_020_000)
        self.cancel("stale-bid")
        self.cancel("stale-ask")
        bad_events = [
            market_sell_event(self.seq + 1, "bad", value)
            for value in (True, False, 0, -1, 1.0)
        ]
        for value in (True, False, 0, -1, 6_000_000.0):
            bad_events.append(limit_event(self.seq + 1, "bad", "BUY", value, BTC_UNITS))
        for seq in (True, False, 0, -1, self.seq, float(self.seq + 1)):
            bad_events.append(market_sell_event(seq, "bad", BTC_UNITS))
        for event in bad_events:
            with self.subTest(event=event):
                before = self.raw_state()
                self.assertEqual(self.submit(event)["status"], "rejected")
                self.assertEqual(self.raw_state(), before)
        self.assertEqual(self.cancel("bid")["status"], "cancelled")

    def test_partial_fill_and_middle_cancellation_keep_fifo(self):
        for side in ("BUY", "SELL"):
            with self.subTest(side=side):
                self.reset_book()
                self.add("Z", side, 6_000_000, 2 * BTC_UNITS)
                self.add("M", side, 6_000_000)
                self.add("A", side, 6_000_000)
                original_seq = self.book.orders_by_id["Z"]["arrival_seq"]
                result = self.take(side, BTC_UNITS)
                self.assertEqual(result["fills"][0]["maker_id"], "Z")
                self.assertEqual(self.book.orders_by_id["Z"]["arrival_seq"], original_seq)
                self.cancel("M")
                queue = self.price_index(side)[0][6_000_000]
                self.assertEqual(
                    [order["order_id"] for order in queue
                     if self.book.orders_by_id.get(order["order_id"]) is order],
                    ["Z", "A"],
                )
                result = self.take(side, 2 * BTC_UNITS)
                self.assertEqual([fill["maker_id"] for fill in result["fills"]], ["Z", "A"])
                self.assertEqual([fill["price_ticks"] for fill in result["fills"]], [6_000_000, 6_000_000])


if __name__ == "__main__":
    unittest.main()
