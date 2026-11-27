"""Compare A and B and benchmark B on the saved last-year BTC parameters."""
import hashlib
import json
import platform
from pathlib import Path
import statistics
import sys
import time
import numpy as np
from price_american_put import PriceAmericanPut
from price_american_put_numpy import PriceAmericanPutB

root = Path(__file__).resolve().parents[1]
result_path = root / '40_Results' / 'numpy_btc_comparison.json'
if result_path.exists():
    raise SystemExit('Result exists; preserve it before rerunning')
with (root / '40_Results' / 'bitcoin_last_year_summary.json').open(encoding='utf-8-sig') as f:
    saved = json.load(f)
slide = (100, 100, 1.2, 0.8, 1.05, 2)
slide_a, slide_b = PriceAmericanPut(*slide), PriceAmericanPutB(*slide)
if abs(slide_a - 7.9931972789) > 1e-8 or abs(slide_a - slide_b) > 1e-8:
    raise ValueError('Slide example failed')
args = tuple(saved[k] for k in ('S0', 'K', 'u', 'd', 'R', 'N'))
print('Checking Version A on the BTC inputs...', flush=True)
a = PriceAmericanPut(*args)
print('Warming up Version B...', flush=True)
warm = PriceAmericanPutB(*args)
if abs(a - warm) > 1e-4:
    raise ValueError(f'BTC disagreement exceeds tolerance: A={a}, B={warm}')
times = []
for repeat in range(3):
    start = time.perf_counter()
    value = PriceAmericanPutB(*args)
    times.append(time.perf_counter() - start)
    if abs(a - value) > 1e-4:
        raise ValueError(f'BTC disagreement on repetition {repeat + 1}')
    print(f'Version B repetition {repeat + 1}: {times[-1]:.6f} seconds', flush=True)
median = statistics.median(times)
result = {'slide_A':slide_a, 'slide_B':slide_b, 'BTC_A_current':a, 'BTC_B':value,
          'BTC_absolute_difference':abs(a-value), 'tolerance':1e-4, 'N':saved['N'],
          'version_B_warmup_count':1, 'version_B_runtime_seconds':times,
          'version_B_median_seconds':median, 'version_A_historical_single_seconds':saved['pricing_runtime_seconds'],
          'speedup_historical_A_single_over_B_median':saved['pricing_runtime_seconds']/median,
          'numpy_version':np.__version__, 'python':sys.version, 'platform':platform.platform(),
          'version_A_sha256':hashlib.sha256((root/'20_Code'/'price_american_put.py').read_bytes()).hexdigest(),
          'version_B_sha256':hashlib.sha256((root/'20_Code'/'price_american_put_numpy.py').read_bytes()).hexdigest()}
with result_path.open('x', encoding='utf-8') as f:
    json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
print(json.dumps(result, indent=2))
