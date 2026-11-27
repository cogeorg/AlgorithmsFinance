"""Self-tests for the implementation-independent transition verifier."""

import unittest

from support import cancel, fill, limit, market_sell, order, submission_result, verify_transition


class TestTransitionVerifierValidCases(unittest.TestCase):
    def test_partial_maker_reduction(self) -> None:
        before = [order("b1", "BUY", 100, 5, 1)]
        event = market_sell(2, "e2", "m1", 2)
        result = submission_result("e2", "m1", "filled", 0, [fill("b1", "m1", 100, 2)])
        after = [order("b1", "BUY", 100, 3, 1)]
        verify_transition(before, event, result, after, 1, 2)

    def test_limit_residual_and_maker_price(self) -> None:
        before = [order("s1", "SELL", 99, 2, 1)]
        event = limit(5, "e5", "b1", "BUY", 100, 5)
        result = submission_result("e5", "b1", "resting", 3, [fill("s1", "b1", 99, 2)])
        after = [order("b1", "BUY", 100, 3, 5)]
        verify_transition(before, event, result, after, 1, 5)

    def test_successful_and_unknown_cancellation(self) -> None:
        before = [order("b1", "BUY", 100, 3, 1)]
        cancelled = {
            "event_id": "e2",
            "target_order_id": "b1",
            "status": "cancelled",
            "cancelled_qty_units": 3,
        }
        verify_transition(before, cancel(2, "e2", "b1"), cancelled, [], 1, 2)
        not_found = {
            "event_id": "e3",
            "target_order_id": "missing",
            "status": "not_found",
            "cancelled_qty_units": 0,
        }
        verify_transition([], cancel(3, "e3", "missing"), not_found, [], 2, 3)

    def test_rejection_preserves_snapshot_and_sequence(self) -> None:
        snapshot = [order("b1", "BUY", 100, 3, 1)]
        rejected = {"event_id": "e2", "status": "rejected", "reason": "invalid_quantity"}
        verify_transition(snapshot, market_sell(2, "e2", "m1", 1), rejected, list(snapshot), 1, 1)


class TestTransitionVerifierCorruptCases(unittest.TestCase):
    def assert_corrupt(
        self,
        before: list[dict],
        event: dict,
        result: dict,
        after: list[dict],
        before_seq: int | None,
        after_seq: int | None,
    ) -> None:
        with self.assertRaises(AssertionError):
            verify_transition(before, event, result, after, before_seq, after_seq)

    def test_wrong_price_and_fifo_are_detected(self) -> None:
        before = [order("z", "BUY", 100, 1, 1), order("a", "BUY", 100, 1, 2)]
        event = market_sell(3, "e3", "m", 1)
        with self.subTest("wrong maker price"):
            bad = submission_result("e3", "m", "filled", 0, [fill("z", "m", 99, 1)])
            self.assert_corrupt(before, event, bad, [order("a", "BUY", 100, 1, 2)], 2, 3)
        with self.subTest("reversed FIFO"):
            bad = submission_result("e3", "m", "filled", 0, [fill("a", "m", 100, 1)])
            self.assert_corrupt(before, event, bad, [order("z", "BUY", 100, 1, 1)], 2, 3)

    def test_incorrect_quantity_delta_and_exhausted_maker_are_detected(self) -> None:
        before = [order("b1", "BUY", 100, 2, 1)]
        event = market_sell(2, "e2", "m", 2)
        result = submission_result("e2", "m", "filled", 0, [fill("b1", "m", 100, 2)])
        self.assert_corrupt(before, event, result, [order("b1", "BUY", 100, 1, 1)], 1, 2)

    def test_market_residual_cannot_rest(self) -> None:
        event = market_sell(1, "e1", "m", 2)
        result = submission_result("e1", "m", "unfilled", 2)
        self.assert_corrupt([], event, result, [order("m", "SELL", 100, 2, 1)], None, 1)

    def test_duplicate_nonpositive_and_crossed_snapshots_are_detected(self) -> None:
        event = cancel(3, "e3", "missing")
        result = {
            "event_id": "e3",
            "target_order_id": "missing",
            "status": "not_found",
            "cancelled_qty_units": 0,
        }
        bad_snapshots = [
            [order("x", "BUY", 100, 1, 1), order("x", "SELL", 101, 1, 2)],
            [{**order("x", "BUY", 100, 1, 1), "qty_units": 0}],
            [order("b", "BUY", 101, 1, 1), order("s", "SELL", 100, 1, 2)],
        ]
        for snapshot in bad_snapshots:
            with self.subTest(snapshot=snapshot):
                self.assert_corrupt(snapshot, event, result, snapshot, 2, 3)

    def test_rejected_state_or_sequence_mutation_is_detected(self) -> None:
        before = [order("b1", "BUY", 100, 1, 1)]
        rejected = {"event_id": "e2", "status": "rejected", "reason": "invalid_quantity"}
        self.assert_corrupt(before, market_sell(2, "e2", "m", 1), rejected, [], 1, 1)
        self.assert_corrupt(before, market_sell(2, "e2", "m", 1), rejected, before, 1, 2)


if __name__ == "__main__":
    unittest.main()

