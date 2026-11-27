import gzip
import json
from pathlib import Path
import tempfile
import unittest

from generate_orders import SCENARIOS, events, write_stream


class TestGenerator(unittest.TestCase):
    def test_deterministic_all_scenarios_and_schema(self):
        for scenario in SCENARIOS:
            a = list(events(scenario, 200, 42, 20))
            self.assertEqual(a, list(events(scenario, 200, 42, 20)))
            self.assertNotEqual(a, list(events(scenario, 200, 43, 20)))
            self.assertEqual([r["seq"] for r in a], list(range(1, 201)))
            self.assertEqual(len({r["event_id"] for r in a}), 200)
            self.assertTrue(all(r["type"] in ("LIMIT", "MARKET_SELL", "CANCEL") for r in a))

    def test_stable_gzip_and_roundtrip(self):
        # Scratch files stay under the authorized submission, never system /tmp.
        scratch = Path(__file__).resolve().parents[1] / ".preview"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as folder:
            a, b = Path(folder) / "a.gz", Path(folder) / "b.gz"
            rows = list(events("mixed", 100, 42, 10))
            write_stream(a, rows)
            write_stream(b, rows)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            with gzip.open(a, "rt") as stream:
                self.assertEqual([json.loads(line) for line in stream], rows)

    def test_churn_and_crowded_structure(self):
        rows = list(events("cancel_churn", 100, 42, 10))
        for add, remove in zip(rows[::2], rows[1::2]):
            self.assertEqual(remove["target_order_id"], add["order_id"])
        rows = list(events("crowded", 300, 42, 1000))
        for side in ("BUY", "SELL"):
            self.assertEqual(len({r["price_ticks"] for r in rows if r["side"] == side}), 4)
