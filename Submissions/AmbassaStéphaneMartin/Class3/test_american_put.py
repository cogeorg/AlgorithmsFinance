"""Scalar PriceAmericanPut contracts; standard-library unittest.

Expected values are hand-derived rational constants, not a second tree pricer.
See PRICING_TESTS.txt for the independent derivations and run instructions.
"""
from fractions import Fraction
import math
from numbers import Real
import unittest

from american_put import price_american_put


REL_TOL = 1e-12
ABS_TOL = 1e-12


class PricingNotImplemented(AssertionError):
    """Identify an expected red-stage failure separately from a test error."""


class AmericanPutTests(unittest.TestCase):
    def call_price(self, **overrides):
        inputs = dict(S0=100.0, K=100.0, u=1.2, d=0.8, R=1.05, N=1)
        inputs.update(overrides)
        try:
            return price_american_put(**inputs)
        except NotImplementedError as exc:
            # Only the explicit stub signal is converted. Import problems,
            # syntax errors and all other exceptions remain unittest errors.
            raise PricingNotImplemented(
                'PENDING_IMPLEMENTATION: price_american_put has no production implementation.'
            ) from exc

    def assert_price(self, expected, **inputs):
        actual = self.call_price(**inputs)
        self.assertIsInstance(actual, Real, 'The interface must return a scalar real price.')
        self.assertNotIsInstance(actual, bool, 'A boolean is not a put price.')
        self.assertTrue(math.isfinite(actual), f'Price is not finite: {actual!r}')
        expected_float = float(expected)
        self.assertTrue(
            math.isclose(actual, expected_float, rel_tol=REL_TOL, abs_tol=ABS_TOL),
            f'Expected {expected!s} ({expected_float:.17g}), got {actual!r}; '
            f'rel_tol={REL_TOL}, abs_tol={ABS_TOL}',
        )

    def test_immediate_expiry_positive_payoff(self):
        self.assert_price(20, S0=80, K=100, N=0)

    def test_immediate_expiry_at_money_zero_payoff(self):
        self.assert_price(0, S0=100, K=100, N=0)

    def test_immediate_expiry_out_of_money_zero_payoff(self):
        self.assert_price(0, S0=120, K=100, N=0)

    def test_zero_strike_at_expiry_and_positive_horizons(self):
        for periods in (0, 1, 2):
            with self.subTest(N=periods):
                self.assert_price(0, K=0, N=periods)

    def test_one_period_exact_reference(self):
        self.assert_price(Fraction(50, 7), N=1)

    def test_two_period_exact_reference(self):
        self.assert_price(Fraction(1175, 147), N=2)

    def test_immediate_exercise_beats_continuation(self):
        # Immediate payoff 20; independent continuation value is 320/21 < 20.
        self.assert_price(20, S0=80, K=100, N=1)

    def test_continuation_beats_immediate_exercise(self):
        # Immediate payoff is zero; the down terminal payoff is 4.
        self.assert_price(Fraction(10, 7), S0=120, K=100, N=1)

    def test_reject_negative_period_counts(self):
        for periods in (-1, -2):
            with self.subTest(N=periods):
                with self.assertRaises(ValueError):
                    self.call_price(N=periods)

    def test_reject_noninteger_period_counts(self):
        for periods in (0.5, 1.5, -0.5, 2.0):
            with self.subTest(N=periods):
                with self.assertRaises(ValueError):
                    self.call_price(N=periods)

    def test_reject_boolean_period_counts(self):
        for periods in (False, True):
            with self.subTest(N=periods):
                with self.assertRaises(ValueError):
                    self.call_price(N=periods)

    def test_reject_nonpositive_initial_prices(self):
        for spot in (0, -80):
            with self.subTest(S0=spot):
                with self.assertRaises(ValueError):
                    self.call_price(S0=spot)

    def test_reject_negative_strikes(self):
        for strike in (-1, -100):
            with self.subTest(K=strike):
                with self.assertRaises(ValueError):
                    self.call_price(K=strike)

    def test_reject_nonfinite_inputs_in_every_parameter(self):
        for parameter in ('S0', 'K', 'u', 'd', 'R', 'N'):
            for value in (float('nan'), float('inf'), float('-inf')):
                with self.subTest(parameter=parameter, value=value):
                    with self.assertRaises(ValueError):
                        self.call_price(**{parameter: value})

    def test_reject_factor_and_no_arbitrage_violations(self):
        cases = (
            ('zero_down_factor', dict(d=0)),
            ('negative_down_factor', dict(d=-0.8)),
            ('zero_risk_free_factor', dict(R=0)),
            ('negative_risk_free_factor', dict(R=-1.05)),
            ('zero_up_factor', dict(u=0)),
            ('negative_up_factor', dict(u=-1.2)),
            ('down_equals_risk_free', dict(d=1.05)),
            ('risk_free_equals_up', dict(R=1.2)),
            ('down_above_risk_free', dict(d=1.1)),
            ('risk_free_above_up', dict(R=1.3)),
            ('up_and_down_equal', dict(u=1, d=1, R=1)),
            ('up_and_down_reversed', dict(u=0.8, d=1.2, R=1)),
        )
        for label, inputs in cases:
            with self.subTest(case=label):
                with self.assertRaises(ValueError):
                    self.call_price(**inputs)

    def test_invalid_inputs_are_rejected_even_at_immediate_expiry(self):
        for inputs in (dict(S0=0), dict(K=-1), dict(d=1.05), dict(R=1.2)):
            with self.subTest(inputs=inputs):
                with self.assertRaises(ValueError):
                    self.call_price(N=0, **inputs)

    def test_invalid_inputs_are_rejected_even_with_zero_strike(self):
        for inputs in (dict(N=-1), dict(N=1.5), dict(S0=0), dict(R=1.2), dict(d=0)):
            with self.subTest(inputs=inputs):
                with self.assertRaises(ValueError):
                    self.call_price(K=0, **inputs)


if __name__ == '__main__':
    unittest.main()
