import copy
import json
from pathlib import Path
import random
import unittest

from orderbook import BaselineBook, RevisedBook
from generate_orders import events


def limit(seq, oid, side='BUY', price=100, qty=10):
    return dict(seq=seq, event_id=f'e{seq}', type='LIMIT', order_id=oid,
                side=side, price_ticks=price, qty_units=qty)


def sell(seq, qty):
    return dict(seq=seq, event_id=f'e{seq}', type='MARKET_SELL',
                order_id=f's{seq}', qty_units=qty)


def cancel(seq, oid):
    return dict(seq=seq, event_id=f'e{seq}', type='CANCEL', target_order_id=oid)


class Contract:
    def setUp(self):
        self.book = self.engine()

    def test_empty(self):
        self.assertEqual(self.book.inspect(), [])
        r = self.book.process(sell(1, 10))
        self.assertEqual((r['status'], r['unfilled_qty_units'], r['fills']),
                         ('unfilled', 10, []))

    def test_single_smaller_equal_larger(self):
        for qty, status, residual, remaining in [(4, 'filled', 0, 6),
                                                (10, 'filled', 0, 0),
                                                (15, 'partial', 5, 0)]:
            with self.subTest(qty=qty):
                b = self.engine()
                b.process(limit(1, 'b'))
                r = b.process(sell(2, qty))
                self.assertEqual((r['status'], r['unfilled_qty_units']), (status, residual))
                self.assertEqual(r['fills'], [dict(maker_id='b', taker_id='s2',
                                                  price_ticks=100, qty_units=min(qty, 10))])
                self.assertEqual(sum(o['qty_units'] for o in b.inspect()), remaining)

    def test_fifo_levels_partial_and_cancel(self):
        for e in [limit(1, 'z', price=102), limit(2, 'a', price=102),
                  limit(3, 'low', price=100)]:
            self.book.process(e)
        r = self.book.process(sell(4, 15))
        self.assertEqual([(f['maker_id'], f['qty_units']) for f in r['fills']],
                         [('z', 10), ('a', 5)])
        self.assertEqual(self.book.process(sell(5, 2))['fills'][0]['maker_id'], 'a')
        self.assertEqual(self.book.process(cancel(6, 'a'))['cancelled_qty_units'], 3)
        for seq, oid in [(7, 'z'), (8, 'a'), (9, 'unknown')]:
            r = self.book.process(cancel(seq, oid))
            self.assertEqual((r['status'], r['cancelled_qty_units']), ('not_found', 0))
        self.assertEqual(self.book.process(sell(10, 20))['unfilled_qty_units'], 10)

    def test_cancel_before_fill(self):
        self.book.process(limit(1, 'b'))
        self.assertEqual(self.book.process(cancel(2, 'b'))['cancelled_qty_units'], 10)
        self.assertEqual(self.book.inspect(), [])

    def test_crossing_both_directions_and_residual(self):
        for resting_side, incoming_side, resting_price, incoming_price in [
                ('SELL', 'BUY', 100, 105), ('BUY', 'SELL', 105, 100)]:
            with self.subTest(side=incoming_side):
                b = self.engine()
                b.process(limit(1, 'maker', resting_side, resting_price, 4))
                r = b.process(limit(2, 'taker', incoming_side, incoming_price, 10))
                self.assertEqual(r['fills'], [dict(maker_id='maker', taker_id='taker',
                                                  price_ticks=resting_price, qty_units=4)])
                self.assertEqual((r['status'], r['unfilled_qty_units']), ('resting', 6))
                self.assertEqual(b.inspect(), [dict(order_id='taker', side=incoming_side,
                                                   price_ticks=incoming_price, qty_units=6,
                                                   arrival_seq=2)])

    def test_noncrossing_and_snapshot_isolation(self):
        self.book.process(limit(1, 'b', 'BUY', 99))
        self.book.process(limit(2, 'a', 'SELL', 101))
        snap = self.book.inspect()
        snap[0]['qty_units'] = -1
        self.assertEqual(self.book.inspect()[0]['qty_units'], 10)
        self.assertEqual(len(self.book.inspect()), 2)

    def test_invalid_is_atomic_and_does_not_advance_sequence(self):
        self.book.process(limit(1, 'b'))
        bad = [limit(2, 'b'), limit(1, 'old'), limit(2, 'x', side='OTHER')]
        for field in ['price_ticks', 'qty_units']:
            for value in [0, -1, 1.5, True, '10', None]:
                e = limit(2, 'x')
                e[field] = value
                bad.append(e)
        for value in [True, 0, -1, 1.5, '2', None]:
            e = limit(2, 'x'); e['seq'] = value; bad.append(e)
        bad += [dict(seq=2, event_id='x', type='BOGUS'), {}, None,
                dict(seq=2, event_id='x', type=[]),
                dict(seq=2, event_id='x', type={}),
                dict(seq=2, event_id='x', type='CANCEL'),
                dict(limit(2, 'x'), order_id=[])]
        before = self.book.inspect()
        for e in bad:
            with self.subTest(event=e):
                self.assertEqual(self.book.process(e)['status'], 'rejected')
                self.assertEqual(self.book.inspect(), before)
        self.assertEqual(self.book.process(sell(2, 10))['status'], 'filled')

    def test_worked_example(self):
        root = Path(__file__).resolve().parents[1]
        for line in (root / 'data/worked_example.jsonl').read_text().splitlines():
            result = self.book.process(json.loads(line))
        expected = json.loads((root / 'data/worked_expected.json').read_text())
        self.assertEqual(result, expected['market_sell_result'])
        self.assertEqual(self.book.inspect(), expected['remaining_orders'])
        self.assertEqual(sum(f['price_ticks'] * f['qty_units'] for f in result['fills']),
                         3594000000000000)

    def test_long_queue(self):
        for i in range(1, 1001):
            self.book.process(limit(i, f'order{1001-i}', qty=1))
        for seq in range(1001, 1101):
            self.book.process(cancel(seq, f'order{seq-1000}'))
        r = self.book.process(sell(1101, 950))
        self.assertEqual([f['maker_id'] for f in r['fills']],
                         [f'order{i}' for i in range(1000, 100, -1)])
        self.assertEqual(r['unfilled_qty_units'], 50)
        self.assertEqual(self.book.inspect(), [])


