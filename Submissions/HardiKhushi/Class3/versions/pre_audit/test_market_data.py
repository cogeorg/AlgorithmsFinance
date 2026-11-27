"""Data/calibration checks using tiny CSV fixtures, never large tree runs."""

from datetime import timedelta
import hashlib
from math import exp, log, sqrt
from pathlib import Path
import tempfile
import unittest

from market_data import calibration_report, calibrate_window, load_price_window


CSV = (
    "timestamp_utc,close\n"
    "2026-01-01T00:00:00Z,50\n"
    "2026-01-01T01:00:00Z,100\n"
    "2026-01-01T02:00:00Z,200\n"
    "2026-01-01T03:00:00Z,200\n"
)


class MarketDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "prices.csv"

    def load(self, text=CSV, periods=2):
        self.path.write_text(text, encoding="utf-8")
        return load_price_window(self.path, periods)

    def test_last_n_plus_one_prices_and_provenance(self):
        window = self.load()
        self.assertEqual(window.prices, (100, 200, 200))
        self.assertEqual(window.periods, 2)
        self.assertEqual(window.file_rows, 4)
        self.assertEqual(window.source_sha256, hashlib.sha256(CSV.encode()).hexdigest())

    def test_full_file_uses_all_rows(self):
        self.assertEqual(self.load(periods=None).prices, (50, 100, 200, 200))

    def test_calibration_against_hand_computed_sample_variance(self):
        # Selected returns are log(2), 0. Their sample std is log(2)/sqrt(2).
        model = calibrate_window(self.load())
        expected_std = log(2) / sqrt(2)
        self.assertAlmostEqual(model.mean_log_return, log(2) / 2)
        self.assertAlmostEqual(model.log_return_std, expected_std)
        self.assertAlmostEqual(model.up, exp(expected_std))
        self.assertAlmostEqual(model.down, exp(-expected_std))
        self.assertAlmostEqual(model.years, 2 / 8760)
        self.assertAlmostEqual(model.gross_rate, exp(0.04 / 8760))
        self.assertEqual((model.spot, model.strike, model.steps), (100, 100, 2))
        self.assertGreater(model.probability_up, 0)
        self.assertLess(model.probability_up, 1)
        self.assertAlmostEqual(
            model.probability_up * model.up + (1 - model.probability_up) * model.down,
            model.gross_rate,
        )

    def test_missing_hour_is_reported_and_elapsed_time_used(self):
        text = CSV.replace("2026-01-01T03:00:00Z", "2026-01-01T04:00:00Z")
        window = self.load(text)
        model = calibrate_window(window)
        report = calibration_report(window, model)
        self.assertEqual(window.timestamps[-1] - window.timestamps[0], timedelta(hours=3))
        self.assertEqual(report["missing_hours"], 1)
        self.assertEqual(report["non_hourly_intervals"], 1)
        self.assertEqual(report["maximum_interval_hours"], 2)
        self.assertAlmostEqual(model.gross_rate, exp(0.04 * 3 / 8760 / 2))

    def test_invalid_closes_even_outside_selected_window(self):
        for close in ("0", "-1", "nan", "inf", "bad", ""):
            with self.subTest(close=close), self.assertRaises(ValueError):
                self.load(CSV.replace(",50\n", f",{close}\n"))

    def test_rejects_invalid_or_unordered_dates(self):
        for timestamp in (
            "bad", "2026-01-01T02:00:00Z", "2026-01-01T01:00:00Z",
            "2026-01-01T03:30:00Z", "2026-01-01T03:00:00",
            "2026-01-01T03:00:00+01:00",
        ):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                self.load(CSV.replace("2026-01-01T03:00:00Z", timestamp))

    def test_rejects_bad_columns_and_rows(self):
        for text in (
            CSV.replace("timestamp_utc,close", "date,price"),
            CSV.replace(",50\n", ",50,extra\n"),
            CSV.replace("2026-01-01T00:00:00Z,50", "2026-01-01T00:00:00Z"),
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.load(text)

    def test_rejects_insufficient_data_and_invalid_period_counts(self):
        for periods in (0, 1, True, 2.5, 4):
            with self.subTest(periods=periods), self.assertRaises(ValueError):
                self.load(periods=periods)
        with self.assertRaises(ValueError):
            self.load("timestamp_utc,close\n2026-01-01T00:00:00Z,50\n", periods=None)

    def test_rejects_zero_volatility_and_invalid_interest_factors(self):
        with self.assertRaises(ValueError):
            calibrate_window(self.load(CSV.replace(",100\n", ",200\n")))
        window = self.load()
        for annual_rate in (float("nan"), float("inf"), 10000, -10000):
            with self.subTest(annual_rate=annual_rate), self.assertRaises(ValueError):
                calibrate_window(window, annual_rate)


if __name__ == "__main__":
    unittest.main()
