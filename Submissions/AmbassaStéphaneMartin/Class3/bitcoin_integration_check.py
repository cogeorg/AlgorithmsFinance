"""Expensive opt-in Bitcoin check. Run explicitly with --run after implementation."""
import argparse
import math
from numbers import Real
import unittest

import exercise_policy
import market_test_support as support
from test_exercise_policy import ExerciseNotImplemented

RUN_BITCOIN = False


class OptionalBitcoinIntegration(unittest.TestCase):
    def setUp(self):
        if not RUN_BITCOIN:
            self.skipTest('Explicit opt-in required: python bitcoin_integration_check.py --run')

    def test_one_year_finite_price_and_boundary_dimensions(self):
        window = support.load_prepared_window('BTCUSDT', 'one_year')
        self.assertEqual(len(window.prices), 8761)
        try:
            model = support.calibrate_prepared_window(window)
            inputs = support.pricing_parameters(window, model)
            result = exercise_policy.price_american_put_with_boundary(**inputs)
        except NotImplementedError as exc:
            raise ExerciseNotImplemented(
                'PENDING_IMPLEMENTATION: Bitcoin integration requires production calibration and boundary pricing.'
            ) from exc
        self.assertEqual(inputs['N'], 8760)
        self.assertEqual(inputs['S0'], inputs['K'])
        self.assertEqual(inputs['S0'], window.prices[0])
        self.assertEqual(len(model.log_returns), 8760)
        self.assertIsInstance(result, exercise_policy.PutExerciseResult)
        self.assertIsInstance(result.price, Real)
        self.assertNotIsInstance(result.price, bool)
        self.assertTrue(math.isfinite(result.price))
        self.assertGreaterEqual(result.price, 0)
        self.assertEqual(len(result.boundary), 8761)
        self.assertEqual(len(result.boundary), len(window.timestamps))
        self.assertIsNone(result.boundary[0])  # at-the-money, exact ties continue
        for t, boundary in enumerate(result.boundary):
            with self.subTest(t=t):
                if boundary is not None:
                    self.assertTrue(math.isfinite(boundary))
                    self.assertGreater(boundary, 0)
                    self.assertLess(boundary, inputs['K'])
        # There is deliberately no expected or rounded market-data option price.


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Explicitly allow the 8,760-period production run.')
    args = parser.parse_args()
    if not args.run:
        parser.error('Use --run only when ready to execute the expensive Bitcoin integration check.')
    RUN_BITCOIN = True
    unittest.main(argv=['bitcoin_integration_check.py'], verbosity=2)