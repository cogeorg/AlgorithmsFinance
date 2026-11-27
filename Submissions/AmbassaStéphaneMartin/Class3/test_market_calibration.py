"""Deterministic tests for implemented hourly calibration and its input contract."""
import math
from numbers import Real
import unittest

import market_calibration as calibration
from test_american_put import ABS_TOL, REL_TOL


def symmetric_prices(a):
    """Three hourly log returns (a, 0, -a), constructed without calibration code."""
    high = 100 * math.exp(a)
    return (100, high, high, 100)


class CalibrationNotImplemented(AssertionError):
    """Distinguish pending production behavior from unexpected test errors."""


class MarketCalibrationTests(unittest.TestCase):
    def call(self, function, *args, **kwargs):
        try:
            return function(*args, **kwargs)
        except NotImplementedError as exc:
            raise CalibrationNotImplemented(
                f'PENDING_IMPLEMENTATION: {function.__name__} has no production implementation.'
            ) from exc

    def assert_close(self, actual, expected):
        self.assertIsInstance(actual, Real)
        self.assertNotIsInstance(actual, bool)
        self.assertTrue(math.isfinite(actual))
        self.assertTrue(math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL),
                        f'{actual!r} != {expected!r}')

    def assert_returns(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for index, (value, reference) in enumerate(zip(actual, expected)):
            with self.subTest(return_index=index):
                self.assert_close(value, reference)

    def calibrated(self, prices, T, annual_rate=0.04):
        result = self.call(calibration.calibrate_binomial, prices, T=T, annual_rate=annual_rate)
        self.assertIsInstance(result, calibration.Calibration)
        return result

    def test_returns_are_adjacent_log_ratios(self):
        actual = self.call(calibration.log_returns, (100, 200, 100, 400))
        self.assert_returns(actual, (math.log(2), -math.log(2), math.log(4)))

    def test_log_returns_match_constructed_positive_zero_negative_sequence(self):
        for a in (0.01, 0.05, 0.2):
            with self.subTest(a=a):
                actual = self.call(calibration.log_returns, symmetric_prices(a))
                self.assert_returns(actual, (a, 0.0, -a))

    def test_hourly_volatility_uses_sample_denominator(self):
        # Mean=.03; squared deviations total .0002; N-1=1.
        # Population stdev would be .01; RMS would also give a different value.
        actual = self.call(calibration.sample_hourly_volatility, (0.02, 0.04))
        self.assert_close(actual, 0.02 / math.sqrt(2))

    def test_symmetric_three_return_sequence_has_sample_volatility_a(self):
        for a in (0.01, 0.05, 0.2):
            with self.subTest(a=a):
                actual = self.call(calibration.sample_hourly_volatility, (a, 0.0, -a))
                self.assert_close(actual, a)

    def test_sample_volatility_removes_nonzero_mean(self):
        # Mean=.10; squared deviations .0025+0+.0025; divide by 2.
        actual = self.call(calibration.sample_hourly_volatility, (0.05, 0.10, 0.15))
        self.assert_close(actual, 0.05)

    def test_calibration_uses_hourly_sample_volatility_without_annualization(self):
        for a in (0.01, 0.05, 0.2):
            with self.subTest(a=a):
                result = self.calibrated(symmetric_prices(a), T=3/8760)
                self.assertEqual(result.N, 3)
                self.assert_returns(result.log_returns, (a, 0.0, -a))
                self.assert_close(result.s, a)

    def test_factors_are_exp_s_and_reciprocal(self):
        for a in (0.01, 0.05, 0.2):
            with self.subTest(a=a):
                result = self.calibrated(symmetric_prices(a), T=3/8760)
                # Anchor to independent fixture a, not only internal consistency.
                self.assert_close(result.u, math.exp(a))
                self.assert_close(result.d, math.exp(-a))
                self.assert_close(result.u, math.exp(result.s))
                self.assert_close(result.d, 1 / result.u)
                self.assert_close(result.u * result.d, 1.0)

    def test_8760_hour_one_year_risk_free_factor(self):
        # The sole longer fixture is two alternating levels: 8,761 closes.
        # It generates no real data access or tree-pricing work.
        high = 100 * math.exp(0.02)
        prices = (100,) + (high, 100) * 4380
        result = self.calibrated(prices, T=1.0)
        self.assertEqual(result.N, 8760)
        self.assertEqual(len(result.log_returns), 8760)
        self.assert_close(result.R, math.exp(0.04 / 8760))

    def test_factor_uses_explicit_elapsed_years_and_annual_rate(self):
        result = self.calibrated(symmetric_prices(0.1), T=0.5, annual_rate=0.08)
        self.assert_close(result.R, math.exp(0.08 * 0.5 / 3))

    def test_calibrated_probability_is_strictly_inside_unit_interval(self):
        for a in (0.01, 0.05, 0.2):
            with self.subTest(a=a):
                result = self.calibrated(symmetric_prices(a), T=3/8760)
                self.assertGreater(result.q, 0)
                self.assertLess(result.q, 1)
                self.assertGreater(result.d, 0)
                self.assertLess(result.d, result.R)
                self.assertLess(result.R, result.u)
                expected_R = math.exp(0.04 / 8760)
                expected_q = (expected_R - math.exp(-a)) / (math.exp(a) - math.exp(-a))
                self.assert_close(result.q, expected_q)
                self.assert_close(result.q, (result.R - result.d) / (result.u - result.d))

    def test_log_returns_reject_insufficient_closes(self):
        for prices in ((), (100,)):
            with self.subTest(prices=prices):
                with self.assertRaises(ValueError):
                    self.call(calibration.log_returns, prices)

    def test_sample_volatility_rejects_fewer_than_two_returns(self):
        for returns in ((), (0.01,)):
            with self.subTest(returns=returns):
                with self.assertRaises(ValueError):
                    self.call(calibration.sample_hourly_volatility, returns)

    def test_calibration_rejects_fewer_than_three_closes(self):
        for prices in ((), (100,), (100, 101)):
            with self.subTest(prices=prices):
                with self.assertRaises(ValueError):
                    self.call(calibration.calibrate_binomial, prices, T=1)

    def test_constant_returns_have_zero_statistical_volatility(self):
        for returns in ((0.0, 0.0, 0.0), (0.1, 0.1, 0.1)):
            with self.subTest(returns=returns):
                self.assert_close(self.call(calibration.sample_hourly_volatility, returns), 0.0)

    def test_calibration_explicitly_rejects_zero_volatility(self):
        # Flat prices AND constant nonzero log returns both have zero volatility.
        for prices in ((100, 100, 100, 100), (1, 2, 4, 8)):
            with self.subTest(prices=prices):
                with self.assertRaisesRegex(ValueError, '(?i)volatility'):
                    self.call(calibration.calibrate_binomial, prices, T=3/8760)

    def test_calibration_rejects_nonzero_volatility_with_invalid_probability(self):
        # s=.01, but exp(+/-.06 / 3) lies outside (exp(-s), exp(s)).
        for rate in (-0.06, 0.06):
            with self.subTest(annual_rate=rate):
                with self.assertRaisesRegex(ValueError, '(?i)(arbitrage|probability|d < R < u)'):
                    self.call(calibration.calibrate_binomial, symmetric_prices(0.01), T=1, annual_rate=rate)

    def test_log_returns_reject_nonpositive_or_nonfinite_prices(self):
        for prices in ((100, 0), (0, 100), (100, -1), (100, float('nan')), (100, float('inf'))):
            with self.subTest(prices=prices):
                with self.assertRaises(ValueError):
                    self.call(calibration.log_returns, prices)

    def test_sample_volatility_rejects_nonfinite_returns(self):
        for value in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.call(calibration.sample_hourly_volatility, (0.01, value))

    def test_calibration_rejects_nonpositive_or_nonfinite_elapsed_years(self):
        for years in (0, -1, float('nan'), float('inf')):
            with self.subTest(T=years):
                with self.assertRaises(ValueError):
                    self.call(calibration.calibrate_binomial, symmetric_prices(0.05), T=years)

    def test_calibration_rejects_nonfinite_annual_rate(self):
        for rate in (float('nan'), float('inf'), float('-inf')):
            with self.subTest(annual_rate=rate):
                with self.assertRaises(ValueError):
                    self.call(calibration.calibrate_binomial, symmetric_prices(0.05), T=1, annual_rate=rate)

    def test_calibration_also_rejects_invalid_input_prices(self):
        for prices in ((100, 0, 100), (100, float('nan'), 100)):
            with self.subTest(prices=prices):
                with self.assertRaises(ValueError):
                    self.call(calibration.calibrate_binomial, prices, T=1)


if __name__ == '__main__':
    unittest.main()
