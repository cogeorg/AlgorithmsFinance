"""Load course price data and calibrate an hourly binomial tree (no pricing)."""

import argparse
import csv
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import io
import json
from math import exp, isfinite, log
from pathlib import Path
import platform
import statistics


HERE = Path(__file__).resolve().parent
DEFAULT_DATA = HERE.parents[2] / "Class3/data/hourly/BTCUSDT.csv"
SECONDS_PER_YEAR = 365 * 24 * 60 * 60  # Explicit Actual/365 Fixed convention.


@dataclass(frozen=True)
class PriceWindow:
    source: Path
    source_sha256: str
    file_rows: int
    timestamps: tuple[datetime, ...]
    prices: tuple[float, ...]

    def __post_init__(self):
        if not self.prices or len(self.prices) != len(self.timestamps):
            raise ValueError('prices and timestamps must have the same nonzero length')
        if self.file_rows < len(self.prices):
            raise ValueError('source row count cannot be smaller than the window')
        previous = None
        for timestamp, price in zip(self.timestamps, self.prices):
            if not isfinite(price) or price <= 0:
                raise ValueError('window prices must be finite and positive')
            if not isinstance(timestamp, datetime) or timestamp.utcoffset() != timedelta(0):
                raise ValueError('window timestamps must be UTC datetimes')
            if any((timestamp.minute, timestamp.second, timestamp.microsecond)):
                raise ValueError('window timestamps must fall on full hours')
            if previous is not None and timestamp <= previous:
                raise ValueError('window timestamps must strictly increase')
            previous = timestamp

    @property
    def periods(self):
        return len(self.prices) - 1


@dataclass(frozen=True)
class Calibration:
    spot: float
    strike: float
    steps: int
    mean_log_return: float
    log_return_std: float
    annual_rate: float
    years: float
    up: float
    down: float
    gross_rate: float
    probability_up: float


def load_price_window(path, periods=8760):
    """Validate the whole CSV, retaining its last periods+1 prices.

    None selects the full file. Missing whole hours are retained as gaps, never
    filled. Reject invalid closes, non-UTC/off-hour dates and unordered records.
    At least two returns are needed for a sample standard deviation.
    """
    if periods is not None and (
        isinstance(periods, bool) or not isinstance(periods, int) or periods < 2
    ):
        raise ValueError("periods must be an integer of at least 2, or None")
    path = Path(path).resolve()
    raw = path.read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    if reader.fieldnames != ["timestamp_utc", "close"]:
        raise ValueError("expected CSV columns: timestamp_utc,close")
    selected = deque(maxlen=None if periods is None else periods + 1)
    previous = None
    count = 0
    for row in reader:
        if set(row) != {"timestamp_utc", "close"}:
            raise ValueError(f"CSV line {reader.line_num}: wrong number of fields")
        try:
            timestamp = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
            close = float(row["close"])
        except (ValueError, TypeError, AttributeError) as error:
            raise ValueError(f"CSV line {reader.line_num}: invalid date or close") from error
        if timestamp.utcoffset() != timedelta(0) or any(
            (timestamp.minute, timestamp.second, timestamp.microsecond)
        ):
            raise ValueError(f"CSV line {reader.line_num}: require an hourly UTC timestamp")
        if previous is not None and timestamp <= previous:
            raise ValueError(f"CSV line {reader.line_num}: timestamps must strictly increase")
        if not isfinite(close) or close <= 0:
            raise ValueError(f"CSV line {reader.line_num}: close must be finite and positive")
        selected.append((timestamp, close))
        previous = timestamp
        count += 1
    if len(selected) < 3 or (periods is not None and len(selected) != periods + 1):
        raise ValueError("not enough price rows for the requested window")
    timestamps, prices = zip(*selected)
    return PriceWindow(path, hashlib.sha256(raw).hexdigest(), count, timestamps, prices)


def calibrate_window(window, annual_rate=0.04):
    """Use sample log-return volatility and R=exp(annual_rate * T / N).

    T uses elapsed UTC time and Actual/365 Fixed. When a file has gaps, each
    observed return is still one tree step, following the slides. The period
    interest factor then uses the average elapsed duration per observed step.
    """
    if not isfinite(annual_rate):
        raise ValueError("annual_rate must be finite")
    if window.periods < 2:
        raise ValueError('sample volatility requires at least two returns')
    returns = [log(b / a) for a, b in zip(window.prices, window.prices[1:])]
    volatility = statistics.stdev(returns)
    years = (window.timestamps[-1] - window.timestamps[0]).total_seconds() / SECONDS_PER_YEAR
    try:
        up = exp(volatility)
        down = 1 / up
        gross_rate = exp(annual_rate * years / window.periods)
    except OverflowError as error:
        raise ValueError("calibration factors exceed floating-point range") from error
    if not 0 < down < gross_rate < up:
        raise ValueError("calibration must satisfy 0 < down < gross_rate < up; check volatility/rate")
    return Calibration(
        spot=window.prices[0],
        strike=window.prices[0],
        steps=window.periods,
        mean_log_return=statistics.mean(returns),
        log_return_std=volatility,
        annual_rate=annual_rate,
        years=years,
        up=up,
        down=down,
        gross_rate=gross_rate,
        probability_up=(gross_rate - down) / (up - down),
    )


def calibration_report(window, calibration):
    gaps = [
        (b - a).total_seconds() / 3600
        for a, b in zip(window.timestamps, window.timestamps[1:])
    ]
    return {
        "stage": "calibration only; no option pricing or benchmark",
        "source": str(window.source),
        "source_sha256": window.source_sha256,
        "source_rows": window.file_rows,
        "selected_prices": len(window.prices),
        "start_utc": window.timestamps[0].isoformat(),
        "end_utc": window.timestamps[-1].isoformat(),
        "final_close": window.prices[-1],
        "non_hourly_intervals": sum(gap != 1 for gap in gaps),
        "missing_hours": int(sum(gaps)) - window.periods,
        "maximum_interval_hours": max(gaps),
        "day_count": "Actual/365 Fixed (elapsed UTC seconds / 31536000)",
        "volatility_convention": "sample standard deviation of log returns; denominator N-1",
        "gap_policy": "no filling; one observed return per step; use actual elapsed T",
        "model": asdict(calibration),
        "python": platform.python_version(),
        "source_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--periods", type=int, default=8760)
    selection.add_argument("--full-file", action="store_true")
    parser.add_argument("--annual-rate", type=float, default=0.04)
    parser.add_argument("--output", type=Path, help="optional new JSON file inside this Class3 folder")
    args = parser.parse_args()
    try:
        window = load_price_window(args.data, None if args.full_file else args.periods)
        model = calibrate_window(window, args.annual_rate)
        rendered = json.dumps(calibration_report(window, model), indent=2, allow_nan=False) + "\n"
        if args.output is not None:
            output = args.output.resolve()
            if not output.is_relative_to(HERE):
                raise ValueError("output must stay inside this submission's Class3 folder")
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("x", encoding="utf-8") as stream:
                stream.write(rendered)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(rendered, end="")


if __name__ == "__main__":
    main()
