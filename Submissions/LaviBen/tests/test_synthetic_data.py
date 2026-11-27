"""Contract tests for the synthetic-data generator."""

from __future__ import annotations

import unittest

from synthetic_data import generate_search_case


class SyntheticDataTests(unittest.TestCase):
    def test_same_seed_is_reproducible(self) -> None:
        first = generate_search_case(40, 20, seed=123, hit_rate=0.6)
        second = generate_search_case(40, 20, seed=123, hit_rate=0.6)

        self.assertEqual(first, second)

    def test_requested_sizes_and_hit_count_are_exact(self) -> None:
        ids, queries = generate_search_case(30, 10, seed=8, hit_rate=0.4)
        present = set(ids)

        self.assertEqual(len(ids), 30)
        self.assertEqual(len(queries), 10)
        self.assertEqual(sum(query in present for query in queries), 4)

    def test_empty_array_forces_every_query_to_be_absent(self) -> None:
        ids, queries = generate_search_case(0, 7, seed=4, hit_rate=1.0)

        self.assertEqual(ids, [])
        self.assertEqual(len(queries), 7)
        self.assertFalse(any(query in set(ids) for query in queries))

    def test_zero_queries_and_extreme_hit_rates(self) -> None:
        ids, no_queries = generate_search_case(5, 0, seed=2, hit_rate=0.5)
        all_misses_ids, all_misses = generate_search_case(
            5, 8, seed=2, hit_rate=0.0
        )
        all_hits_ids, all_hits = generate_search_case(
            5, 8, seed=2, hit_rate=1.0
        )

        self.assertEqual(len(ids), 5)
        self.assertEqual(no_queries, [])
        self.assertTrue(all(query not in set(all_misses_ids) for query in all_misses))
        self.assertTrue(all(query in set(all_hits_ids) for query in all_hits))

    def test_single_query_mixed_rate_uses_nearest_representable_hit_count(self) -> None:
        ids, queries = generate_search_case(10, 1, seed=5, hit_rate=0.5)

        self.assertEqual(len(queries), 1)
        self.assertIn(queries[0], set(ids))

    def test_invalid_parameters_are_rejected(self) -> None:
        invalid_arguments = (
            (-1, 3, 0.5),
            (3, -1, 0.5),
            (3, 3, -0.01),
            (3, 3, 1.01),
        )

        for array_size, query_count, hit_rate in invalid_arguments:
            with self.subTest(
                array_size=array_size,
                query_count=query_count,
                hit_rate=hit_rate,
            ):
                with self.assertRaises(ValueError):
                    generate_search_case(
                        array_size,
                        query_count,
                        seed=0,
                        hit_rate=hit_rate,
                    )


if __name__ == "__main__":
    unittest.main()
