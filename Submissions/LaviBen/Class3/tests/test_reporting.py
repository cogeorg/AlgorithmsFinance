import unittest
from pathlib import Path

from build_report import (
    load_results,
    render_combined_values_csv,
    render_report,
    render_summary_csv,
)


SUBMISSION_DIR = Path(__file__).resolve().parents[1]


class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle = load_results(SUBMISSION_DIR / "results")

    def test_all_four_required_scenarios_are_complete(self):
        self.assertEqual(
            {"bitcoin_one_year", "bitcoin_full", "all_assets_one_year", "all_assets_full"},
            set(self.bundle.scenarios),
        )
        for result in self.bundle.scenarios.values():
            self.assertEqual("completed", result["status"])
            self.assertEqual(5, len(result["timing"]["raw_seconds"]))

    def test_all_asset_values_join_and_remain_nonnegative(self):
        one_year = {row["symbol"]: row["value"]
                    for row in self.bundle.scenarios["all_assets_one_year"]["outputs"]}
        full = {row["symbol"]: row["value"]
                for row in self.bundle.scenarios["all_assets_full"]["outputs"]}
        self.assertEqual(40, len(one_year))
        self.assertEqual(set(one_year), set(full))
        self.assertTrue(all(value >= 0 for value in one_year.values()))
        self.assertTrue(all(value >= 0 for value in full.values()))

    def test_rendering_is_byte_stable(self):
        self.assertEqual(render_report(self.bundle), render_report(self.bundle))
        self.assertEqual(render_summary_csv(self.bundle), render_summary_csv(self.bundle))
        self.assertEqual(
            render_combined_values_csv(self.bundle), render_combined_values_csv(self.bundle)
        )

    def test_reports_expose_raw_repeats_memory_and_workers(self):
        report = render_report(self.bundle)
        self.assertIn("Raw timing repeats", report)
        self.assertIn("Peak RSS", report)
        self.assertIn("8 workers", report)
        self.assertIn("BTCUSDT", report)


if __name__ == "__main__":
    unittest.main()
