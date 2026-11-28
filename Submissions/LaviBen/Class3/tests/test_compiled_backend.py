import unittest
from fractions import Fraction
from itertools import product
from pathlib import Path

from american_put import price_american_put, price_american_put_with_boundary
from compiled_backend import (
    ensure_compiled,
    price_american_put_compiled,
    price_american_put_with_boundary_compiled,
)
from market_data import calibrate_window, load_price_series, select_last_periods
from tests.support import TOY_BOUNDARY, TOY_VALUE, recursive_value, toy_inputs


REPO_ROOT = Path(__file__).resolve().parents[4]
BTC_PATH = REPO_ROOT / "Class3" / "data" / "hourly" / "BTCUSDT.csv"


class CompiledBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_compiled()

    def test_two_period_value_and_boundary(self):
        result = price_american_put_with_boundary_compiled(*toy_inputs())
        self.assertAlmostEqual(float(TOY_VALUE), result.value, places=12)
        expected = tuple(float(x) if x is not None else None for x in TOY_BOUNDARY)
        self.assertEqual(expected, result.boundary)
        self.assertEqual(3, result.node_updates)

    def test_small_values_match_oracle_and_python_reference(self):
        for steps, spot, strike, gross in product(
            range(7), (60, 100, 140), (80, 100, 120),
            (Fraction(19, 20), Fraction(1), Fraction(21, 20))
        ):
            down = Fraction(4, 5)
            up = Fraction(6, 5)
            if not down < gross < up:
                continue
            args = (Fraction(spot), Fraction(strike), up, down, gross, steps)
            expected = float(recursive_value(*args))
            compiled = price_american_put_compiled(*args)
            self.assertAlmostEqual(expected, compiled, places=11)
            self.assertAlmostEqual(price_american_put(*args), compiled, places=11)

    def test_bitcoin_one_year_matches_python_reference(self):
        window = select_last_periods(load_price_series(BTC_PATH), 8760)
        calibration = calibrate_window(window)
        args = (
            calibration.spot, calibration.strike, calibration.up,
            calibration.down, calibration.gross_rate, calibration.steps
        )
        reference = price_american_put_with_boundary(*args)
        compiled = price_american_put_with_boundary_compiled(*args)
        self.assertAlmostEqual(reference.value, compiled.value, delta=2e-8)
        self.assertEqual(reference.boundary, compiled.boundary)
        self.assertEqual(reference.node_updates, compiled.node_updates)


if __name__ == "__main__":
    unittest.main()
