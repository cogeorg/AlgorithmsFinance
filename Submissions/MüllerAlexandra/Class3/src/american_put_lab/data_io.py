"""CSV loading for the supplied hourly market data."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


EXPECTED_HEADER = ["timestamp_utc", "close"]


@dataclass(frozen=True)
class MarketSeries:
    symbol: str
    timestamps: tuple[datetime, ...]
    prices: tuple[float, ...]

    @property
    def periods(self) -> int:
        return len(self.prices) - 1


def _parse_utc(value: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"invalid timestamp: {value!r}") from error
    if timestamp.tzinfo is None:
        raise ValueError("timestamps must include a UTC offset")
    return timestamp


def load_hourly_prices(path: str | Path, periods: int | None = None) -> MarketSeries:
    """Load all observations or the last ``periods + 1`` observations."""
    path = Path(path)
    if periods is not None:
        if isinstance(periods, bool) or not isinstance(periods, int):
            raise TypeError("periods must be an integer or None")
        if periods < 0:
            raise ValueError("periods must be nonnegative")

    timestamps: list[datetime] = []
    prices: list[float] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream)
        try:
            header = next(reader)
        except StopIteration as error:
            raise ValueError("CSV is empty") from error
        if header != EXPECTED_HEADER:
            raise ValueError(f"unexpected CSV header: {header!r}")
        for row_number, row in enumerate(reader, start=2):
            if len(row) != 2:
                raise ValueError(f"row {row_number} must contain two fields")
            timestamps.append(_parse_utc(row[0]))
            try:
                prices.append(float(row[1]))
            except ValueError as error:
                raise ValueError(f"invalid close on row {row_number}") from error

    required = len(prices) if periods is None else periods + 1
    if len(prices) < required:
        raise ValueError(
            f"request requires {required} observations but file contains {len(prices)}"
        )
    if periods is not None:
        timestamps = timestamps[-required:]
        prices = prices[-required:]

    return MarketSeries(path.stem, tuple(timestamps), tuple(prices))
