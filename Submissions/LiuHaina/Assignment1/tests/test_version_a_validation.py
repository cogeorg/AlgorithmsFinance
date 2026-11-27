"""Additional boundary regressions; original shared tests remain unchanged."""
import unittest
from lob.version_a import OrderBook
from tests.test_orderbook import limit, cancel, sell, order, fill


class TestVersionAValidation(unittest.TestCase):
    def test_malformed_events_are_rejected_atomically(self):
        book = OrderBook()
        book.process_event(limit(1, "b"))
        original = book.inspect_book()
        events = [None, [], {}, dict(seq=2, event_id="e2", type=[])]
        for key in ("seq", "event_id", "type", "order_id", "side", "price_ticks", "qty_units"):
            event = limit(2, "new")
            del event[key]
            events.append(event)
        for value in (True, 1.5, "2", None):
            event = limit(2, "new")
            event["seq"] = value
            events.append(event)
        for event in events:
            with self.subTest(event=event):
                self.assertEqual(book.process_event(event)["status"], "rejected")
                self.assertEqual(book.inspect_book(), original)
                self.assertEqual(book.last_seq, 1)
        self.assertEqual(book.process_event(cancel(2, "b"))["status"], "cancelled")

    def test_inspection_and_input_do_not_expose_live_state(self):
        book = OrderBook()
        event = limit(1, "b")
        book.AddLimitOrder(event)
        event["qty_units"] = 999
        snapshot = book.inspect_book()
        snapshot[0]["qty_units"] = 999
        snapshot.clear()
        self.assertEqual(book.inspect_book(), [order("b")])

    def test_current_event_fills_only_and_unknown_cancel_advances_sequence(self):
        book = OrderBook()
        book.AddLimitOrder(limit(1, "b"))
        self.assertEqual(book.CancelOrder(cancel(2, "absent"))["status"], "not_found")
        self.assertEqual(book.last_seq, 2)
        self.assertEqual(book.FillMarketSell(sell(3, "t1", 2))["fills"], [fill("b", "t1", qty=2)])
        self.assertEqual(book.FillMarketSell(sell(4, "t2", 2))["fills"], [fill("b", "t2", qty=2)])

    def test_crossing_limit_stops_at_ineligible_depth(self):
        book = OrderBook()
        book.AddLimitOrder(limit(1, "cheap", "SELL", 95, 2))
        book.AddLimitOrder(limit(2, "expensive", "SELL", 105, 4))
        result = book.AddLimitOrder(limit(3, "buy", "BUY", 100, 5))
        self.assertEqual(result["fills"], [fill("cheap", "buy", 95, 2)])
        self.assertEqual((result["status"], result["unfilled_qty_units"]), ("resting", 3))
        self.assertEqual(book.inspect_book(), [order("buy", "BUY", 100, 3, 3),
                                              order("expensive", "SELL", 105, 4, 2)])
