"""Recombining American put tree: O(N²) time, O(N) storage.

Tree state j is the number of up moves. Values are overwritten in increasing
j order, so both children are still values from the following time slice.
Positive-payoff exercise ties exercise; zero-payoff ties continue/lapse.
"""
import math
import numbers
import numpy as np
from numba import njit


@njit(nogil=True)
def _kernel(S0, K, log_u, log_d, log_R, N):
    boundary = np.full(N + 1, np.nan)
    values = np.empty(N + 1)
    if K == 0.0:
        return 0.0, boundary
    origin = math.log(S0 / K)
    spread = (log_u - log_d) / 2.0
    center = (log_u + log_d) / 2.0
    q = math.exp(log_R-log_u) * (-math.expm1(log_d-log_R)) / (-math.expm1(log_d-log_u))
    discount = math.exp(-log_R)
    best = -math.inf
    for j in range(N + 1):
        z = origin + N * center + (2*j-N)*spread
        values[j] = -K*math.expm1(z) if z < 0 else 0.0
        if z < 0:
            best = z
    if best > -math.inf:
        boundary[N] = K * math.exp(best)
    for t in range(N-1, -1, -1):
        best = -math.inf
        for j in range(t+1):
            z = origin + t*center + (2*j-t)*spread
            exercise = -K*math.expm1(z) if z < 0 else 0.0
            continuation = ((1-q)*values[j] + q*values[j+1])*discount
            if exercise > 0 and exercise >= continuation:
                values[j] = exercise
                best = z
            else:
                values[j] = continuation
        if best > -math.inf:
            boundary[t] = K*math.exp(best)
    return values[0], boundary


def PriceAmericanPut(S0, K, u, d, R, N):
    """Return (price, boundary[0:N+1]); NaN means no exercise node.

    u,d,R are gross factors per step, R includes principal. No dividends.
    """
    if isinstance(N, bool) or not isinstance(N, numbers.Integral) or N < 0:
        raise ValueError('N must be a nonnegative integer')
    if not all(math.isfinite(x) for x in (S0,K,u,d,R)):
        raise ValueError('Inputs must be finite')
    if S0 <= 0 or K < 0 or not 0 < d < R < u:
        raise ValueError('Require S0>0, K>=0 and 0<d<R<u')
    return _kernel(float(S0),float(K),math.log(u),math.log(d),math.log(R),int(N))


def calibrate(times, closes, annual_rate=0.04):
    """Sample log-return volatility and ACT/365 elapsed-time discounting."""
    times = np.asarray(times, dtype=np.int64)
    closes = np.asarray(closes, dtype=np.float64)
    if len(times) != len(closes) or len(times) < 3:
        raise ValueError('Need at least three matching timestamps/prices')
    if np.any(np.diff(times) <= 0) or np.any(~np.isfinite(closes)) or np.any(closes <= 0):
        raise ValueError('Require increasing timestamps and positive finite prices')
    N = len(closes)-1
    sigma = float(np.std(np.diff(np.log(closes)), ddof=1))
    T = float(times[-1]-times[0])/(365*24*3600)
    log_R = annual_rate*T/N
    if not math.isfinite(sigma) or not -sigma < log_R < sigma:
        raise ValueError('Calibration violates no-arbitrage')
    return dict(S0=float(closes[0]), K=float(closes[0]), sigma=sigma,
                u=math.exp(sigma), d=math.exp(-sigma), R=math.exp(log_R),
                log_R=log_R, T=T, N=N,
                q=math.expm1(log_R+sigma)/math.expm1(2*sigma),
                missing_hours=int((times[-1]-times[0])//3600-N))


def price_calibrated(parameters):
    p = parameters
    return _kernel(p['S0'],p['K'],p['sigma'],-p['sigma'],p['log_R'],p['N'])


def first_crossing(closes, boundary, K):
    """First observed close at/below the same-index positive-payoff boundary."""
    if len(closes) != len(boundary):
        raise ValueError('Price and boundary lengths differ')
    for i, (spot, level) in enumerate(zip(closes,boundary)):
        if math.isfinite(level) and spot <= level:
            return {'index': i, 'spot': float(spot), 'boundary': float(level),
                    'payoff': float(K-spot)}
    return None
