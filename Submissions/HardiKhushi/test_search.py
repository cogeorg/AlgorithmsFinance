"""Run with python3 -m unittest discover -s Submissions/HardiKhushi -v."""

import random
import unittest

try:
    from .search import VERSIONED_METHODS as SEARCH_METHODS, VERSIONS
    from .data_generator import generate_workload
except ImportError:  # Direct execution or unittest discovery in this folder.
    from search import VERSIONED_METHODS as SEARCH_METHODS, VERSIONS
    from data_generator import generate_workload


class SearchTests(unittest.TestCase):
    def check_methods(self, ids, queries, expected):
        for name, method in SEARCH_METHODS.items():
            with self.subTest(method=name, ids=ids, queries=queries):
                original_ids = ids.copy()
                original_queries = queries.copy()
                result = method(ids, queries)
                self.assertEqual(result, expected)
                self.assertTrue(all(type(answer) is bool for answer in result))
                self.assertEqual(ids, original_ids)
                self.assertEqual(queries, original_queries)

    def test_normal_search(self):
        self.check_methods([7, 11, 7], [11, 9, 7], [True, False, True])

    def test_empty_ids(self):
        self.check_methods([], [5], [False])

    def test_empty_queries(self):
        self.check_methods([1, 2, 3], [], [])
        self.check_methods([], [], [])

    def test_single_element(self):
        self.check_methods([5], [5, 8], [True, False])

    def test_unsorted_ids(self):
        self.check_methods([9, 2, 7], [2, 9, 4], [True, True, False])

    def test_duplicates_and_negative_ids(self):
        self.check_methods([0, -3, -3, 8], [-3, 8, -3, 0, -1],
                           [True, True, True, True, False])

    def test_randomized_reference(self):
        rng = random.Random(42)
        for _ in range(50):
            ids = [rng.randrange(-30, 31) for _ in range(rng.randrange(60))]
            queries = [rng.randrange(-40, 41) for _ in range(30)]
            expected = [any(item == query for item in ids) for query in queries]
            self.check_methods(ids, queries, expected)

    def test_binary_boundaries_and_gaps(self):
        self.check_methods([8, 1, 4], [-1, 1, 2, 4, 7, 8, 9],
                           [False, True, False, True, False, True, False])

    def test_all_equal_and_repeated_queries(self):
        self.check_methods([3] * 30, [3, 3, 2, 3, 4],
                           [True, True, False, True, False])

    def test_varied_generated_workloads(self):
        for seed in (42, 137):
            for policy in ("unique", "repeated"):
                for scenario in ("all-present", "all-absent", "mixed"):
                    workload = generate_workload(200, 51, seed=seed,
                                                 scenario=scenario,
                                                 duplicate_policy=policy)
                    self.check_methods(workload.ids, workload.queries, workload.expected)

    def test_prepared_state_can_be_reused_without_mutation(self):
        for version, methods in VERSIONS.items():
            for name, prepare in methods["prepare"].items():
                with self.subTest(version=version, method=name):
                    ids, queries = [9, -2, 9, 0], [9, 3, -2]
                    prepared = prepare(ids)
                    snapshot = prepared.copy()
                    for _ in range(2):
                        self.assertEqual(methods["query"][name](prepared, queries),
                                         [True, False, True])
                        self.assertEqual(prepared, snapshot)
                        self.assertEqual(ids, [9, -2, 9, 0])
                        self.assertEqual(queries, [9, 3, -2])


if __name__ == "__main__":
    unittest.main()
