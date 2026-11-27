"""Input gates shared ONLY by tests and opt-in benchmark/integration entrypoints.

These helpers read the existing preparation outputs. They neither prepare new
market data nor implement calibration, pricing, or exercise decisions.
"""
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path

import market_calibration

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class PreparedWindow:
    prices: tuple[float, ...]
    timestamps: tuple[datetime, ...]
    indices: tuple[int, ...]
    labels: tuple[str, ...]
    metadata: dict[str, str]


def load_prepared_window(asset='BTCUSDT', window='one_year', *, project=ROOT):
    output = Path(project).resolve() / 'output'
    summary = output / 'window_summary.csv'
    if not summary.is_file():
        summary = Path(project).resolve() / 'results' / 'window_summary.csv'
    with summary.open(newline='', encoding='utf-8') as stream:
        matches = [row for row in csv.DictReader(stream) if row['asset'] == asset and row['window'] == window]
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one prepared window: {asset}/{window}.')
    metadata = matches[0]
    path = (output / metadata['file']).resolve()
    if not path.is_relative_to(output):
        raise ValueError('Prepared window file must stay inside output/.')
    with path.open(newline='', encoding='utf-8') as stream:
        records = list(csv.DictReader(stream))
    prices = tuple(float(row['close']) for row in records)
    if not all(math.isfinite(price) and price > 0 for price in prices):
        raise ValueError('Prepared prices must be positive and finite.')
    stamps = tuple(datetime.fromisoformat(row['timestamp_utc'].replace('Z', '+00:00')) for row in records)
    if any(stamp.tzinfo is None or stamp.utcoffset() != timedelta(0) for stamp in stamps):
        raise ValueError('Prepared timestamps must be UTC-aware.')
    if len(records) != int(metadata['observations']) or int(metadata['N']) != len(records)-1:
        raise ValueError('Prepared counts and summary disagree.')
    indices = tuple(int(row['observation_index']) for row in records)
    labels = tuple(row['observation_label'] for row in records)
    if indices != tuple(range(len(records))) or labels != tuple(f'P_{i}' for i in indices):
        raise ValueError('Prepared observation indexing is inconsistent.')
    return PreparedWindow(prices, stamps, indices, labels, metadata)


def require_hourly_window(window):
    """Return ACT/365F elapsed years; reject gaps before any calibration call."""
    if len(window.prices) < 3:
        raise ValueError('Calibration requires at least three prepared closes.')
    if len(window.timestamps) != len(window.prices):
        raise ValueError('Prepared date axis and prices have different lengths.')
    if any(b-a != timedelta(hours=1) for a, b in zip(window.timestamps, window.timestamps[1:])):
        raise ValueError('Missing or irregular hours require explicit treatment before equal-hour calibration.')
    if window.metadata['ready_for_hourly_pricing'] != 'True':
        raise ValueError('Preparation flagged this window for explicit treatment before equal-hour calibration.')
    return (window.timestamps[-1]-window.timestamps[0]).total_seconds() / (365*24*3600)


def calibrate_prepared_window(window, *, annual_rate=0.04):
    years = require_hourly_window(window)
    return market_calibration.calibrate_binomial(window.prices, T=years, annual_rate=annual_rate)


def pricing_parameters(window, model):
    if model.N != len(window.prices)-1:
        raise ValueError('Calibration periods disagree with prepared observations.')
    return dict(S0=window.prices[0], K=window.prices[0],
                u=model.u, d=model.d, R=model.R, N=model.N)
