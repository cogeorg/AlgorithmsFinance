"""Checks for supplied streams and reproducible Phase 1 teaching data."""

import gzip
import hashlib
import importlib.util
import json
import unittest

from support import ROOT


SCENARIOS = ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
SMALL = (("buildup", 42), ("crowded", 43), ("mixed", 44),
         ("sweep", 42), ("cancel_churn", 43))


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as source:
        return [json.loads(line) for line in source]


class SyntheticDataTests(unittest.TestCase):
    def test_instructor_files_match_original_manifest(self):
        manifest = json.loads((ROOT / "MANIFEST.json").read_text(encoding="utf-8"))
        for relative, expected in manifest["files"].items():
            with self.subTest(file=relative):
                data = (ROOT / relative).read_bytes()
                self.assertEqual(len(data), expected["bytes"])
                self.assertEqual(hashlib.sha256(data).hexdigest(), expected["sha256"])

    def test_supplied_ten_thousand_event_streams(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                path = ROOT / "10_Data" / f"{scenario}_10000.jsonl.gz"
                data = rows(path)
                self.assertEqual(len(data), 10000)
                self.assertEqual([row["seq"] for row in data], list(range(1, 10001)))
                self.assertEqual(len({row["event_id"] for row in data}), 10000)
                self.assertTrue(all(row["type"] in ("LIMIT", "MARKET_SELL", "CANCEL")
                                    for row in data))
                extracted = (ROOT / "10_Data" / f"{scenario}_10000.jsonl").read_text()
                with gzip.open(path, "rt", encoding="utf-8") as source:
                    self.assertEqual(source.read(), extracted)

    def test_small_streams_match_seeded_generator_and_metadata(self):
        path = ROOT / "20_Code" / "generate_orders.py"
        spec = importlib.util.spec_from_file_location("instructor_generator", path)
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        for scenario, seed in SMALL:
            with self.subTest(scenario=scenario, seed=seed):
                name = f"phase1_{scenario}_80_seed{seed}.jsonl.gz"
                stream = ROOT / "10_Data" / name
                meta = json.loads((ROOT / "10_Data" / f"{name}.metadata.json").read_text())
                actual = rows(stream)
                expected = list(generator.events(scenario, 80, seed, 20))
                self.assertEqual(actual, expected)
                self.assertEqual(expected, list(generator.events(scenario, 80, seed, 20)))
                self.assertEqual(meta["scenario"], scenario)
                self.assertEqual(meta["seed"], seed)
                self.assertEqual(meta["events"], 80)
                self.assertEqual(meta["levels"], 20)
                self.assertEqual(meta["sha256"], hashlib.sha256(stream.read_bytes()).hexdigest())
                self.assertEqual([r["seq"] for r in actual], list(range(1, 81)))
                self.assertGreater(len({r["qty_units"] for r in actual if "qty_units" in r}), 1)
                self.assertGreater(len({r["price_ticks"] for r in actual if "price_ticks" in r}), 1)
                self.assertGreater(len({r["order_id"] for r in actual if "order_id" in r}), 1)
                kinds = {r["type"] for r in actual}
                if scenario in ("mixed", "sweep", "cancel_churn"):
                    self.assertGreater(len(kinds), 1)


if __name__ == "__main__":
    unittest.main()
