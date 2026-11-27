"""Independent behavioral contract shared by both future implementations."""

from __future__ import annotations

import unittest

from tests.support import (
    assert_book_invariants,
    cancel,
    fill,
    limit,
    market_sell,
    process_without_input_mutation,
    require_implementations,
    resting_order,
)


class OrderBookContractTests(unittest.TestCase):
    def test_additional_input_fields_are_ignored_without_mutation(self) -> None:
        event = {
            **limit(1, "b1", "BUY", 100, 7),
            "source": "optional-client-metadata",
        }
        expected_result = {
            "event_id": "event1",
            "order_id": "b1",
            "status": "resting",
            "unfilled_qty_units": 7,
            "fills": [],
        }
        for name, book_class in self.implementations():
            with self.subTest(version=name):
                book = book_class()
                self.assertEqual(
                    process_without_input_mutation(self, book, event),
                    expected_result,
                )

    def implementations(self):
        return require_implementations(self).items()

    def test_empty_book_and_required_public_api(self) -> None:
        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                for method_name in (
                    "ProcessEvent",
                    "AddLimitOrder",
                    "CancelOrder",
                    "FillMarketSell",
                    "InspectBook",
                ):
                    self.assertTrue(callable(getattr(book, method_name, None)))
                self.assertEqual(book.InspectBook(), [])
                self.assertIsNone(book.last_accepted_seq)

    def test_one_order_rests_and_inspection_is_canonical_copy(self) -> None:
        event = limit(1, "b1", "BUY", 100, 7)
        expected_result = {
            "event_id": "event1",
            "order_id": "b1",
            "status": "resting",
            "unfilled_qty_units": 7,
            "fills": [],
        }
        expected_book = [resting_order("b1", "BUY", 100, 7, 1)]

        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                self.assertEqual(
                    process_without_input_mutation(self, book, event),
                    expected_result,
                )
                inspected = book.InspectBook()
                self.assertEqual(inspected, expected_book)
                inspected[0]["qty_units"] = 999
                inspected.append(resting_order("fake", "BUY", 1, 1, 99))
                self.assertEqual(book.InspectBook(), expected_book)
                self.assertEqual(book.last_accepted_seq, 1)

    def test_fifo_priority_uses_arrival_not_identifier_spelling(self) -> None:
        events = (
            limit(1, "z_first", "BUY", 100, 4),
            limit(2, "a_second", "BUY", 100, 4),
            market_sell(3, "sell", 6),
        )
        expected_sell = {
            "event_id": "event3",
            "order_id": "sell",
            "status": "filled",
            "unfilled_qty_units": 0,
            "fills": [
                fill("z_first", "sell", 100, 4),
                fill("a_second", "sell", 100, 2),
            ],
        }
        expected_book = [resting_order("a_second", "BUY", 100, 2, 2)]

        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                results = [book.ProcessEvent(event) for event in events]
                self.assertEqual(results[-1], expected_sell)
                self.assertEqual(book.InspectBook(), expected_book)
                assert_book_invariants(self, book)

    def test_best_price_precedes_arrival_across_levels(self) -> None:
        events = (
            limit(1, "old_low", "BUY", 100, 3),
            limit(2, "best", "BUY", 102, 2),
            limit(3, "middle", "BUY", 101, 5),
            market_sell(4, "sell", 6),
        )
        expected_fills = [
            fill("best", "sell", 102, 2),
            fill("middle", "sell", 101, 4),
        ]
        expected_book = [
            resting_order("middle", "BUY", 101, 1, 3),
            resting_order("old_low", "BUY", 100, 3, 1),
        ]

        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                results = [book.ProcessEvent(event) for event in events]
                self.assertEqual(results[-1]["fills"], expected_fills)
                self.assertEqual(results[-1]["status"], "filled")
                self.assertEqual(book.InspectBook(), expected_book)

    def test_market_sell_filled_partial_and_unfilled_statuses(self) -> None:
        for name, book_class in self.implementations():
            cases = (
                (
                    [],
                    market_sell(1, "empty_sell", 5),
                    "unfilled",
                    5,
                    [],
                ),
                (
                    [limit(1, "b", "BUY", 100, 5)],
                    market_sell(2, "exact_sell", 5),
                    "filled",
                    0,
                    [fill("b", "exact_sell", 100, 5)],
                ),
                (
                    [limit(1, "b", "BUY", 100, 3)],
                    market_sell(2, "large_sell", 5),
                    "partial",
                    2,
                    [fill("b", "large_sell", 100, 3)],
                ),
            )
            for setup, sale, status, residual, fills in cases:
                with self.subTest(implementation=name, status=status):
                    book = book_class()
                    for event in setup:
                        book.ProcessEvent(event)
                    result = book.ProcessEvent(sale)
                    self.assertEqual(result["status"], status)
                    self.assertEqual(result["unfilled_qty_units"], residual)
                    self.assertEqual(result["fills"], fills)
                    self.assertFalse(
                        any(order["order_id"] == sale["order_id"] for order in book.InspectBook())
                    )

    def test_partial_maker_keeps_fifo_priority(self) -> None:
        events = (
            limit(1, "b1", "BUY", 100, 5),
            limit(2, "b2", "BUY", 100, 5),
            market_sell(3, "s1", 3),
            market_sell(4, "s2", 4),
        )
        expected_last_fills = [
            fill("b1", "s2", 100, 2),
            fill("b2", "s2", 100, 2),
        ]
        expected_book = [resting_order("b2", "BUY", 100, 3, 2)]

        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                results = [book.ProcessEvent(event) for event in events]
                self.assertEqual(results[-1]["fills"], expected_last_fills)
                self.assertEqual(book.InspectBook(), expected_book)

    def test_crossing_limit_buy_executes_at_maker_prices_and_rests_residual(self) -> None:
        events = (
            limit(1, "ask1", "SELL", 105, 3),
            limit(2, "ask2", "SELL", 106, 4),
            limit(3, "buy", "BUY", 106, 8),
        )
        expected_result = {
            "event_id": "event3",
            "order_id": "buy",
            "status": "resting",
            "unfilled_qty_units": 1,
            "fills": [
                fill("ask1", "buy", 105, 3),
                fill("ask2", "buy", 106, 4),
            ],
        }
        expected_book = [resting_order("buy", "BUY", 106, 1, 3)]

        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                results = [book.ProcessEvent(event) for event in events]
                self.assertEqual(results[-1], expected_result)
                self.assertEqual(book.InspectBook(), expected_book)
                assert_book_invariants(self, book)

    def test_crossing_limit_sell_and_noncrossing_residual(self) -> None:
        events = (
            limit(1, "bid1", "BUY", 104, 2),
            limit(2, "bid2", "BUY", 103, 3),
            limit(3, "sell", "SELL", 103, 6),
            limit(4, "ask", "SELL", 110, 2),
        )
        expected_sell = {
            "event_id": "event3",
            "order_id": "sell",
            "status": "resting",
            "unfilled_qty_units": 1,
            "fills": [
                fill("bid1", "sell", 104, 2),
                fill("bid2", "sell", 103, 3),
            ],
        }
        expected_book = [
            resting_order("sell", "SELL", 103, 1, 3),
            resting_order("ask", "SELL", 110, 2, 4),
        ]

        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                results = [book.ProcessEvent(event) for event in events]
                self.assertEqual(results[2], expected_sell)
                self.assertEqual(book.InspectBook(), expected_book)

    def test_cancellation_before_after_partial_and_full_fill(self) -> None:
        events = (
            limit(1, "cancel_now", "BUY", 99, 5),
            cancel(2, "cancel_now"),
            cancel(3, "cancel_now"),
            limit(4, "partial", "BUY", 100, 5),
            market_sell(5, "take_two", 2),
            cancel(6, "partial"),
            limit(7, "filled", "BUY", 101, 2),
            market_sell(8, "take_all", 2),
            cancel(9, "filled"),
            cancel(10, "never_existed"),
        )
        expected_cancellations = (
            {"event_id": "event2", "target_order_id": "cancel_now", "status": "cancelled", "cancelled_qty_units": 5},
            {"event_id": "event3", "target_order_id": "cancel_now", "status": "not_found", "cancelled_qty_units": 0},
            {"event_id": "event6", "target_order_id": "partial", "status": "cancelled", "cancelled_qty_units": 3},
            {"event_id": "event9", "target_order_id": "filled", "status": "not_found", "cancelled_qty_units": 0},
            {"event_id": "event10", "target_order_id": "never_existed", "status": "not_found", "cancelled_qty_units": 0},
        )

        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                results = [book.ProcessEvent(event) for event in events]
                actual = (results[1], results[2], results[5], results[8], results[9])
                self.assertEqual(actual, expected_cancellations)
                self.assertEqual(book.InspectBook(), [])
                self.assertEqual(book.last_accepted_seq, 10)

    def test_long_fifo_queue(self) -> None:
        makers = 200
        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                for seq in range(1, makers + 1):
                    book.ProcessEvent(limit(seq, f"maker-{makers - seq:03d}", "BUY", 100, 1))
                result = book.ProcessEvent(market_sell(makers + 1, "sell", makers))
                self.assertEqual(
                    [item["maker_id"] for item in result["fills"]],
                    [f"maker-{makers - seq:03d}" for seq in range(1, makers + 1)],
                )
                self.assertEqual(book.InspectBook(), [])

    def test_direct_operation_methods_share_dispatch_contract(self) -> None:
        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                add = book.AddLimitOrder(limit(1, "b", "BUY", 100, 3))
                sale = book.FillMarketSell(market_sell(2, "s", 1))
                cancellation = book.CancelOrder(cancel(3, "b"))
                self.assertEqual(add["status"], "resting")
                self.assertEqual(sale["fills"], [fill("b", "s", 100, 1)])
                self.assertEqual(cancellation["cancelled_qty_units"], 2)
                self.assertEqual(book.InspectBook(), [])

    def test_direct_operation_methods_reject_wrong_event_type_atomically(self) -> None:
        cases = (
            ("AddLimitOrder", cancel(2, "kept")),
            ("CancelOrder", market_sell(2, "seller", 1)),
            ("FillMarketSell", limit(2, "new", "BUY", 101, 1)),
        )
        for name, book_class in self.implementations():
            for method_name, wrong_event in cases:
                with self.subTest(implementation=name, method=method_name):
                    book = book_class()
                    book.ProcessEvent(limit(1, "kept", "BUY", 100, 3))
                    before = book.InspectBook()

                    result = getattr(book, method_name)(wrong_event)

                    self.assertEqual(
                        result,
                        {
                            "event_id": wrong_event["event_id"],
                            "status": "rejected",
                            "reason": "wrong_event_type_for_method",
                        },
                    )
                    self.assertEqual(book.InspectBook(), before)
                    self.assertEqual(book.last_accepted_seq, 1)

    def test_same_price_ask_fifo(self) -> None:
        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                book.ProcessEvent(limit(1, "ask-z", "SELL", 100, 2))
                book.ProcessEvent(limit(2, "ask-a", "SELL", 100, 2))

                result = book.ProcessEvent(limit(3, "buyer", "BUY", 100, 3))

                self.assertEqual(
                    result["fills"],
                    [
                        fill("ask-z", "buyer", 100, 2),
                        fill("ask-a", "buyer", 100, 1),
                    ],
                )
                self.assertEqual(
                    book.InspectBook(),
                    [
                        {
                            "order_id": "ask-a",
                            "side": "SELL",
                            "price_ticks": 100,
                            "qty_units": 1,
                            "arrival_seq": 2,
                        }
                    ],
                )

    def test_crossing_limit_residual_keeps_priority_over_later_same_price_order(self) -> None:
        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                book.ProcessEvent(limit(1, "ask", "SELL", 99, 2))
                crossing = book.ProcessEvent(limit(2, "residual", "BUY", 100, 5))
                book.ProcessEvent(limit(3, "later", "BUY", 100, 4))

                self.assertEqual(crossing["fills"], [fill("ask", "residual", 99, 2)])
                self.assertEqual(crossing["unfilled_qty_units"], 3)
                sale = book.ProcessEvent(market_sell(4, "seller", 4))
                self.assertEqual(
                    sale["fills"],
                    [
                        fill("residual", "seller", 100, 3),
                        fill("later", "seller", 100, 1),
                    ],
                )


if __name__ == "__main__":
    unittest.main()
