import math
import unittest
from datetime import datetime, timedelta, timezone
from calibrate import calibrate


class CalibrationTests(unittest.TestCase):
    def test_known_returns_and_excludes_next_year(self):
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        rows = [(start, 100), (start + timedelta(days=1), 100 * math.exp(0.01)),
                (start + timedelta(days=2), 100), (start.replace(year=2024), 99999)]
        result = calibrate(rows)
        self.assertEqual(result['N_returns'], 2)
        self.assertEqual(result['last_calibration_price'], 100)
        self.assertAlmostEqual(result['sample_log_return_std'], math.sqrt(0.0002))
        self.assertAlmostEqual(result['u'], math.exp(math.sqrt(0.0002)))
        self.assertAlmostEqual(result['q_risk_neutral'], (result['R_per_observation'] - result['d']) / (result['u'] - result['d']))

    def test_rejects_flat_and_incomplete_data(self):
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            calibrate([(start, 100), (start + timedelta(days=1), 101)])
        with self.assertRaises(ValueError):
            calibrate([(start, 100), (start + timedelta(days=1), 100), (start + timedelta(days=2), 100), (start.replace(year=2024), 100)])


if __name__ == '__main__':
    unittest.main()
