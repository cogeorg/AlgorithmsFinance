from __future__ import annotations

import json
import unittest
from pathlib import Path

from generate_orders import SCENARIOS, events
from lob import IndexedOrderBook, ListOrderBook, gross_proceeds_tick_units
from lob.io import read_events, replay_events


ROOT = Path(__file__).resolve().parents[1]
BOOKS = (ListOrderBook, IndexedOrderBook)


def limit(seq, order_id, side="BUY", price=100, qty=10):
    return {
        "seq": seq,
        "event_id": f"e{seq}",
        "type": "LIMIT",
        "order_id": order_id,
        "side": side,
        "price_ticks": price,
        "qty_units": qty,
    }


def market(seq, order_id, qty):
    return {
        "seq": seq,
        "event_id": f"e{seq}",
        "type": "MARKET_SELL",
        "order_id": order_id,
        "qty_units": qty,
    }


def cancel(seq, target):
    return {
        "seq": seq,
        "event_id": f"e{seq}",
        "type": "CANCEL",
        "target_order_id": target,
    }


class ContractTests(unittest.TestCase):
    def for_each_book(self):
        for book_class in BOOKS:
            with self.subTest(book=book_class.__name__):
                yield book_class()

    def test_worked_example(self):
        expected = json.loads((ROOT / "data/worked_expected.json").read_text())
        source = read_events(ROOT / "data/worked_example.jsonl")
        for book in self.for_each_book():
            results = replay_events(book, source, validate_each=True)
            self.assertEqual(results[-1], expected["market_sell_result"])
            self.assertEqual(book.inspect_book(), expected["remaining_orders"])
            self.assertEqual(
                gross_proceeds_tick_units(results[-1]["fills"]),
                expected["gross_proceeds_tick_units"],
            )

    def test_empty_book_market_sell(self):
        for book in self.for_each_book():
            result = book.process_event(market(1, "s", 10))
            self.assertEqual(result["status"], "unfilled")
            self.assertEqual(result["unfilled_qty_units"], 10)
            self.assertEqual(result["fills"], [])
            self.assertEqual(book.inspect_book(), [])

    def test_one_order_rests(self):
        for book in self.for_each_book():
            result = book.process_event(limit(1, "b"))
            self.assertEqual(result["status"], "resting")
            self.assertEqual(result["unfilled_qty_units"], 10)
            self.assertEqual(book.inspect_book()[0]["order_id"], "b")

    def test_smaller_exact_and_oversized_sales(self):
        for quantity, status, residual in (
            (4, "filled", 0),
            (10, "filled", 0),
            (15, "partial", 5),
        ):
            for book_class in BOOKS:
                with self.subTest(quantity=quantity, book=book_class.__name__):
                    book = book_class()
                    book.process_event(limit(1, "b", qty=10))
                    result = book.process_event(market(2, "s", quantity))
                    self.assertEqual(result["status"], status)
                    self.assertEqual(result["unfilled_qty_units"], residual)
                    self.assertEqual(result["fills"][0]["qty_units"], min(quantity, 10))

    def test_fifo_uses_arrival_not_identifier(self):
        for book in self.for_each_book():
            book.process_event(limit(1, "z-first", price=100, qty=5))
            book.process_event(limit(2, "a-second", price=100, qty=5))
            result = book.process_event(market(3, "seller", 7))
            self.assertEqual(
                [fill["maker_id"] for fill in result["fills"]],
                ["z-first", "a-second"],
            )
            self.assertEqual(book.inspect_book()[0]["qty_units"], 3)
            self.assertEqual(book.inspect_book()[0]["arrival_seq"], 2)

    def test_best_price_before_fifo(self):
        for book in self.for_each_book():
            book.process_event(limit(1, "old-worse", price=99, qty=5))
            book.process_event(limit(2, "new-better", price=101, qty=5))
            result = book.process_event(market(3, "s", 6))
            self.assertEqual(
                [fill["maker_id"] for fill in result["fills"]],
                ["new-better", "old-worse"],
            )

    def test_partial_fill_preserves_priority(self):
        for book in self.for_each_book():
            book.process_event(limit(1, "first", qty=10))
            book.process_event(limit(2, "second", qty=10))
            book.process_event(market(3, "s1", 4))
            result = book.process_event(market(4, "s2", 8))
            self.assertEqual(
                [(fill["maker_id"], fill["qty_units"]) for fill in result["fills"]],
                [("first", 6), ("second", 2)],
            )

    def test_cancel_before_and_after_partial_fill(self):
        for book in self.for_each_book():
            book.process_event(limit(1, "b1", qty=10))
            first = book.process_event(cancel(2, "b1"))
            self.assertEqual(first["cancelled_qty_units"], 10)
            self.assertEqual(book.process_event(cancel(3, "b1"))["status"], "not_found")
            book.process_event(limit(4, "b2", qty=10))
            book.process_event(market(5, "s", 4))
            second = book.process_event(cancel(6, "b2"))
            self.assertEqual(second["cancelled_qty_units"], 6)
            self.assertEqual(book.inspect_book(), [])

    def test_cancel_after_full_fill_and_unknown(self):
        for book in self.for_each_book():
            book.process_event(limit(1, "b", qty=2))
            book.process_event(market(2, "s", 2))
            self.assertEqual(book.process_event(cancel(3, "b"))["status"], "not_found")
            self.assertEqual(book.process_event(cancel(4, "missing"))["status"], "not_found")
            self.assertEqual(book.last_accepted_seq, 4)

    def test_crossing_limit_buy_executes_at_resting_ask(self):
        for book in self.for_each_book():
            book.process_event(limit(1, "ask", side="SELL", price=105, qty=4))
            result = book.process_event(limit(2, "buy", side="BUY", price=110, qty=6))
            self.assertEqual(result["fills"][0]["price_ticks"], 105)
            self.assertEqual(result["status"], "resting")
            self.assertEqual(result["unfilled_qty_units"], 2)
            self.assertEqual(book.inspect_book()[0]["order_id"], "buy")

    def test_crossing_limit_sell_and_noncrossing_residual(self):
        for book in self.for_each_book():
            book.process_event(limit(1, "bid", price=100, qty=4))
            result = book.process_event(limit(2, "sell", side="SELL", price=99, qty=6))
            self.assertEqual(result["fills"][0]["price_ticks"], 100)
            self.assertEqual(result["unfilled_qty_units"], 2)
            self.assertEqual(book.inspect_book()[0]["side"], "SELL")
            book.process_event(limit(3, "low-bid", side="BUY", price=98, qty=1))
            book.validate_invariants()

    def test_rejections_are_atomic_and_do_not_advance_sequence(self):
        invalid_events = [
            limit(1, "bad-price", price=0),
            limit(1, "bad-qty", qty=-1),
            {**limit(1, "bad-side"), "side": "MAYBE"},
            {**limit(1, "float-price"), "price_ticks": 1.5},
            {**market(1, "float-qty", 1), "qty_units": True},
            {"seq": 1, "event_id": "x", "type": "UNKNOWN"},
        ]
        for book in self.for_each_book():
            for event in invalid_events:
                result = book.process_event(event)
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(book.inspect_book(), [])
                self.assertEqual(book.last_accepted_seq, 0)
            accepted = book.process_event(limit(1, "good"))
            self.assertEqual(accepted["status"], "resting")

    def test_duplicate_live_and_nonincreasing_sequence(self):
        for book in self.for_each_book():
            book.process_event(limit(2, "same"))
            snapshot = book.inspect_book()
            duplicate = book.process_event(limit(3, "same"))
            self.assertEqual(duplicate["status"], "rejected")
            nonincreasing = book.process_event(limit(2, "other"))
            self.assertEqual(nonincreasing["status"], "rejected")
            self.assertEqual(book.inspect_book(), snapshot)
            self.assertEqual(book.last_accepted_seq, 2)

    def test_long_queue_at_one_price(self):
        for book in self.for_each_book():
            for seq in range(1, 51):
                book.process_event(limit(seq, f"b{seq:02d}", qty=1))
            result = book.process_event(market(51, "seller", 50))
            self.assertEqual(
                [fill["maker_id"] for fill in result["fills"]],
                [f"b{seq:02d}" for seq in range(1, 51)],
            )
            self.assertEqual(book.inspect_book(), [])


class EquivalenceTests(unittest.TestCase):
    def test_versions_agree_after_every_generated_event(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                stream = list(events(scenario, 300, 7, 20))
                baseline = ListOrderBook()
                optimized = IndexedOrderBook()
                for event in stream:
                    self.assertEqual(
                        baseline.process_event(event), optimized.process_event(event)
                    )
                    self.assertEqual(baseline.inspect_book(), optimized.inspect_book())
                    baseline.validate_invariants()
                    optimized.validate_invariants()


if __name__ == "__main__":
    unittest.main()
