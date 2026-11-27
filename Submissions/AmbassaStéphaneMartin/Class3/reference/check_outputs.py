"""Independent reconciliation of this course snapshot and every exported window.

Uses set-difference for missing hours and compares each window directly against
raw CSV records. This intentionally does not call the preparation loader.
"""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output'
UTC = timezone.utc
HOUR = timedelta(hours=1)
START = datetime(2021, 11, 1, tzinfo=UTC)
END = datetime(2026, 10, 31, 23, tzinfo=UTC)


def read_csv(path):
    with path.open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def summary_path(name):
    generated = OUT / name
    return generated if generated.is_file() else ROOT / 'results' / name


def check():
    manifest = json.loads((ROOT / 'data' / 'source_manifest.json').read_text(encoding='utf-8'))
    summaries = {row['asset']: row for row in read_csv(summary_path('asset_summary.csv'))}
    windows = {(row['asset'], row['window']): row for row in read_csv(summary_path('window_summary.csv'))}
    expected = {START + i * HOUR for i in range(int((END-START)/HOUR) + 1)}
    assert len(expected) == 43824
    assert len(summaries) == 40 and len(windows) == 80
    missing_by_asset = {}
    hashes = 0
    exported_rows = 0
    for entry in manifest['files']:
        path = ROOT / entry['file']
        raw_bytes = path.read_bytes()
        assert hashlib.sha256(raw_bytes).hexdigest() == entry['sha256']
        checkout = Path(manifest['source_checkout'])
        if not checkout.is_absolute():
            checkout = ROOT / checkout
        original = checkout / entry['repository_file']
        assert original.read_bytes() == raw_bytes, f'Source/snapshot mismatch: {path}'
        hashes += 1
        raw = read_csv(path)
        timestamps = [datetime.fromisoformat(row['timestamp_utc'].replace('Z', '+00:00')) for row in raw]
        assert all(math.isfinite(float(row['close'])) and float(row['close']) > 0 for row in raw)
        assert timestamps == sorted(timestamps)
        assert len(set(timestamps)) == len(timestamps)
        missing = expected - set(timestamps)
        asset = entry['asset']
        summary = summaries[asset]
        assert int(summary['raw_observations']) == len(raw)
        assert int(summary['usable_observations']) == len(raw)
        assert int(summary['missing_course_hours']) == len(missing)
        assert int(summary['invalid_prices']) == 0
        assert int(summary['duplicate_timestamp_rows']) == 0
        assert int(summary['excluded_rows']) == 0
        assert len(raw) == 43823
        assert missing == {datetime(2023, 3, 24, 13, tzinfo=UTC)}
        missing_by_asset[asset] = [t.isoformat().replace('+00:00', 'Z') for t in sorted(missing)]
        for name in ('one_year', 'full_history'):
            metadata = windows[asset, name]
            expected_rows = raw[-8761:] if name == 'one_year' else raw
            # Course snapshot is already entirely inside the documented five-year cap.
            first_source_line = len(raw) - len(expected_rows) + 2
            n = len(expected_rows) - 1
            assert int(metadata['observations']) == len(expected_rows)
            assert int(metadata['N']) == n
            assert metadata['start_utc'] == expected_rows[0]['timestamp_utc']
            assert metadata['end_utc'] == expected_rows[-1]['timestamp_utc']
            assert metadata['S_0'] == metadata['K'] == metadata['P_0'] == expected_rows[0]['close']
            first = datetime.fromisoformat(expected_rows[0]['timestamp_utc'].replace('Z', '+00:00'))
            last = datetime.fromisoformat(expected_rows[-1]['timestamp_utc'].replace('Z', '+00:00'))
            assert float(metadata['elapsed_hours']) == (last-first)/HOUR
            expected_missing = 0 if name == 'one_year' else 1
            assert int(metadata['missing_hours']) == expected_missing
            assert metadata['ready_for_hourly_pricing'] == ('True' if name == 'one_year' else 'False')
            with (OUT / metadata['file']).open(newline='', encoding='utf-8') as stream:
                reader = csv.DictReader(stream)
                previous = None
                observed = 0
                for index, expected_row in enumerate(expected_rows):
                    row = next(reader)
                    assert row['timestamp_utc'] == expected_row['timestamp_utc']
                    assert row['close'] == expected_row['close']
                    assert row['observation_label'] == f'P_{index}'
                    assert int(row['observation_index']) == index
                    assert int(row['source_row']) == first_source_line + index
                    stamp = datetime.fromisoformat(row['timestamp_utc'].replace('Z', '+00:00'))
                    if previous is None:
                        assert row['elapsed_hours_from_previous'] == ''
                        assert row['missing_hours_before'] == ''
                    else:
                        elapsed = int((stamp - previous) / HOUR)
                        assert int(row['elapsed_hours_from_previous']) == elapsed
                        assert int(row['missing_hours_before']) == elapsed - 1
                    previous = stamp
                    observed += 1
                assert next(reader, None) is None
                assert observed == len(expected_rows)
                exported_rows += observed
    assert len(read_csv(summary_path('exclusions.csv'))) == 0
    gap_rows = read_csv(summary_path('gaps.csv'))
    assert len(gap_rows) == 40
    assert {row['first_missing_utc'] for row in gap_rows} == {'2023-03-24T13:00:00Z'}
    btc_one = windows['BTCUSDT', 'one_year']
    btc_full = windows['BTCUSDT', 'full_history']
    assert btc_one['P_0'] == '109608.01' and btc_one['N'] == '8760'
    assert btc_full['P_0'] == '61560.49' and btc_full['N'] == '43822'
    result = {
        'result': 'passed', 'method': 'independent raw-to-output reconciliation and expected-grid set difference',
        'assets_verified': len(summaries), 'windows_verified': len(windows),
        'exported_rows_verified': exported_rows, 'source_and_snapshot_hashes_verified': hashes,
        'missing_hour_each_asset_utc': '2023-03-24T13:00:00Z',
        'one_year_ready': 40, 'full_history_ready': 0,
    }
    (OUT / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    check()
