"""Invalid inputs, boundary values, and unchanged-state checks."""

import unittest

from support import (VERSIONS, assert_case, assert_step, event, limit,
                     load_book, order, submission)


class InputRobustnessTests(unittest.TestCase):
    def test_empty_stream_and_one_order(self):
        assert_case(self, [])
        assert_case(self, [(limit(1, "b", "BUY", 1, 1),
                            submission("e1", "b", "resting", 1),
                            [order("b", "BUY", 1, 1, 1)])])

    def test_bad_price_and_quantity(self):
        for field in ("price_ticks", "qty_units"):
            for value in (0, -1, 1.5, "1", True, None):
                with self.subTest(field=field, value=value):
                    bad = limit(2, "bad", "BUY", 100, 10)
                    bad[field] = value
                    self.check_rejected_seq_reusable(bad)

    def test_missing_fields_and_invalid_events(self):
        bad_events = [
            {},
            {"seq": 2, "event_id": "e2"},
            event(2, "LIMIT", order_id="x", side="BUY", qty_units=1),
            event(2, "MARKET_SELL", order_id="x"),
            event(2, "CANCEL"),
            event(2, "OTHER"),
            limit(2, "x", "HOLD", 100, 1),
            limit(2, "x", "buy", 100, 1),
            limit(2, "base", "BUY", 100, 1),
        ]
        for bad in bad_events:
            with self.subTest(bad=bad):
                self.check_rejected_seq_reusable(bad)

    def test_invalid_sequence_values_and_order(self):
        for value in (0, -1, 1, 1.5, "2", True, None):
            with self.subTest(seq=value):
                bad = limit(2, "bad", "BUY", 100, 1)
                bad["seq"] = value
                self.check_rejected_seq_reusable(bad)

        # A duplicate arrival rank is rejected after that rank has succeeded.
        for version in VERSIONS:
            with self.subTest(version=version):
                book = load_book(version)
                b1 = [order("base", "BUY", 100, 10, 1)]
                assert_step(self, book, limit(1, "base", "BUY", 100, 10),
                            submission("e1", "base", "resting", 10), b1)
                b2 = b1 + [order("second", "BUY", 99, 1, 2)]
                assert_step(self, book, limit(2, "second", "BUY", 99, 1),
                            submission("e2", "second", "resting", 1), b2)
                for seq in (2, 1):
                    bad = limit(seq, f"bad{seq}", "BUY", 98, 1)
                    self.assert_rejected(book, bad, b2)
                assert_step(self, book, limit(3, "third", "BUY", 98, 1),
                            submission("e3", "third", "resting", 1),
                            b2 + [order("third", "BUY", 98, 1, 3)])

    def test_positive_integer_extremes_have_no_arbitrary_cap(self):
        huge = 10**80
        assert_case(self, [
            (limit(1, "tiny", "BUY", 1, 1),
             submission("e1", "tiny", "resting", 1),
             [order("tiny", "BUY", 1, 1, 1)]),
            (limit(2, "huge", "BUY", huge, huge),
             submission("e2", "huge", "resting", huge),
             [order("huge", "BUY", huge, huge, 2),
              order("tiny", "BUY", 1, 1, 1)]),
        ])

    def check_rejected_seq_reusable(self, bad):
        for version in VERSIONS:
            with self.subTest(version=version):
                book = load_book(version)
                expected = [order("base", "BUY", 100, 10, 1)]
                assert_step(self, book, limit(1, "base", "BUY", 100, 10),
                            submission("e1", "base", "resting", 10), expected)
                self.assert_rejected(book, bad, expected)
                assert_step(self, book, limit(2, "good", "BUY", 99, 1),
                            submission("e2", "good", "resting", 1),
                            expected + [order("good", "BUY", 99, 1, 2)])

    def assert_rejected(self, book, bad, expected_book):
        before = dict(bad)
        result = book.process_event(bad)
        self.assertEqual(bad, before)
        self.assertEqual(result.get("status"), "rejected")
        self.assertTrue(result.get("reason"))
        if "event_id" in bad:
            self.assertEqual(result.get("event_id"), bad["event_id"])
        self.assertEqual(book.inspect_book(), expected_book)


if __name__ == "__main__":
    unittest.main()
