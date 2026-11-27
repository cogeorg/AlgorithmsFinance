"""Build the four required performance rows from saved run metadata."""

import argparse
import csv
import json
from pathlib import Path

from market_data import HERE
from verify_assets import verify_batch
from verify_results import digest, verify_run


def build(output):
    output = Path(output).resolve()
    manifest_path = output.with_suffix('.manifest.json')
    if not output.is_relative_to(HERE) or output.exists() or manifest_path.exists():
        raise ValueError('choose a new summary filename inside Class3')
    rows, identities = [], {}
    for horizon, name in (('1y', 'bitcoin_1y_numpy'), ('full', 'bitcoin_full_numpy')):
        folder = HERE / 'results/audit_v1' / name
        verify_run(folder)
        path = folder / 'result.json'
        run = json.loads(path.read_text())
        rows.append(dict(horizon=horizon, asset_group='BTCUSDT', assets=1, engine='numpy',
                         output='price_and_boundary', N_min=run['model']['steps'], N_max=run['model']['steps'],
                         seconds=run['seconds'], peak_traced_bytes=run['peak_traced_bytes'],
                         peak_traced_MiB=run['peak_traced_bytes'] / 1024**2))
        identities[str(path.relative_to(HERE))] = digest(path)
    for horizon in ('1y', 'full'):
        folder = HERE / 'results/all_assets_v1' / horizon
        verify_batch(folder)
        path = folder / 'batch.json'
        run = json.loads(path.read_text())
        rows.append(dict(horizon=horizon, asset_group='all_40_supplied', assets=run['assets'], engine='numpy',
                         output=run['output'], N_min=run['N_min'], N_max=run['N_max'], seconds=run['seconds'],
                         peak_traced_bytes=run['peak_traced_bytes'], peak_traced_MiB=run['peak_traced_bytes'] / 1024**2))
        identities[str(path.relative_to(HERE))] = digest(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with manifest_path.open('x') as stream:
        json.dump({'rows': len(rows), 'run_sha256': identities, 'summary_sha256': digest(output),
                   'builder_sha256': digest(Path(__file__))}, stream, indent=2)
        stream.write('\n')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'results/final_summary.csv')
    args = parser.parse_args()
    try:
        rows = build(args.output)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(rows, indent=2))
