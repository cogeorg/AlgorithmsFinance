"""Independent CRR reference: relative-price rows and a European lower bound.

This audit intentionally does not import either pricer or tree_model. It
reconstructs prices as spot * exp((2*j-t)*log(up)), rather than updating stock
rows in place or exponentiating absolute log prices as the audited engines do.
"""

import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np


HERE = Path(__file__).resolve().parent


def reference(model):
    n, spot, strike = model['steps'], model['spot'], model['strike']
    q, rate, sigma = model['probability_up'], model['gross_rate'], math.log(model['up'])
    j = np.arange(n + 1)
    stock = spot * np.exp((2 * j - n) * sigma)
    value = np.maximum(strike - stock, 0)
    tolerance = 32 * sys.float_info.epsilon * strike
    boundary = [None] * (n + 1)
    selected = np.flatnonzero(value > tolerance)
    boundary[n] = float(stock[selected[-1]]) if len(selected) else None
    # An independent O(N) European binomial sum bounds the American value.
    weights = [math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                        + k * math.log(q) + (n - k) * math.log1p(-q)) for k in range(n + 1)]
    european = math.fsum(float(payoff) * probability for payoff, probability in zip(value, weights)) / rate**n
    for t in range(n - 1, -1, -1):
        prices = spot * np.exp((2 * j[:t + 1] - t) * sigma)
        exercise = np.maximum(strike - prices, 0)
        continuation = ((1 - q) * value[:-1] + q * value[1:]) / rate
        value = np.maximum(exercise, continuation)
        selected = np.flatnonzero((exercise > tolerance) & (exercise >= continuation))
        if rate >= 1 and len(selected):
            boundary[t] = float(prices[selected[-1]])
    return float(value[0]), boundary, european, math.fsum(weights)


def node_index(threshold, t, model):
    if threshold is None:
        return None
    return round((math.log(threshold / model['spot']) / math.log(model['up']) + t) / 2)


def check(name):
    folder = HERE / 'results/audit_v1' / name
    result = json.loads((folder / 'result.json').read_text())
    with (folder / 'boundary.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    price, boundary, european, total_probability = reference(result['model'])
    if not math.isclose(price, result['put_value'], rel_tol=1e-10, abs_tol=1e-8):
        raise ArithmeticError(f'{name}: independent price disagrees')
    if not math.isclose(total_probability, 1, rel_tol=1e-7):
        raise ArithmeticError('binomial probabilities do not sum to one')
    if european > price + 1e-7 * result['model']['strike']:
        raise ArithmeticError('American put is below European lower bound')
    first, disagreements, old_changes = None, [], []
    old_folder = HERE / 'results' / name
    with (old_folder / 'boundary.csv').open(newline='') as stream:
        old_rows = list(csv.DictReader(stream))
    for t, (row, expected, old_row) in enumerate(zip(rows, boundary, old_rows)):
        actual = float(row['exercise_boundary']) if row['exercise_boundary'] else None
        old = float(old_row['exercise_boundary']) if old_row['exercise_boundary'] else None
        if node_index(actual, t, result['model']) != node_index(expected, t, result['model']):
            disagreements.append(t)
        if node_index(actual, t, result['model']) != node_index(old, t, result['model']):
            old_changes.append(t)
        if first is None and expected is not None and float(row['observed_close']) <= expected:
            first = t
    if disagreements:
        raise ArithmeticError(f'{name}: policy disagreement at {disagreements[:10]}')
    if first != (result['first_exercise']['t'] if result['first_exercise'] else None):
        raise ArithmeticError('independent first crossing disagrees')
    old_result = json.loads((old_folder / 'result.json').read_text())
    return {'run': name, 'reference_price': price, 'audited_price': result['put_value'],
            'price_difference_from_reference': result['put_value'] - price,
            'price_difference_from_legacy': result['put_value'] - old_result['put_value'],
            'european_lower_bound': european, 'binomial_probability_sum': total_probability,
            'policy_rows_checked': len(rows), 'policy_disagreements': disagreements,
            'first_crossing_t': first, 'changed_policy_nodes_vs_legacy': old_changes,
            'result_sha256': hashlib.sha256((folder / 'result.json').read_bytes()).hexdigest()}


if __name__ == '__main__':
    reports = [check(name) for name in ('bitcoin_1y_numpy', 'bitcoin_full_numpy')]
    output = HERE / 'audit/numerical_check.json'
    payload = {'runs': reports, 'reference_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    with output.open('x') as stream:
        json.dump(payload, stream, indent=2)
        stream.write('\n')
    print(json.dumps(payload, indent=2))
