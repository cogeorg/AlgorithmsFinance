"""Check the vectorized recurrence against exact policies and scalar output."""

from fractions import Fraction
from itertools import product
import unittest

from price_american_put import price_american_put as scalar_price
from price_american_put_numpy import price_american_put
from test_exercise import exact_boundary


class NumpyPricerTests(unittest.TestCase):
    def test_exact_policies_and_scalar_agreement(self):
        up, down = Fraction(6, 5), Fraction(4, 5)
        for n, spot, strike, rate in product(
            range(7), (60, 100, 140), (80, 100, 120),
            (Fraction(19, 20), Fraction(1), Fraction(21, 20)),
        ):
            with self.subTest(n=n, spot=spot, strike=strike, rate=rate):
                expected, boundary = exact_boundary(spot, strike, up, down, rate, n)
                args = (spot, strike, float(up), float(down), float(rate), n)
                actual, found = price_american_put(*args, return_boundary=True)
                self.assertAlmostEqual(actual, float(expected), places=10)
                self.assertEqual((actual, found), scalar_price(*args, return_boundary=True))
                for a, b in zip(found, boundary):
                    if b is None:
                        self.assertIsNone(a)
                    else:
                        self.assertAlmostEqual(a, float(b), places=10)

    def test_price_only_zero_strike_and_expiry(self):
        self.assertAlmostEqual(price_american_put(100, 100, 1.2, 0.8, 1.05, 2), 1175 / 147)
        self.assertEqual(price_american_put(100, 0, 1.2, 0.8, 1.05, 3, return_boundary=True), (0, [None] * 4))
        self.assertEqual(price_american_put(80, 100, 1.2, 0.8, 1.05, 0, return_boundary=True), (20, [80]))

    def test_rejects_invalid_and_unsafe_inputs(self):
        for args in (
            (100, 100, 1.2, 0.8, 1.05, -1),
            (100, 100, 1.2, 0.8, 1.05, True),
            (100, 100, 1.2, 0.8, 1.05, 1.5),
            (0, 100, 1.2, 0.8, 1.05, 2),
            (100, 100, 1.2, 0.8, 1.2, 2),
            (100, 100, 2, 0.5, 1.05, 10000),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                price_american_put(*args, return_boundary=True)


if __name__ == "__main__":
    unittest.main()
