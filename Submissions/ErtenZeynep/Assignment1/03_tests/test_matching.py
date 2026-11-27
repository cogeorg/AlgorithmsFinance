"""Hand-calculated matching, priority, residual, and conservation cases."""

import unittest

from support import ENGINE_CLASSES, fill, limit, market_sell, order, run_expected_sequence, submission_result


class TestMatching(unittest.TestCase):
    def run_case(self, events, results, snapshots, sequences) -> None:
        for engine_class in ENGINE_CLASSES:
            with self.subTest(engine=engine_class.__name__):
                run_expected_sequence(engine_class(), events, results, snapshots, sequences)

    def test_empty_opposite_side_and_same_side_orders_rest(self) -> None:
        events = [limit(10, "e10", "b1", "BUY", 100, 1), limit(20, "e20", "b2", "BUY", 101, 1)]
        results = [
            submission_result("e10", "b1", "resting", 1),
            submission_result("e20", "b2", "resting", 1),
        ]
        snapshots = [
            [order("b1", "BUY", 100, 1, 10)],
            [order("b2", "BUY", 101, 1, 20), order("b1", "BUY", 100, 1, 10)],
        ]
        self.run_case(events, results, snapshots, [10, 20])

    def test_one_unit_exact_price_crossing(self) -> None:
        events = [limit(1, "e1", "s1", "SELL", 100, 1), limit(2, "e2", "b1", "BUY", 100, 1)]
        results = [
            submission_result("e1", "s1", "resting", 1),
            submission_result("e2", "b1", "filled", 0, [fill("s1", "b1", 100, 1)]),
        ]
        self.run_case(events, results, [[order("s1", "SELL", 100, 1, 1)], []], [1, 2])

    def test_opposite_side_noncrossing_limits_both_rest(self) -> None:
        events = [limit(1, "e1", "s1", "SELL", 101, 2), limit(2, "e2", "b1", "BUY", 100, 3)]
        results = [
            submission_result("e1", "s1", "resting", 2),
            submission_result("e2", "b1", "resting", 3),
        ]
        snapshots = [
            [order("s1", "SELL", 101, 2, 1)],
            [order("b1", "BUY", 100, 3, 2), order("s1", "SELL", 101, 2, 1)],
        ]
        self.run_case(events, results, snapshots, [1, 2])

    def test_partial_fill_preserves_fifo_for_follow_up_taker(self) -> None:
        events = [
            limit(1, "e1", "z", "BUY", 100, 5),
            limit(2, "e2", "a", "BUY", 100, 4),
            market_sell(3, "e3", "m1", 2),
            market_sell(4, "e4", "m2", 5),
        ]
        results = [
            submission_result("e1", "z", "resting", 5),
            submission_result("e2", "a", "resting", 4),
            submission_result("e3", "m1", "filled", 0, [fill("z", "m1", 100, 2)]),
            submission_result("e4", "m2", "filled", 0, [fill("z", "m2", 100, 3), fill("a", "m2", 100, 2)]),
        ]
        snapshots = [
            [order("z", "BUY", 100, 5, 1)],
            [order("z", "BUY", 100, 5, 1), order("a", "BUY", 100, 4, 2)],
            [order("z", "BUY", 100, 3, 1), order("a", "BUY", 100, 4, 2)],
            [order("a", "BUY", 100, 2, 2)],
        ]
        self.run_case(events, results, snapshots, [1, 2, 3, 4])

    def test_price_priority_overrides_arrival_and_proceeds_are_exact(self) -> None:
        events = [
            limit(1, "e1", "a", "BUY", 99, 2),
            limit(2, "e2", "b", "BUY", 101, 3),
            limit(3, "e3", "c", "BUY", 100, 4),
            market_sell(4, "e4", "m", 6),
        ]
        final_fills = [fill("b", "m", 101, 3), fill("c", "m", 100, 3)]
        self.assertEqual(sum(item["price_ticks"] * item["qty_units"] for item in final_fills), 603)
        results = [
            submission_result("e1", "a", "resting", 2),
            submission_result("e2", "b", "resting", 3),
            submission_result("e3", "c", "resting", 4),
            submission_result("e4", "m", "filled", 0, final_fills),
        ]
        snapshots = [
            [order("a", "BUY", 99, 2, 1)],
            [order("b", "BUY", 101, 3, 2), order("a", "BUY", 99, 2, 1)],
            [order("b", "BUY", 101, 3, 2), order("c", "BUY", 100, 4, 3), order("a", "BUY", 99, 2, 1)],
            [order("c", "BUY", 100, 1, 3), order("a", "BUY", 99, 2, 1)],
        ]
        self.run_case(events, results, snapshots, [1, 2, 3, 4])

    def test_multilevel_crossing_buy_rests_residual_with_original_sequence(self) -> None:
        events = [
            limit(1, "e1", "s1", "SELL", 99, 2),
            limit(2, "e2", "s2", "SELL", 100, 2),
            limit(5, "e5", "b1", "BUY", 100, 7),
        ]
        results = [
            submission_result("e1", "s1", "resting", 2),
            submission_result("e2", "s2", "resting", 2),
            submission_result("e5", "b1", "resting", 3, [fill("s1", "b1", 99, 2), fill("s2", "b1", 100, 2)]),
        ]
        snapshots = [
            [order("s1", "SELL", 99, 2, 1)],
            [order("s1", "SELL", 99, 2, 1), order("s2", "SELL", 100, 2, 2)],
            [order("b1", "BUY", 100, 3, 5)],
        ]
        self.run_case(events, results, snapshots, [1, 2, 5])

    def test_multilevel_crossing_sell_rests_residual(self) -> None:
        events = [
            limit(1, "e1", "b1", "BUY", 101, 2),
            limit(2, "e2", "b2", "BUY", 100, 2),
            limit(5, "e5", "s1", "SELL", 100, 7),
        ]
        results = [
            submission_result("e1", "b1", "resting", 2),
            submission_result("e2", "b2", "resting", 2),
            submission_result("e5", "s1", "resting", 3, [fill("b1", "s1", 101, 2), fill("b2", "s1", 100, 2)]),
        ]
        snapshots = [
            [order("b1", "BUY", 101, 2, 1)],
            [order("b1", "BUY", 101, 2, 1), order("b2", "BUY", 100, 2, 2)],
            [order("s1", "SELL", 100, 3, 5)],
        ]
        self.run_case(events, results, snapshots, [1, 2, 5])

    def test_market_sell_exact_depth_and_depth_plus_one(self) -> None:
        cases = [
            (3, submission_result("e2", "m", "filled", 0, [fill("b", "m", 100, 3)])),
            (4, submission_result("e2", "m", "partial", 1, [fill("b", "m", 100, 3)])),
        ]
        for quantity, final_result in cases:
            with self.subTest(quantity=quantity):
                self.run_case(
                    [limit(1, "e1", "b", "BUY", 100, 3), market_sell(2, "e2", "m", quantity)],
                    [submission_result("e1", "b", "resting", 3), final_result],
                    [[order("b", "BUY", 100, 3, 1)], []],
                    [1, 2],
                )

    def test_very_large_python_integers_remain_exact(self) -> None:
        huge = 10**40
        events = [limit(1, "e1", "b", "BUY", huge, huge), market_sell(2, "e2", "m", 1)]
        results = [
            submission_result("e1", "b", "resting", huge),
            submission_result("e2", "m", "filled", 0, [fill("b", "m", huge, 1)]),
        ]
        snapshots = [[order("b", "BUY", huge, huge, 1)], [order("b", "BUY", huge, huge - 1, 1)]]
        self.run_case(events, results, snapshots, [1, 2])

    def test_long_same_price_queue_uses_arrival_not_identifier_order(self) -> None:
        identifiers = [f"id-{20-index:02d}" for index in range(20)]
        events = [limit(index, f"e{index}", identifier, "BUY", 100, 1) for index, identifier in enumerate(identifiers, 1)]
        events.append(market_sell(21, "e21", "market", 12))
        results = [submission_result(f"e{index}", identifier, "resting", 1) for index, identifier in enumerate(identifiers, 1)]
        results.append(submission_result("e21", "market", "filled", 0, [fill(identifier, "market", 100, 1) for identifier in identifiers[:12]]))
        snapshots = [[order(identifier, "BUY", 100, 1, seq) for seq, identifier in enumerate(identifiers[:index], 1)] for index in range(1, 21)]
        snapshots.append([order(identifier, "BUY", 100, 1, seq) for seq, identifier in enumerate(identifiers[12:], 13)])
        self.run_case(events, results, snapshots, list(range(1, 22)))


if __name__ == "__main__":
    unittest.main()

