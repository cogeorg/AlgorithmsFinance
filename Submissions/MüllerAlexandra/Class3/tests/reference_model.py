"""Small, deliberately unoptimized oracle used only by the tests."""

from __future__ import annotations


def full_tree_american_put(
    spot: float,
    strike: float,
    up: float,
    down: float,
    gross_rate: float,
    steps: int,
) -> tuple[float, tuple[float | None, ...]]:
    """Return value and boundaries using full stock/value trees.

    This implementation intentionally differs from the rolling-array production
    algorithm. It stores every node and is suitable only for small test trees.
    """
    probability_up = (gross_rate - down) / (up - down)
    stocks = [
        [spot * up**up_moves * down ** (time - up_moves) for up_moves in range(time + 1)]
        for time in range(steps + 1)
    ]
    values = [[0.0] * (time + 1) for time in range(steps + 1)]
    boundaries: list[float | None] = [None] * (steps + 1)

    terminal_exercise_prices = []
    for node, stock in enumerate(stocks[steps]):
        intrinsic = max(strike - stock, 0.0)
        values[steps][node] = intrinsic
        if intrinsic > 0.0:
            terminal_exercise_prices.append(stock)
    if terminal_exercise_prices:
        boundaries[steps] = max(terminal_exercise_prices)

    for time in range(steps - 1, -1, -1):
        exercise_prices = []
        for node, stock in enumerate(stocks[time]):
            continuation = (
                probability_up * values[time + 1][node + 1]
                + (1.0 - probability_up) * values[time + 1][node]
            ) / gross_rate
            intrinsic = max(strike - stock, 0.0)
            values[time][node] = max(intrinsic, continuation)
            if intrinsic > 0.0 and intrinsic >= continuation:
                exercise_prices.append(stock)
        if exercise_prices:
            boundaries[time] = max(exercise_prices)

    return values[0][0], tuple(boundaries)
