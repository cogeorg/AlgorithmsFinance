import csv
import math
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from market_data import (
    MarketDataError,
    calibrate_window,
    find_first_exercise,
    load_price_series,
    select_last_periods,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
BTC_PATH = REPO_ROOT / "Class3" / "data" / "hourly" / "BTCUSDT.csv"


def write_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp_utc", "close"])
        writer.writerows(rows)


class MarketDataContractTests(unittest.TestCase):
    def test_rejects_nonpositive_and_nonfinite_closes(self):
        for bad in ("0", "-1", "nan", "inf", "-inf"):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "BAD.csv"
                write_csv(path, [("2026-01-01T00:00:00Z", "100"),
                                 ("2026-01-01T01:00:00Z", bad)])
                with self.assertRaises(MarketDataError):
                    load_price_series(path)

    def test_rejects_duplicate_or_non_hour_aligned_timestamps(self):
        cases = [
            [("2026-01-01T00:00:00Z", 100), ("2026-01-01T00:00:00Z", 101)],
            [("2026-01-01T00:00:00Z", 100), ("2026-01-01T01:30:00Z", 101)],
        ]
        for rows in cases:
            with self.subTest(rows=rows), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "BAD.csv"
                write_csv(path, rows)
                with self.assertRaises(MarketDataError):
                    load_price_series(path)

    def test_reports_missing_whole_hours_without_filling(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "GAP.csv"
            write_csv(path, [("2026-01-01T00:00:00Z", 100),
                             ("2026-01-01T02:00:00Z", 101),
                             ("2026-01-01T03:00:00Z", 99)])
            series = load_price_series(path)
        self.assertEqual(3, len(series.closes))
        self.assertEqual(1, len(series.gaps))
        self.assertEqual(1, series.gaps[0].missing_hours)

    def test_bitcoin_one_year_window_and_calibration(self):
        series = load_price_series(BTC_PATH)
        window = select_last_periods(series, 8760)
        self.assertEqual(8761, len(window.closes))
        self.assertEqual(8760, window.steps)
        self.assertEqual(datetime(2025, 10, 31, 23, tzinfo=timezone.utc),
                         window.timestamps[0])
        self.assertEqual(datetime(2026, 10, 31, 23, tzinfo=timezone.utc),
                         window.timestamps[-1])
        self.assertFalse(window.gaps)
        calibration = calibrate_window(window)
        self.assertEqual(window.closes[0], calibration.spot)
        self.assertEqual(calibration.spot, calibration.strike)
        self.assertAlmostEqual(1.0, calibration.up * calibration.down, places=14)
        self.assertTrue(0 < calibration.q < 1)
        self.assertGreater(calibration.volatility, 0)

    def test_zero_volatility_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "FLAT.csv"
            write_csv(path, [("2026-01-01T00:00:00Z", 100),
                             ("2026-01-01T01:00:00Z", 100),
                             ("2026-01-01T02:00:00Z", 100)])
            window = select_last_periods(load_price_series(path), 2)
        with self.assertRaises(MarketDataError):
            calibrate_window(window)

    def test_first_exercise_and_never(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "PATH.csv"
            write_csv(path, [("2026-01-01T00:00:00Z", 100),
                             ("2026-01-01T01:00:00Z", 90),
                             ("2026-01-01T02:00:00Z", 80)])
            window = select_last_periods(load_price_series(path), 2)
        decision = find_first_exercise(window, (None, 95.0, 85.0), 100.0)
        self.assertTrue(decision.exercised)
        self.assertEqual(1, decision.index)
        self.assertEqual(10.0, decision.payoff)
        never = find_first_exercise(window, (None, None, None), 100.0)
        self.assertFalse(never.exercised)
        self.assertIsNone(never.index)
        self.assertEqual(0.0, never.payoff)


if __name__ == "__main__":
    unittest.main()
