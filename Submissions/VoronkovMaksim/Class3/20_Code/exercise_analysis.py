"""Compare a fixed American-put exercise boundary with later observed closes."""
import csv
from datetime import datetime, timedelta
import json
import math
from pathlib import Path
import sys

from calibrate import read_prices
from price_american_put import PriceAmericanPut


def boundary_tree(S0, K, u, d, R, N):
    # Use the existing public implementation for input validation and price comparison.
    original = PriceAmericanPut(S0, K, u, d, R, N)
    q = (R - d) / (u - d)
    stock = [S0] * (N + 1)
    for _ in range(N):
        stock[0] *= d
    for j in range(1, N + 1):
        stock[j] = stock[j - 1] * (u / d)
    values = [max(K - s, 0.0) for s in stock]
    boundaries = [None] * (N + 1)
    # At maturity, exercise if the intrinsic payoff is positive.
    for j in range(N + 1):
        if values[j] > 0:
            boundaries[N] = stock[j]
    for t in range(N - 1, -1, -1):
        for j in range(t + 1):
            stock[j] /= d
            exercise = max(K - stock[j], 0.0)
            continuation = (q * values[j + 1] + (1 - q) * values[j]) / R
            if exercise > 0 and exercise >= continuation:
                if boundaries[t] is None or stock[j] > boundaries[t]:
                    boundaries[t] = stock[j]
            values[j] = max(exercise, continuation)
    if not math.isclose(original, values[0], rel_tol=1e-12, abs_tol=1e-10):
        raise ValueError('Boundary calculation changed the price')
    return values[0], boundaries


def main(input_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    root = Path(__file__).resolve().parents[1]
    results = root / '40_Results'
    with (results / 'sp500_pricing_baseline.json').open(encoding='utf-8-sig') as f:
        model = json.load(f)
    with (results / 'sp500_calibration.json').open(encoding='utf-8-sig') as f:
        calibration = json.load(f)
    rows = read_prices(input_path)
    start = datetime.fromisoformat(calibration['last_calibration_observation_utc'])
    end = start + timedelta(days=365.25 * model['T_years'])
    if rows[-1][0] < end:
        raise ValueError('Input does not cover the full out-of-sample horizon')
    anchor = [price for date, price in rows if date == start]
    if anchor != [model['S0']]:
        raise ValueError('Starting observation differs from saved calibration')
    observed = [(date, price) for date, price in rows if start < date <= end]
    if not observed:
        raise ValueError('No out-of-sample observations')
    N = model['N']
    value, boundaries = boundary_tree(model['S0'], model['K'], model['u'], model['d'], model['R'], N)
    if not math.isclose(value, model['american_put_price'], rel_tol=1e-12, abs_tol=1e-10):
        raise ValueError('Recomputed price differs from saved baseline')
    matches = []
    for date, price in observed:
        step = min(N, math.floor((date - start).total_seconds() / (end - start).total_seconds() * N))
        b = boundaries[step]
        if b is not None and price <= b and model['K'] - price > 0:
            matches.append({'timestamp_utc': date.isoformat(), 'model_step': step,
                            'underlying_price': price, 'boundary': b, 'intrinsic_payoff': model['K'] - price})
            break
    paths = [results / 'sp500_exercise_summary.json', results / 'sp500_boundary.csv', results / 'sp500_exercise_chart.png']
    if any(p.exists() for p in paths):
        raise FileExistsError('An output already exists; preserve it before rerunning')
    summary = {'model_price': value, 'model_steps': N, 'origin_utc': start.isoformat(),
               'maturity_utc': end.isoformat(), 'observations': len(observed),
               'first_observation_utc': observed[0][0].isoformat(), 'last_observation_utc': observed[-1][0].isoformat(),
               'mapping': 'floor(elapsed calendar time / 365.25 days * N); use latest tree step',
               'first_crossing': matches[0] if matches else None}
    with paths[0].open('x', encoding='utf-8') as f:
        json.dump(summary, f, indent=2); f.write('\n')
    with paths[1].open('x', encoding='utf-8', newline='') as f:
        writer = csv.writer(f); writer.writerow(['step', 'model_time_utc', 'boundary'])
        for t, boundary in enumerate(boundaries):
            writer.writerow([t, (start + (end - start) * (t / N)).isoformat(), '' if boundary is None else boundary])
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot([start] + [date for date, _ in observed], [model['S0']] + [price for _, price in observed], label='S&P 500 close', linewidth=1.2)
    ax.plot([start + (end - start) * (t / N) for t in range(N + 1)], boundaries, label='Exercise boundary', linewidth=1.5)
    if matches:
        hit = matches[0]
        ax.scatter([datetime.fromisoformat(hit['timestamp_utc'])], [hit['underlying_price']], color='red', zorder=5, label='First observed crossing')
    ax.set(title='S&P 500: observed closes and American-put exercise boundary', xlabel='Date (UTC; model steps mapped by calendar time)', ylabel='Index points')
    ax.grid(alpha=.25); ax.legend(); fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(paths[2], dpi=150); plt.close(fig)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python exercise_analysis.py PATH_TO_SP500_CSV')
    main(sys.argv[1])
