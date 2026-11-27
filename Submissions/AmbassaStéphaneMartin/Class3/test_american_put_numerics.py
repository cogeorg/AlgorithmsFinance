"""Scalar regressions for general factors and binary64 edge cases."""
from fractions import Fraction
import math
import unittest

from american_put import price_american_put


class ScalarNumericsTests(unittest.TestCase):
    def test_both_stock_factors_above_one_allow_immediate_exercise(self):
        # Every future stock exceeds K; immediate payoff is exactly 20.
        actual = price_american_put(100, 120, 1.25, 1.125, 1.1875, 2)
        self.assertEqual(actual, 20.0)

    def test_both_stock_factors_below_one_and_negative_rates_can_exceed_strike(self):
        # All terminal nodes are in the money. With R<1, continuation wins;
        # discounted expected payoff is 100/(4/5)**4 - 100 = 9225/64.
        actual = price_american_put(100, 100, 0.9, 0.7, 0.8, 4)
        self.assertGreater(actual, 100)
        self.assertTrue(math.isclose(actual, float(Fraction(9225, 64)), rel_tol=1e-12, abs_tol=1e-12))

    def test_finite_option_value_with_overflowing_up_stock_node(self):
        # S_up=2e308 cannot be stored, but has zero payoff; S_down=5e307.
        # q=1/3 and the discounted continuation is (2/3)*1e308.
        actual = price_american_put(1e308, 1.5e308, 2, 0.5, 1, 1)
        expected = float(Fraction(2, 3) * Fraction.from_float(1e308))
        self.assertTrue(math.isfinite(actual))
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-12))

    def test_small_complementary_probability_is_preserved(self):
        eps = math.ulp(1.0)
        u, d, R = 1+3*eps, eps/2, 1+2*eps
        # Rounded subtraction/division can make q exactly 1. Use an exact
        # one-period expectation as the independent tiny-value reference.
        fu, fd, fR = map(Fraction.from_float, (u, d, R))
        expected = float(((fu-fR)/(fu-fd)) * (1-fd) / fR)
        actual = price_american_put(1, 1, u, d, R, 1)
        self.assertGreater(actual, 0)
        self.assertTrue(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=0))

    def test_unrepresentable_valid_option_value_has_explicit_overflow(self):
        # Parameters satisfy no-arbitrage, but K/R**3-S0 exceeds float max.
        with self.assertRaises(OverflowError):
            price_american_put(1, 1e308, 2, 0.5, 0.75, 3)

    def test_nonnumeric_scalar_inputs_raise_value_error(self):
        base = dict(S0=100, K=100, u=1.2, d=0.8, R=1.05, N=1)
        for name in ('S0', 'K', 'u', 'd', 'R'):
            for value in (None, '100', complex(1, 1)):
                with self.subTest(parameter=name, value=value):
                    with self.assertRaises(ValueError):
                        price_american_put(**{**base, name: value})


if __name__ == '__main__':
    unittest.main()