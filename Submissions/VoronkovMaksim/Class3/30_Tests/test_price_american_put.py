import math
import unittest
from price_american_put import PriceAmericanPut


class PriceTests(unittest.TestCase):
    def test_slide_example(self):
        self.assertAlmostEqual(PriceAmericanPut(100, 100, 1.2, 0.8, 1.05, 2), 7.9931972789, places=8)

    def test_expiry_and_zero_strike(self):
        self.assertEqual(PriceAmericanPut(80, 100, 1.2, .8, 1.05, 0), 20)
        self.assertEqual(PriceAmericanPut(100, 0, 1.2, .8, 1.05, 4), 0)

    def test_invalid_inputs(self):
        valid = [100, 100, 1.2, .8, 1.05, 2]
        for index, wrong in [(0, -1), (0, 0), (1, -1), (2, float('nan')), (3, -1),
                             (4, 1.3), (5, -1), (5, 1.5), (5, True), (0, True), (1, math.inf)]:
            args = valid.copy()
            args[index] = wrong
            with self.subTest(index=index, wrong=wrong), self.assertRaises(ValueError):
                PriceAmericanPut(*args)


if __name__ == '__main__':
    unittest.main()
