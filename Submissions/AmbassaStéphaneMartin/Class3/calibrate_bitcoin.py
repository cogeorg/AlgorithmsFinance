"""Reproduce the prepared Bitcoin calibration report without tree pricing."""
import argparse
from datetime import timedelta
import hashlib
import json
from pathlib import Path

import market_test_support as support

ROOT = Path(__file__).resolve().parent


def utc_label(stamp):
    return stamp.isoformat().replace('+00:00', 'Z')


def calibration_report():
    year = support.load_prepared_window('BTCUSDT', 'one_year')
    T = support.require_hourly_window(year)
    if len(year.prices) != 8761 or len(year.prices) - 1 != 8760 or T != 1.0:
        raise ValueError('Expected 8,761 hourly Bitcoin closes, 8,760 periods and T=1 ACT/365F year.')
    model = support.calibrate_prepared_window(year, annual_rate=0.04)
    if model.N != 8760:
        raise ValueError('Calibrated period count differs from the prepared window.')
    full = support.load_prepared_window('BTCUSDT', 'full_history')
    if full.metadata['ready_for_hourly_pricing'] != 'False':
        raise ValueError('Full-history preparation must remain flagged for explicit gap treatment.')
    try:
        support.require_hourly_window(full)
    except ValueError as exc:
        full_history_reason = str(exc)
    else:
        raise ValueError('Expected the full-history window to remain flagged for explicit gap treatment.')
    gaps = []
    for previous, current in zip(full.timestamps, full.timestamps[1:]):
        elapsed_hours = (current - previous).total_seconds() / 3600
        if elapsed_hours != 1:
            gaps.append({'previous_utc': utc_label(previous), 'next_utc': utc_label(current),
                         'first_missing_utc': utc_label(previous + timedelta(hours=1)),
                         'elapsed_hours': elapsed_hours, 'missing_hours': elapsed_hours - 1})
    source = ROOT / 'output' / year.metadata['file']
    return {
        'reproduce': 'python -B calibrate_bitcoin.py',
        'scope': 'Market calibration only; no boundary construction or large tree pricing.',
        'asset': 'BTCUSDT', 'window': 'one_year', 'quote_currency': 'USDT',
        'start_utc': utc_label(year.timestamps[0]), 'end_utc': utc_label(year.timestamps[-1]),
        'closes': len(year.prices), 'N': model.N,
        'elapsed_hours': (year.timestamps[-1] - year.timestamps[0]).total_seconds() / 3600,
        'day_count': 'ACT/365F', 'T': T, 'annual_rate': 0.04,
        'S0': year.prices[0], 'K': year.prices[0], 'P0': year.prices[0],
        's': model.s, 's_units': 'hourly log-return sample standard deviation (N-1)',
        'u': model.u, 'd': model.d, 'R': model.R, 'q': model.q,
        'source_window': 'output/' + year.metadata['file'],
        'source_window_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'calibration_module_lf_sha256': hashlib.sha256(
            (ROOT / 'market_calibration.py').read_text(encoding='utf-8').encode('utf-8')).hexdigest(),
        'full_history': {
            'closes': len(full.prices), 'N': len(full.prices) - 1,
            'ready_for_hourly_pricing': full.metadata['ready_for_hourly_pricing'] == 'True',
            'calibrated': False, 'hourly_spacing_check': 'rejected',
            'reason': full_history_reason, 'gaps': gaps,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'results' / 'bitcoin_calibration.json')
    args = parser.parse_args()
    report = calibration_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
