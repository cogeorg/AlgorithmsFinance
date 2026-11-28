import tempfile
import unittest
from pathlib import Path

from dashboard import load_dashboard_data, render_dashboard


SUBMISSION_DIR = Path(__file__).resolve().parents[1]


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_dashboard_data(SUBMISSION_DIR / "results")
        cls.html = render_dashboard(cls.data)

    def test_all_required_runs_and_raw_evidence_are_present(self):
        self.assertEqual(4, len(self.data["scenarios"]))
        self.assertTrue(all(item["status"] == "completed"
                            for item in self.data["scenarios"]))
        self.assertTrue(all(len(item["raw_seconds"]) == 5
                            for item in self.data["scenarios"]))
        for text in ("Raw timing repeats", "Peak RSS", "seconds", "MiB",
                     "8 workers", "completed"):
            self.assertIn(text, self.html)

    def test_all_assets_and_bitcoin_exercise_are_exposed(self):
        self.assertEqual(40, len(self.data["assets"]))
        self.assertIn("BTCUSDT", {item["symbol"] for item in self.data["assets"]})
        self.assertIn("2026-06-02", self.html)
        self.assertIn("2022-06-18", self.html)
        self.assertIn("bitcoin_full_boundary.csv", self.html)

    def test_environment_correctness_and_optimization_are_exposed(self):
        for text in ("Compiler", "Python", "Source checksums", "65.88",
                     "positive", "2023-03-24 13:00 UTC"):
            self.assertIn(text, self.html)

    def test_dashboard_is_standalone_accessible_and_byte_stable(self):
        self.assertNotIn("<script src=", self.html)
        self.assertNotIn("<link rel=\"stylesheet\"", self.html)
        self.assertIn('name="viewport"', self.html)
        self.assertIn("aria-label", self.html)
        self.assertEqual(self.html, render_dashboard(self.data))

    def test_missing_runs_remain_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            data = load_dashboard_data(Path(folder))
            html = render_dashboard(data)
        self.assertTrue(all(item["status"] == "missing" for item in data["scenarios"]))
        self.assertIn("missing", html)


if __name__ == "__main__":
    unittest.main()
