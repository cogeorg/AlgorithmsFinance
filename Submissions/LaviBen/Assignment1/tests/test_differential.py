"""Supplementary two-version agreement on small generated valid streams."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from tests.support import assert_book_invariants, require_implementations


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_generator():
    path = PROJECT_ROOT / "tools" / "generate_orders.py"
    spec = importlib.util.spec_from_file_location("assignment1_generator", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DifferentialTests(unittest.TestCase):
    def test_versions_agree_after_every_generated_event(self) -> None:
        implementations = require_implementations(self)
        generator = load_generator()

        for scenario in generator.SCENARIOS:
            for seed in (7, 8):
                with self.subTest(scenario=scenario, seed=seed):
                    stream = tuple(generator.events(scenario, 250, seed, 25))
                    books = {
                        name: book_class()
                        for name, book_class in implementations.items()
                    }
                    for event in stream:
                        results = {
                            name: book.ProcessEvent(event)
                            for name, book in books.items()
                        }
                        states = {
                            name: book.InspectBook()
                            for name, book in books.items()
                        }
                        self.assertEqual(results["baseline"], results["revised"])
                        self.assertEqual(states["baseline"], states["revised"])
                        for book in books.values():
                            assert_book_invariants(self, book)


if __name__ == "__main__":
    unittest.main()
