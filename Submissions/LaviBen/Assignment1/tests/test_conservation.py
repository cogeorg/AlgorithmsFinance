"""Quantity, maker-loss, cancellation, proceeds, and book invariant checks."""

from __future__ import annotations

from collections import Counter
import unittest

from tests.support import (
    assert_book_invariants,
    cancel,
    limit,
    market_sell,
    require_implementations,
)


EVENTS = (
    limit(1, "bid1", "BUY", 105, 5),
    limit(2, "bid2", "BUY", 103, 4),
    limit(3, "ask1", "SELL", 110, 2),
    limit(4, "incoming_sell", "SELL", 104, 7),
    limit(5, "incoming_buy", "BUY", 105, 3),
    market_sell(6, "market", 6),
    cancel(7, "ask1"),
)


class ConservationTests(unittest.TestCase):
    def test_conservation_after_every_event(self) -> None:
        for name, book_class in require_implementations(self).items():
            with self.subTest(implementation=name):
                book = book_class()
                total_proceeds = 0

                for event in EVENTS:
                    before = {
                        order["order_id"]: order["qty_units"]
                        for order in book.InspectBook()
                    }
                    result = book.ProcessEvent(event)
                    after = {
                        order["order_id"]: order["qty_units"]
                        for order in book.InspectBook()
                    }

                    if event["type"] in {"LIMIT", "MARKET_SELL"}:
                        executed = sum(item["qty_units"] for item in result["fills"])
                        self.assertEqual(
                            event["qty_units"],
                            executed + result["unfilled_qty_units"],
                        )

                        maker_fills = Counter()
                        for item in result["fills"]:
                            maker_fills[item["maker_id"]] += item["qty_units"]
                            total_proceeds += item["price_ticks"] * item["qty_units"]
                        for maker_id, quantity in maker_fills.items():
                            self.assertIn(maker_id, before)
                            self.assertEqual(
                                before[maker_id] - quantity,
                                after.get(maker_id, 0),
                            )

                    if event["type"] == "CANCEL":
                        target = event["target_order_id"]
                        self.assertEqual(
                            result["cancelled_qty_units"],
                            before.get(target, 0),
                        )
                        self.assertNotIn(target, after)

                    assert_book_invariants(self, book)

                self.assertEqual(total_proceeds, 1_250)
                self.assertEqual(book.InspectBook(), [])


if __name__ == "__main__":
    unittest.main()
