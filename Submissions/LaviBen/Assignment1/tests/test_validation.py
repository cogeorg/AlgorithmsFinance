"""Validation precedence and atomic-state rejection tests."""

from __future__ import annotations

from copy import deepcopy
import unittest

from tests.support import cancel, limit, market_sell, require_implementations


class ValidationTests(unittest.TestCase):
    def implementations(self):
        return require_implementations(self).items()

    def assert_atomic_rejection(
        self,
        book_class,
        invalid_event,
        expected_result,
    ) -> None:
        book = book_class()
        accepted = book.ProcessEvent(limit(1, "kept", "BUY", 100, 5))
        self.assertEqual(accepted["status"], "resting")
        before_book = book.InspectBook()
        before_event = deepcopy(invalid_event)

        self.assertEqual(book.ProcessEvent(invalid_event), expected_result)
        self.assertEqual(invalid_event, before_event)
        self.assertEqual(book.InspectBook(), before_book)
        self.assertEqual(book.last_accepted_seq, 1)

        follow_up = book.ProcessEvent(limit(2, "after_rejection", "BUY", 99, 1))
        self.assertEqual(follow_up["status"], "resting")
        self.assertEqual(book.last_accepted_seq, 2)

    def test_rejection_reasons_and_precedence_are_stable(self) -> None:
        cases = (
            (None, {"status": "rejected", "reason": "event_must_be_mapping"}),
            ({}, {"status": "rejected", "reason": "missing_event_id"}),
            ({"event_id": "", "seq": 2, "type": "CANCEL", "target_order_id": "x"}, {"status": "rejected", "reason": "invalid_event_id"}),
            ({"event_id": "bad"}, {"event_id": "bad", "status": "rejected", "reason": "missing_seq"}),
            ({"event_id": "bad", "seq": True, "type": "CANCEL", "target_order_id": "x"}, {"event_id": "bad", "status": "rejected", "reason": "invalid_seq"}),
            ({"event_id": "bad", "seq": 0, "type": "CANCEL", "target_order_id": "x"}, {"event_id": "bad", "status": "rejected", "reason": "invalid_seq"}),
            ({"event_id": "bad", "seq": -1, "type": "CANCEL", "target_order_id": "x"}, {"event_id": "bad", "status": "rejected", "reason": "invalid_seq"}),
            ({"event_id": "bad", "seq": 1, "type": "NOPE"}, {"event_id": "bad", "status": "rejected", "reason": "nonincreasing_seq"}),
            ({"event_id": "bad", "seq": 2}, {"event_id": "bad", "status": "rejected", "reason": "missing_type"}),
            ({"event_id": "bad", "seq": 2, "type": "NOPE"}, {"event_id": "bad", "status": "rejected", "reason": "unknown_event_type"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "side": "BUY", "price_ticks": 100, "qty_units": 1}, {"event_id": "bad", "status": "rejected", "reason": "missing_order_id"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": 7, "side": "BUY", "price_ticks": 100, "qty_units": 1}, {"event_id": "bad", "status": "rejected", "reason": "invalid_order_id"}),
            (limit(2, "kept", "BUY", 100, 1, event_id="bad"), {"event_id": "bad", "status": "rejected", "reason": "duplicate_live_order_id"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "price_ticks": 100, "qty_units": 1}, {"event_id": "bad", "status": "rejected", "reason": "missing_side"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "HOLD", "price_ticks": 100, "qty_units": 1}, {"event_id": "bad", "status": "rejected", "reason": "invalid_side"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "BUY", "qty_units": 1}, {"event_id": "bad", "status": "rejected", "reason": "missing_price_ticks"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "BUY", "price_ticks": True, "qty_units": 1}, {"event_id": "bad", "status": "rejected", "reason": "invalid_price_ticks"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "BUY", "price_ticks": 0, "qty_units": 1}, {"event_id": "bad", "status": "rejected", "reason": "invalid_price_ticks"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "BUY", "price_ticks": -100, "qty_units": 1}, {"event_id": "bad", "status": "rejected", "reason": "invalid_price_ticks"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "BUY", "price_ticks": 100.0, "qty_units": 1}, {"event_id": "bad", "status": "rejected", "reason": "invalid_price_ticks"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "BUY", "price_ticks": 100}, {"event_id": "bad", "status": "rejected", "reason": "missing_qty_units"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "BUY", "price_ticks": 100, "qty_units": True}, {"event_id": "bad", "status": "rejected", "reason": "invalid_qty_units"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "BUY", "price_ticks": 100, "qty_units": False}, {"event_id": "bad", "status": "rejected", "reason": "invalid_qty_units"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "BUY", "price_ticks": 100, "qty_units": 0}, {"event_id": "bad", "status": "rejected", "reason": "invalid_qty_units"}),
            ({"event_id": "bad", "seq": 2, "type": "LIMIT", "order_id": "x", "side": "BUY", "price_ticks": 100, "qty_units": -1}, {"event_id": "bad", "status": "rejected", "reason": "invalid_qty_units"}),
            (market_sell(2, "kept", 1, event_id="bad"), {"event_id": "bad", "status": "rejected", "reason": "duplicate_live_order_id"}),
            ({"event_id": "bad", "seq": 2, "type": "MARKET_SELL", "order_id": "s", "qty_units": True}, {"event_id": "bad", "status": "rejected", "reason": "invalid_qty_units"}),
            ({"event_id": "bad", "seq": 2, "type": "MARKET_SELL", "order_id": "s", "qty_units": False}, {"event_id": "bad", "status": "rejected", "reason": "invalid_qty_units"}),
            ({"event_id": "bad", "seq": 2, "type": "MARKET_SELL", "order_id": "s", "qty_units": 0}, {"event_id": "bad", "status": "rejected", "reason": "invalid_qty_units"}),
            ({"event_id": "bad", "seq": 2, "type": "MARKET_SELL", "order_id": "s", "qty_units": 1.5}, {"event_id": "bad", "status": "rejected", "reason": "invalid_qty_units"}),
            ({"event_id": "bad", "seq": 2, "type": "CANCEL"}, {"event_id": "bad", "status": "rejected", "reason": "missing_target_order_id"}),
            ({"event_id": "bad", "seq": 2, "type": "CANCEL", "target_order_id": ""}, {"event_id": "bad", "status": "rejected", "reason": "invalid_target_order_id"}),
            ({"event_id": "bad", "seq": 2, "type": "CANCEL", "target_order_id": 7}, {"event_id": "bad", "status": "rejected", "reason": "invalid_target_order_id"}),
        )

        for name, book_class in self.implementations():
            for invalid_event, expected in cases:
                with self.subTest(implementation=name, reason=expected["reason"]):
                    self.assert_atomic_rejection(book_class, invalid_event, expected)

    def test_unknown_cancel_is_valid_and_advances_sequence(self) -> None:
        for name, book_class in self.implementations():
            with self.subTest(implementation=name):
                book = book_class()
                result = book.ProcessEvent(cancel(5, "missing"))
                self.assertEqual(
                    result,
                    {
                        "event_id": "event5",
                        "target_order_id": "missing",
                        "status": "not_found",
                        "cancelled_qty_units": 0,
                    },
                )
                self.assertEqual(book.last_accepted_seq, 5)
                self.assertEqual(
                    book.ProcessEvent(limit(5, "late", "BUY", 100, 1)),
                    {
                        "event_id": "event5",
                        "status": "rejected",
                        "reason": "nonincreasing_seq",
                    },
                )


if __name__ == "__main__":
    unittest.main()
