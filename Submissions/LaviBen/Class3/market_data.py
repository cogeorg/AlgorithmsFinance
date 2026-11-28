"""Strict CSV loading, calibration, and observed exercise decisions."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import math
from numbers import Real
from pathlib import Path
import statistics


class MarketDataError(ValueError):
    """Raised when data or calibrated parameters violate the frozen contract."""


@dataclass(frozen=True)
class Gap:
    before: datetime
    after: datetime
    missing_hours: int


@dataclass(frozen=True)
class PriceSeries:
    symbol: str
    timestamps: tuple[datetime, ...]
    closes: tuple[float, ...]
    gaps: tuple[Gap, ...]
    source_sha256: str
    source_path: str


@dataclass(frozen=True)
class PriceWindow:
    symbol: str
    timestamps: tuple[datetime, ...]
    closes: tuple[float, ...]
    gaps: tuple[Gap, ...]
    source_sha256: str

    @property
    def steps(self) -> int:
        return len(self.closes) - 1


@dataclass(frozen=True)
class Calibration:
    symbol: str
    spot: float
    strike: float
    up: float
    down: float
    gross_rate: float
    steps: int
    q: float
    volatility: float
    elapsed_years: float
    annual_rate: float
    hours_per_year: float


@dataclass(frozen=True)
class ExerciseDecision:
    exercised: bool
    index: int | None
    timestamp: datetime | None
    observed_price: float | None
    boundary_price: float | None
    payoff: float


_ONE_HOUR = timedelta(hours=1)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_timestamp(raw: str, line_number: int) -> datetime:
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise MarketDataError(f"line {line_number}: invalid timestamp {raw!r}") from exc
    if stamp.tzinfo is None or stamp.utcoffset() != timedelta(0):
        raise MarketDataError(f"line {line_number}: timestamp must be UTC")
    stamp = stamp.astimezone(timezone.utc)
    if stamp.minute or stamp.second or stamp.microsecond:
        raise MarketDataError(f"line {line_number}: timestamp must start a whole hour")
    return stamp


def _parse_close(raw: str, line_number: int) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise MarketDataError(f"line {line_number}: invalid close {raw!r}") from exc
    if not math.isfinite(value) or value <= 0:
        raise MarketDataError(
            f"line {line_number}: close must be finite and strictly positive"
        )
    return value


def _find_gaps(timestamps: tuple[datetime, ...]) -> tuple[Gap, ...]:
    gaps = []
    for before, after in zip(timestamps, timestamps[1:]):
        delta = after - before
        if delta <= timedelta(0):
            raise MarketDataError("timestamps must be unique and strictly increasing")
        if delta != _ONE_HOUR:
            hours = delta.total_seconds() / 3600
            if not hours.is_integer() or hours < 1:
                raise MarketDataError("timestamps must be aligned to whole-hour steps")
            gaps.append(Gap(before, after, int(hours) - 1))
    return tuple(gaps)


def load_price_series(path: str | Path) -> PriceSeries:
    path = Path(path).resolve()
    timestamps = []
    closes = []
    try:
        stream = path.open(newline="")
    except OSError as exc:
        raise MarketDataError(f"cannot open {path}") from exc
    with stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != ["timestamp_utc", "close"]:
            raise MarketDataError("CSV header must be exactly timestamp_utc,close")
        for line_number, row in enumerate(reader, 2):
            timestamps.append(_parse_timestamp(row["timestamp_utc"], line_number))
            closes.append(_parse_close(row["close"], line_number))
    if not closes:
        raise MarketDataError("price file must contain at least one observation")
    timestamp_tuple = tuple(timestamps)
    return PriceSeries(
        symbol=path.stem,
        timestamps=timestamp_tuple,
        closes=tuple(closes),
        gaps=_find_gaps(timestamp_tuple),
        source_sha256=_sha256(path),
        source_path=str(path),
    )


def select_last_periods(series: PriceSeries, periods: int) -> PriceWindow:
    if isinstance(periods, bool) or not isinstance(periods, int) or periods <= 0:
        raise MarketDataError("periods must be a positive integer")
    required = periods + 1
    if len(series.closes) < required:
        raise MarketDataError(
            f"{series.symbol} has {len(series.closes)} observations; {required} required"
        )
    timestamps = series.timestamps[-required:]
    return PriceWindow(
        symbol=series.symbol,
        timestamps=timestamps,
        closes=series.closes[-required:],
        gaps=_find_gaps(timestamps),
        source_sha256=series.source_sha256,
    )


def select_full_history(series: PriceSeries) -> PriceWindow:
    if len(series.closes) < 3:
        raise MarketDataError("full-history calibration requires at least three observations")
    return PriceWindow(
        symbol=series.symbol,
        timestamps=series.timestamps,
        closes=series.closes,
        gaps=series.gaps,
        source_sha256=series.source_sha256,
    )


def calibrate_window(
    window: PriceWindow, *, annual_rate: float = 0.04, hours_per_year: float = 8760.0
) -> Calibration:
    if window.steps < 2:
        raise MarketDataError("sample volatility requires at least two returns")
    for name, value in (("annual_rate", annual_rate),
                        ("hours_per_year", hours_per_year)):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise MarketDataError(f"{name} must be a real number")
        if not math.isfinite(float(value)):
            raise MarketDataError(f"{name} must be finite")
    annual_rate = float(annual_rate)
    hours_per_year = float(hours_per_year)
    if hours_per_year <= 0:
        raise MarketDataError("hours_per_year must be positive")

    returns = [
        math.log(current) - math.log(previous)
        for previous, current in zip(window.closes, window.closes[1:])
    ]
    volatility = statistics.stdev(returns)
    if not math.isfinite(volatility) or volatility <= 0:
        raise MarketDataError("sample volatility must be finite and strictly positive")
    up = math.exp(volatility)
    down = 1.0 / up
    elapsed_hours = (
        window.timestamps[-1] - window.timestamps[0]
    ).total_seconds() / 3600
    elapsed_years = elapsed_hours / hours_per_year
    gross_rate = math.exp(annual_rate * elapsed_years / window.steps)
    q = (gross_rate - down) / (up - down)
    if not all(math.isfinite(x) for x in (up, down, gross_rate, q)):
        raise MarketDataError("calibrated parameters must be finite")
    if not 0 < down < gross_rate < up or not 0 < q < 1:
        raise MarketDataError("calibration violates 0 < down < R < up")
    return Calibration(
        symbol=window.symbol,
        spot=window.closes[0],
        strike=window.closes[0],
        up=up,
        down=down,
        gross_rate=gross_rate,
        steps=window.steps,
        q=q,
        volatility=volatility,
        elapsed_years=elapsed_years,
        annual_rate=annual_rate,
        hours_per_year=hours_per_year,
    )


def find_first_exercise(
    window: PriceWindow, boundary: tuple[float | None, ...], strike: float
) -> ExerciseDecision:
    if len(boundary) != len(window.closes):
        raise MarketDataError("boundary length must match the selected price window")
    if isinstance(strike, bool) or not isinstance(strike, Real):
        raise MarketDataError("strike must be a real number")
    strike = float(strike)
    if not math.isfinite(strike) or strike < 0:
        raise MarketDataError("strike must be finite and nonnegative")
    for index, (stamp, observed, limit) in enumerate(
        zip(window.timestamps, window.closes, boundary)
    ):
        if limit is None:
            continue
        if isinstance(limit, bool) or not isinstance(limit, Real):
            raise MarketDataError("boundary prices must be real numbers or None")
        limit = float(limit)
        if not math.isfinite(limit) or limit <= 0:
            raise MarketDataError("boundary prices must be finite and positive")
        if observed <= limit:
            payoff = strike - observed
            if payoff < 0:
                raise MarketDataError("exercise boundary implies a negative payoff")
            return ExerciseDecision(True, index, stamp, observed, limit, payoff)
    return ExerciseDecision(False, None, None, None, None, 0.0)
