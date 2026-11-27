"""Small independent checks; these do not run market-data benchmarks."""

from fractions import Fraction
from itertools import product
import unittest

from price_american_put import price_american_put


def exact_tree(spot, strike, up, down, gross_rate, steps):
    """Enumerate both successor trees with exact rational arithmetic.

    Deliberately avoid rolling arrays and in-place updates, so a wrong update
    order in the implementation is not duplicated by this reference.
    """
    exercise = max(strike - spot, 0)
    if steps == 0:
        return exercise
    q = (gross_rate - down) / (up - down)
    continuation = (
        q * exact_tree(spot * up, strike, up, down, gross_rate, steps - 1)
        + (1 - q)
        * exact_tree(spot * down, strike, up, down, gross_rate, steps - 1)
    ) / gross_rate
    return max(exercise, continuation)


class AmericanPutTests(unittest.TestCase):
    def test_slide_example(self):
        actual = price_american_put(100, 100, 1.2, 0.8, 1.05, 2)
        self.assertAlmostEqual(actual, float(Fraction(1175, 147)), places=11)
        self.assertEqual(f"{actual:.4f}", "7.9932")

    def test_zero_periods_is_current_payoff(self):
        for spot, expected in [(80, 20), (100, 0), (120, 0)]:
            with self.subTest(spot=spot):
                self.assertEqual(
                    price_american_put(spot, 100, 1.2, 0.8, 1.05, 0), expected
                )

    def test_zero_strike_is_worthless(self):
        self.assertEqual(price_american_put(100, 0, 1.2, 0.8, 1.05, 5), 0)

    def test_matches_exact_independent_trees(self):
        up, down = Fraction(6, 5), Fraction(4, 5)
        rates = (Fraction(19, 20), Fraction(1), Fraction(21, 20))
        for steps, spot, strike, rate in product(
            range(7), (60, 100, 140), (80, 100, 120), rates
        ):
            with self.subTest(steps=steps, spot=spot, strike=strike, rate=rate):
                expected = exact_tree(spot, strike, up, down, rate, steps)
                actual = price_american_put(
                    spot, strike, float(up), float(down), float(rate), steps
                )
                self.assertAlmostEqual(actual, float(expected), places=10)

    def test_rejects_invalid_period_counts(self):
        for steps in (-1, 1.5, True):
            with self.subTest(steps=steps), self.assertRaises(ValueError):
                price_american_put(100, 100, 1.2, 0.8, 1.05, steps)

    def test_rejects_invalid_model_parameters(self):
        invalid = [
            (0, 100, 1.2, 0.8, 1.05),
            (100, -1, 1.2, 0.8, 1.05),
            (100, 100, 1.2, 0.8, 0.8),
            (100, 100, 1.2, 0.8, 1.2),
            (100, 100, 1.2, 0, 1.05),
            (100, 100, 0.8, 1.2, 1.05),
            (float("nan"), 100, 1.2, 0.8, 1.05),
            (100, 100, float("inf"), 0.8, 1.05),
        ]
        for args in invalid:
            with self.subTest(args=args), self.assertRaises(ValueError):
                price_american_put(*args, 2)


if __name__ == "__main__":
    unittest.main()
