"""Shared contract tests. Run: python3 -B -m unittest -v test_search"""

import unittest

import search


METHODS = ("linear_search", "binary_search", "hash_set_search")


class MembershipContractTests(unittest.TestCase):
    def check_case(self, array, queries, expected):
        for name in METHODS:
            with self.subTest(method=name):
                method = getattr(search, name, None)
                self.assertTrue(callable(method), f"search.{name} is not implemented")
                # Each method receives independent copies of the same inputs.
                given_array = array.copy()
                given_queries = queries.copy()
                result = method(given_array, given_queries)
                self.assertIsInstance(result, list)
                self.assertEqual(result, expected)
                # Python considers 1 == True, so check Boolean types explicitly.
                self.assertTrue(all(type(value) is bool for value in result))
                self.assertEqual(given_array, array, "Input array was modified")

    def test_both_inputs_empty(self):
        self.check_case([], [], [])

    def test_empty_array(self):
        self.check_case([], [0, 7, -1], [False, False, False])

    def test_empty_queries(self):
        self.check_case([3, 1, 3], [], [])

    def test_single_entry(self):
        self.check_case([7], [7, 6, 8, 7], [True, False, False, True])

    def test_slide_example(self):
        self.check_case([7, 11, 7], [11, 9, 7], [True, False, True])

    def test_unsorted_array_and_query_order(self):
        self.check_case(
            [9, 2, 7, 4], [7, 3, 9, 2, 8, 4],
            [True, False, True, True, False, True],
        )

    def test_all_entries_equal(self):
        self.check_case([5, 5, 5, 5], [4, 5, 6, 5], [False, True, False, True])

    def test_sorted_boundaries_and_gaps(self):
        # Includes the first/last entries and values outside/between entries.
        self.check_case(
            [2, 4, 6, 8], [2, 8, 1, 9, 5, 4, 6],
            [True, True, False, False, False, True, True],
        )

    def test_two_entries(self):
        self.check_case([8, 2], [2, 8, 5, 1, 9], [True, True, False, False, False])

    def test_negative_zero_and_large_integers(self):
        self.check_case(
            [10**30, -7, 0, -10**30],
            [-10**30, 0, 10**30, -7, 7, 10**30 + 1],
            [True, True, True, True, False, False],
        )

    def test_all_queries_present(self):
        self.check_case([8, 3, 5], [5, 8, 3, 5], [True, True, True, True])

    def test_all_queries_absent(self):
        self.check_case([8, 3, 5], [2, 4, 9], [False, False, False])

    def test_repeated_calls_do_not_reuse_stale_state(self):
        for name in METHODS:
            with self.subTest(method=name):
                method = getattr(search, name, None)
                self.assertTrue(callable(method), f"search.{name} is not implemented")
                array = [9, 2, 9]
                first = method(array, [9, 4, 2])
                self.assertEqual(first, [True, False, True])
                self.assertEqual(array, [9, 2, 9])
                self.assertEqual(method(array, [4, 9]), [False, True])
                self.assertEqual(array, [9, 2, 9])
                self.assertEqual(method([4], [9, 4, 2]), [False, True, False])
                self.assertEqual(method([], [9]), [False])
                self.assertEqual(method(array, [9, 4, 2]), [True, False, True])
                self.assertEqual(array, [9, 2, 9])
                self.assertEqual(first, [True, False, True], "Earlier output was modified")


if __name__ == "__main__":
    unittest.main()
