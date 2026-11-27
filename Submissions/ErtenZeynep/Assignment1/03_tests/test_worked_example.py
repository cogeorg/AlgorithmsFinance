"""Exact instructor worked-example and independent arithmetic checks."""

import json
import unittest
from pathlib import Path

from support import ENGINE_CLASSES


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORKED_EVENTS = PROJECT_ROOT / "02_data" / "supplied" / "data" / "worked_example.jsonl"
WORKED_EXPECTED = PROJECT_ROOT / "02_data" / "supplied" / "data" / "worked_expected.json"


def load_worked() -> tuple[list[dict], dict]:
    events = [json.loads(line) for line in WORKED_EVENTS.read_text(encoding="utf-8").splitlines()]
    expected = json.loads(WORKED_EXPECTED.read_text(encoding="utf-8"))
    return events, expected


class TestWorkedFixtures(unittest.TestCase):
    def test_supplied_fixture_is_exact_and_self_consistent(self) -> None:
        events, expected = load_worked()
        self.assertEqual(len(events), 6)
        self.assertEqual(events[-1]["event_id"], "event6")
        result = expected["market_sell_result"]
        self.assertEqual(
            [(item["maker_id"], item["price_ticks"], item["qty_units"]) for item in result["fills"]],
            [
                ("b1", 6_000_000, 100_000_000),
                ("b2", 6_000_000, 100_000_000),
                ("b3", 5_990_000, 300_000_000),
                ("b4", 5_970_000, 100_000_000),
            ],
        )
        proceeds = sum(item["price_ticks"] * item["qty_units"] for item in result["fills"])
        self.assertEqual(proceeds, 3_594_000_000_000_000)
        self.assertEqual(proceeds, expected["gross_proceeds_tick_units"])
        self.assertEqual(expected["gross_proceeds_usd"], "359400.00")
        self.assertEqual(
            expected["remaining_orders"],
            [
                {"order_id": "b4", "side": "BUY", "price_ticks": 5_970_000, "qty_units": 400_000_000, "arrival_seq": 4},
                {"order_id": "a1", "side": "SELL", "price_ticks": 6_010_000, "qty_units": 200_000_000, "arrival_seq": 5},
            ],
        )

    def test_each_engine_matches_exact_supplied_expected_output(self) -> None:
        events, expected = load_worked()
        for engine_class in ENGINE_CLASSES:
            with self.subTest(engine=engine_class.__name__):
                engine = engine_class()
                results = [engine.process_event(event) for event in events]
                self.assertEqual(results[-1], expected["market_sell_result"])
                self.assertEqual(engine.canonical_snapshot(), expected["remaining_orders"])
                self.assertEqual(engine.last_accepted_seq, 6)


if __name__ == "__main__":
    unittest.main()

