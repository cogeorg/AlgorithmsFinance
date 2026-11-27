"""PriceAmericanPut, naive full-tree version: stores every node of the value tree.

For contrast only. The backward pass keeps V for every date, (N+1)(N+2)/2 floats,
about 7.7 GB at N = 43,800. The boundary is then read off the stored tree in a
second pass. The arithmetic is the same as vectorised.py, so the results are identical.
"""
import numpy as np

from american_put.common import PutResult, check_inputs
from american_put.vectorised import _initial_prices, _top_index


def tree_bytes(N):
    """Bytes of float64 data in the stored value tree."""
    return 8 * (N + 1) * (N + 2) // 2


def value_tree(S0, K, u, d, R, N):
    """List of N+1 arrays: tree[t][j] = option value at date t, node j."""
    q = check_inputs(S0, K, u, d, R, N)
    S = _initial_prices(S0, u, d, N)
    tree = [None] * (N + 1)
    tree[N] = np.maximum(K - S, 0.0)
    for t in range(N - 1, -1, -1):
        St = S[: t + 1]
        St /= d
        nxt = tree[t + 1]
        c = (q * nxt[1 : t + 2] + (1 - q) * nxt[: t + 1]) / R
        tree[t] = np.maximum(np.maximum(K - St, 0.0), c)  # new array per date, all kept
    return tree


def price_american_put(S0, K, u, d, R, N):
    q = check_inputs(S0, K, u, d, R, N)
    tree = value_tree(S0, K, u, d, R, N)

    # Second pass over the stored tree: recompute the prices in the same order and
    # compare exercise with continuation at every node.
    boundary = [None] * (N + 1)
    S = _initial_prices(S0, u, d, N)
    j = _top_index(K - S > 0)
    if j >= 0:
        boundary[N] = float(S[j])
    for t in range(N - 1, -1, -1):
        St = S[: t + 1]
        St /= d
        nxt = tree[t + 1]
        c = (q * nxt[1 : t + 2] + (1 - q) * nxt[: t + 1]) / R
        exercise = K - St
        j = _top_index((exercise > 0) & (exercise >= c))
        if j >= 0:
            boundary[t] = float(St[j])

    return PutResult(float(tree[0][0]), boundary)
