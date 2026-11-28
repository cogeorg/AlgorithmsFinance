"""Independent small-tree expected results; never imported by production code."""

from fractions import Fraction


def recursive_value(spot, strike, up, down, gross_rate, steps):
    """Exponential oracle that follows both branches independently."""
    intrinsic = max(strike - spot, 0)
    if steps == 0:
        return intrinsic
    q = (gross_rate - down) / (up - down)
    continuation = (
        q * recursive_value(spot * up, strike, up, down, gross_rate, steps - 1)
        + (1 - q)
        * recursive_value(spot * down, strike, up, down, gross_rate, steps - 1)
    ) / gross_rate
    return max(intrinsic, continuation)


def toy_inputs():
    return (
        Fraction(100),
        Fraction(100),
        Fraction(6, 5),
        Fraction(4, 5),
        Fraction(21, 20),
        2,
    )


TOY_VALUE = Fraction(1175, 147)
TOY_BOUNDARY = (None, Fraction(80), Fraction(96))
