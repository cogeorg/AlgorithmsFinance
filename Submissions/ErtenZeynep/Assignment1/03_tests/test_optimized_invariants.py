"""Implementation-specific storage invariants for the optimized engine."""

import unittest

from orderbook import OptimizedOrderBook
from support import cancel, limit, market_sell


def assert_internal_invariants(test: unittest.TestCase, engine: OptimizedOrderBook) -> None:
    union: dict[str, object] = {}
    for side, levels, heap in (
        ("BUY", engine._bid_levels, engine._bid_heap),
        ("SELL", engine._ask_levels, engine._ask_heap),
    ):
        for price, level in levels.items():
            test.assertEqual(level.price_ticks, price)
            test.assertTrue(level.orders, "active price level must not be empty")
            arrivals = []
            for order_id, order in level.orders.items():
                test.assertNotIn(order_id, union)
                test.assertEqual(order.order_id, order_id)
                test.assertEqual(order.side, side)
                test.assertEqual(order.price_ticks, price)
                arrivals.append(order.arrival_seq)
                union[order_id] = order
            test.assertEqual(arrivals, sorted(arrivals), "FIFO must follow original arrival sequence")
            valid = [
                entry
                for entry in heap
                if entry[2] == price and engine._is_heap_entry_valid(side, entry)
            ]
            test.assertEqual(len(valid), 1, "each active price needs one valid heap entry")
            test.assertEqual(valid[0][1], level.generation)

        test.assertLessEqual(
            len(heap),
            engine._COMPACTION_MULTIPLIER * len(levels) + engine._COMPACTION_SLACK,
            "heap storage exceeded the declared compaction bound",
        )

    test.assertEqual(set(union), set(engine._active_by_id))
    for order_id, order in union.items():
        test.assertIs(engine._active_by_id[order_id], order)


class TestOptimizedInternalInvariants(unittest.TestCase):
    def test_exhaustion_and_cancellation_remove_all_indexes(self) -> None:
        engine = OptimizedOrderBook()
        events = [
            limit(1, "e1", "b1", "BUY", 101, 2),
            limit(2, "e2", "b2", "BUY", 101, 3),
            limit(3, "e3", "b3", "BUY", 100, 4),
            market_sell(4, "e4", "m1", 2),
            cancel(5, "e5", "b2"),
            market_sell(6, "e6", "m2", 4),
        ]
        for event in events:
            engine.process_event(event)
            assert_internal_invariants(self, engine)
        self.assertEqual(engine.canonical_snapshot(), [])
        self.assertEqual(engine._active_by_id, {})
        self.assertEqual(engine._bid_levels, {})

    def test_recreated_price_invalidates_old_heap_generation(self) -> None:
        engine = OptimizedOrderBook()
        engine.process_event(limit(1, "e1", "old", "BUY", 100, 1))
        old_entry = engine._bid_heap[0]
        old_generation = engine._bid_levels[100].generation
        engine.process_event(cancel(2, "e2", "old"))
        self.assertFalse(engine._is_heap_entry_valid("BUY", old_entry))
        engine.process_event(limit(3, "e3", "new", "BUY", 100, 1))
        new_generation = engine._bid_levels[100].generation
        self.assertNotEqual(old_generation, new_generation)
        self.assertFalse(engine._is_heap_entry_valid("BUY", old_entry))
        assert_internal_invariants(self, engine)

    def test_fifo_and_partial_fill_preserve_queue_position(self) -> None:
        engine = OptimizedOrderBook()
        for event in (
            limit(1, "e1", "first", "BUY", 100, 5),
            limit(2, "e2", "second", "BUY", 100, 4),
            market_sell(3, "e3", "m1", 2),
        ):
            engine.process_event(event)
            assert_internal_invariants(self, engine)
        self.assertEqual(list(engine._bid_levels[100].orders), ["first", "second"])
        result = engine.process_event(market_sell(4, "e4", "m2", 5))
        self.assertEqual([fill["maker_id"] for fill in result["fills"]], ["first", "second"])
        assert_internal_invariants(self, engine)

    def test_churn_compaction_bound_and_post_rebuild_matching(self) -> None:
        engine = OptimizedOrderBook()
        seq = 0
        for index in range(160):
            seq += 1
            order_id = f"churn-{index}"
            engine.process_event(limit(seq, f"add-{index}", order_id, "BUY", 100 + index, 1))
            seq += 1
            engine.process_event(cancel(seq, f"cancel-{index}", order_id))
            assert_internal_invariants(self, engine)
        self.assertEqual(engine._bid_levels, {})
        self.assertLessEqual(len(engine._bid_heap), engine._COMPACTION_SLACK)
        seq += 1
        engine.process_event(limit(seq, "best", "best", "BUY", 102, 2))
        seq += 1
        engine.process_event(limit(seq, "worse", "worse", "BUY", 101, 2))
        seq += 1
        result = engine.process_event(market_sell(seq, "sweep", "market", 3))
        self.assertEqual(
            [(fill["maker_id"], fill["price_ticks"], fill["qty_units"]) for fill in result["fills"]],
            [("best", 102, 2), ("worse", 101, 1)],
        )
        assert_internal_invariants(self, engine)


if __name__ == "__main__":
    unittest.main()
