"""First-year Bitcoin calibration and fixed-model next-year exercise comparison."""
import csv
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time
import tracemalloc

from calibrate import read_prices, calibrate
from price_american_put import PriceAmericanPut
from exercise_analysis import boundary_tree


def main(path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root = Path(__file__).resolve().parents[1]
    out = root / '40_Results'
    paths = [out / 'bitcoin_year1_summary.json', out / 'bitcoin_year1_boundary.csv', out / 'bitcoin_year1_chart.png']
    if any(p.exists() for p in paths):
        raise FileExistsError('Results already exist; preserve them before rerunning')
    rows = read_prices(path)  # Reject invalid values, duplicate or unordered timestamps.
    gaps = [(b[0] - a[0]).total_seconds() / 3600 for a, b in zip(rows, rows[1:])]
    calibration = calibrate(rows)
    start = datetime.fromisoformat(calibration['last_calibration_observation_utc'])
    end = start + timedelta(days=365.25)
    if rows[-1][0] < end:
        raise ValueError('Data does not cover the following one-year horizon')
    observed = [(date, price) for date, price in rows if start < date <= end]
    if not observed:
        raise ValueError('No observations after calibration')
    N = calibration['N_returns']
    S0 = K = calibration['last_calibration_price']
    u, d = calibration['u'], calibration['d']
    R = math.exp(0.04 / N)
    q = (R - d) / (u - d)
    args = (S0, K, u, d, R, N)
    print(f'Data verified; N={N}. Measuring baseline...', flush=True)
    begin = time.perf_counter()
    price = PriceAmericanPut(*args)
    seconds = time.perf_counter() - begin
    print('Measuring memory in a separate pricing call...', flush=True)
    tracemalloc.start()
    try:
        traced_price = PriceAmericanPut(*args)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    if not math.isclose(price, traced_price, rel_tol=1e-12, abs_tol=1e-10):
        raise ValueError('Pricing and memory calls disagree')
    print('Calculating boundary...', flush=True)
    begin = time.perf_counter()
    boundary_price, boundary = boundary_tree(*args)
    boundary_seconds = time.perf_counter() - begin
    if not math.isclose(price, boundary_price, rel_tol=1e-12, abs_tol=1e-10):
        raise ValueError('Boundary price differs from original pricing')
    crossing = None
    for date, observed_price in observed:
        step = min(N, math.floor((date - start).total_seconds() / (end - start).total_seconds() * N))
        level = boundary[step]
        if level is not None and observed_price <= level and K - observed_price > 0:
            crossing = {'timestamp_utc': date.isoformat(), 'step': step, 'price_usdt': observed_price,
                        'boundary_usdt': level, 'payoff_usdt': K - observed_price}
            break
    result = {'source_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
              'data_quality': {'rows': len(rows), 'first_utc': rows[0][0].isoformat(), 'last_utc': rows[-1][0].isoformat(),
                               'invalid_prices_or_timestamps': 0, 'duplicates_or_unordered': 0,
                               'intervals_not_one_hour': sum(g != 1 for g in gaps),
                               'missing_hourly_slots': sum(max(0, round(g)-1) for g in gaps),
                               'max_gap_hours': max(gaps)},
              'calibration': calibration, 'contract': {'S0': S0, 'K': K, 'N': N, 'T_years': 1,
                          'u': u, 'd': d, 'R': R, 'q': q, 'currency': 'USDT per BTC'},
              'price_usdt_per_btc': price, 'pricing_runtime_seconds': seconds,
              'peak_traced_pricing_bytes': peak, 'boundary_calculation_seconds_including_baseline_check': boundary_seconds,
              'memory_method': 'tracemalloc peak in separate pricing call; not total process memory',
              'evaluation': {'origin_utc': start.isoformat(), 'maturity_utc': end.isoformat(),
                             'observations': len(observed), 'first_utc': observed[0][0].isoformat(),
                             'last_utc': observed[-1][0].isoformat(), 'first_crossing': crossing,
                             'mapping': 'floor(elapsed calendar time / 365.25 days * N)'},
              'python': sys.version, 'platform': platform.platform()}
    with paths[0].open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    with paths[1].open('x', encoding='utf-8', newline='') as f:
        writer = csv.writer(f); writer.writerow(['step', 'model_time_utc', 'boundary_usdt'])
        for step, level in enumerate(boundary):
            writer.writerow([step, (start + (end-start) * (step/N)).isoformat(), '' if level is None else level])
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot([start] + [d for d, _ in observed], [S0] + [p for _, p in observed], label='BTC hourly close', linewidth=1)
    ax.plot([start + (end-start)*(i/N) for i in range(N+1)], boundary, label='Exercise boundary')
    if crossing:
        ax.scatter([datetime.fromisoformat(crossing['timestamp_utc'])], [crossing['price_usdt']], color='red', zorder=5, label='First observed crossing')
    ax.set(title='Bitcoin: observed closes and American put exercise boundary', xlabel='Date (UTC; model steps mapped by calendar time)', ylabel='USDT per BTC')
    ax.grid(alpha=.25); ax.legend(); fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(paths[2], dpi=150); plt.close(fig)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python bitcoin_experiment.py PATH_TO_BTCUSDT.csv')
    main(sys.argv[1])
