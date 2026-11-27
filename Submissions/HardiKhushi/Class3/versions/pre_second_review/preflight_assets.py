"""Validate all 40 asset files at both horizons without pricing any put."""

import argparse
import hashlib
import json
from math import log
from pathlib import Path

from market_data import HERE, calibrate_window, calibration_report, load_price_window
from tree_model import validate_tree


def preflight():
    files = sorted((HERE.parents[2] / 'Class3/data/hourly').glob('*USDT.csv'))
    if len(files) != 40 or not {'BTCUSDT', 'PAXGUSDT'} <= {p.stem for p in files}:
        raise ValueError('expected the 40 supplied USDT asset files, including BTC and PAXG')
    rows = []
    for file in files:
        for horizon, periods in (('1y', 8760), ('full', None)):
            window = load_price_window(file, periods)
            model = calibrate_window(window)
            tree = validate_tree(model.spot, model.strike, model.up, model.down, model.gross_rate, model.steps)
            data = calibration_report(window, model)
            rows.append({'asset': file.stem, 'horizon': horizon, 'N': model.steps,
                         'prices': len(window.prices), 'data_sha256': window.source_sha256,
                         'missing_hours': data['missing_hours'],
                         'log_return_std': model.log_return_std, 'q': model.probability_up,
                         'min_log_node': min(tree.log_spot, tree.log_spot + tree.steps * tree.log_down),
                         'max_log_node': max(tree.log_spot, tree.log_spot + tree.steps * log(tree.up)),
                         'range_check': 'passed'})
    return {'scope': 'calibration and numerical-range preflight only; no 40-asset pricing or measurement',
            'asset_count': len(files), 'calibrations_checked': len(rows), 'cases': rows,
            'source_sha256': {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest()
                              for name in ('preflight_assets.py', 'market_data.py', 'tree_model.py')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = preflight()
    if args.output:
        output = args.output.resolve()
        if not output.is_relative_to(HERE):
            parser.error('output must stay inside Class3')
        with output.open('x') as stream:
            json.dump(report, stream, indent=2)
            stream.write('\n')
    print(f"Checked {report['calibrations_checked']} calibrations across {report['asset_count']} assets; all ranges passed. No batch pricing performed.")
