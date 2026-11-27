"""Independent full-tree policy checks and observed-price crossing checks."""

from datetime import datetime, timedelta, timezone
from fractions import Fraction
from functools import lru_cache
from itertools import product
from pathlib import Path
import unittest

from exercise import first_exercise
from market_data import PriceWindow
from price_american_put import price_american_put
from price_american_put_original import price_american_put as original_price


def exact_boundary(spot, strike, up, down, rate, steps):
    """Keep an exact rational full tree; do not reuse the rolling arrays."""
    q = (rate - down) / (up - down)

    def stock(t, j):
        return spot * up**j * down**(t - j)

    @lru_cache(None)
    def value(t, j):
        payoff = max(strike - stock(t, j), 0)
        if t == steps:
            return payoff
        return max(payoff, (q * value(t + 1, j + 1) + (1 - q) * value(t + 1, j)) / rate)

    boundary = []
    for t in range(steps + 1):
        optimal = []
        for j in range(t + 1):
            payoff = max(strike - stock(t, j), 0)
            if payoff > 0 and payoff == value(t, j):
                optimal.append(stock(t, j))
        boundary.append(max(optimal) if optimal else None)
    return value(0, 0), boundary


class BoundaryTests(unittest.TestCase):
    def test_slide_boundary(self):
        price, boundary = price_american_put(100, 100, 1.2, 0.8, 1.05, 2, return_boundary=True)
        self.assertAlmostEqual(price, float(Fraction(1175, 147)))
        self.assertIsNone(boundary[0])
        self.assertAlmostEqual(boundary[1], 80)
        self.assertAlmostEqual(boundary[2], 96)

    def test_matches_exact_full_tree_policies_and_original_prices(self):
        up, down = Fraction(6, 5), Fraction(4, 5)
        for steps, spot, strike, rate in product(
            range(7), (60, 100, 140), (80, 100, 120),
            (Fraction(19, 20), Fraction(1), Fraction(21, 20)),
        ):
            with self.subTest(steps=steps, spot=spot, strike=strike, rate=rate):
                expected, boundaries = exact_boundary(spot, strike, up, down, rate, steps)
                args = (spot, strike, float(up), float(down), float(rate), steps)
                actual, found = price_american_put(*args, return_boundary=True)
                self.assertAlmostEqual(actual, float(expected), places=10)
                self.assertAlmostEqual(actual, original_price(*args), places=10)
                self.assertEqual(len(found), steps + 1)
                for a, b in zip(found, boundaries):
                    if b is None:
                        self.assertIsNone(a)
                    else:
                        self.assertIsNotNone(a)
                        self.assertAlmostEqual(a, float(b), places=10)

    def test_no_worthless_exercise_ties(self):
        price, boundary = price_american_put(100, 0, 1.2, 0.8, 1.05, 3, return_boundary=True)
        self.assertEqual(price, 0)
        self.assertEqual(boundary, [None] * 4)

    def test_expiry_only(self):
        self.assertEqual(price_american_put(80, 100, 1.2, 0.8, 1.05, 0, return_boundary=True), (20, [80]))
        self.assertEqual(price_american_put(100, 100, 1.2, 0.8, 1.05, 0, return_boundary=True), (0, [None]))

    def test_rejects_numerically_unsafe_tree_before_allocation(self):
        for args in ((100, 100, 2, 0.5, 1.05, 10000), (1e308, 100, 2, 0.5, 1.05, 2)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                price_american_put(*args, return_boundary=True)


class ObservedPathTests(unittest.TestCase):
    def setUp(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.window = PriceWindow(
            Path("fixture.csv"), "fixture", 3,
            tuple(start + timedelta(hours=t) for t in range(3)), (100, 75, 60),
        )

    def test_first_crossing_and_equality(self):
        found = first_exercise(self.window, [None, 75, 70], 100)
        self.assertEqual(found["t"], 1)
        self.assertEqual(found["payoff"], 25)
        self.assertFalse(found["at_expiry"])

    def test_never_and_expiry_crossing(self):
        self.assertIsNone(first_exercise(self.window, [None, 70, 59], 100))
        self.assertIsNone(first_exercise(self.window, [None] * 3, 100))
        found = first_exercise(self.window, [None, 70, 60], 100)
        self.assertEqual(found["t"], 2)
        self.assertEqual(found["payoff"], 40)
        self.assertTrue(found["at_expiry"])

    def test_rejects_invalid_boundary(self):
        for boundary in ([None], [None, -1, 60], [None, 101, 60], [None, float("nan"), 60]):
            with self.subTest(boundary=boundary), self.assertRaises(ValueError):
                first_exercise(self.window, boundary, 100)


if __name__ == "__main__":
    unittest.main()
