import math
import unittest
from fractions import Fraction
from itertools import product

from american_put import (
    PricingInputError,
    price_american_put,
    price_american_put_with_boundary,
)
from tests.support import TOY_BOUNDARY, TOY_VALUE, recursive_value, toy_inputs


class PricerContractTests(unittest.TestCase):
    def test_two_period_value_and_boundary(self):
        args = toy_inputs()
        result = price_american_put_with_boundary(*args)
        self.assertAlmostEqual(result.value, float(TOY_VALUE), places=12)
        self.assertEqual(tuple(float(x) if x is not None else None for x in TOY_BOUNDARY),
                         result.boundary)
        self.assertEqual(3, result.node_updates)
        self.assertEqual("7.9932", f"{result.value:.4f}")

    def test_value_wrapper_matches_boundary_version(self):
        args = (100.0, 100.0, 1.2, 0.8, 1.05, 2)
        self.assertEqual(price_american_put(*args),
                         price_american_put_with_boundary(*args).value)

    def test_exhaustive_small_values_match_recursive_oracle(self):
        for steps, spot, strike, gross in product(
            range(7), (60, 100, 140), (80, 100, 120),
            (Fraction(19, 20), Fraction(1), Fraction(21, 20))
        ):
            down = Fraction(4, 5)
            up = Fraction(6, 5)
            if not down < gross < up:
                continue
            args = (Fraction(spot), Fraction(strike), up, down, gross, steps)
            expected = recursive_value(*args)
            self.assertAlmostEqual(float(expected), price_american_put(*args), places=11)

    def test_zero_period_contract(self):
        result = price_american_put_with_boundary(80, 100, 1.2, 0.8, 1.05, 0)
        self.assertEqual(20.0, result.value)
        self.assertEqual((80.0,), result.boundary)
        self.assertEqual(0, result.node_updates)

    def test_values_and_boundaries_are_nonnegative_and_finite(self):
        result = price_american_put_with_boundary(100, 100, 1.2, 0.8, 1.05, 8)
        self.assertTrue(math.isfinite(result.value))
        self.assertGreaterEqual(result.value, 0)
        self.assertLessEqual(result.value, 100)
        for boundary in result.boundary:
            if boundary is not None:
                self.assertTrue(math.isfinite(boundary))
                self.assertGreater(boundary, 0)

    def test_invalid_inputs_are_rejected(self):
        valid = [100.0, 100.0, 1.2, 0.8, 1.05, 2]
        cases = [
            (0, 0.0), (0, -1.0), (0, math.nan), (0, math.inf),
            (1, -1.0), (1, math.nan),
            (2, 0.0), (3, 0.0), (4, 0.0),
            (5, -1), (5, 2.5), (5, True),
        ]
        for index, bad in cases:
            args = list(valid)
            args[index] = bad
            with self.subTest(index=index, bad=bad):
                with self.assertRaises(PricingInputError):
                    price_american_put(*args)

    def test_no_arbitrage_order_is_enforced(self):
        for up, down, gross in ((1.0, 1.0, 1.0), (1.2, 0.8, 1.3),
                                (1.2, 1.1, 1.05)):
            with self.subTest(up=up, down=down, gross=gross):
                with self.assertRaises(PricingInputError):
                    price_american_put(100, 100, up, down, gross, 2)


if __name__ == "__main__":
    unittest.main()
