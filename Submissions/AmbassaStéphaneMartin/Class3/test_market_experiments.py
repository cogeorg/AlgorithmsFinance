"""Independent small-tree and explicit time-convention checks for market runs."""
from datetime import datetime, timedelta, timezone
import math
import unittest

from exercise_policy import price_american_put_with_boundary
from market_test_support import PreparedWindow, require_hourly_window
from test_exercise_policy import exact_full_tree_decisions
from market_experiments import experiment_calibration, price_atm_put


class FastMarketPricingTests(unittest.TestCase):
    def assert_boundary_close(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for left, right in zip(actual, expected):
            if right is None:
                self.assertIsNone(left)
            else:
                self.assertTrue(math.isclose(left, float(right), rel_tol=1e-12, abs_tol=1e-12))

    def test_small_trees_match_exact_rational_decisions(self):
        for N in (0, 1, 2, 3, 5):
            for R in (0.95, 1.0, 1.05):
                with self.subTest(N=N, R=R):
                    reference = exact_full_tree_decisions(100, 100, 1.25, 0.75, R, N)
                    actual = price_atm_put(100, 1.25, 0.75, R, N)
                    self.assertTrue(math.isclose(actual.price, float(reference.price), rel_tol=1e-12, abs_tol=1e-12))
                    self.assert_boundary_close(actual.boundary, reference.boundary)

    def test_reciprocal_calibrated_factors_match_scalar_engine(self):
        for N in (1, 2, 7, 16, 31, 64):
            u = math.exp(0.03)
            with self.subTest(N=N):
                reference = price_american_put_with_boundary(100, 100, u, 1/u, 1.00001, N)
                actual = price_atm_put(100, u, 1/u, 1.00001, N)
                self.assertTrue(math.isclose(actual.price, reference.price, rel_tol=1e-12, abs_tol=1e-12))
                self.assert_boundary_close(actual.boundary, reference.boundary)

    def test_joint_price_and_strike_scaling_scales_outputs(self):
        base = price_atm_put(100, 1.2, 0.8, 1.05, 8)
        scaled = price_atm_put(250, 1.2, 0.8, 1.05, 8)
        self.assertTrue(math.isclose(scaled.price, 2.5*base.price, rel_tol=1e-12))
        self.assert_boundary_close(scaled.boundary, tuple(2.5*b if b is not None else None for b in base.boundary))

    def test_invalid_inputs_are_rejected_before_expiry_shortcut(self):
        for args in ((0,1.2,.8,1.05,0),(100,1,.8,1.05,0),
                     (100,1.2,.8,1.05,True),(100,1.2,.8,1.05,2.0),
                     (100,1.2,.8,1.05,-1),(float('nan'),1.2,.8,1.05,2)):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):
                    price_atm_put(*args)

    def test_expiry_and_always_out_of_money_trees(self):
        self.assertEqual(price_atm_put(100,1.2,.8,1.05,0).boundary,(None,))
        result = price_atm_put(100,1.25,1.125,1.1875,4)
        self.assertEqual(result.price,0)
        self.assertEqual(result.boundary,(None,)*5)


class ExperimentTimePolicyTests(unittest.TestCase):
    def window(self, offsets=(0,1,3,4), ready=False):
        start = datetime(2025,1,1,tzinfo=timezone.utc)
        return PreparedWindow((100.,110.,105.,108.),
                              tuple(start+timedelta(hours=t) for t in offsets),
                              (0,1,2,3),('P_0','P_1','P_2','P_3'),
                              {'ready_for_hourly_pricing':str(ready)})

    def test_default_policy_keeps_existing_gap_rejection(self):
        with self.assertRaises(ValueError):
            experiment_calibration(self.window())
        with self.assertRaises(ValueError):
            require_hourly_window(self.window())

    def test_explicit_observed_intervals_preserve_every_observation(self):
        window = self.window()
        before = (window.prices,window.timestamps)
        model, info = experiment_calibration(window,gap_policy='observed-intervals')
        self.assertEqual(model.N,3)
        self.assertEqual(len(model.log_returns),3)
        self.assertEqual(info['elapsed_hours'],4)
        self.assertEqual(info['missing_hours'],1)
        self.assertEqual(info['max_interval_hours'],2)
        self.assertTrue(math.isclose(info['mean_period_hours'],4/3))
        self.assertEqual(info['time_convention'],'observed_intervals_approximation')
        self.assertTrue(math.isclose(model.R,math.exp(.04*(4/8760)/3)))
        self.assertEqual((window.prices,window.timestamps),before)
        with self.assertRaises(ValueError):
            require_hourly_window(window)

    def test_complete_windows_retain_the_hourly_convention(self):
        model, info = experiment_calibration(self.window((0,1,2,3),True),gap_policy='observed-intervals')
        self.assertEqual(info['time_convention'],'consecutive_hourly')
        self.assertEqual(info['mean_period_hours'],1)
        self.assertEqual(info['missing_hours'],0)
        self.assertTrue(math.isclose(model.R,math.exp(.04/8760)))

    def test_unknown_policy_and_irregular_dates_are_rejected(self):
        with self.assertRaises(ValueError):
            experiment_calibration(self.window(),gap_policy='fill')
        for offsets in ((0,1,2.5,4),(0,1,1,4),(0,2,1,4)):
            with self.subTest(offsets=offsets):
                with self.assertRaises(ValueError):
                    experiment_calibration(self.window(offsets),gap_policy='observed-intervals')

    def test_flagged_complete_window_is_not_silently_approved(self):
        with self.assertRaises(ValueError):
            experiment_calibration(self.window((0,1,2,3),False),gap_policy='observed-intervals')


if __name__ == '__main__':
    unittest.main()