class TestBaseline(Contract, unittest.TestCase):
    engine = BaselineBook


class TestRevised(Contract, unittest.TestCase):
    engine = RevisedBook


class TestDifferential(unittest.TestCase):
    def test_heap_churn_with_persistent_best(self):
        book = RevisedBook()
        book.process(limit(1, 'anchor', price=10000))
        for i in range(2, 2002, 2):
            book.process(limit(i, f'b{i}', price=i))
            book.process(cancel(i + 1, f'b{i}'))
            self.assertLessEqual(len(book.heaps['BUY']), 2 * len(book.queues['BUY']) + 32)
        self.assertEqual(len(book.inspect()), 1)
        self.assertEqual(book.process(sell(2002, 10))['fills'][0]['maker_id'], 'anchor')

    def test_generated_every_event_and_conservation(self):
        for scenario in ['buildup', 'crowded', 'mixed', 'sweep', 'cancel_churn']:
            for seed in [42, 43, 44]:
                a, b = BaselineBook(), RevisedBook()
                for event in events(scenario, 250, seed, 10):
                    before = {o['order_id']: o for o in a.inspect()}
                    result = a.process(copy.deepcopy(event))
                    self.assertEqual(result, b.process(copy.deepcopy(event)))
                    after = a.inspect()
                    self.assertEqual(after, b.inspect())
                    self.assertEqual(len(after), len({o['order_id'] for o in after}))
                    self.assertTrue(all(o['qty_units'] > 0 for o in after))
                    bids = [o['price_ticks'] for o in after if o['side'] == 'BUY']
                    asks = [o['price_ticks'] for o in after if o['side'] == 'SELL']
                    self.assertTrue(not bids or not asks or max(bids) < min(asks))
                    if event['type'] != 'CANCEL':
                        fills = result['fills']
                        self.assertEqual(event['qty_units'],
                                         sum(f['qty_units'] for f in fills) + result['unfilled_qty_units'])
                        remaining = {o['order_id']: o['qty_units'] for o in after}
                        for oid, maker in before.items():
                            executed = sum(f['qty_units'] for f in fills if f['maker_id'] == oid)
                            self.assertEqual(maker['qty_units'] - executed, remaining.get(oid, 0))
                    else:
                        target = event['target_order_id']
                        self.assertEqual(result['cancelled_qty_units'], before.get(target, {}).get('qty_units', 0))


if __name__ == '__main__':
    unittest.main()
