"""Run with python3 -m unittest discover -s Submissions/HardiKhushi -v."""

import random
import unittest

try:
    from .search import SEARCH_METHODS
except ImportError:  # Direct execution or unittest discovery in this folder.
    from search import SEARCH_METHODS


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


if __name__ == "__main__":
    unittest.main()
    
