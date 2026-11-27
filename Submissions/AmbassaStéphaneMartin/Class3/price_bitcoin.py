"""Opt-in one-year Bitcoin price, exercise boundary and observed decision."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from time import perf_counter

from benchmark_pricing import process_peak_memory
from exercise_policy import first_observed_exercise, price_american_put_with_boundary
import market_test_support as support

ROOT = Path(__file__).resolve().parent


def utc_label(stamp):
    return stamp.isoformat().replace('+00:00', 'Z') if stamp is not None else None


def run_one_year(output_dir):
    window = support.load_prepared_window('BTCUSDT', 'one_year')
    years = support.require_hourly_window(window)
    model = support.calibrate_prepared_window(window)
    inputs = support.pricing_parameters(window, model)
    if model.N != 8760 or len(window.prices) != 8761 or years != 1.0:
        raise ValueError('Expected 8,761 hourly Bitcoin closes and one ACT/365F year.')
    source = ROOT / 'output' / window.metadata['file']
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    start = perf_counter()
    result = price_american_put_with_boundary(**inputs)
    seconds = perf_counter()-start
    process_peak, process_scope = process_peak_memory()
    if process_peak is None:
        process_scope = 'Whole-process peak memory unavailable; no traced-memory pass was run.'
    if not math.isfinite(result.price) or not 0 <= result.price <= inputs['K']:
        raise ValueError('Invalid finite-price/bounds result for the positive-rate Bitcoin contract.')
    if len(result.boundary) != len(window.prices) or result.boundary[0] is not None:
        raise ValueError('Invalid boundary dimensions or at-the-money root exercise decision.')
    if any(level is not None and (not math.isfinite(level) or not 0 < level < inputs['K'])
           for level in result.boundary):
        raise ValueError('Exercise boundaries must be finite positive prices below K.')
    decision = first_observed_exercise(window.prices, result.boundary, inputs['K'],
                                       timestamps_utc=window.timestamps)
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_hash:
        raise ValueError('Prepared input changed during the experiment.')

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    boundary_file = output_dir / 'bitcoin_exercise_boundary.csv'
    with boundary_file.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(('observation_index', 'timestamp_utc', 'observed_close', 'exercise_boundary'))
        writer.writerows((t, utc_label(stamp), price, level)
                         for t, (stamp, price, level) in enumerate(
                             zip(window.timestamps, window.prices, result.boundary)))
    report = {
        'reproduce': 'python -B price_bitcoin.py --run',
        'asset': 'BTCUSDT', 'window': 'one_year', 'assets': 1, 'quote_currency': 'USDT',
        'start_utc': utc_label(window.timestamps[0]), 'end_utc': utc_label(window.timestamps[-1]),
        'closes': len(window.prices), 'N': model.N, 'T': years, 'day_count': 'ACT/365F',
        'parameters': inputs, 's': model.s, 'q': model.q,
        'price': result.price, 'price_units': 'USDT per BTC',
        'boundary_entries': len(result.boundary), 'boundary_file': boundary_file.name,
        'boundary_csv_sha256': hashlib.sha256(boundary_file.read_bytes()).hexdigest(),
        'exercise': {
            'kind': decision.kind, 'index': decision.index,
            'timestamp_utc': utc_label(decision.timestamp_utc), 'payoff': decision.payoff,
            'observed_price': window.prices[decision.index] if decision.index is not None else None,
        },
        'elapsed_seconds_untraced': seconds, 'pricing_runs': 1,
        'timing_scope': 'Boundary pricing only; loading, calibration and observed-path scan excluded.',
        'process_peak_memory_bytes': process_peak, 'process_peak_scope': process_scope,
        'memory_notes': 'Whole-process peak includes imports and prepared data; no traced allocation pass.',
        'python': sys.version, 'platform': platform.platform(),
        'source_window': 'output/' + window.metadata['file'], 'source_window_sha256': source_hash,
        'implementation_lf_sha256': {
            name: hashlib.sha256((ROOT / name).read_text(encoding='utf-8').encode('utf-8')).hexdigest()
            for name in ('american_put.py', 'exercise_policy.py', 'market_calibration.py')
        },
        'interpretation': 'Retrospective lab experiment; calibration uses the full selected window.',
        'full_history': 'Not priced: its missing hour still requires explicit treatment.',
    }
    report_file = output_dir / 'bitcoin_exercise.json'
    report_file.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true', help='Allow one 8,760-period pricing run.')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'results')
    args = parser.parse_args()
    if not args.run:
        parser.error('Use --run to execute the one-year Bitcoin pricing experiment.')
    print(json.dumps(run_one_year(args.output_dir), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
