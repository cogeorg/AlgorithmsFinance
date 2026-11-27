"""American put pricing using the two-array algorithm from the slides."""
import math


def PriceAmericanPut(S0, K, u, d, R, N):
    """Return the per-unit American put value at time zero."""
    for name, value in (('S0', S0), ('K', K), ('u', u), ('d', d), ('R', R)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError(f'{name} must be a finite number')
    if S0 <= 0 or K < 0:
        raise ValueError('S0 must be positive and K must be nonnegative')
    if type(N) is not int or N < 0:
        raise ValueError('N must be a nonnegative integer')
    if not 0 < d < R < u:
        raise ValueError('The model requires 0 < d < R < u')

    q = (R - d) / (u - d)
    stock = [S0] * (N + 1)
    for _ in range(N):
        stock[0] *= d
    if stock[0] == 0 or not math.isfinite(stock[0]):
        raise ValueError('Stock prices exceed floating-point range')
    for j in range(1, N + 1):
        stock[j] = stock[j - 1] * (u / d)
        if not math.isfinite(stock[j]):
            raise ValueError('Stock prices exceed floating-point range')
    value = [max(K - price, 0.0) for price in stock]
    for t in range(N - 1, -1, -1):
        for j in range(t + 1):
            stock[j] /= d
            continuation = (q * value[j + 1] + (1 - q) * value[j]) / R
            value[j] = max(K - stock[j], 0.0, continuation)
    return value[0]
