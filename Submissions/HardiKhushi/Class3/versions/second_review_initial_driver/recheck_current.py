"""Recalibrate/reprice every delivered contract with current production code.

This is correctness verification, not a replacement timing or memory run.
Preserved benchmark values remain attached to their original source hashes.
"""

import ast
import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path

from market_data import DEFAULT_DATA, HERE, calibrate_window, load_price_window
from price_american_put_numpy import price_american_put
from verify_assets import verify_collection
from verify_results import verify_run


SOURCES = ('recheck_current.py', 'market_data.py', 'tree_model.py', 'price_american_put.py',
           'price_american_put_numpy.py', 'exercise.py')


def hashes():
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in SOURCES}


def reference_body(path):
    tree = ast.parse(path.read_text())
    return ast.dump(next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'reference_price'))


def recheck():
    source_hashes = hashes()
    root = HERE / 'results/all_assets_v1'
    verify_collection(root)
    boundary_checks, records = [], []
    for horizon, name in (('1y', 'bitcoin_1y_numpy'), ('full', 'bitcoin_full_numpy')):
        folder = HERE / 'results/audit_v1' / name
        verify_run(folder)
        saved = json.loads((folder / 'result.json').read_text())
        model = calibrate_window(load_price_window(DEFAULT_DATA, 8760 if horizon == '1y' else None))
        if asdict(model) != saved['model']:
            raise ArithmeticError('current Bitcoin calibration changed')
        actual, boundary = price_american_put(model.spot, model.strike, model.up, model.down,
                                            model.gross_rate, model.steps, return_boundary=True)
        with (folder / 'boundary.csv').open(newline='') as stream:
            old = [float(row['exercise_boundary']) if row['exercise_boundary'] else None for row in csv.DictReader(stream)]
        if actual != saved['put_value'] or boundary != old:
            raise ArithmeticError('current Bitcoin price or full boundary changed')
        boundary_checks.append({'horizon': horizon, 'price_exactly_equal': True,
                                'boundary_exactly_equal': True, 'rows': len(boundary)})
        print(f'Current Bitcoin {horizon}: price and all {len(boundary):,} boundary rows exactly match.', flush=True)
    for horizon in ('1y', 'full'):
        folder = root / horizon
        saved = json.loads((folder / 'batch.json').read_text())
        inputs = json.loads((folder / 'inputs.json').read_text())
        for index, case in enumerate(inputs['cases'], 1):
            asset, original = case['asset'], case['input']
            model = calibrate_window(load_price_window(DEFAULT_DATA.parent / (asset + '.csv'),
                                                       8760 if horizon == '1y' else None))
            if asdict(model) != original['model']:
                raise ArithmeticError(f'{asset}: current calibration changed')
            actual = price_american_put(model.spot, model.strike, model.up, model.down, model.gross_rate, model.steps)
            expected = saved['prices'][asset]
            if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-14 * model.strike):
                raise ArithmeticError(f'{horizon}/{asset}: current price changed')
            records.append({'horizon': horizon, 'asset': asset, 'N': model.steps,
                            'put_value': actual, 'saved_value': expected,
                            'exactly_equal': actual == expected,
                            'data_sha256': original['source_sha256']})
            print(f'Current code {horizon} {index:02d}/40: {asset} passed', flush=True)
    old_reference = HERE / 'versions/pre_second_review/check_asset_numerics.py'
    if reference_body(old_reference) != reference_body(HERE / 'check_asset_numerics.py'):
        raise ArithmeticError('independent numerical reference computation changed; rerun it')
    if hashes() != source_hashes or len(records) != 80:
        raise RuntimeError('current source changed or not all contracts were checked')
    return {'status': 'verified', 'cases_checked': len(records), 'cases': records,
            'bitcoin_boundaries': boundary_checks, 'source_sha256': source_hashes,
            'reference_computation_unchanged': True,
            'measured_results_note': 'this report verifies current values; no historical timing or memory record was replaced'}


if __name__ == '__main__':
    report = recheck()
    with (HERE / 'audit/second_review/current_prices.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print('Current code: all 80 prices and both complete Bitcoin boundaries verified.')
