"""Focused checks for indexed queues and price-heap cleanup."""
import unittest
from support import load_book, limit, cancel, sell, fill


class CleanupTests(unittest.TestCase):
    def test_stale_best_price_is_removed_before_matching(self):
        b = load_book('order_book_v2')
        b.process_event(limit(1, 'best', 'BUY', 110, 1))
        b.process_event(limit(2, 'next', 'BUY', 100, 1))
        b.process_event(cancel(3, 'best'))
        self.assertIn(-110, b.bid_heap)
        result = b.process_event(sell(4, 's', 1))
        self.assertEqual(result['fills'], [fill('next', 's', 100, 1)])
        self.assertEqual(b.orders_by_id, {})
        self.assertEqual(b.bid_heap, [])

    def test_middle_cancel_and_fifo(self):
        b = load_book('order_book_v2')
        for i in range(1, 4):
            b.process_event(limit(i, f'b{i}', 'BUY', 100, 2))
        self.assertEqual(b.process_event(cancel(4, 'b2'))['cancelled_qty_units'], 2)
        self.assertNotIn('b2', b.orders_by_id)
        self.assertNotIn('b2', b.bids_by_price[100])
        result = b.process_event(sell(5, 's', 3))
        self.assertEqual(result['fills'], [fill('b1', 's', 100, 2), fill('b3', 's', 100, 1)])
        self.assertEqual(b.orders_by_id['b3']['arrival_seq'], 3)

    def test_stale_recreation_and_cleanup_on_both_sides(self):
        for side in ('BUY', 'SELL'):
            with self.subTest(side=side):
                b = load_book('order_book_v2')
                b.process_event(limit(1, 'anchor', side, 100, 1))
                b.process_event(limit(2, 'old', side, 99, 1))
                b.process_event(cancel(3, 'old'))
                b.process_event(limit(4, 'new', side, 99, 2))
                heap = b.bid_heap if side == 'BUY' else b.ask_heap
                prices = b.bid_heap_prices if side == 'BUY' else b.ask_heap_prices
                self.assertEqual(len(heap), len(set(heap)))
                self.assertEqual(len(heap), len(prices))
                incoming = limit(5, 'cross', 'SELL' if side == 'BUY' else 'BUY',
                                 1 if side == 'BUY' else 200, 3)
                result = b.process_event(incoming)
                expected = ['anchor', 'new'] if side == 'BUY' else ['new', 'anchor']
                self.assertEqual([f['maker_id'] for f in result['fills']], expected)
                self.assertEqual(b.orders_by_id, {})
                self.assertEqual(heap, [])
                self.assertEqual(prices, set())

    def test_churn_rebuilds_heaps_and_removes_inactive_orders(self):
        for side in ('BUY', 'SELL'):
            b = load_book('order_book_v2')
            b.process_event(limit(1, 'anchor', side, 100, 1))
            for i in range(100):
                identifier = f'x{i}'
                b.process_event(limit(2*i+2, identifier, side, 1000+i, 1))
                b.process_event(cancel(2*i+3, identifier))
                levels = b.bids_by_price if side == 'BUY' else b.asks_by_price
                heap = b.bid_heap if side == 'BUY' else b.ask_heap
                self.assertLessEqual(len(heap), 3 * len(levels))
                self.assertEqual(set(b.orders_by_id), {'anchor'})
                self.assertEqual(sum(len(q) for q in levels.values()), 1)
            b.process_event(cancel(202, 'anchor'))
            self.assertEqual(b.orders_by_id, {})
            self.assertEqual(heap, [])


if __name__ == '__main__':
    unittest.main()
