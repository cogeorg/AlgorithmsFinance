"""Project identifier policy for both order-book versions."""
import copy
import unittest

from support import VERSIONS, cancel, limit, load_book, sell


class IdentifierTests(unittest.TestCase):
    def test_valid_ids_and_distinct_string_and_integer(self):
        outputs = []
        for version in VERSIONS:
            with self.subTest(version=version):
                b = load_book(version)
                events = [limit(1, 0, 'BUY', 100, 1),
                          limit(2, -7, 'BUY', 100, 1),
                          limit(3, 123, 'BUY', 100, 1),
                          limit(4, '123', 'BUY', 100, 1),
                          cancel(5, 0), cancel(6, -7),
                          sell(7, -9, 2), cancel(8, 999)]
                events[0]['event_id'] = 0
                events[1]['event_id'] = -12
                events[2]['event_id'] = 123
                events[3]['event_id'] = '123'
                original = copy.deepcopy(events)
                results = [b.process_event(e) for e in events]
                self.assertEqual(events, original)
                self.assertEqual([x['status'] for x in results],
                                 ['resting']*4 + ['cancelled', 'cancelled', 'filled', 'not_found'])
                self.assertEqual([f['maker_id'] for f in results[6]['fills']], [123, '123'])
                self.assertEqual(b.inspect_book(), [])
                outputs.append(results)
        self.assertEqual(outputs[0], outputs[1])

    def test_invalid_identifiers_are_atomic(self):
        invalid = [True, False, 1.0, -1.5, None, [], {}, '', ('tuple',)]
        for field in ('event_id', 'order_id', 'target_order_id'):
            for value in invalid:
                for version in VERSIONS:
                    with self.subTest(field=field, value=value, version=version):
                        b = load_book(version)
                        b.process_event(limit(1, 'base', 'BUY', 100, 5))
                        before = b.inspect_book()
                        bad = cancel(2, 'base') if field == 'target_order_id' else limit(2, 'new', 'BUY', 99, 1)
                        bad[field] = value
                        saved = copy.deepcopy(bad)
                        result = b.process_event(bad)
                        self.assertEqual(result['status'], 'rejected')
                        self.assertTrue(result.get('reason'))
                        self.assertEqual(bad, saved)
                        self.assertEqual(b.inspect_book(), before)
                        accepted = b.process_event(cancel(2, 'base'))
                        self.assertEqual(accepted['status'], 'cancelled')
                        self.assertEqual(accepted['cancelled_qty_units'], 5)

    def test_invalid_market_sell_order_ids(self):
        for version in VERSIONS:
            for value in (True, 1.0, None, [], {}, ''):
                with self.subTest(version=version, value=value):
                    b = load_book(version)
                    incoming = sell(1, value, 1)
                    before = copy.deepcopy(incoming)
                    result = b.process_event(incoming)
                    self.assertEqual(result['status'], 'rejected')
                    self.assertTrue(result.get('reason'))
                    self.assertEqual(incoming, before)
                    self.assertEqual(b.inspect_book(), [])
                    self.assertEqual(b.process_event(sell(1, 'valid', 1))['status'], 'unfilled')

    def test_duplicate_live_integer_id_and_valid_unknown_cancel(self):
        for version in VERSIONS:
            with self.subTest(version=version):
                b = load_book(version)
                b.process_event(limit(1, -1, 'BUY', 100, 2))
                state = b.inspect_book()
                duplicate = limit(2, -1, 'SELL', 200, 2)
                saved = copy.deepcopy(duplicate)
                result = b.process_event(duplicate)
                self.assertEqual(result['status'], 'rejected')
                self.assertTrue(result['reason'])
                self.assertEqual(duplicate, saved)
                self.assertEqual(b.inspect_book(), state)
                result = b.process_event(cancel(2, 0))
                self.assertEqual(result['status'], 'not_found')
                self.assertEqual(result['cancelled_qty_units'], 0)
                self.assertEqual(b.inspect_book(), state)


if __name__ == '__main__':
    unittest.main()
