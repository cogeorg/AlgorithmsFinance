"""Required in-sample Bitcoin experiment using the last 8,761 observations."""
import csv
from datetime import timedelta
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc
from calibrate import read_prices
from price_american_put import PriceAmericanPut
from exercise_analysis import boundary_tree


def main(path):
    root = Path(__file__).resolve().parents[1]
    out = root / '40_Results'
    summary = out / 'bitcoin_last_year_summary.json'
    boundaries_file = out / 'bitcoin_last_year_boundary.csv'
    if summary.exists() or boundaries_file.exists():
        raise FileExistsError('Output already exists; preserve previous results')
    rows = read_prices(path)
    if len(rows) < 8761:
        raise ValueError('Fewer than 8761 observations available')
    rows = rows[-8761:]
    n = len(rows) - 1
    gaps = [(b[0]-a[0]).total_seconds()/3600 for a,b in zip(rows, rows[1:])]
    returns = [math.log(b[1]/a[1]) for a,b in zip(rows, rows[1:])]
    s = statistics.stdev(returns)
    u = math.exp(s)
    d = 1 / u
    years = (rows[-1][0]-rows[0][0]).total_seconds()/(365.25*86400)
    R = math.exp(0.04*years/n)
    if not 0 < d < R < u:
        raise ValueError('No-arbitrage condition is not satisfied')
    q = (R-d)/(u-d)
    S0 = K = rows[0][1]
    args = (S0, K, u, d, R, n)
    print('Window verified. Measuring pricing runtime...', flush=True)
    t = time.perf_counter()
    price = PriceAmericanPut(*args)
    runtime = time.perf_counter()-t
    if not math.isfinite(price) or price < 0:
        raise ValueError('Invalid option value')
    print('Measuring traced Python memory separately...', flush=True)
    tracemalloc.start()
    try:
        traced = PriceAmericanPut(*args)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    if not math.isclose(price, traced, rel_tol=1e-12, abs_tol=1e-10):
        raise ValueError('Traced pricing differs')
    print('Calculating exercise boundary...', flush=True)
    checked, boundaries = boundary_tree(*args)
    if not math.isclose(price, checked, rel_tol=1e-12, abs_tol=1e-10):
        raise ValueError('Boundary price differs')
    crossing = None
    for step, (date, close) in enumerate(rows):
        b = boundaries[step]
        if b is not None and close <= b and K - close > 0:
            crossing = {'step':step, 'timestamp_utc':date.isoformat(), 'price_usdt':close, 'boundary_usdt':b, 'payoff_usdt':K-close}
            break
    result = {'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
              'window_start_utc':rows[0][0].isoformat(), 'window_end_utc':rows[-1][0].isoformat(),
              'observations':len(rows), 'N':n, 'intervals_not_one_hour':sum(g != 1 for g in gaps),
              'missing_hourly_slots':sum(max(0,round(g)-1) for g in gaps), 'T_years_actual_365_25':years,
              'S0':S0, 'K':K, 'volatility_per_observation':s, 'u':u, 'd':d, 'R':R, 'q':q,
              'price_usdt_per_btc':price, 'pricing_runtime_seconds':runtime,
              'peak_traced_pricing_bytes':peak, 'memory_method':'tracemalloc peak on separate pricing call; not process RSS',
              'exercise_analysis':'in sample; observation i compared with tree step i', 'first_crossing':crossing,
              'python':sys.version, 'platform':platform.platform()}
    with summary.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    with boundaries_file.open('x', encoding='utf-8', newline='') as f:
        writer = csv.writer(f); writer.writerow(['step','timestamp_utc','boundary_usdt'])
        for i, ((date, _), level) in enumerate(zip(rows, boundaries)):
            writer.writerow([i, date.isoformat(), '' if level is None else level])
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python btc_last_year.py PATH_TO_BTCUSDT.csv')
    main(sys.argv[1])
