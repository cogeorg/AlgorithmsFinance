"""Valid but unusual prices, unmatched flow, and long-lived orders."""

import unittest

from support import (assert_case, cancel, cancellation, fill, limit,
                     order, sell, submission)


class MarketBehaviorTests(unittest.TestCase):
    def test_non_crossing_limits_and_unmatched_sell(self):
        assert_case(self, [
            (limit(1, "ask", "SELL", 200, 3),
             submission("e1", "ask", "resting", 3),
             [order("ask", "SELL", 200, 3, 1)]),
            (limit(2, "bid", "BUY", 100, 2),
             submission("e2", "bid", "resting", 2),
             [order("bid", "BUY", 100, 2, 2), order("ask", "SELL", 200, 3, 1)]),
            (sell(3, "s1", 5),
             submission("e3", "s1", "partial", 3,
                        [fill("bid", "s1", 100, 2)]),
             [order("ask", "SELL", 200, 3, 1)]),
            (sell(4, "s2", 1),
             submission("e4", "s2", "unfilled", 1),
             [order("ask", "SELL", 200, 3, 1)]),
        ])

    def test_extreme_valid_prices_and_maker_prices(self):
        high = 10**60
        assert_case(self, [
            (limit(1, "low_bid", "BUY", 1, 2),
             submission("e1", "low_bid", "resting", 2),
             [order("low_bid", "BUY", 1, 2, 1)]),
            (limit(2, "high_ask", "SELL", high, 1),
             submission("e2", "high_ask", "resting", 1),
             [order("low_bid", "BUY", 1, 2, 1),
              order("high_ask", "SELL", high, 1, 2)]),
            (limit(3, "huge_buy", "BUY", high + 1, 1),
             submission("e3", "huge_buy", "filled", 0,
                        [fill("high_ask", "huge_buy", high, 1)]),
             [order("low_bid", "BUY", 1, 2, 1)]),
            (limit(4, "cheap_sell", "SELL", 1, 1),
             submission("e4", "cheap_sell", "filled", 0,
                        [fill("low_bid", "cheap_sell", 1, 1)]),
             [order("low_bid", "BUY", 1, 1, 1)]),
        ])

    def test_old_unmatched_order_survives_unrelated_flow_then_cancels(self):
        steps = [
            (limit(1, "old_ask", "SELL", 200, 7),
             submission("e1", "old_ask", "resting", 7),
             [order("old_ask", "SELL", 200, 7, 1)])
        ]
        for seq in range(2, 22):
            # Each incoming market sell has no bid and cannot touch the ask.
            steps.append((sell(seq, f"s{seq}", seq),
                          submission(f"e{seq}", f"s{seq}", "unfilled", seq),
                          [order("old_ask", "SELL", 200, 7, 1)]))
        steps += [
            (cancel(22, "old_ask"),
             cancellation("e22", "old_ask", "cancelled", 7), []),
            (cancel(23, "old_ask"),
             cancellation("e23", "old_ask", "not_found", 0), []),
        ]
        assert_case(self, steps)


if __name__ == "__main__":
    unittest.main()
