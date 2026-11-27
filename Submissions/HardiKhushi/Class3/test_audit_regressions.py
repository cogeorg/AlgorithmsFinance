"""Regressions discovered by the Class3 audit; no expensive benchmark tests."""

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from math import exp, nextafter
from pathlib import Path
import tempfile
import unittest

from market_data import PriceWindow, calibrate_window
from price_american_put import price_american_put as scalar
from price_american_put_numpy import price_american_put as vector
from run_bitcoin import run


class AuditRegressions(unittest.TestCase):
    def test_boundary_is_invariant_to_currency_scale(self):
        for pricer in (scalar, vector):
            for scale in (1e-15, 1e-8, 1.0, 1e8):
                with self.subTest(engine=pricer.__module__, scale=scale):
                    value, boundary = pricer(100 * scale, 100 * scale, 1.2, .8, 1.05, 2, return_boundary=True)
                    self.assertAlmostEqual(value / scale, 1175 / 147, places=10)
                    self.assertIsNone(boundary[0])
                    self.assertIsNotNone(boundary[1])
                    self.assertAlmostEqual(boundary[1] / scale, 80, places=10)
                    self.assertAlmostEqual(boundary[2] / scale, 96, places=10)

    def test_negative_rate_near_indifference_does_not_trigger_exercise(self):
        for pricer in (scalar, vector):
            with self.subTest(engine=pricer.__module__):
                value, boundary = pricer(80, 100, 1.2, .8, nextafter(1.0, 0.0), 1, return_boundary=True)
                self.assertGreaterEqual(value, 20)
                self.assertIsNone(boundary[0])

    def test_safe_nodes_do_not_overflow_during_initialization(self):
        for pricer in (scalar, vector):
            with self.subTest(engine=pricer.__module__):
                _, boundary = pricer(1e305, 1.1e307, 100., 90., 95., 1, return_boundary=True)
                self.assertAlmostEqual(boundary[-1] / 1e307, 1.0, places=12)

    def test_reciprocal_tree_does_not_exercise_worthless_atm_expiry_node(self):
        up = exp(.003)
        for pricer in (scalar, vector):
            with self.subTest(engine=pricer.__module__):
                _, boundary = pricer(100, 100, up, 1 / up, exp(.04 / 8760), 500, return_boundary=True)
                self.assertAlmostEqual(boundary[-1], 100 / up**2, places=10)

    def test_rejects_misaligned_price_window(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with self.assertRaises(ValueError):
            PriceWindow(Path('fixture.csv'), 'fixture', 3, (start,), (100., 101., 102.))

    def test_calibration_reports_extreme_returns_as_value_error(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        window = PriceWindow(Path('fixture.csv'), 'fixture', 3,
                             tuple(start + timedelta(hours=t) for t in range(3)),
                             (1e-300, 1e300, 1e-300))
        with self.assertRaises(ValueError):
            calibrate_window(window)

    def test_runner_labels_the_actual_asset(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            folder = Path(tmp)
            data = folder / 'ETHUSDT.csv'
            data.write_text('timestamp_utc,close\n2026-01-01T00:00:00Z,100\n2026-01-01T01:00:00Z,102\n2026-01-01T02:00:00Z,101\n')
            with redirect_stdout(StringIO()):
                result = run(data, 2, folder / 'results', 'numpy')
            self.assertEqual(result['asset'], 'ETHUSDT')

    def test_unsafe_run_does_not_leave_a_results_directory(self):
        # The input passes calibration but produces a numerically unsafe tree.
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            folder = Path(tmp)
            data = folder / 'RANGE.csv'
            lines = ['timestamp_utc,close']
            start = datetime(2026, 1, 1, tzinfo=timezone.utc)
            for t in range(201):
                lines.append(f'{(start + timedelta(hours=t)).isoformat()},{100 if t % 2 else 1}')
            data.write_text('\n'.join(lines) + '\n')
            output = folder / 'results'
            with redirect_stdout(StringIO()), self.assertRaises(ValueError):
                run(data, 200, output, 'numpy')
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
