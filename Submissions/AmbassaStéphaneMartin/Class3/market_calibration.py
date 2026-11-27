"""Hourly log-return calibration for the PriceAmericanPut lab.

Inputs are already-validated consecutive hourly prices from prepare_data.py.
The caller must supply actual elapsed T in years; this price-only interface
cannot detect timestamp gaps and must not bridge them silently.
"""
from collections.abc import Sequence
from dataclasses import dataclass
import math
import statistics
import sys


@dataclass(frozen=True)
class Calibration:
    """Outputs for direct use with the established scalar pricing interface."""
    N: int
    log_returns: tuple[float, ...]
    s: float
    u: float
    d: float
    R: float
    q: float


def _finite_float(value, name):
    """Normalize finite real inputs without accepting numeric text or booleans."""
    try:
        if isinstance(value, bool) or not math.isfinite(value):
            raise ValueError(f'{name} must be a finite real number.')
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f'{name} must be a finite real number representable as float.') from exc
    if not math.isfinite(number):
        raise ValueError(f'{name} must be finite.')
    return number


def _finite_sequence(values, name, minimum):
    try:
        normalized = tuple(_finite_float(value, name) for value in values)
    except TypeError as exc:
        raise ValueError(f'{name} must be a sequence of finite real numbers.') from exc
    if len(normalized) < minimum:
        raise ValueError(f'{name} requires at least {minimum} observations.')
    return normalized


def log_returns(prices: Sequence[float]) -> tuple[float, ...]:
    """Return ln(P_i/P_(i-1)) in input order, for i=1,...,len(prices)-1.

    Require at least two positive finite prices; otherwise raise ValueError.
    Do not substitute arithmetic returns or returns relative to the first price.
    """
    prices = _finite_sequence(prices, 'prices', 2)
    if any(price <= 0 for price in prices):
        raise ValueError('Prices must be positive and finite.')
    returns = []
    for previous, current in zip(prices, prices[1:]):
        ratio = current / previous
        if 0.5 <= ratio <= 2.0:
            # Preserve small changes that a rounded ratio can obscure.
            value = math.log1p((current - previous) / previous)
        elif sys.float_info.min <= ratio < math.inf:
            value = math.log(ratio)
        else:
            # Avoid overflowing and subnormal ratios, including rounded zero.
            value = math.log(current) - math.log(previous)
        returns.append(value)
    return tuple(returns)


def sample_hourly_volatility(returns: Sequence[float]) -> float:
    """Return the sample standard deviation of hourly LOG returns.

    For N returns, use sqrt(sum((r_i-mean(r))**2)/(N-1)). Require at least
    two finite returns; otherwise raise ValueError. Constant returns have s=0,
    even if their mean is nonzero. Do not annualize or rescale hourly s.
    """
    returns = _finite_sequence(returns, 'returns', 2)
    # statistics.stdev uses N-1 and accurate sums; it avoids forming a naive
    # sum of squared floats that can overflow or underflow unnecessarily.
    try:
        s = statistics.stdev(returns)
    except (OverflowError, ValueError) as exc:
        raise ValueError('Hourly volatility must be representable as a finite float.') from exc
    if not math.isfinite(s):
        raise ValueError('Hourly volatility must be finite.')
    return s


def calibrate_binomial(prices: Sequence[float], *, T: float, annual_rate: float = 0.04) -> Calibration:
    """Calibrate the lab tree and return immutable Calibration outputs.

    N=len(prices)-1, s=sample hourly log-return standard deviation,
    u=exp(s), d=1/u, R=exp(annual_rate*T/N), q=(R-d)/(u-d).
    T is actual elapsed years; annual_rate is continuously compounded.

    Require >=3 positive finite closes, finite T>0 and finite annual_rate.
    Raise ValueError for insufficient observations or invalid numeric inputs.
    Reject zero volatility with ValueError whose message mentions volatility:
    u=d=1 makes q undefined. Do not inject a volatility floor.
    Also reject nonfinite/degenerate factors and failures of 0<d<R<u (or
    0<q<1) with ValueError explaining no-arbitrage/probability. Never clip q.

    A nonzero constant log return still has zero volatility and is rejected.
    """
    T = _finite_float(T, 'T')
    annual_rate = _finite_float(annual_rate, 'annual_rate')
    if T <= 0:
        raise ValueError('T must be positive elapsed years.')
    returns = log_returns(prices)
    s = sample_hourly_volatility(returns)
    if s == 0:
        raise ValueError('Zero hourly volatility makes the binomial probability undefined.')
    N = len(returns)
    exponent = annual_rate * T
    # Divide first only when the intermediate annual_rate*T overflows.
    exponent = exponent / N if math.isfinite(exponent) else annual_rate * (T / N)
    try:
        u = math.exp(s)
        d = 1.0 / u
        R = math.exp(exponent)
    except OverflowError as exc:
        raise ValueError('No-arbitrage requires finite nondegenerate factors: 0 < d < R < u.') from exc
    if not all(math.isfinite(value) for value in (u, d, R)) or not 0 < d < R < u:
        raise ValueError('No-arbitrage requires finite nondegenerate factors: 0 < d < R < u.')
    q = (R - d) / (u - d)
    if not math.isfinite(q) or not 0 < q < 1:
        raise ValueError('No-arbitrage probability must satisfy 0 < q < 1.')
    return Calibration(N=N, log_returns=returns, s=s, u=u, d=d, R=R, q=q)
