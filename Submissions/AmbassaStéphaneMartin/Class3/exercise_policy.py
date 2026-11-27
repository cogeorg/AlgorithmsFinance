"""American put exercise boundaries and decisions on an observed price path.

The existing american_put.price_american_put scalar interface is unchanged.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from american_put import _finite_float, _price_tree


@dataclass(frozen=True)
class PutExerciseResult:
    price: float
    boundary: tuple[float | None, ...]


@dataclass(frozen=True)
class ObservedExercise:
    kind: Literal['early_exercise', 'maturity_settlement', 'never']
    index: int | None
    timestamp_utc: datetime | None
    payoff: float


def price_american_put_with_boundary(S0: float, K: float, u: float, d: float, R: float, N: int) -> PutExerciseResult:
    """Use the scalar pricer's six inputs and validation; additionally report boundary.

    boundary[t], t=0,...,N, is the highest stock among exercising nodes, or None
    if there is no exercising node. Length is N+1, including root and maturity.
    Before maturity exercise ONLY when intrinsic > continuation: exact ties,
    including 0 == 0, continue. At maturity positive-payoff nodes settle;
    zero-payoff nodes are not exercise nodes. Thus any numeric boundary is <K.
    For N=0, boundary[0] describes maturity, not an early-exercise opportunity.
    Return the same time-zero price as american_put.price_american_put.
    """
    price, boundary = _price_tree(S0, K, u, d, R, N, record_boundary=True)
    return PutExerciseResult(price=price, boundary=boundary)


def first_observed_exercise(prices: Sequence[float], boundary: Sequence[float | None], K: float,
                            *, timestamps_utc: Sequence[datetime]) -> ObservedExercise:
    """Map the indexed boundary onto an observed path with the same date axis.

    Scan t=0,...,N-1: the first non-None boundary with P_t<=boundary[t] and a
    positive payoff gives early_exercise. Boundary-price equality qualifies.
    Report its index, original UTC timestamp, and K-P_t.
    If no early exercise, a positive K-P_N gives maturity_settlement at N,
    regardless of whether the off-lattice observed price hits boundary[N].
    Otherwise return kind='never', index/timestamp=None, payoff=0.

    Exact NODE value ties continue; touching an already-classified exercise
    boundary qualifies. These are separate comparisons.
    Require nonempty equal-length prices/boundary/timestamps, positive finite
    prices, finite K>=0, UTC-aware strictly increasing dates, and boundaries
    that are None or finite positive values below K. Raise ValueError for
    invalid inputs. Missing exercise regions must use None, never zero or NaN.
    Timestamp gaps are handled by the calibration gate, not filled here.
    """
    try:
        prices, boundary, dates = tuple(prices), tuple(boundary), tuple(timestamps_utc)
    except TypeError as exc:
        raise ValueError('Prices, boundaries and timestamps must be sequences.') from exc
    if not prices or len(prices) != len(boundary) or len(prices) != len(dates):
        raise ValueError('Prices, boundaries and timestamps must be nonempty and equally sized.')
    if isinstance(K, bool):
        raise ValueError('K must be a finite nonnegative strike.')
    K = _finite_float(K, 'K')
    if K < 0:
        raise ValueError('K must be nonnegative.')

    def positive_float(value, name):
        if isinstance(value, bool):
            raise ValueError(f'{name} must be a positive finite price.')
        value = _finite_float(value, name)
        if value <= 0:
            raise ValueError(f'{name} must be a positive finite price.')
        return value

    prices = tuple(positive_float(value, 'Observed price') for value in prices)
    checked_boundary = []
    for value in boundary:
        if value is not None:
            value = positive_float(value, 'Exercise boundary')
            if value >= K:
                raise ValueError('Exercise boundaries must be strictly below K.')
        checked_boundary.append(value)
    for t, stamp in enumerate(dates):
        if not isinstance(stamp, datetime) or stamp.utcoffset() != timedelta(0):
            raise ValueError('Timestamps must be UTC-aware datetimes.')
        if t and stamp <= dates[t-1]:
            raise ValueError('Timestamps must be strictly increasing.')

    # Validate the whole path before accepting even a time-zero decision.
    for t in range(len(prices)-1):
        level = checked_boundary[t]
        payoff = K-prices[t]
        if level is not None and prices[t] <= level and payoff > 0:
            return ObservedExercise('early_exercise', t, dates[t], payoff)
    payoff = K-prices[-1]
    if payoff > 0:
        return ObservedExercise('maturity_settlement', len(prices)-1, dates[-1], payoff)
    return ObservedExercise('never', None, None, 0.0)
