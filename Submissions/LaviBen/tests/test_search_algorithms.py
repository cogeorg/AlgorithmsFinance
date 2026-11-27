"""Shared behavioral tests for every search implementation."""

from __future__ import annotations

import unittest

from search_algorithms import (
    binary_search,
    binary_search_recursive_v1,
    hash_set_membership,
    linear_search,
)


REQUIRED_IMPLEMENTATIONS = {
    "linear": linear_search,
    "binary_iterative": binary_search,
    "hash_set": hash_set_membership,
}

# The original recursive implementation remains covered after the iterative
# revision so that the two binary-search versions can be compared fairly.
ALL_IMPLEMENTATIONS = {
    **REQUIRED_IMPLEMENTATIONS,
    "binary_recursive_v1": binary_search_recursive_v1,
}

CASES = (
    ("both empty", [], [], []),
    ("empty array", [], [4, -1], [False, False]),
    ("empty queries", [4, 2], [], []),
    ("one entry present", [5], [5], [True]),
    ("one entry absent", [5], [6], [False]),
    (
        "duplicates and unsorted example",
        [7, 11, 7],
        [11, 9, 7],
        [True, False, True],
    ),
    (
        "unsorted mixed signs",
        [9, -2, 4, 1],
        [1, 9, 8, -2],
        [True, True, False, True],
    ),
    (
        "repeated queries preserve order",
        [2, 4, 6],
        [6, 1, 2, 6, 4, 1],
        [True, False, True, True, True, False],
    ),
    (
        "boundary misses around duplicate values",
        [5, 1, 5, 9, 5],
        [0, 1, 5, 9, 10],
        [False, True, True, True, False],
    ),
)


class SearchAlgorithmContractTests(unittest.TestCase):
    def test_every_implementation_satisfies_the_same_cases(self) -> None:
        for implementation_name, search in ALL_IMPLEMENTATIONS.items():
            for case_name, ids, queries, expected in CASES:
                with self.subTest(
                    implementation=implementation_name,
                    case=case_name,
                ):
                    original_ids = ids.copy()
                    original_queries = queries.copy()

                    result = search(ids, queries)

                    self.assertEqual(result, expected)
                    self.assertIs(type(result), list)
                    self.assertTrue(all(type(item) is bool for item in result))
                    self.assertEqual(ids, original_ids, "input IDs were mutated")
                    self.assertEqual(
                        queries,
                        original_queries,
                        "query order or values were mutated",
                    )

    def test_sequence_inputs_do_not_require_lists(self) -> None:
        ids = (8, 3, 8)
        queries = (3, 7, 8)
        expected = [True, False, True]

        for implementation_name, search in ALL_IMPLEMENTATIONS.items():
            with self.subTest(implementation=implementation_name):
                self.assertEqual(search(ids, queries), expected)

    def test_required_public_methods_are_distinct_callables(self) -> None:
        methods = list(REQUIRED_IMPLEMENTATIONS.values())

        self.assertTrue(all(callable(method) for method in methods))
        self.assertEqual(len({id(method) for method in methods}), 3)


if __name__ == "__main__":
    unittest.main()
