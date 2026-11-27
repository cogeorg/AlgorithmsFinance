"""Calibrate a binomial pricing tree on the first calendar year of closes."""
import argparse
import csv
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import statistics


def read_prices(path):
    rows = []
    with open(path, newline='', encoding='utf-8-sig') as stream:
        for line, row in enumerate(csv.DictReader(stream), 2):
            try:
                date = datetime.fromisoformat(row['timestamp_utc'].replace('Z', '+00:00'))
                price = float(row['close'])
                if date.tzinfo is None or not math.isfinite(price) or price <= 0:
                    raise ValueError('timestamp must have a timezone and price must be positive and finite')
                date = date.astimezone(timezone.utc)
                if rows and date <= rows[-1][0]:
                    raise ValueError('timestamps must be strictly increasing')
                rows.append((date, price))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f'Invalid row {line}: {exc}') from exc
    return rows


def calibrate(rows):
    if not rows:
        raise ValueError('No observations')
    start = rows[0][0]
    try:
        cutoff = start.replace(year=start.year + 1)
    except ValueError:  # 29 February, when the following year is not a leap year
        cutoff = start.replace(year=start.year + 1, day=28)
    if rows[-1][0] < cutoff:
        raise ValueError('Data does not cover the full one-year calibration window')
    window = [(date, price) for date, price in rows if start <= date < cutoff]
    n = len(window) - 1
    if n < 2:
        raise ValueError('At least three observations are needed')
    returns = [math.log(window[i][1] / window[i-1][1]) for i in range(1, len(window))]
    s = statistics.stdev(returns)
    up = math.exp(s)
    down = 1.0 / up
    elapsed_years = (window[-1][0] - start).total_seconds() / (365.25 * 86400)
    gross_rate = math.exp(0.04 * elapsed_years / n)
    if not 0 < down < gross_rate < up:
        raise ValueError('No-arbitrage condition 0 < d < R < u is not satisfied')
    return {'window_start_utc': start.isoformat(), 'window_end_exclusive_utc': cutoff.isoformat(),
            'last_calibration_observation_utc': window[-1][0].isoformat(),
            'observations': len(window), 'N_returns': n, 'initial_price': window[0][1],
            'last_calibration_price': window[-1][1], 'elapsed_years_actual_365_25': elapsed_years,
            'mean_log_return': statistics.mean(returns), 'sample_log_return_std': s,
            'u': up, 'd': down, 'annual_continuous_rate': 0.04, 'R_per_observation': gross_rate,
            'q_risk_neutral': (gross_rate - down) / (up - down)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='CSV with timestamp_utc and close columns')
    args = parser.parse_args()
    try:
        print(json.dumps(calibrate(read_prices(args.input)), indent=2, allow_nan=False))
    except (OSError, ValueError, OverflowError) as exc:
        parser.exit(1, f'Calibration failed: {exc}\n')


if __name__ == '__main__':
    main()
