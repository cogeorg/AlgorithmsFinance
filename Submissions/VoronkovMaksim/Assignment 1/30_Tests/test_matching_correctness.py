"""Hand-calculated price-time outcomes for both future versions."""

import gzip
import json
import unittest

from support import (ROOT, VERSIONS, assert_case, assert_step, cancel,
                     cancellation, fill, limit, load_book, order, sell,
                     submission)


class MatchingCorrectnessTests(unittest.TestCase):
    def test_small_seeded_streams_compare_both_versions_after_each_event(self):
        specs = (("buildup", 42), ("crowded", 43), ("mixed", 44),
                 ("sweep", 42), ("cancel_churn", 43))
        for scenario, seed in specs:
            with self.subTest(scenario=scenario, seed=seed):
                books = [load_book(version) for version in VERSIONS]
                path = ROOT / "10_Data" / f"phase1_{scenario}_80_seed{seed}.jsonl.gz"
                with gzip.open(path, "rt", encoding="utf-8") as source:
                    for line in source:
                        incoming = json.loads(line)
                        outcomes = [book.process_event(dict(incoming)) for book in books]
                        states = [book.inspect_book() for book in books]
                        self.assertEqual(outcomes[0], outcomes[1], incoming)
                        self.assertEqual(states[0], states[1], incoming)
                        if incoming["type"] in ("LIMIT", "MARKET_SELL"):
                            self.assertEqual(
                                incoming["qty_units"],
                                sum(f["qty_units"] for f in outcomes[0]["fills"])
                                + outcomes[0]["unfilled_qty_units"], incoming)
                        for state in states:
                            bids = [o["price_ticks"] for o in state if o["side"] == "BUY"]
                            asks = [o["price_ticks"] for o in state if o["side"] == "SELL"]
                            self.assertTrue(all(o["qty_units"] > 0 for o in state))
                            if bids and asks:
                                self.assertLess(max(bids), min(asks))

    def test_supplied_worked_example(self):
        data = ROOT / "10_Data"
        events = [json.loads(line) for line in
                  (data / "worked_example.jsonl").read_text().splitlines()]
        expected = json.loads((data / "worked_expected.json").read_text())
        books = [
            [order("b1", "BUY", 6000000, 100000000, 1)],
            [order("b1", "BUY", 6000000, 100000000, 1),
             order("b2", "BUY", 6000000, 100000000, 2)],
            [order("b1", "BUY", 6000000, 100000000, 1),
             order("b2", "BUY", 6000000, 100000000, 2),
             order("b3", "BUY", 5990000, 300000000, 3)],
            [order("b1", "BUY", 6000000, 100000000, 1),
             order("b2", "BUY", 6000000, 100000000, 2),
             order("b3", "BUY", 5990000, 300000000, 3),
             order("b4", "BUY", 5970000, 500000000, 4)],
            [order("b1", "BUY", 6000000, 100000000, 1),
             order("b2", "BUY", 6000000, 100000000, 2),
             order("b3", "BUY", 5990000, 300000000, 3),
             order("b4", "BUY", 5970000, 500000000, 4),
             order("a1", "SELL", 6010000, 200000000, 5)],
        ]
        for version in VERSIONS:
            with self.subTest(version=version):
                book = load_book(version)
                for incoming, remaining in zip(events[:-1], books):
                    assert_step(self, book, incoming,
                                submission(incoming["event_id"], incoming["order_id"],
                                           "resting", incoming["qty_units"]), remaining)
                result = assert_step(self, book, events[-1],
                                     expected["market_sell_result"],
                                     expected["remaining_orders"])
                proceeds = sum(f["price_ticks"] * f["qty_units"]
                               for f in result["fills"])
                self.assertEqual(proceeds, 3594000000000000)
                self.assertEqual(proceeds, expected["gross_proceeds_tick_units"])

    def test_empty_one_order_and_sell_sizes(self):
        assert_case(self, [(sell(1, "s", 4),
                            submission("e1", "s", "unfilled", 4), [])])
        cases = (
            (4, "filled", 0, [fill("b", "s", 100, 4)],
             [order("b", "BUY", 100, 6, 1)]),
            (10, "filled", 0, [fill("b", "s", 100, 10)], []),
            (14, "partial", 4, [fill("b", "s", 100, 10)], []),
        )
        for quantity, status, residual, fills, remaining in cases:
            with self.subTest(quantity=quantity):
                assert_case(self, [
                    (limit(1, "b", "BUY", 100, 10),
                     submission("e1", "b", "resting", 10),
                     [order("b", "BUY", 100, 10, 1)]),
                    (sell(2, "s", quantity),
                     submission("e2", "s", status, residual, fills), remaining),
                ])

    def test_best_price_fifo_and_identifier_spelling(self):
        steps = [
            (limit(1, "z_old", "BUY", 100, 2),
             submission("e1", "z_old", "resting", 2),
             [order("z_old", "BUY", 100, 2, 1)]),
            (limit(2, "a_low", "BUY", 99, 3),
             submission("e2", "a_low", "resting", 3),
             [order("z_old", "BUY", 100, 2, 1), order("a_low", "BUY", 99, 3, 2)]),
            (limit(3, "a_new", "BUY", 100, 4),
             submission("e3", "a_new", "resting", 4),
             [order("z_old", "BUY", 100, 2, 1),
              order("a_new", "BUY", 100, 4, 3),
              order("a_low", "BUY", 99, 3, 2)]),
            (sell(4, "s", 7),
             submission("e4", "s", "filled", 0,
                        [fill("z_old", "s", 100, 2),
                         fill("a_new", "s", 100, 4),
                         fill("a_low", "s", 99, 1)]),
             [order("a_low", "BUY", 99, 2, 2)]),
        ]
        assert_case(self, steps)

    def test_partial_maker_keeps_fifo_priority(self):
        assert_case(self, [
            (limit(1, "first", "BUY", 100, 5),
             submission("e1", "first", "resting", 5),
             [order("first", "BUY", 100, 5, 1)]),
            (limit(2, "second", "BUY", 100, 3),
             submission("e2", "second", "resting", 3),
             [order("first", "BUY", 100, 5, 1), order("second", "BUY", 100, 3, 2)]),
            (sell(3, "s1", 2),
             submission("e3", "s1", "filled", 0, [fill("first", "s1", 100, 2)]),
             [order("first", "BUY", 100, 3, 1), order("second", "BUY", 100, 3, 2)]),
            (sell(4, "s2", 4),
             submission("e4", "s2", "filled", 0,
                        [fill("first", "s2", 100, 3), fill("second", "s2", 100, 1)]),
             [order("second", "BUY", 100, 2, 2)]),
        ])

    def test_cancel_before_after_partial_full_and_repeat(self):
        assert_case(self, [
            (limit(1, "a", "BUY", 100, 5),
             submission("e1", "a", "resting", 5), [order("a", "BUY", 100, 5, 1)]),
            (cancel(2, "a"), cancellation("e2", "a", "cancelled", 5), []),
            (cancel(3, "a"), cancellation("e3", "a", "not_found", 0), []),
            (cancel(4, "missing"), cancellation("e4", "missing", "not_found", 0), []),
            (limit(5, "b", "BUY", 100, 5),
             submission("e5", "b", "resting", 5), [order("b", "BUY", 100, 5, 5)]),
            (sell(6, "s", 2),
             submission("e6", "s", "filled", 0, [fill("b", "s", 100, 2)]),
             [order("b", "BUY", 100, 3, 5)]),
            (cancel(7, "b"), cancellation("e7", "b", "cancelled", 3), []),
            (limit(8, "c", "BUY", 100, 1),
             submission("e8", "c", "resting", 1), [order("c", "BUY", 100, 1, 8)]),
            (sell(9, "s2", 1),
             submission("e9", "s2", "filled", 0, [fill("c", "s2", 100, 1)]), []),
            (cancel(10, "c"), cancellation("e10", "c", "not_found", 0), []),
        ])

    def test_crossing_limits_and_resting_residual(self):
        assert_case(self, [
            (limit(1, "ask", "SELL", 101, 3),
             submission("e1", "ask", "resting", 3),
             [order("ask", "SELL", 101, 3, 1)]),
            (limit(2, "buy", "BUY", 105, 5),
             submission("e2", "buy", "resting", 2,
                        [fill("ask", "buy", 101, 3)]),
             [order("buy", "BUY", 105, 2, 2)]),
            (limit(3, "sell", "SELL", 99, 1),
             submission("e3", "sell", "filled", 0,
                        [fill("buy", "sell", 105, 1)]),
             [order("buy", "BUY", 105, 1, 2)]),
            (limit(4, "low_buy", "BUY", 98, 2),
             submission("e4", "low_buy", "resting", 2),
             [order("buy", "BUY", 105, 1, 2),
              order("low_buy", "BUY", 98, 2, 4)]),
            (limit(5, "high_ask", "SELL", 106, 2),
             submission("e5", "high_ask", "resting", 2),
             [order("buy", "BUY", 105, 1, 2),
              order("low_buy", "BUY", 98, 2, 4),
              order("high_ask", "SELL", 106, 2, 5)]),
        ])

    def test_long_queue_at_one_price(self):
        steps = []
        for seq in range(1, 31):
            # Each maker has one unit; the expected queue is independent of an engine.
            remaining = [order(f"b{i}", "BUY", 100, 1, i)
                         for i in range(1, seq + 1)]
            steps.append((limit(seq, f"b{seq}", "BUY", 100, 1),
                          submission(f"e{seq}", f"b{seq}", "resting", 1), remaining))
        steps.append((sell(31, "s", 31),
                      submission("e31", "s", "partial", 1,
                                 [fill(f"b{i}", "s", 100, 1)
                                  for i in range(1, 31)]), []))
        assert_case(self, steps)


if __name__ == "__main__":
    unittest.main()
