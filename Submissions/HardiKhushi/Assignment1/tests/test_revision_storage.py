"""Additional storage regression checks; original contract tests stay unchanged."""
import unittest
from orderbook.revised import OrderBook
from test_contract import cancel, limit, market


class TestRevisionStorage(unittest.TestCase):
    def test_churn_releases_logical_entries_and_prices(self):
        book = OrderBook()
        for i in range(1, 3001):
            book.process(limit(2*i-1, f"b{i}", price=100+i))
            book.process(cancel(2*i, f"b{i}"))
        self.assertEqual(book.by_id, {})
        self.assertEqual(book.levels, {"BUY": {}, "SELL": {}})
        self.assertEqual(book.prices, {"BUY": [], "SELL": []})
        self.assertEqual(book.storage(), dict(active_orders=0, stored_orders=0,
                                             occupied_prices=0, stale_entries=0))

    def test_price_can_disappear_and_reappear_with_new_fifo(self):
        book = OrderBook()
        for row in [limit(1, "old"), cancel(2, "old"), limit(3, "new"),
                    limit(4, "later"), market(5, 11)]:
            result = book.process(row)
        self.assertEqual([f["maker_id"] for f in result["fills"]], ["new", "later"])
        self.assertEqual(book.inspect()[0]["qty_units"], 9)

    def test_direct_method_wrong_type_is_atomic(self):
        book = OrderBook()
        self.assertEqual(book.FillMarketSell(limit(1, "b"))["status"], "rejected")
        self.assertEqual(book.last_seq, 0)
        self.assertEqual(book.inspect(), [])
