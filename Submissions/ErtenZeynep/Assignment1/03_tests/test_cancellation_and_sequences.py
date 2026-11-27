"""Cancellation lifecycle, accepted sequence, and rejection atomicity cases."""

import unittest

from support import ENGINE_CLASSES, cancel, fill, limit, market_sell, order, run_expected_sequence, submission_result


def cancellation_result(event_id: str, target: str, status: str, quantity: int) -> dict:
    return {
        "event_id": event_id,
        "target_order_id": target,
        "status": status,
        "cancelled_qty_units": quantity,
    }


class TestCancellationAndSequences(unittest.TestCase):
    def run_case(self, events, results, snapshots, sequences) -> None:
        for engine_class in ENGINE_CLASSES:
            with self.subTest(engine=engine_class.__name__):
                run_expected_sequence(engine_class(), events, results, snapshots, sequences)

    def test_cancel_middle_and_last_order_then_follow_up_match(self) -> None:
        events = [
            limit(1, "e1", "a", "BUY", 100, 1),
            limit(2, "e2", "b", "BUY", 100, 1),
            limit(3, "e3", "c", "BUY", 100, 1),
            cancel(4, "e4", "b"),
            cancel(5, "e5", "c"),
            market_sell(6, "e6", "m", 1),
        ]
        results = [
            submission_result("e1", "a", "resting", 1),
            submission_result("e2", "b", "resting", 1),
            submission_result("e3", "c", "resting", 1),
            cancellation_result("e4", "b", "cancelled", 1),
            cancellation_result("e5", "c", "cancelled", 1),
            submission_result("e6", "m", "filled", 0, [fill("a", "m", 100, 1)]),
        ]
        snapshots = [
            [order("a", "BUY", 100, 1, 1)],
            [order("a", "BUY", 100, 1, 1), order("b", "BUY", 100, 1, 2)],
            [order("a", "BUY", 100, 1, 1), order("b", "BUY", 100, 1, 2), order("c", "BUY", 100, 1, 3)],
            [order("a", "BUY", 100, 1, 1), order("c", "BUY", 100, 1, 3)],
            [order("a", "BUY", 100, 1, 1)],
            [],
        ]
        self.run_case(events, results, snapshots, [1, 2, 3, 4, 5, 6])

    def test_best_price_changes_after_cancellation(self) -> None:
        events = [
            limit(1, "e1", "best", "BUY", 101, 2),
            limit(2, "e2", "worse", "BUY", 100, 2),
            cancel(3, "e3", "best"),
            market_sell(4, "e4", "m", 1),
        ]
        results = [
            submission_result("e1", "best", "resting", 2),
            submission_result("e2", "worse", "resting", 2),
            cancellation_result("e3", "best", "cancelled", 2),
            submission_result("e4", "m", "filled", 0, [fill("worse", "m", 100, 1)]),
        ]
        snapshots = [
            [order("best", "BUY", 101, 2, 1)],
            [order("best", "BUY", 101, 2, 1), order("worse", "BUY", 100, 2, 2)],
            [order("worse", "BUY", 100, 2, 2)],
            [order("worse", "BUY", 100, 1, 2)],
        ]
        self.run_case(events, results, snapshots, [1, 2, 3, 4])

    def test_partial_fill_then_cancel_removes_only_remaining_quantity(self) -> None:
        events = [
            limit(1, "e1", "b", "BUY", 100, 5),
            market_sell(2, "e2", "m", 2),
            cancel(3, "e3", "b"),
            cancel(4, "e4", "b"),
            market_sell(5, "e5", "m2", 1),
        ]
        results = [
            submission_result("e1", "b", "resting", 5),
            submission_result("e2", "m", "filled", 0, [fill("b", "m", 100, 2)]),
            cancellation_result("e3", "b", "cancelled", 3),
            cancellation_result("e4", "b", "not_found", 0),
            submission_result("e5", "m2", "unfilled", 1),
        ]
        snapshots = [
            [order("b", "BUY", 100, 5, 1)],
            [order("b", "BUY", 100, 3, 1)],
            [],
            [],
            [],
        ]
        self.run_case(events, results, snapshots, [1, 2, 3, 4, 5])

    def test_exhausted_cancelled_unknown_and_market_ids_are_not_found(self) -> None:
        events = [
            limit(1, "e1", "b", "BUY", 100, 1),
            market_sell(2, "e2", "market", 1),
            cancel(3, "e3", "b"),
            cancel(4, "e4", "market"),
            cancel(5, "e5", "missing"),
        ]
        results = [
            submission_result("e1", "b", "resting", 1),
            submission_result("e2", "market", "filled", 0, [fill("b", "market", 100, 1)]),
            cancellation_result("e3", "b", "not_found", 0),
            cancellation_result("e4", "market", "not_found", 0),
            cancellation_result("e5", "missing", "not_found", 0),
        ]
        self.run_case(events, results, [[order("b", "BUY", 100, 1, 1)], [], [], [], []], [1, 2, 3, 4, 5])

    def test_sequence_may_start_nonone_and_have_gaps(self) -> None:
        events = [limit(50, "e50", "b1", "BUY", 100, 1), limit(100, "e100", "b2", "BUY", 99, 1)]
        results = [submission_result("e50", "b1", "resting", 1), submission_result("e100", "b2", "resting", 1)]
        snapshots = [
            [order("b1", "BUY", 100, 1, 50)],
            [order("b1", "BUY", 100, 1, 50), order("b2", "BUY", 99, 1, 100)],
        ]
        self.run_case(events, results, snapshots, [50, 100])

    def test_equal_decreasing_and_other_rejections_are_atomic(self) -> None:
        for engine_class in ENGINE_CLASSES:
            with self.subTest(engine=engine_class.__name__):
                engine = engine_class()
                self.assertEqual(engine.process_event(limit(10, "e10", "b", "BUY", 100, 1)), submission_result("e10", "b", "resting", 1))
                expected_book = [order("b", "BUY", 100, 1, 10)]
                for bad_event, reason in [
                    (limit(10, "equal", "x", "BUY", 99, 1), "nonincreasing_sequence"),
                    (limit(9, "lower", "y", "BUY", 99, 1), "nonincreasing_sequence"),
                    (market_sell(11, "invalid", "m", 0), "nonpositive_quantity"),
                ]:
                    with self.subTest(event=bad_event["event_id"]):
                        result = engine.process_event(bad_event)
                        self.assertEqual(result, {"event_id": bad_event["event_id"], "status": "rejected", "reason": reason})
                        self.assertEqual(engine.canonical_snapshot(), expected_book)
                        self.assertEqual(engine.last_accepted_seq, 10)
                corrected = market_sell(11, "corrected", "m", 1)
                self.assertEqual(engine.process_event(corrected), submission_result("corrected", "m", "filled", 0, [fill("b", "m", 100, 1)]))
                self.assertEqual(engine.last_accepted_seq, 11)

    def test_duplicate_live_crossing_submission_is_rejected_before_matching(self) -> None:
        events = [
            limit(1, "e1", "same", "SELL", 100, 2),
            limit(2, "e2", "same", "BUY", 100, 2),
            limit(2, "e2-corrected", "different", "BUY", 100, 2),
        ]
        results = [
            submission_result("e1", "same", "resting", 2),
            {"event_id": "e2", "status": "rejected", "reason": "duplicate_live_order_id"},
            submission_result("e2-corrected", "different", "filled", 0, [fill("same", "different", 100, 2)]),
        ]
        snapshots = [[order("same", "SELL", 100, 2, 1)], [order("same", "SELL", 100, 2, 1)], []]
        self.run_case(events, results, snapshots, [1, 1, 2])

    def test_market_sell_live_id_collision_is_rejected_before_matching(self) -> None:
        events = [
            limit(1, "e1", "same", "BUY", 100, 2),
            market_sell(2, "e2", "same", 1),
            market_sell(2, "e2-corrected", "different", 1),
        ]
        results = [
            submission_result("e1", "same", "resting", 2),
            {"event_id": "e2", "status": "rejected", "reason": "duplicate_live_order_id"},
            submission_result("e2-corrected", "different", "filled", 0, [fill("same", "different", 100, 1)]),
        ]
        snapshots = [
            [order("same", "BUY", 100, 2, 1)],
            [order("same", "BUY", 100, 2, 1)],
            [order("same", "BUY", 100, 1, 1)],
        ]
        self.run_case(events, results, snapshots, [1, 1, 2])


if __name__ == "__main__":
    unittest.main()

