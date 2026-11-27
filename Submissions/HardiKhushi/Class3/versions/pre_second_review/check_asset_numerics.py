"""Independently reprice every batch contract and check European lower bounds.

No production pricer, tree helper, loader or calibration function is imported.
The reference uses relative CRR prices and freshly allocated backward rows.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent


def reference_price(model):
    n, spot, strike = model['steps'], model['spot'], model['strike']
    q, rate, sigma = model['probability_up'], model['gross_rate'], math.log(model['up'])
    if model['down'] != 1 / model['up']:
        raise ValueError('this reference expects a calibrated reciprocal CRR model')
    j = np.arange(n + 1)
    terminal = np.maximum(strike - spot * np.exp((2 * j - n) * sigma), 0)
    weights = [math.exp(math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
                        + k * math.log(q) + (n - k) * math.log1p(-q)) for k in range(n + 1)]
    european = math.fsum(float(v) * w for v, w in zip(terminal, weights)) / rate**n
    value = terminal
    for t in range(n - 1, -1, -1):
        exercise = np.maximum(strike - spot * np.exp((2 * j[:t + 1] - t) * sigma), 0)
        holding = ((1 - q) * value[:-1] + q * value[1:]) / rate
        value = np.maximum(exercise, holding)
    return float(value[0]), european, math.fsum(weights)


def check(directory):
    records, identities = [], {}
    for horizon in ('1y', 'full'):
        folder = directory / horizon
        result = json.loads((folder / 'batch.json').read_text())
        inputs = json.loads((folder / 'inputs.json').read_text())
        identities[horizon] = hashlib.sha256((folder / 'batch.json').read_bytes()).hexdigest()
        for index, case in enumerate(inputs['cases'], 1):
            asset, model = case['asset'], case['input']['model']
            expected, european, mass = reference_price(model)
            actual = result['prices'][asset]
            if not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12 * model['strike']):
                raise ArithmeticError(f'{horizon}/{asset}: independent price disagrees')
            if not math.isclose(mass, 1, rel_tol=1e-7):
                raise ArithmeticError(f'{horizon}/{asset}: invalid binomial probability sum')
            if not european <= actual + 1e-7 * model['strike']:
                raise ArithmeticError(f'{horizon}/{asset}: below European put bound')
            records.append({'horizon': horizon, 'asset': asset, 'N': model['steps'],
                            'put_value': actual, 'reference_value': expected,
                            'difference': actual - expected,
                            'difference_as_fraction_of_strike': (actual - expected) / model['strike'],
                            'european_lower_bound': european, 'binomial_probability_sum': mass})
            print(f'Independent check {horizon} {index:02d}/{result["assets"]}: {asset} passed', flush=True)
        bitcoin = json.loads((HERE / 'results/audit_v1' / ('bitcoin_1y_numpy' if horizon == '1y' else 'bitcoin_full_numpy') / 'result.json').read_text())
        if result['prices']['BTCUSDT'] != bitcoin['put_value']:
            raise ArithmeticError('batch Bitcoin price does not exactly match audited boundary run')
    return {'status': 'verified', 'cases_checked': len(records), 'cases': records,
            'batch_sha256': identities,
            'bitcoin_exactly_matches_audited_runs': True,
            'reference_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=HERE / 'results/all_assets_v1')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = check(args.directory.resolve())
    if args.output:
        output = args.output.resolve()
        if not output.is_relative_to(HERE):
            parser.error('output must stay inside Class3')
        with output.open('x') as stream:
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write('\n')
    print(f'All {report["cases_checked"]} contracts independently verified.')
