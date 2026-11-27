"""Historical comparison with the computed exercise boundary."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import math


@dataclass(frozen=True)
class ExerciseObservation:
    index: int
    timestamp: datetime
    price: float
    boundary: float
    payoff: float


def first_historical_exercise(
    prices: Sequence[float],
    timestamps: Sequence[datetime],
    boundary: Sequence[float],
    strike: float,
) -> ExerciseObservation | None:
    """Return the first observed close at or below a finite boundary."""
    if not (len(prices) == len(timestamps) == len(boundary)):
        raise ValueError("prices, timestamps, and boundary must have equal lengths")
    if not math.isfinite(strike) or strike <= 0.0:
        raise ValueError("strike must be finite and positive")

    for index, (price, timestamp, exercise_level) in enumerate(
        zip(prices, timestamps, boundary, strict=True)
    ):
        price = float(price)
        exercise_level = float(exercise_level)
        if not math.isfinite(price) or price <= 0.0:
            raise ValueError("prices must be finite and positive")
        if math.isfinite(exercise_level) and price <= exercise_level:
            return ExerciseObservation(
                index=index,
                timestamp=timestamp,
                price=price,
                boundary=exercise_level,
                payoff=float(strike - price),
            )
    return None
