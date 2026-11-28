"""Memory-efficient American put pricing on a recombining binomial tree."""

from __future__ import annotations

from dataclasses import dataclass
import math
from numbers import Integral, Real
import sys


class PricingInputError(ValueError):
    """Raised before pricing when the binomial contract is invalid."""


@dataclass(frozen=True)
class PricingResult:
    value: float
    boundary: tuple[float | None, ...]
    node_updates: int


_LOG_MIN_POSITIVE = math.log(float.fromhex("0x0.0000000000001p-1022"))
_LOG_MAX_FLOAT = math.log(sys.float_info.max)


def _finite_real(name: str, value: Real) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise PricingInputError(f"{name} must be a real number, not {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise PricingInputError(f"{name} must be finite")
    return number


def _validate_inputs(spot, strike, up, down, gross_rate, steps):
    spot_f = _finite_real("spot", spot)
    strike_f = _finite_real("strike", strike)
    up_f = _finite_real("up", up)
    down_f = _finite_real("down", down)
    gross_f = _finite_real("gross_rate", gross_rate)

    if isinstance(steps, bool) or not isinstance(steps, Integral):
        raise PricingInputError("steps must be an integer and bool is not accepted")
    steps_i = int(steps)
    if steps_i < 0:
        raise PricingInputError("steps must be nonnegative")
    if spot_f <= 0:
        raise PricingInputError("spot must be strictly positive")
    if strike_f < 0:
        raise PricingInputError("strike must be nonnegative")
    if not 0 < down_f < gross_f < up_f:
        raise PricingInputError("no arbitrage requires 0 < down < gross_rate < up")

    log_spot = math.log(spot_f)
    log_down_terminal = log_spot + steps_i * math.log(down_f)
    log_up_terminal = log_spot + steps_i * math.log(up_f)
    lowest_log = min(log_spot, log_down_terminal, log_up_terminal)
    highest_log = max(log_spot, log_down_terminal, log_up_terminal)
    if lowest_log < _LOG_MIN_POSITIVE or highest_log > _LOG_MAX_FLOAT:
        raise PricingInputError(
            "tree price range is not representable by a positive finite float"
        )
    return spot_f, strike_f, up_f, down_f, gross_f, steps_i


def _rollback(spot, strike, up, down, gross_rate, steps, *, keep_boundary):
    spot, strike, up, down, gross_rate, steps = _validate_inputs(
        spot, strike, up, down, gross_rate, steps
    )
    q = (gross_rate - down) / (up - down)
    if not 0 < q < 1 or not math.isfinite(q):
        raise PricingInputError("risk-neutral probability must be finite and in (0, 1)")

    ratio = up / down
    up_weight = q / gross_rate
    down_weight = (1 - q) / gross_rate
    # Repeated multiplication is part of the stated algorithm and preserves
    # simple lattice values such as 100 * 0.8 == 80 more faithfully than
    # reconstructing them through exp(log(spot) + n * log(down)).
    lowest_stock = spot
    for _ in range(steps):
        lowest_stock *= down
    if not 0 < lowest_stock <= sys.float_info.max:
        raise PricingInputError("lowest tree price is not a positive finite float")

    values = [0.0] * (steps + 1)
    boundary = [None] * (steps + 1) if keep_boundary else None

    stock = lowest_stock
    expiry_boundary_index = None
    for j in range(steps + 1):
        intrinsic = strike - stock if stock < strike else 0.0
        values[j] = intrinsic
        if intrinsic > 0:
            expiry_boundary_index = j
        if j < steps:
            stock *= ratio
    if boundary is not None:
        if expiry_boundary_index is not None:
            boundary[steps] = (
                spot
                * up ** expiry_boundary_index
                * down ** (steps - expiry_boundary_index)
            )

    node_updates = 0
    for t in range(steps - 1, -1, -1):
        lowest_stock /= down
        if not 0 < lowest_stock <= sys.float_info.max:
            raise ArithmeticError("tree price became nonpositive or nonfinite")
        stock = lowest_stock
        row_boundary_index = None
        for j in range(t + 1):
            continuation = up_weight * values[j + 1] + down_weight * values[j]
            intrinsic = strike - stock if stock < strike else 0.0
            if intrinsic > 0 and intrinsic >= continuation:
                values[j] = intrinsic
                row_boundary_index = j
            else:
                values[j] = continuation
            if j < t:
                stock *= ratio
        if boundary is not None:
            if row_boundary_index is not None:
                boundary[t] = (
                    spot * up ** row_boundary_index * down ** (t - row_boundary_index)
                )
        node_updates += t + 1

    value = values[0]
    if not math.isfinite(value) or value < 0:
        raise ArithmeticError("put value became negative or nonfinite")
    return PricingResult(
        value=value,
        boundary=tuple(boundary) if boundary is not None else (),
        node_updates=node_updates,
    )


def price_american_put(spot, strike, up, down, gross_rate, steps) -> float:
    """Return only the date-zero value, using one rolling value vector."""
    return _rollback(
        spot, strike, up, down, gross_rate, steps, keep_boundary=False
    ).value


def price_american_put_with_boundary(
    spot, strike, up, down, gross_rate, steps
) -> PricingResult:
    """Return the value and positive-intrinsic exercise boundary at every date."""
    return _rollback(
        spot, strike, up, down, gross_rate, steps, keep_boundary=True
    )
