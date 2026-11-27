"""Audit saved lab outputs without rerunning the expensive trees."""
import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
OUT = HERE / 'results'
DATA = HERE.parents[2] / 'data' / 'hourly'


def read(path):
    with path.open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def main():
    global OUT, DATA
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, default=OUT)
    parser.add_argument('--data', type=Path, default=DATA)
    args = parser.parse_args()
    OUT, DATA = args.results, args.data
    metadata = json.loads((OUT/'metadata.json').read_text())
    assert hashlib.sha256((HERE/'lab.py').read_bytes()).hexdigest() == metadata['source_sha256'], 'Stale source metadata'
    rows = read(OUT/'asset_results.csv')
    runs = read(OUT/'performance.csv')
    assert len(rows) == 82 and len(runs) == 4
    assert len({(r['experiment'],r['asset']) for r in rows}) == 82
    checked_nodes = 0
    for result in rows:
        n = int(result['N'])
        strike = float(result['spot_and_strike'])
        value = float(result['put_value'])
        assert math.isfinite(value) and 0 <= value <= strike
        assert 0 < float(result['q']) < 1
        source_path = DATA/(result['asset']+'.csv')
        assert hashlib.sha256(source_path.read_bytes()).hexdigest() == result['input_sha256'], 'Input changed'
        source = read(source_path)[-n-1:]
        prices = [float(r['close']) for r in source]
        expected_std = statistics.stdev(math.log(b/a) for a,b in zip(prices,prices[1:]))
        assert math.isclose(float(result['hourly_log_return_std']), expected_std, rel_tol=1e-10)
        assert strike == prices[0]
        start = datetime.fromisoformat(source[0]['timestamp_utc'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(source[-1]['timestamp_utc'].replace('Z', '+00:00'))
        years = (end-start).total_seconds()/(365*24*3600)
        assert math.isclose(float(result['R']), math.exp(.04*years/n), rel_tol=1e-14)
        assert math.isclose(float(result['u']), math.exp(expected_std), rel_tol=1e-12)
        assert math.isclose(float(result['d']), 1/float(result['u']), rel_tol=1e-14)
        expected_n = 8760 if result['experiment'].endswith('1year') else len(read(DATA/(result['asset']+'.csv')))-1
        assert n == expected_n
        boundary_file = OUT/(result['experiment']+'_'+result['asset']+'_boundary.csv')
        first = None
        with boundary_file.open(newline='', encoding='utf-8') as handle:
            count = 0
            for t, node in enumerate(csv.DictReader(handle)):
                assert int(node['t']) == t
                assert node['timestamp_utc'] == source[t]['timestamp_utc']
                assert float(node['observed_close']) == prices[t]
                if node['exercise_boundary']:
                    bound = float(node['exercise_boundary'])
                    assert math.isfinite(bound) and 0 <= bound < strike
                    if first is None and prices[t] <= bound:
                        first = t
                if t == n:
                    # ATM reciprocal tree: positive-payoff expiry nodes have
                    # exponent -s (odd N) or -2s (even N); exponent 0 pays zero.
                    expected_terminal = strike * math.exp(-expected_std * (1 if n % 2 else 2))
                    assert node['exercise_boundary'], 'Missing expiry boundary'
                    assert math.isclose(float(node['exercise_boundary']), expected_terminal, rel_tol=1e-9, abs_tol=1e-14), (result['experiment'], result['asset'], 'wrong expiry boundary', node['exercise_boundary'], expected_terminal)
                count += 1
        assert count == n+1
        checked_nodes += count
        if first is None and prices[-1] < strike:
            first = n
        if first is None:
            assert result['exercise_kind'] == 'never' and float(result['payoff']) == 0
        else:
            assert int(result['exercise_t']) == first
            assert result['exercise_utc'] == source[first]['timestamp_utc']
            assert result['exercise_kind'] == ('expiry' if first == n else 'early')
            assert math.isclose(float(result['payoff']),strike-prices[first],abs_tol=1e-10)
    for suffix in ('1year','full'):
        bitcoin = [r for r in rows if r['asset'] == 'BTCUSDT' and r['experiment'].endswith(suffix)]
        assert len(bitcoin) == 2
        assert bitcoin[0]['put_value'] == bitcoin[1]['put_value']
        assert bitcoin[0]['exercise_utc'] == bitcoin[1]['exercise_utc']
    for run in runs:
        selected = [r for r in rows if r['experiment'] == run['experiment']]
        assert len(selected) == int(run['assets'])
        assert min(int(r['N']) for r in selected) == int(run['N_min'])
        assert max(int(r['N']) for r in selected) == int(run['N_max'])
        assert float(run['seconds']) > 0
        assert float(run['peak_sampled_RSS_MiB']) >= float(run['baseline_RSS_MiB']) > 0
    metadata = json.loads((OUT/'metadata.json').read_text())
    assert metadata['validation_cases'] == 162
    print(f'PASS: 82 asset/horizon results, four experiment summaries, and {checked_nodes:,} boundary rows.')
    print('Verified sample volatility independently, valid prices/probabilities, source alignment, first exercise crossing, payoffs, and duplicate Bitcoin reproducibility.')


if __name__ == '__main__':
    main()
