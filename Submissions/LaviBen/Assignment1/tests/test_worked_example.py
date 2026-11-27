"""Exact course worked example, calculated independently before implementation."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from tests.support import assert_book_invariants, require_implementations


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class WorkedExampleTests(unittest.TestCase):
    def test_six_btc_example_matches_exact_fills_book_and_proceeds(self) -> None:
        events = [
            json.loads(line)
            for line in (PROJECT_ROOT / "fixtures" / "worked_example.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line
        ]
        expected = json.loads(
            (PROJECT_ROOT / "fixtures" / "worked_expected.json").read_text(
                encoding="utf-8"
            )
        )

        for name, book_class in require_implementations(self).items():
            with self.subTest(implementation=name):
                book = book_class()
                results = []
                for event in events:
                    results.append(book.ProcessEvent(event))
                    assert_book_invariants(self, book)

                self.assertTrue(all(result["status"] == "resting" for result in results[:5]))
                self.assertEqual(results[-1], expected["market_sell_result"])
                self.assertEqual(book.InspectBook(), expected["remaining_orders"])
                proceeds = sum(
                    item["price_ticks"] * item["qty_units"]
                    for item in results[-1]["fills"]
                )
                self.assertEqual(proceeds, expected["gross_proceeds_tick_units"])
                self.assertEqual(proceeds // 10_000_000_000, 359_400)


if __name__ == "__main__":
    unittest.main()
