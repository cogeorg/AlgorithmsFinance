"""Shared public-interface, snapshot, and differential-observation tests."""

import unittest

from support import ENGINE_CLASSES, cancel, fill, limit, market_sell, order, submission_result


class TestPublicInterface(unittest.TestCase):
    def test_both_stubs_expose_identical_required_interface(self) -> None:
        for engine_class in ENGINE_CLASSES:
            engine = engine_class()
            with self.subTest(engine=engine_class.__name__):
                for name in ("process_event", "AddLimitOrder", "CancelOrder", "FillMarketSell", "canonical_snapshot"):
                    self.assertTrue(callable(getattr(engine, name)))
                self.assertIsNone(engine.last_accepted_seq)
                self.assertEqual(engine.canonical_snapshot(), [])

    def test_empty_snapshots_are_detached(self) -> None:
        for engine_class in ENGINE_CLASSES:
            engine = engine_class()
            snapshot = engine.canonical_snapshot()
            snapshot.append(order("fake", "BUY", 1, 1, 1))
            self.assertEqual(engine.canonical_snapshot(), [])

    def test_populated_snapshot_mutation_does_not_change_engine(self) -> None:
        for engine_class in ENGINE_CLASSES:
            with self.subTest(engine=engine_class.__name__):
                engine = engine_class()
                engine.process_event(limit(1, "e1", "b", "BUY", 100, 2))
                snapshot = engine.canonical_snapshot()
                snapshot[0]["qty_units"] = 999
                self.assertEqual(engine.canonical_snapshot(), [order("b", "BUY", 100, 2, 1)])


class TestDirectOperationParity(unittest.TestCase):
    def test_direct_operations_equal_dispatch_on_fresh_engines(self) -> None:
        cases = [
            {
                "name": "valid limit",
                "setup": None,
                "event": limit(1, "e1", "b", "BUY", 100, 1),
                "operation": "AddLimitOrder",
                "result": submission_result("e1", "b", "resting", 1),
                "snapshot": [order("b", "BUY", 100, 1, 1)],
                "last_seq": 1,
            },
            {
                "name": "successful active cancellation",
                "setup": (
                    limit(10, "setup", "b", "BUY", 100, 2),
                    submission_result("setup", "b", "resting", 2),
                    [order("b", "BUY", 100, 2, 10)],
                    10,
                ),
                "event": cancel(20, "cancel", "b"),
                "operation": "CancelOrder",
                "result": {
                    "event_id": "cancel",
                    "target_order_id": "b",
                    "status": "cancelled",
                    "cancelled_qty_units": 2,
                },
                "snapshot": [],
                "last_seq": 20,
            },
            {
                "name": "market sell against resting bid",
                "setup": (
                    limit(10, "setup", "b", "BUY", 100, 2),
                    submission_result("setup", "b", "resting", 2),
                    [order("b", "BUY", 100, 2, 10)],
                    10,
                ),
                "event": market_sell(20, "market", "m", 1),
                "operation": "FillMarketSell",
                "result": submission_result("market", "m", "filled", 0, [fill("b", "m", 100, 1)]),
                "snapshot": [order("b", "BUY", 100, 1, 10)],
                "last_seq": 20,
            },
            {
                "name": "duplicate live limit rejection",
                "setup": (
                    limit(10, "setup", "same", "BUY", 100, 2),
                    submission_result("setup", "same", "resting", 2),
                    [order("same", "BUY", 100, 2, 10)],
                    10,
                ),
                "event": limit(20, "duplicate", "same", "SELL", 100, 1),
                "operation": "AddLimitOrder",
                "result": {"event_id": "duplicate", "status": "rejected", "reason": "duplicate_live_order_id"},
                "snapshot": [order("same", "BUY", 100, 2, 10)],
                "last_seq": 10,
            },
            {
                "name": "equal sequence market rejection",
                "setup": (
                    limit(10, "setup", "b", "BUY", 100, 2),
                    submission_result("setup", "b", "resting", 2),
                    [order("b", "BUY", 100, 2, 10)],
                    10,
                ),
                "event": market_sell(10, "equal", "m", 1),
                "operation": "FillMarketSell",
                "result": {"event_id": "equal", "status": "rejected", "reason": "nonincreasing_sequence"},
                "snapshot": [order("b", "BUY", 100, 2, 10)],
                "last_seq": 10,
            },
        ]
        for engine_class in ENGINE_CLASSES:
            for case in cases:
                with self.subTest(engine=engine_class.__name__, case=case["name"]):
                    dispatched = engine_class()
                    direct = engine_class()
                    if case["setup"] is not None:
                        setup_event, setup_result, setup_snapshot, setup_seq = case["setup"]
                        for engine in (dispatched, direct):
                            self.assertEqual(engine.process_event(setup_event), setup_result)
                            self.assertEqual(engine.canonical_snapshot(), setup_snapshot)
                            self.assertEqual(engine.last_accepted_seq, setup_seq)
                    direct_result = getattr(direct, case["operation"])(case["event"])
                    dispatched_result = dispatched.process_event(case["event"])
                    self.assertEqual(direct_result, dispatched_result)
                    self.assertEqual(direct_result, case["result"])
                    self.assertEqual(direct.canonical_snapshot(), dispatched.canonical_snapshot())
                    self.assertEqual(direct.canonical_snapshot(), case["snapshot"])
                    self.assertEqual(direct.last_accepted_seq, dispatched.last_accepted_seq)
                    self.assertEqual(direct.last_accepted_seq, case["last_seq"])


class TestDifferentialObservations(unittest.TestCase):
    def test_each_engine_matches_oracle_before_cross_engine_comparison(self) -> None:
        events = [limit(1, "e1", "b", "BUY", 100, 2), market_sell(2, "e2", "m", 1)]
        expected_results = [
            submission_result("e1", "b", "resting", 2),
            submission_result("e2", "m", "filled", 0, [fill("b", "m", 100, 1)]),
        ]
        expected_books = [[order("b", "BUY", 100, 2, 1)], [order("b", "BUY", 100, 1, 1)]]
        observations = []
        for engine_class in ENGINE_CLASSES:
            engine = engine_class()
            per_event = []
            for event, expected_result, expected_book in zip(events, expected_results, expected_books, strict=True):
                result = engine.process_event(event)
                self.assertEqual(result, expected_result)
                self.assertEqual(engine.canonical_snapshot(), expected_book)
                per_event.append((result, engine.canonical_snapshot()))
            observations.append(per_event)
        self.assertEqual(observations[0], observations[1])


if __name__ == "__main__":
    unittest.main()

