import math
import unittest
from pathlib import Path

from american_put import price_american_put_with_boundary
from market_data import (
    calibrate_window,
    find_first_exercise,
    load_price_series,
    select_last_periods,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
BTC_PATH = REPO_ROOT / "Class3" / "data" / "hourly" / "BTCUSDT.csv"


class BitcoinOneYearAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.window = select_last_periods(load_price_series(BTC_PATH), 8760)
        cls.calibration = calibrate_window(cls.window)
        cls.result = price_american_put_with_boundary(
            cls.calibration.spot,
            cls.calibration.strike,
            cls.calibration.up,
            cls.calibration.down,
            cls.calibration.gross_rate,
            cls.calibration.steps,
        )

    def test_value_and_boundary_invariants(self):
        result = self.result
        self.assertTrue(math.isfinite(result.value))
        self.assertGreaterEqual(result.value, 0)
        self.assertLessEqual(result.value, self.calibration.strike)
        self.assertEqual(8761, len(result.boundary))
        self.assertEqual(8760 * 8761 // 2, result.node_updates)
        for value in result.boundary:
            if value is not None:
                self.assertTrue(math.isfinite(value))
                self.assertGreater(value, 0)

    def test_observed_exercise_decision_is_well_formed(self):
        decision = find_first_exercise(
            self.window, self.result.boundary, self.calibration.strike
        )
        self.assertGreaterEqual(decision.payoff, 0)
        if decision.exercised:
            self.assertIsNotNone(decision.index)
            self.assertIsNotNone(decision.timestamp)
            self.assertLessEqual(self.window.closes[decision.index],
                                 self.result.boundary[decision.index])
        else:
            self.assertIsNone(decision.index)


if __name__ == "__main__":
    unittest.main()
