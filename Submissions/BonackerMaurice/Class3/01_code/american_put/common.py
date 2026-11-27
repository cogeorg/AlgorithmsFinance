"""Shared pieces of the three pricers: result type, q, and the float-range guard."""
import math
import sys
from typing import NamedTuple

# Smallest positive normal float and largest float, as natural logs (about -708.4 and 709.8).
LOG_FLOAT_MIN = math.log(sys.float_info.min)
LOG_FLOAT_MAX = math.log(sys.float_info.max)


class PutResult(NamedTuple):
    value: float                    # V[0], the option value at the root
    boundary: list                  # boundary[t] for t = 0..N: highest tree price where
                                    # exercising is optimal (K-S > 0 and K-S >= continuation), or None


def risk_neutral_q(u, d, R):
    """q = (R-d)/(u-d). Raises ValueError unless d < R < u (otherwise 0 < q < 1 fails)."""
    if not d < R < u:
        raise ValueError(f"need d < R < u for 0 < q < 1, got d={d}, R={R}, u={u}")
    return (R - d) / (u - d)


def tree_log_range(S0, u, d, N):
    """Natural logs of the lowest and highest final tree prices, S0*d^N and S0*u^N."""
    return math.log(S0) + N * math.log(d), math.log(S0) + N * math.log(u)


def check_inputs(S0, K, u, d, R, N):
    """Validate the tree and return q.

    Numerical trap: S[0] = S0*d^N underflows when ln S0 + N ln d < ln(float min); with
    u = e^s, d = 1/u this is roughly s*N > 708. Then S[0] becomes 0 (or a subnormal with
    few significant digits), and S[j] = S[j-1]*u/d makes every node 0. The pricer refuses
    such trees instead of returning a wrong price. d^N on its own is checked too, because
    the pseudocode computes d**N before multiplying by S0.
    """
    if N < 0:
        raise ValueError(f"N must be >= 0, got {N}")
    if S0 <= 0 or K < 0:
        raise ValueError(f"need S0 > 0 and K >= 0, got S0={S0}, K={K}")
    q = risk_neutral_q(u, d, R)
    lo, hi = tree_log_range(S0, u, d, N)
    if min(lo, N * math.log(d)) < LOG_FLOAT_MIN or hi > LOG_FLOAT_MAX:
        raise ValueError(
            f"tree prices leave the float range: ln(S0 d^N) = {lo:.1f}, ln(S0 u^N) = {hi:.1f}, "
            f"allowed [{LOG_FLOAT_MIN:.1f}, {LOG_FLOAT_MAX:.1f}]"
        )
    return q
