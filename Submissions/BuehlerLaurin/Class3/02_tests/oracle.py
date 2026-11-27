"""Independent exact small-tree oracle: recursive, no production imports."""
from fractions import Fraction as F
from functools import lru_cache


def exact(S0, K, u, d, R, N, european=False):
    S0, K, u, d, R = map(F, (S0, K, u, d, R))
    q = (R-d)/(u-d)

    def stock(t, j):
        return S0*u**j*d**(t-j)

    @lru_cache(None)
    def value(t, j):
        intrinsic = max(K-stock(t,j), 0)
        if t == N:
            return intrinsic
        continuation = (q*value(t+1,j+1)+(1-q)*value(t+1,j))/R
        return continuation if european else max(intrinsic, continuation)

    boundary = []
    for t in range(N+1):
        exercise = []
        for j in range(t+1):
            intrinsic = K-stock(t,j)
            continuation = 0 if t == N else (q*value(t+1,j+1)+(1-q)*value(t+1,j))/R
            if intrinsic > 0 and intrinsic >= continuation:
                exercise.append(stock(t,j))
        boundary.append(max(exercise) if exercise else None)
    return value(0,0), boundary
