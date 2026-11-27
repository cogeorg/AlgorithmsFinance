"""Check workload guarantees independently of the search implementations."""

import random
import unittest

try:
    from .data_generator import generate_workload
except ImportError:
    from data_generator import generate_workload


class GeneratorTests(unittest.TestCase):
    def test_reproducible_without_changing_global_randomness(self):
        state = random.getstate()
        first = generate_workload(25, 11, seed=7)
        self.assertEqual(first, generate_workload(25, 11, seed=7))
        self.assertEqual(random.getstate(), state)
        self.assertNotEqual(first.ids, generate_workload(25, 11, seed=8).ids)

    def test_scenarios_and_known_answers(self):
        for policy in ("unique", "repeated"):
            for scenario, hits in (("all-present", 7), ("all-absent", 0), ("mixed", 4)):
                with self.subTest(policy=policy, scenario=scenario):
                    workload = generate_workload(20, 7, scenario=scenario,
                                                 duplicate_policy=policy)
                    self.assertEqual(len(workload.ids), 20)
                    self.assertEqual(len(workload.queries), 7)
                    reference = [query in set(workload.ids) for query in workload.queries]
                    self.assertEqual(workload.expected, reference)
                    self.assertEqual(sum(reference), hits)
                    self.assertEqual(workload.settings["hit_rate"], hits / 7)

    def test_duplicate_policies(self):
        for n in (0, 1, 2, 9, 10):
            for policy in ("unique", "repeated"):
                with self.subTest(n=n, policy=policy):
                    workload = generate_workload(n, 0, duplicate_policy=policy)
                    distinct = n if policy == "unique" else (n + 1) // 2
                    self.assertEqual(len(set(workload.ids)), distinct)
                    self.assertEqual(workload.settings["distinct_ids"], distinct)

    def test_empty_inputs(self):
        empty = generate_workload(0, 0)
        self.assertEqual((empty.ids, empty.queries, empty.expected), ([], [], []))
        absent = generate_workload(0, 3, scenario="all-absent")
        self.assertEqual(absent.expected, [False] * 3)
        self.assertEqual(absent.settings["hit_rate"], 0)
        for scenario in ("all-present", "mixed"):
            with self.assertRaises(ValueError):
                generate_workload(0, 1, scenario=scenario)

    def test_invalid_settings(self):
        for n, q in ((-1, 3), (3, -1)):
            with self.assertRaises(ValueError):
                generate_workload(n, q)
        with self.assertRaises(ValueError):
            generate_workload(10, 3, scenario="unknown")
        with self.assertRaises(ValueError):
            generate_workload(10, 3, duplicate_policy="unknown")

    def test_default_preserves_original_benchmark_workload(self):
        # Keep existing results reproducible after extracting the generator.
        for n in (1000, 5000, 10000):
            rng = random.Random(42 + n)
            ids = list(range(n))
            rng.shuffle(ids)
            queries = [rng.randrange(n) if i % 2 == 0 else n + rng.randrange(n)
                       for i in range(200)]
            rng.shuffle(queries)
            workload = generate_workload(n, 200)
            self.assertEqual(workload.ids, ids)
            self.assertEqual(workload.queries, queries)


if __name__ == "__main__":
    unittest.main()
