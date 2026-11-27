"""Version B: NumPy-vectorized American put backward induction."""
import math
import numpy as np
from price_american_put import PriceAmericanPut


def PriceAmericanPutB(S0, K, u, d, R, N):
    # Reuse Version A's validation without performing its full calculation.
    if type(N) is not int or N < 0:
        raise ValueError('N must be a nonnegative integer')
    PriceAmericanPut(S0, K, u, d, R, 0)
    q = (R - d) / (u - d)
    stock = np.empty(N + 1, dtype=float)
    stock[0] = S0
    for _ in range(N):
        stock[0] *= d
    if stock[0] == 0 or not math.isfinite(stock[0]):
        raise ValueError('Stock prices exceed floating-point range')
    # Keep the same multiplication order as A for close numerical agreement.
    for j in range(1, N + 1):
        stock[j] = stock[j - 1] * (u / d)
        if not math.isfinite(stock[j]):
            raise ValueError('Stock prices exceed floating-point range')
    value = np.maximum(K - stock, 0.0)
    for t in range(N - 1, -1, -1):
        stock[:t + 1] /= d
        # Evaluate the complete right-hand side before overwriting either successor.
        continuation = (q * value[1:t + 2] + (1 - q) * value[:t + 1]) / R
        value[:t + 1] = np.maximum(np.maximum(K - stock[:t + 1], 0.0), continuation)
    return float(value[0])
