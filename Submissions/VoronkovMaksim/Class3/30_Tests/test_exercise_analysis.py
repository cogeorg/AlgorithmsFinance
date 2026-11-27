import unittest
from exercise_analysis import boundary_tree


class BoundaryTests(unittest.TestCase):
    def test_two_period_tree(self):
        price, boundaries = boundary_tree(100, 100, 1.2, 0.8, 1.05, 2)
        self.assertAlmostEqual(price, 7.9931972789, places=8)
        self.assertIsNone(boundaries[0])
        self.assertAlmostEqual(boundaries[1], 80)
        self.assertAlmostEqual(boundaries[2], 96)

    def test_no_positive_payoff(self):
        price, boundaries = boundary_tree(100, 0, 1.2, .8, 1.05, 2)
        self.assertEqual(price, 0)
        self.assertEqual(boundaries, [None, None, None])


if __name__ == '__main__':
    unittest.main()
