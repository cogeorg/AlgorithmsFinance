"""Check complete 40-asset batches against raw prices, calibration and tables."""

import argparse
import csv
from datetime import datetime
import json
import math
from pathlib import Path

from market_data import DEFAULT_DATA, HERE, SECONDS_PER_YEAR
from verify_results import digest, require, source_location


def verify_batch(folder, expected_assets=40, expected_horizon=None):
    folder = Path(folder).resolve()
    require(folder.is_relative_to(HERE), 'batch must stay inside Class3')
    result = json.loads((folder / 'batch.json').read_text())
    if expected_horizon is not None:
        require(result['horizon'] == expected_horizon, 'batch stored under the wrong horizon')
    require(result['status'] == 'complete' and result['assets'] == expected_assets, 'incomplete/wrong-size batch')
    names = result['asset_order']
    require(len(names) == expected_assets and names == sorted(set(names)), 'duplicate/missing/unordered assets')
    if expected_assets == 40:
        require(set(names) == {p.stem for p in DEFAULT_DATA.parent.glob('*USDT.csv')}, 'batch omits a supplied asset')
        require(result['horizon'] in ('1y', 'full'), 'unknown horizon')
    require(result['engine'] == 'numpy' and result['output'] == 'prices_only', 'wrong batch method')
    require(set(result['prices']) == set(result['N_by_asset']) == set(names), 'incomplete price/N map')
    require({'run_assets.py', 'price_american_put_numpy.py', 'tree_model.py', 'market_data.py'} <= set(result['source_sha256']), 'missing producer source identity')
    for name, sha in result['source_sha256'].items():
        source_location(name, sha)
    files = result['result_file_sha256']
    require({'inputs.json', 'timing.json', 'memory.json', 'prices.csv', 'summary.csv'} <= set(files), 'missing evidence file')
    for name, sha in files.items():
        require(Path(name).name == name and digest(folder / name) == sha, f'output hash mismatch: {name}')
    inputs = json.loads((folder / 'inputs.json').read_text())
    require(inputs['horizon'] == result['horizon'] and inputs['asset_order'] == names, 'input batch identity mismatch')
    require([case['asset'] for case in inputs['cases']] == names, 'wrong input asset order')
    with (folder / 'prices.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    require([row['asset'] for row in rows] == names, 'missing/duplicate price row')
    close = lambda a, b: math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-14)
    for name, case, row in zip(names, inputs['cases'], rows):
        data = case['input']
        source_location('market_data.py', data['source_code_sha256'])
        source = Path(data['source'])
        if not source.is_file():
            source = DEFAULT_DATA.parent / source.name
        require(source.stem == name and digest(source) == data['source_sha256'], f'{name}: input data identity')
        with source.open(newline='') as stream:
            raw = list(csv.DictReader(stream))
        model = data['model']
        n = model['steps']
        require(n == result['N_by_asset'][name] == int(row['N']), f'{name}: wrong N')
        if result['horizon'] == '1y':
            require(n == 8760, f'{name}: wrong one-year window')
        elif result['horizon'] == 'full':
            require(n == len(raw) - 1, f'{name}: wrong full-file window')
        require(len(raw) == data['source_rows'], f'{name}: wrong file size')
        selected = raw[-n - 1:]
        require(len(selected) == n + 1 == data['selected_prices'], f'{name}: wrong price count')
        prices = [float(item['close']) for item in selected]
        times = [datetime.fromisoformat(item['timestamp_utc'].replace('Z', '+00:00')) for item in selected]
        require(prices[0] == model['spot'] == model['strike'], f'{name}: initial price/strike')
        require(prices[-1] == data['final_close'], f'{name}: final close')
        require(times[0].isoformat() == data['start_utc'] and times[-1].isoformat() == data['end_utc'], f'{name}: window dates')
        returns = [math.log(b / a) for a, b in zip(prices, prices[1:])]
        mean = math.fsum(returns) / n
        std = math.sqrt(math.fsum((r - mean)**2 for r in returns) / (n - 1))
        years = (times[-1] - times[0]).total_seconds() / SECONDS_PER_YEAR
        require(close(mean, model['mean_log_return']) and close(std, model['log_return_std']), f'{name}: sample calibration')
        require(close(years, model['years']) and model['annual_rate'] == .04, f'{name}: year/rate convention')
        require(close(math.exp(std), model['up']) and close(1 / model['up'], model['down']), f'{name}: move factors')
        require(close(math.exp(.04 * years / n), model['gross_rate']), f'{name}: interest factor')
        require(0 < model['down'] < model['gross_rate'] < model['up'], f'{name}: no arbitrage')
        require(close((model['gross_rate'] - model['down']) / (model['up'] - model['down']), model['probability_up']), f'{name}: q')
        hours = [(b - a).total_seconds() / 3600 for a, b in zip(times, times[1:])]
        require(all(h >= 1 and h.is_integer() for h in hours), f'{name}: timestamp gaps')
        require(int(sum(hours)) - n == data['missing_hours'] and sum(h != 1 for h in hours) == data['non_hourly_intervals'], f'{name}: gap reporting')
        for key in ('spot', 'strike', 'log_return_std', 'up', 'down', 'gross_rate', 'probability_up'):
            require(float(row[key]) == model[key], f'{name}: table calibration {key}')
        require(row['horizon'] == result['horizon'], f'{name}: table horizon')
        price = result['prices'][name]
        require(math.isfinite(price) and 0 <= price <= model['strike'], f'{name}: invalid put value')
        require(float(row['put_value']) == price, f'{name}: table price mismatch')
    ns = list(result['N_by_asset'].values())
    require(min(ns) == result['N_min'] and max(ns) == result['N_max'], 'N range mismatch')
    timing = json.loads((folder / 'timing.json').read_text())
    memory = json.loads((folder / 'memory.json').read_text())
    require(timing['prices'] == [result['prices'][name] for name in names], 'timed prices disagree')
    require(math.isfinite(result['seconds']) and timing['seconds'] == result['seconds'] > 0 and not timing['tracing_enabled'] and timing['repeats'] == 1, 'timing mismatch')
    require(memory['peak_traced_bytes'] == result['peak_traced_bytes'] >= memory['current_traced_bytes'] >= 0, 'memory mismatch')
    require(memory['agrees_with_timing_call'] and memory['repeats'] == 1, 'memory batch did not agree')
    require(result['peak_traced_KiB'] == result['peak_traced_bytes'] / 1024, 'wrong memory conversion')
    with (folder / 'summary.csv').open(newline='') as stream:
        summaries = list(csv.DictReader(stream))
    require(len(summaries) == 1, 'wrong number of summary rows')
    summary = summaries[0]
    for key in ('horizon', 'engine', 'output'):
        require(summary[key] == result[key], f'summary {key} mismatch')
    for key in ('N_min', 'N_max', 'assets', 'peak_traced_bytes'):
        require(int(summary[key]) == result[key], f'summary {key} mismatch')
    require(float(summary['seconds']) == result['seconds'], 'summary timing mismatch')
    return {'batch': str(folder.relative_to(HERE)), 'status': 'verified', 'assets': expected_assets,
            'horizon': result['horizon'], 'batch_sha256': digest(folder / 'batch.json')}


def verify_collection(root, expected_assets=40):
    root = Path(root).resolve()
    require(root.is_relative_to(HERE), 'collection must stay inside Class3')
    completion = json.loads((root / 'completion.json').read_text())
    require(completion['status'] == 'complete' and set(completion['batch_files']) == {'1y', 'full'}, 'both horizons must complete')
    for horizon, sha in completion['batch_files'].items():
        require(digest(root / horizon / 'batch.json') == sha, 'completion hash mismatch')
    reports = [verify_batch(root / name, expected_assets, expected_horizon=name) for name in ('1y', 'full')]
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=HERE / 'results/all_assets_v1')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        root = args.directory.resolve()
        reports = verify_collection(root)
        report = {'batches': reports, 'source_sha256': {name: digest(HERE / name) for name in ('verify_assets.py', 'verify_results.py')}}
        if args.output:
            output = args.output.resolve()
            require(output.is_relative_to(HERE), 'output must stay inside Class3')
            with output.open('x') as stream:
                json.dump(report, stream, indent=2)
                stream.write('\n')
        print(json.dumps(report, indent=2))
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
