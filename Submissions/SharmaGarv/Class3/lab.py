"""Class 3: American puts on hourly data. Run with --validate or --run-all."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import threading
import time

import numpy as np
import numba
from numba import njit
import psutil

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[2] / 'data' / 'hourly'


@njit(nogil=True)
def _tree(spot, strike, up, down, gross, steps):
    """Ascending-index backward induction, O(N^2) time and O(N) storage.

    Rebuild each stock-price row by geometric multiplication. Restart from
    log-prices each row so deep-tree underflow cannot propagate backward.
    All prices here are normalized by the strike in the public wrapper.
    """
    q = (gross - down) / (up - down)
    values = np.empty(steps + 1)
    boundary = np.full(steps + 1, np.nan)
    log_spot, log_down = math.log(spot), math.log(down)
    log_up = math.log(up)
    reciprocal = abs(log_up + log_down) <= 8 * np.finfo(np.float64).eps
    if reciprocal:
        log_down = -log_up
    log_ratio = log_up - log_down
    ratio = up * up if reciprocal else up / down
    for t in range(steps, -1, -1):
        start = log_spot + t * log_down
        # Below exp(-700), the stock is negligible at float64 precision.
        first = max(0, int(math.ceil((-700.0 - start) / log_ratio)))
        first = min(first, t + 1)
        stock = 0.0
        if first <= t:
            initial_log = start + first * log_ratio
            stock = math.exp(initial_log) if initial_log < 700 else math.inf
        for j in range(t + 1):
            # In a reciprocal CRR tree, the central node is exactly spot
            # (even t) or spot/up (odd t). Reset here to stop accumulated
            # multiplication error turning a zero ATM payoff positive.
            if reciprocal and j == t // 2:
                stock = spot if t % 2 == 0 else spot / up
            current_stock = 0.0 if j < first else stock
            exercise = max(strike - current_stock, 0.0)
            if t == steps:
                continuation = 0.0
                values[j] = exercise
            else:
                continuation = (q * values[j + 1] + (1.0 - q) * values[j]) / gross
                values[j] = max(exercise, continuation)
            # Positive payoff excludes economically irrelevant zero/zero ties.
            if exercise > 0.0 and exercise >= continuation:
                boundary[t] = current_stock
            if j >= first:
                stock *= ratio
    return values[0], boundary


def price_american_put(spot, strike, up, down, gross, steps):
    if not isinstance(steps, (int, np.integer)) or steps < 0:
        raise ValueError('steps must be a nonnegative integer')
    if not all(math.isfinite(x) for x in (spot, strike, up, down, gross)):
        raise ValueError('parameters must be finite')
    if spot <= 0 or strike < 0 or not (0 < down < gross < up):
        raise ValueError('need spot > 0, strike >= 0 and 0 < down < gross < up')
    if strike == 0:
        return 0.0, np.full(steps + 1, np.nan)
    value, boundary = _tree(spot / strike, 1.0, up, down, gross, steps)
    return value * strike, boundary * strike


def load_prices(path):
    with path.open(newline='', encoding='utf-8-sig') as handle:
        rows = list(csv.DictReader(handle))
    stamps = [row['timestamp_utc'] for row in rows]
    prices = np.array([float(row['close']) for row in rows])
    dates = [datetime.fromisoformat(s.replace('Z', '+00:00')) for s in stamps]
    if len(prices) < 3 or not np.all(np.isfinite(prices)) or np.any(prices <= 0):
        raise ValueError(f'{path.name}: need at least three finite positive closes')
    if any(b <= a for a, b in zip(dates, dates[1:])):
        raise ValueError(f'{path.name}: timestamps must increase strictly')
    return stamps, dates, prices


def calibrate(dates, prices):
    steps = len(prices) - 1
    returns = np.diff(np.log(prices))
    sigma = float(np.std(returns, ddof=1))
    years = (dates[-1] - dates[0]).total_seconds() / (365 * 24 * 3600)
    if not sigma > 0:
        raise ValueError('positive sample volatility required for binomial calibration')
    up = math.exp(sigma)
    down = 1.0 / up
    gross = math.exp(0.04 * years / steps)
    return steps, sigma, years, up, down, gross


def exercise_outcome(stamps, prices, strike, boundary):
    for t in range(len(prices)):
        if math.isfinite(boundary[t]) and prices[t] <= boundary[t]:
            return t, stamps[t], 'expiry' if t == len(prices) - 1 else 'early', float(strike - prices[t])
    # The terminal payoff is defined for all prices, including off-grid prices.
    if prices[-1] < strike:
        return len(prices) - 1, stamps[-1], 'expiry', float(strike - prices[-1])
    return None, 'never', 'never', 0.0


class MemorySampler:
    """Sample total process resident memory, including native arrays, every 10ms."""
    def __enter__(self):
        self.process = psutil.Process()
        self.baseline = self.process.memory_info().rss
        self.peak = self.baseline
        self.stop = threading.Event()
        def sample():
            while not self.stop.wait(0.01):
                self.peak = max(self.peak, self.process.memory_info().rss)
        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.peak = max(self.peak, self.process.memory_info().rss)
        self.stop.set()
        self.thread.join()


def write_csv(path, rows, fields=None):
    if not rows and fields is None:
        return
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_experiment(name, files, periods, out):
    results = []
    with MemorySampler() as memory:
        started = time.perf_counter()
        for file in files:
            stamps, dates, prices = load_prices(file)
            if periods is not None:
                if len(prices) < periods + 1:
                    raise ValueError(f'{file.name}: insufficient prices for {periods} periods')
                stamps, dates, prices = stamps[-periods-1:], dates[-periods-1:], prices[-periods-1:]
            n, sigma, years, up, down, gross = calibrate(dates, prices)
            spot = float(prices[0])
            before = time.perf_counter()
            value, boundary = price_american_put(spot, spot, up, down, gross, n)
            pricing_seconds = time.perf_counter() - before
            t, stamp, kind, payoff = exercise_outcome(stamps, prices, spot, boundary)
            missing = sum(max(0, int((b-a).total_seconds()/3600)-1) for a, b in zip(dates, dates[1:]))
            row = dict(experiment=name, asset=file.stem, N=n, start_utc=stamps[0], end_utc=stamps[-1],
                       spot_and_strike=spot, hourly_log_return_std=sigma, years=years,
                       u=up, d=down, R=gross, q=(gross-down)/(up-down), put_value=value,
                       put_percent_of_spot=100*value/spot, exercise_t=t, exercise_utc=stamp,
                       exercise_kind=kind, payoff=payoff, pricing_seconds=pricing_seconds,
                       missing_hours=missing, input_sha256=hashlib.sha256(file.read_bytes()).hexdigest())
            results.append(row)
            boundary_path = out / f'{name}_{file.stem}_boundary.csv'
            with boundary_path.open('w', newline='', encoding='utf-8') as handle:
                writer = csv.writer(handle)
                writer.writerow(['t', 'timestamp_utc', 'observed_close', 'exercise_boundary'])
                for i, (stamp_i, price_i, bound_i) in enumerate(zip(stamps, prices, boundary)):
                    writer.writerow([i, stamp_i, price_i, '' if np.isnan(bound_i) else bound_i])
            print(f'{name}: {file.stem}, N={n}, put={value:.8g}, exercise={stamp}, pricing={pricing_seconds:.2f}s', flush=True)
            del boundary
        elapsed = time.perf_counter() - started
    summary = dict(experiment=name, assets=len(files), N_min=min(r['N'] for r in results),
                   N_max=max(r['N'] for r in results), seconds=elapsed,
                   peak_sampled_RSS_MiB=memory.peak/2**20,
                   baseline_RSS_MiB=memory.baseline/2**20,
                   peak_increase_MiB=(memory.peak-memory.baseline)/2**20)
    return results, summary


def validate():
    # Exact recursive exercise-decision oracle, independent of rolling arrays.
    def oracle(s, k, u, d, r, n):
        payoff = max(k-s, 0)
        if n == 0:
            return payoff
        q = (r-d)/(u-d)
        return max(payoff, (q*oracle(s*u,k,u,d,r,n-1)+(1-q)*oracle(s*d,k,u,d,r,n-1))/r)
    count = 0
    for n in range(6):
        for s in (60, 100, 140):
            for k in (80, 100, 120):
                for r in (Fraction(19,20), Fraction(1), Fraction(21,20)):
                    args = (Fraction(s), Fraction(k), Fraction(6,5), Fraction(4,5), r, n)
                    expected = float(oracle(*args))
                    actual, boundary = price_american_put(s,k,1.2,0.8,float(r),n)
                    assert math.isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-11), (args, actual, expected)
                    assert len(boundary) == n+1
                    assert max(k-s,0)-1e-10 <= actual <= k+1e-10
                    count += 1
    value, boundary = price_american_put(100,100,1.2,0.8,1.05,2)
    assert math.isclose(value, float(Fraction(1175,147)), rel_tol=1e-12)
    assert np.isnan(boundary[0]) and np.allclose(boundary[1:], [80,96])
    assert exercise_outcome(['a','b','c'], np.array([100.,79.,95.]),100,boundary) == (1,'b','early',21.)
    assert exercise_outcome(['a','b','c'], np.array([100.,120.,99.]),100,boundary) == (2,'c','expiry',1.)
    assert exercise_outcome(['a','b','c'], np.array([100.,120.,110.]),100,boundary)[2] == 'never'
    zero, b = price_american_put(100,0,1.2,0.8,1.05,2)
    assert zero == 0 and np.all(np.isnan(b))
    # Severe expiry underflow must not corrupt the root value.
    deep, _ = price_american_put(100,100,math.exp(1),math.exp(-1),1.00001,800)
    assert math.isfinite(deep) and 0 <= deep <= 100
    # Direct exponent formula is independent of geometric row construction.
    for n in (10, 101, 500):
        sigma = .025
        u, d, r = math.exp(sigma), 1/math.exp(sigma), math.exp(.04/8760)
        q = (r-d)/(u-d)
        stocks = 100*np.exp((2*np.arange(n+1)-n)*sigma)
        reference = np.maximum(100-stocks, 0)
        expected_bounds = np.full(n+1, np.nan)
        for t in range(n, -1, -1):
            stocks = 100*np.exp((2*np.arange(t+1)-t)*sigma)
            exercise = np.maximum(100-stocks, 0)
            if t == n:
                continuation = np.zeros(t+1)
            else:
                continuation = (q*reference[1:] + (1-q)*reference[:-1])/r
            eligible = stocks[(exercise > 0) & (exercise >= continuation)]
            if len(eligible):
                expected_bounds[t] = eligible[-1]
            reference = np.maximum(exercise, continuation)
        actual, actual_bounds = price_american_put(100,100,u,d,r,n)
        assert math.isclose(actual, reference[0], rel_tol=1e-10, abs_tol=1e-10)
        assert np.allclose(actual_bounds, expected_bounds, equal_nan=True, rtol=1e-10, atol=1e-10)
    # Market-scale odd/even maturity regressions: an ATM node pays EXACTLY zero.
    for n in (8760, 8761):
        sigma = .004607395140495904
        u = math.exp(sigma)
        _, actual_bounds = price_american_put(100,100,u,1/u,math.exp(.04/8760),n)
        expected_terminal = 100*math.exp(-sigma*(1 if n % 2 else 2))
        assert math.isclose(actual_bounds[-1], expected_terminal, rel_tol=1e-10)
    print(f'PASS: {count} exact-reference cases; toy value={value:.10f}; independent full-boundary checks at N=10,101,500; odd/even market-scale expiry regressions; exercise, zero-strike and underflow checks.', flush=True)
    return count



def write_report(out, results, summaries):
    lines = ['CLASS 3 LAB - GARV SHARMA', '========================', '',
             'All six numbered lab tasks completed. Nothing has been submitted.', '',
             'PERFORMANCE', 'Experiment          Assets   N range        Seconds   Sampled peak RSS MiB']
    for row in summaries:
        periods = str(row['N_min']) if row['N_min'] == row['N_max'] else f"{row['N_min']}..{row['N_max']}"
        lines.append(f"{row['experiment']:<20}{row['assets']:>6} {periods:>10} {row['seconds']:>12.3f} {row['peak_sampled_RSS_MiB']:>22.2f}")
    lines += ['', 'Time includes loading, calibration, pricing, exercise analysis and boundary CSV',
              'writing. JIT compilation and validation are excluded. Memory is process RSS',
              'sampled every 10ms, including runtime and native arrays. Sampling may miss short',
              'peaks. This is not auxiliary space; baseline/increase are in performance.csv.',
              '', 'BITCOIN RESULTS']
    for row in results:
        if row['experiment'].startswith('bitcoin_'):
            lines += ['', row['experiment'], f"  N: {row['N']}",
                      f"  Window: {row['start_utc']} to {row['end_utc']}",
                      f"  Initial price and strike: {row['spot_and_strike']:,.8f}",
                      f"  Put value per underlying unit: {row['put_value']:,.8f}",
                      f"  Exercise: {row['exercise_utc']} ({row['exercise_kind']})",
                      f"  Exercise payoff per unit: {row['payoff']:,.8f}",
                      f"  Missing hours: {row['missing_hours']}"]
    lines += ['', 'ALL-ASSET OUTCOMES']
    for name in ('all40_1year', 'all40_full'):
        selected = [r for r in results if r['experiment'] == name]
        counts = {kind: sum(r['exercise_kind'] == kind for r in selected) for kind in ('early','expiry','never')}
        lines.append(f"{name}: {counts['early']} early, {counts['expiry']} at expiry, {counts['never']} never.")
    lines += ['', 'MODEL AND NUMERICAL CONVENTIONS',
              'Sample hourly log-return standard deviation; u=exp(s), d=1/u.',
              'ATM strike equals the first selected close. Risk-neutral q=(R-d)/(u-d).',
              'R=exp(.04*T/N), T=elapsed 365-day calendar years. Missing observations',
              'are not filled, so equal tree steps approximate average elapsed time.',
              'Full history uses the actual file row count, including leap-day observations.',
              'Values are in USDT per underlying unit. Historical timestamps are UTC.',
              'Exercise payoff is not profit net of premium. This historical analysis uses',
              'volatility from the same window and is not an out-of-sample trading strategy.',
              '', 'Boundary: highest positive-payoff tree price with exercise>=continuation.',
              'Zero-payoff ties are excluded. The reciprocal tree central price is anchored',
              'exactly each date to prevent rounding from falsely activating an ATM node.',
              'For an ATM tree, the positive-payoff expiry boundary is K*exp(-s) for odd N',
              'or K*exp(-2s) for even N. These identities are audited for all 82 outputs.',
              'An empty boundary means no exercise node. At expiry, observed positive payoff',
              'is checked directly to handle prices between tree nodes.',
              '', 'SCALING',
              'Backward induction takes O(N^2) work and O(N) storage using rolling values.',
              'Assets are processed sequentially. All requested runs fit in memory.',
              'At N=43,822, value and boundary arrays together need about 0.67 MiB;',
              'one triangular full float64 tree would need about 7.15 GiB.',
              'Numba accelerates the recurrence without fast-math. Strike normalization and',
              'log-price row restarts prevent propagated underflow; normalized stocks below',
              'exp(-700) are treated as zero at float64 precision.',
              '', 'VERIFICATION',
              '- Lecture result: 7.9931972789, matching 1175/147.',
              '- 162 exact recursive reference cases.',
              '- Independent values and every boundary at N=10,101,500.',
              '- Market-scale expiry regressions for both even and odd N.',
              '- Exercise timing, zero-strike and severe underflow checks.',
              '- verify_results.py checks saved source/input hashes, calibration, expiry',
              '  boundaries, source alignment, historical exercise and performance tables.',
              '', 'OUTPUTS',
              'asset_results.csv: all 82 asset/window results.',
              'performance.csv: four requested experiment measurements.',
              '*_boundary.csv: observed prices and exercise boundaries at every date.',
              'metadata.json: environment, conventions and source hash.',
              'See ../README.txt for instructions. Folder: Submissions/SharmaGarv/Class3/.']
    (out/'report.txt').write_text('\n'.join(lines)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate', action='store_true')
    parser.add_argument('--run-all', action='store_true')
    parser.add_argument('--data', type=Path, default=DATA)
    parser.add_argument('--out', type=Path, default=HERE/'results')
    args = parser.parse_args()
    if not args.validate and not args.run_all:
        parser.error('choose --validate or --run-all')
    cases = validate()  # Also warms JIT before measurement.
    if not args.run_all:
        return
    files = sorted(p for p in args.data.glob('*.csv') if p.stem != 'SP500')
    if len(files) != 40:
        raise ValueError(f'Expected 40 supplied assets, found {len(files)}')
    args.out.mkdir(parents=True, exist_ok=True)
    all_results, summaries = [], []
    for name, selected, periods in [('bitcoin_1year',[args.data/'BTCUSDT.csv'],8760),
                                    ('bitcoin_full',[args.data/'BTCUSDT.csv'],None),
                                    ('all40_1year',files,8760), ('all40_full',files,None)]:
        results, summary = run_experiment(name,selected,periods,args.out)
        all_results.extend(results)
        summaries.append(summary)
        write_csv(args.out/'asset_results.csv', all_results)
        write_csv(args.out/'performance.csv', summaries)
    metadata = dict(python=sys.version, platform=platform.platform(), numpy=np.__version__,
                    numba=numba.__version__, psutil=psutil.__version__, validation_cases=cases,
                    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                    timing='Sequential end-to-end per experiment, including loading, calibration, pricing and boundary CSV writing; excludes JIT warmup and validation.',
                    memory='10ms sampled process RSS including native memory and runtime; a sampled lower bound on peak, not auxiliary space. Allocator retention can affect later baselines.',
                    model='ATM put; sample log-return std; u=exp(s), d=1/u; R=exp(.04*T/N), T=elapsed calendar years with 365-day years. Missing observations are not filled; equal tree intervals approximate average elapsed time.',
                    boundary='Highest tree price with positive intrinsic value >= continuation; none recorded as empty CSV cell. Maturity handled explicitly for observed off-grid prices. Historical exercise uses raw observed price <= tree boundary.',
                    numerics='Float64, strike-normalized values, geometric stock rows restarted from log prices and reciprocal central nodes anchored exactly; stocks below exp(-700) normalized units treated as zero. No fast-math.',
                    historical_caveat='Volatility estimated over the same historical window; retrospective exercise analysis, not an out-of-sample trading strategy.')
    (args.out/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    write_report(args.out, all_results, summaries)
    print('COMPLETE: ' + str(args.out), flush=True)


if __name__ == '__main__':
    main()
