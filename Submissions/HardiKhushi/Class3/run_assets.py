"""Price all 40 supplied assets in two directly measured, price-only batches."""

import argparse
import csv
from datetime import datetime, timezone
import gc
import hashlib
import json
from math import isfinite
from pathlib import Path
import platform
import sys
from time import perf_counter
import tracemalloc

import numpy as np

from market_data import DEFAULT_DATA, HERE, calibration_report, calibrate_window, load_price_window
from price_american_put_numpy import price_american_put
from tree_model import validate_tree


SOURCES = ('run_assets.py', 'price_american_put_numpy.py', 'tree_model.py', 'market_data.py')


def source_hashes():
    return {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in SOURCES}


def save_json(path, contents):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(contents, stream, indent=2, allow_nan=False)
        stream.write('\n')


def price_all(cases):
    """One sequential batch call; retain every price, with no boundary output."""
    return [price_american_put(*case) for case in cases]


def run_horizon(paths, periods, output, horizon, expected_assets=40):
    paths = sorted((Path(p).resolve() for p in paths), key=lambda p: p.stem)
    if len(paths) != expected_assets or not paths or len({p.stem for p in paths}) != len(paths):
        raise ValueError('wrong asset count or duplicate asset names')
    output = Path(output).resolve()
    if not output.is_relative_to(HERE):
        raise ValueError('output must stay inside Class3')
    if output.exists():
        raise FileExistsError(f'refusing to replace existing results: {output}')
    prepared, cases, inputs = [], [], []
    for path in paths:
        window = load_price_window(path, periods)
        model = calibrate_window(window)
        case = (model.spot, model.strike, model.up, model.down, model.gross_rate, model.steps)
        validate_tree(*case)
        prepared.append((window, model))
        cases.append(case)
        inputs.append({'asset': path.stem, 'input': calibration_report(window, model)})
    hashes = source_hashes()
    output.mkdir(parents=True)
    names = [p.stem for p in paths]
    save_json(output / 'inputs.json', {'horizon': horizon, 'asset_order': names, 'cases': inputs})
    print(f'{horizon}: timing one batch of {len(cases)} assets (prices only)...', flush=True)
    gc.collect()
    start = perf_counter()
    prices = price_all(cases)
    seconds = perf_counter() - start
    if any(not isfinite(p) or not 0 <= p <= model.strike for p, (_, model) in zip(prices, prepared)):
        raise ArithmeticError('invalid positive-rate put price')
    save_json(output / 'timing.json', {'seconds': seconds, 'prices': prices, 'repeats': 1, 'tracing_enabled': False})
    print(f'{horizon}: timed batch complete in {seconds:.6f}s; measuring a separate batch allocation peak...', flush=True)
    gc.collect()
    tracemalloc.start()
    start = perf_counter()
    try:
        traced = price_all(cases)
        current, peak = tracemalloc.get_traced_memory()
    finally:
        memory_seconds = perf_counter() - start
        tracemalloc.stop()
    if traced != prices:
        raise ArithmeticError('timing and memory batches disagree')
    del traced
    save_json(output / 'memory.json', {'current_traced_bytes': current, 'peak_traced_bytes': peak,
              'instrumented_call_seconds': memory_seconds, 'repeats': 1, 'agrees_with_timing_call': True})
    if source_hashes() != hashes:
        raise RuntimeError('source code changed during measurement')
    fields = ('asset', 'horizon', 'N', 'spot', 'strike', 'log_return_std', 'up', 'down', 'gross_rate', 'probability_up', 'put_value')
    with (output / 'prices.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for name, (_, model), price in zip(names, prepared, prices):
            row = {key: getattr(model, key) for key in fields if hasattr(model, key)}
            row.update(asset=name, horizon=horizon, N=model.steps, put_value=price)
            writer.writerow(row)
    ns = [model.steps for _, model in prepared]
    metrics = {'horizon': horizon, 'engine': 'numpy', 'output': 'prices_only',
               'N_min': min(ns), 'N_max': max(ns), 'assets': len(paths),
               'seconds': seconds, 'peak_traced_bytes': peak}
    with (output / 'summary.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(metrics))
        writer.writeheader()
        writer.writerow(metrics)
    result = {**metrics, 'status': 'complete', 'completed_utc': datetime.now(timezone.utc).isoformat(),
              'asset_order': names, 'prices': dict(zip(names, prices)),
              'N_by_asset': {name: model.steps for name, (_, model) in zip(names, prepared)},
              'peak_traced_KiB': peak / 1024, 'source_sha256': hashes,
              'python': sys.version, 'numpy_version': np.__version__, 'platform': platform.platform(),
              'protocol': {
                  'timing': 'one perf_counter call around the complete sequential price_all call; includes output list and internal validation; excludes input loading, calibration, logging and files',
                  'memory': 'separate fresh tracemalloc session around the complete price_all call; includes work buffers and all returned prices; preloaded inputs and first-call prices excluded; not process RSS',
                  'execution': 'one process, sequential assets in sorted order; one asset work tree at a time; all prices retained; no exercise boundary requested in task 5',
                  'samples': 'one timed batch and one memory batch, not a sum of separately measured per-asset peaks or timings',
                  'units': 'put value in USDT per native unit of the named asset; PAXG represents a fine troy ounce',
              }}
    result['result_file_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir()) if p.is_file()}
    save_json(output / 'batch.json', result)
    print(f'{horizon}: complete; peak traced allocation {peak:,} bytes ({peak / 1024**2:.3f} MiB).', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=DEFAULT_DATA.parent)
    parser.add_argument('--output', type=Path, default=HERE / 'results/all_assets_v1')
    args = parser.parse_args()
    try:
        paths = sorted(args.data_dir.glob('*USDT.csv'))
        if len(paths) != 40 or not {'BTCUSDT', 'PAXGUSDT'} <= {p.stem for p in paths}:
            raise ValueError('expected all 40 supplied USDT assets, including BTCUSDT and PAXGUSDT')
        output = args.output.resolve()
        if not output.is_relative_to(HERE) or output.exists():
            raise ValueError('output must be a new directory inside Class3')
        one = run_horizon(paths, 8760, output / '1y', '1y')
        full = run_horizon(paths, None, output / 'full', 'full')
        save_json(output / 'completion.json', {'status': 'complete', 'batch_files': {
            name: hashlib.sha256((output / name / 'batch.json').read_bytes()).hexdigest() for name in ('1y', 'full')}})
    except (ValueError, OSError, ArithmeticError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
