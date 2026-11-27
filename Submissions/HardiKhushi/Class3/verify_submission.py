"""One-command verification of the delivered table, runs and numerical evidence."""

import argparse
import ast
import csv
import json
import math
from pathlib import Path

from market_data import HERE
from verify_assets import verify_batch, verify_collection
from verify_results import digest, require, source_location, verify_run


def verify_summary(path):
    path = Path(path).resolve()
    require(path.is_relative_to(HERE), 'summary must stay inside Class3')
    manifest = json.loads(path.with_suffix('.manifest.json').read_text())
    require(manifest['summary_sha256'] == digest(path), 'summary hash mismatch')
    source_location('build_summary.py', manifest['builder_sha256'])
    require(manifest['rows'] == 4 and len(manifest['run_sha256']) == 4, 'expected four source runs')
    expected, batch_parents = {}, set()
    for relative, sha in manifest['run_sha256'].items():
        run_path = (HERE / relative).resolve()
        require(run_path.is_relative_to(HERE) and digest(run_path) == sha, 'source run identity mismatch')
        run = json.loads(run_path.read_text())
        if run_path.name == 'result.json':
            verify_run(run_path.parent)
            require(run['asset'] == 'BTCUSDT', 'summary Bitcoin asset mismatch')
            inputs = json.loads((run_path.parent / 'inputs.json').read_text())
            n = run['model']['steps']
            horizon = '1y' if n == 8760 else 'full'
            require(n == (8760 if horizon == '1y' else inputs['source_rows'] - 1), 'wrong Bitcoin horizon')
            group, mode, n_min, n_max = 'BTCUSDT', 'price_and_boundary', n, n
        elif run_path.name == 'batch.json':
            horizon = run['horizon']
            verify_batch(run_path.parent, expected_horizon=horizon)
            batch_parents.add(run_path.parent.parent)
            group, mode, n_min, n_max = 'all_40_supplied', 'prices_only', run['N_min'], run['N_max']
        else:
            raise ValueError('unrecognized summary source')
        key = (group, horizon)
        require(key not in expected, 'duplicate source horizon')
        expected[key] = dict(assets=run['assets'], engine='numpy', output=mode,
                             N_min=n_min, N_max=n_max, seconds=run['seconds'],
                             peak_traced_bytes=run['peak_traced_bytes'],
                             peak_traced_MiB=run['peak_traced_bytes'] / 1024**2)
    require(set(expected) == {(group, h) for group in ('BTCUSDT', 'all_40_supplied') for h in ('1y', 'full')}, 'missing summary phase')
    require(len(batch_parents) == 1, 'batches must belong to one completed collection')
    verify_collection(next(iter(batch_parents)))
    with path.open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 4, 'expected four summary rows')
    seen = set()
    for row in rows:
        key = (row['asset_group'], row['horizon'])
        require(key in expected and key not in seen, 'missing/duplicate/mislabelled summary row')
        seen.add(key)
        wanted = expected[key]
        for field in ('engine', 'output'):
            require(row[field] == wanted[field], f'summary {field} mismatch')
        for field in ('assets', 'N_min', 'N_max', 'peak_traced_bytes'):
            require(int(row[field]) == wanted[field], f'summary {field} mismatch')
        for field in ('seconds', 'peak_traced_MiB'):
            require(float(row[field]) == wanted[field], f'summary {field} mismatch')
    return {'summary': str(path.relative_to(HERE)), 'rows_verified': 4, 'summary_sha256': digest(path)}


def function_body(path, name):
    nodes = ast.parse(Path(path).read_text()).body
    return ast.dump(next(node for node in nodes if isinstance(node, ast.FunctionDef) and node.name == name))


def verify_submission(current_check=None):
    summary = verify_summary(HERE / 'results/final_summary.csv')
    root = HERE / 'results/all_assets_v1'
    numerical = json.loads((HERE / 'audit/batch_numerics.json').read_text())
    source_location('check_asset_numerics.py', numerical['reference_source_sha256'])
    expected, prices, models, data_hashes = set(), {}, {}, {}
    for horizon in ('1y', 'full'):
        path = root / horizon / 'batch.json'
        require(digest(path) == numerical['batch_sha256'][horizon], 'numerical evidence belongs to another batch')
        result = json.loads(path.read_text())
        inputs = json.loads((path.parent / 'inputs.json').read_text())
        for case in inputs['cases']:
            models[horizon, case['asset']] = case['input']['model']
            data_hashes[horizon, case['asset']] = case['input']['source_sha256']
        for asset in result['asset_order']:
            expected.add((horizon, asset))
            prices[horizon, asset] = result['prices'][asset]
    cases = numerical['cases']
    require(numerical['status'] == 'verified' and numerical['cases_checked'] == len(cases) == 80, 'incomplete numerical evidence')
    require({(case['horizon'], case['asset']) for case in cases} == expected, 'numerical coverage mismatch')
    require(all(case['put_value'] == prices[case['horizon'], case['asset']] for case in cases), 'numerical price mismatch')
    current_path = Path(current_check) if current_check is not None else HERE / 'audit/second_review/current_prices.json'
    current = json.loads(current_path.read_text())
    require(current['status'] == 'verified' and current['cases_checked'] == len(current['cases']) == 80, 'current-code check incomplete')
    require({(case['horizon'], case['asset']) for case in current['cases']} == expected, 'current-code coverage mismatch')
    for name, sha in current['source_sha256'].items():
        if name == 'recheck_current.py':
            driver = HERE / source_location(name, sha)
            for function in ('recheck', 'hashes', 'reference_body'):
                require(function_body(driver, function) == function_body(HERE / name, function), 'recheck computation changed')
        else:
            require(digest(HERE / name) == sha, 'pricing source changed; rerun recheck_current.py --output NEW_REPORT and pass --current-check')
    require(all(case['saved_value'] == prices[case['horizon'], case['asset']] for case in current['cases']), 'current-code evidence price mismatch')
    for case in current['cases']:
        key = (case['horizon'], case['asset'])
        model = models[key]
        require(case['N'] == model['steps'] and case['data_sha256'] == data_hashes[key], 'current-code input evidence mismatch')
        require(math.isclose(case['put_value'], prices[key], rel_tol=1e-12, abs_tol=1e-14 * model['strike']), 'current price does not match saved value')
    checks = current['bitcoin_boundaries']
    require(len(checks) == 2 and {check['horizon'] for check in checks} == {'1y', 'full'}, 'missing current Bitcoin boundary check')
    for check in checks:
        name = 'bitcoin_1y_numpy' if check['horizon'] == '1y' else 'bitcoin_full_numpy'
        saved = json.loads((HERE / 'results/audit_v1' / name / 'result.json').read_text())
        require(check['rows'] == saved['boundary_entries'] and check['price_exactly_equal'] and check['boundary_exactly_equal'], 'current Bitcoin boundary check failed')
    return {'status': 'verified', **summary, 'independent_contracts': 80,
            'current_code_contracts': 80, 'current_bitcoin_boundaries': current['bitcoin_boundaries'],
            'measured_source_note': 'timing/memory records retain original version hashes; those sources are preserved in versions/pre_second_review',
            'verifier_sha256': digest(Path(__file__))}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--current-check', type=Path)
    args = parser.parse_args()
    try:
        report = verify_submission(args.current_check)
        if args.output:
            output = args.output.resolve()
            require(output.is_relative_to(HERE), 'output must stay inside Class3')
            with output.open('x') as stream:
                json.dump(report, stream, indent=2)
                stream.write('\n')
        print(json.dumps(report, indent=2))
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))
