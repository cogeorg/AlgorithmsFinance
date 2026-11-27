"""Financial contracts and exponential full-tree oracles for tiny trees only."""
from fractions import Fraction
from itertools import product
import math
from numbers import Real
import unittest

from american_put import price_american_put
from test_american_put import ABS_TOL, REL_TOL, PricingNotImplemented

# Fixed factors, discount factor, and depth are reused in every paired comparison.
TREES = (
    dict(S0=100, K=100, u=1.2, d=0.8, R=1.05, N=0),
    dict(S0=100, K=100, u=1.2, d=0.8, R=1.05, N=1),
    dict(S0=100, K=100, u=1.2, d=0.8, R=1.05, N=2),
    dict(S0=80, K=100, u=1.15, d=0.85, R=1.01, N=3),
    dict(S0=120, K=110, u=1.3, d=0.75, R=1.0, N=4),
    dict(S0=100, K=110, u=1.1, d=0.85, R=0.98, N=5),
)


def full_tree_american_put(S0, K, u, d, R, N):
    """Expand BOTH children at every node, with no recombination or memoization.

    This deliberately exponential, test-only oracle is limited to tiny fixtures.
    It imports no production pricing helpers and traverses actual path prices.
    """
    q = (R - d) / (u - d)

    def visit(stock, remaining):
        exercise = max(K - stock, 0.0)
        if remaining == 0:
            return exercise
        up = visit(stock * u, remaining - 1)
        down = visit(stock * d, remaining - 1)
        continuation = (q * up + (1 - q) * down) / R
        return max(exercise, continuation)

    return visit(S0, N)


def full_tree_european_put(S0, K, u, d, R, N):
    """Enumerate all 2**N terminal paths; discount the expected terminal payoff."""
    q = (R - d) / (u - d)
    weighted = []
    for path in product((True, False), repeat=N):
        stock = S0
        probability = 1.0
        for up in path:
            stock *= u if up else d
            probability *= q if up else 1 - q
        weighted.append(probability * max(K - stock, 0.0))
    return math.fsum(weighted) / R**N


class FullTreeReferenceTests(unittest.TestCase):
    """Check the independent evaluators even while production is unimplemented."""
    def assert_close(self, actual, expected):
        self.assertTrue(math.isfinite(actual))
        self.assertTrue(math.isclose(actual, float(expected), rel_tol=REL_TOL, abs_tol=ABS_TOL),
                        f'{actual!r} != {expected!s}')

    def test_american_reference_matches_hand_worked_values(self):
        cases = ((80, 0, 20), (100, 0, 0), (120, 0, 0),
                 (100, 1, Fraction(50, 7)), (100, 2, Fraction(1175, 147)),
                 (80, 1, 20), (120, 1, Fraction(10, 7)))
        for spot, periods, expected in cases:
            with self.subTest(S0=spot, N=periods):
                self.assert_close(full_tree_american_put(spot, 100, 1.2, 0.8, 1.05, periods), expected)

    def test_european_reference_matches_terminal_payoff_sums(self):
        # At N=2: probabilities 25/64, 30/64, 9/64; payoffs 0,4,36.
        cases = ((80, 0, 20), (120, 0, 0),
                 (100, 1, Fraction(50, 7)), (100, 2, Fraction(925, 147)))
        for spot, periods, expected in cases:
            with self.subTest(S0=spot, N=periods):
                self.assert_close(full_tree_european_put(spot, 100, 1.2, 0.8, 1.05, periods), expected)

    def test_reference_distinguishes_exercise_from_terminal_only_value(self):
        tree = dict(S0=80, K=100, u=1.2, d=0.8, R=1.05, N=1)
        american = full_tree_american_put(**tree)
        european = full_tree_european_put(**tree)
        self.assert_close(american, 20)
        self.assert_close(european, Fraction(320, 21))
        self.assertGreater(american, european)


class AmericanPutPropertyTests(unittest.TestCase):
    def price(self, tree):
        try:
            value = price_american_put(**tree)
        except NotImplementedError as exc:
            raise PricingNotImplemented(
                'PENDING_IMPLEMENTATION: price_american_put has no production implementation.'
            ) from exc
        self.assertIsInstance(value, Real)
        self.assertNotIsInstance(value, bool)
        self.assertTrue(math.isfinite(value))
        return value

    def assert_no_less(self, actual, lower):
        tolerance = ABS_TOL + REL_TOL * max(abs(actual), abs(lower))
        self.assertGreaterEqual(actual + tolerance, lower)

    def test_price_dominates_immediate_exercise(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                value = self.price(tree)
                self.assert_no_less(value, max(tree['K'] - tree['S0'], 0))

    def test_american_dominates_european_on_same_tree(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                self.assert_no_less(self.price(tree), full_tree_european_put(**tree))

    def test_increasing_strike_cannot_decrease_value(self):
        for tree in TREES:
            for lower, higher in ((0, 80), (80, 100), (100, 120)):
                with self.subTest(tree=tree, lower_K=lower, higher_K=higher):
                    low_value = self.price({**tree, 'K': lower})
                    high_value = self.price({**tree, 'K': higher})
                    self.assert_no_less(high_value, low_value)

    def test_increasing_initial_stock_cannot_increase_value(self):
        for tree in TREES:
            for lower, higher in ((60, 80), (80, 100), (100, 140)):
                with self.subTest(tree=tree, lower_S0=lower, higher_S0=higher):
                    low_stock_value = self.price({**tree, 'S0': lower})
                    high_stock_value = self.price({**tree, 'S0': higher})
                    self.assert_no_less(low_stock_value, high_stock_value)

    def test_price_does_not_exceed_strike_for_R_at_least_one(self):
        for tree in (tree for tree in TREES if tree['R'] >= 1):
            with self.subTest(tree=tree):
                self.assert_no_less(tree['K'], self.price(tree))

    def test_joint_spot_and_strike_scaling_scales_value(self):
        for tree in TREES:
            for factor in (0.125, 2.0, 3.7):
                with self.subTest(tree=tree, factor=factor):
                    base = self.price(tree)
                    scaled = self.price({**tree, 'S0': factor * tree['S0'], 'K': factor * tree['K']})
                    self.assertTrue(math.isclose(scaled, factor * base,
                                                rel_tol=REL_TOL, abs_tol=ABS_TOL))

    def test_production_matches_full_tree_reference(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                expected = full_tree_american_put(**tree)
                actual = self.price(tree)
                self.assertTrue(math.isclose(actual, expected, rel_tol=REL_TOL, abs_tol=ABS_TOL),
                                f'Production {actual!r} != full-tree reference {expected!r}')


if __name__ == '__main__':
    unittest.main()