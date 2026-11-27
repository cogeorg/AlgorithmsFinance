"""Full-history BTC pricing: independent operations with bounded runtimes."""
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc

from calibrate import read_prices
from price_american_put import PriceAmericanPut
from exercise_analysis import boundary_tree

TIMEOUT_SECONDS = 1000


def setup(path):
    rows = read_prices(path)
    n = len(rows) - 1
    if n < 2:
        raise ValueError('At least three valid observations are required')
    returns = [math.log(b[1] / a[1]) for a, b in zip(rows, rows[1:])]
    s = statistics.stdev(returns)
    u = math.exp(s)
    d = 1 / u
    years = (rows[-1][0] - rows[0][0]).total_seconds() / (365.25 * 86400)
    R = math.exp(0.04 * years / n)
    if not 0 < d < R < u:
        raise ValueError('No-arbitrage condition failed')
    return rows, (rows[0][1], rows[0][1], u, d, R, n), s, years


def worker(mode, path):
    rows, args, _, _ = setup(path)
    if mode == 'pricing':
        start = time.perf_counter()
        price = PriceAmericanPut(*args)
        seconds = time.perf_counter() - start
        if not math.isfinite(price) or price < 0:
            raise ValueError('Invalid option price')
        return {'status': 'completed', 'price_usdt_per_btc': price, 'runtime_seconds': seconds}
    if mode == 'memory':
        tracemalloc.start()
        try:
            price = PriceAmericanPut(*args)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        return {'status': 'completed', 'peak_traced_bytes': peak, 'price_usdt_per_btc': price}
    if mode == 'boundary':
        start = time.perf_counter()
        price, boundaries = boundary_tree(*args)
        crossing = None
        for i, ((date, close), level) in enumerate(zip(rows, boundaries)):
            if level is not None and close <= level and args[1] - close > 0:
                crossing = {'step': i, 'timestamp_utc': date.isoformat(), 'price_usdt': close,
                            'boundary_usdt': level, 'intrinsic_payoff_usdt': args[1] - close}
                break
        return {'status': 'completed', 'price_usdt_per_btc': price,
                'runtime_seconds_including_price_check': time.perf_counter()-start, 'first_crossing': crossing}
    raise ValueError('Unknown operation')


def main(path):
    root = Path(__file__).resolve().parents[1]
    output = root / '40_Results' / 'bitcoin_full_history.json'
    if output.exists():
        raise FileExistsError('Result already exists; preserve it before running')
    rows, args, s, years = setup(path)
    S0, K, u, d, R, N = args
    gaps = [(b[0]-a[0]).total_seconds()/3600 for a,b in zip(rows, rows[1:])]
    result = {'asset': 'BTC', 'asset_count': 1, 'source_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
              'window_start_utc': rows[0][0].isoformat(), 'window_end_utc': rows[-1][0].isoformat(),
              'observations': len(rows), 'N': N, 'intervals_not_one_hour': sum(g != 1 for g in gaps),
              'T_years_actual_365_25': years, 'S0': S0, 'K': K, 'volatility': s,
              'u': u, 'd': d, 'R': R, 'q': (R-d)/(u-d), 'timeout_seconds_per_operation': TIMEOUT_SECONDS,
              'memory_method': 'tracemalloc peak for pricing only; excludes process RSS',
              'exercise_method': 'in-sample; observation index maps to tree step; gaps not filled',
              'python': sys.version, 'platform': platform.platform(), 'operations': {}}
    with output.open('x', encoding='utf-8') as f:
        json.dump(result, f, indent=2); f.write('\n')
    for mode in ('pricing', 'memory', 'boundary'):
        print(f'Starting {mode} (limit {TIMEOUT_SECONDS} seconds)...', flush=True)
        try:
            proc = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--worker', mode, str(path)],
                                  capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
            if proc.returncode:
                operation = {'status': 'failed', 'error': proc.stderr[-3000:]}
            else:
                operation = json.loads(proc.stdout)
        except subprocess.TimeoutExpired:
            operation = {'status': 'timeout', 'limit_seconds': TIMEOUT_SECONDS}
        result['operations'][mode] = operation
        with output.open('w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
        print(json.dumps({mode: operation}), flush=True)
    print(f'Results: {output}', flush=True)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        print(json.dumps(worker(sys.argv[2], sys.argv[3]), allow_nan=False))
    elif len(sys.argv) == 2:
        main(sys.argv[1])
    else:
        raise SystemExit('Usage: python btc_full_history.py PATH_TO_BTCUSDT.csv')
