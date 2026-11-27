"""Regression cases added during implementation review; expectations stay fixed."""

from __future__ import annotations

from copy import deepcopy
import unittest

from tests.support import cancel, fill, limit, market_sell, require_implementations


class RegressionTests(unittest.TestCase):
    def test_unhashable_type_and_side_are_rejected_without_state_change(self) -> None:
        invalid_events = (
            (
                {"event_id": "bad-type", "seq": 1, "type": []},
                {
                    "event_id": "bad-type",
                    "status": "rejected",
                    "reason": "unknown_event_type",
                },
            ),
            (
                {
                    "event_id": "bad-side",
                    "seq": 1,
                    "type": "LIMIT",
                    "order_id": "x",
                    "side": [],
                    "price_ticks": 100,
                    "qty_units": 1,
                },
                {
                    "event_id": "bad-side",
                    "status": "rejected",
                    "reason": "invalid_side",
                },
            ),
        )

        for name, book_class in require_implementations(self).items():
            with self.subTest(implementation=name):
                book = book_class()
                for event, expected in invalid_events:
                    before = deepcopy(event)
                    self.assertEqual(book.ProcessEvent(event), expected)
                    self.assertEqual(event, before)
                    self.assertEqual(book.InspectBook(), [])
                    self.assertIsNone(book.last_accepted_seq)

                accepted = book.ProcessEvent(limit(1, "after", "BUY", 100, 1))
                self.assertEqual(accepted["status"], "resting")
                self.assertEqual(book.last_accepted_seq, 1)

    def test_cancelling_middle_of_price_queue_preserves_fifo(self) -> None:
        for name, book_class in require_implementations(self).items():
            with self.subTest(implementation=name):
                book = book_class()
                book.ProcessEvent(limit(1, "first", "BUY", 100, 1))
                book.ProcessEvent(limit(2, "middle", "BUY", 100, 1))
                book.ProcessEvent(limit(3, "last", "BUY", 100, 1))
                cancelled = book.ProcessEvent(cancel(4, "middle"))
                sale = book.ProcessEvent(market_sell(5, "sell", 2))

                self.assertEqual(cancelled["cancelled_qty_units"], 1)
                self.assertEqual(
                    sale["fills"],
                    [
                        fill("first", "sell", 100, 1),
                        fill("last", "sell", 100, 1),
                    ],
                )
                self.assertEqual(book.InspectBook(), [])


if __name__ == "__main__":
    unittest.main()
