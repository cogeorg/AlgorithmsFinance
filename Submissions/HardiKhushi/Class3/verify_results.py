"""Verify saved single-asset runs against raw data, sources and their CSVs."""

import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

from market_data import HERE, SECONDS_PER_YEAR


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_location(name, expected):
    require(Path(name).name == name, 'invalid source filename')
    candidates = [HERE / name, *sorted((HERE / 'versions').rglob(name))]
    for candidate in candidates:
        if candidate.is_file() and digest(candidate) == expected:
            return str(candidate.relative_to(HERE))
    raise ValueError(f'no current or archived source matches {name}')


def verify_run(folder):
    folder = Path(folder).resolve()
    require(folder.is_relative_to(HERE), 'run must be inside this Class3 folder')
    result = json.loads((folder / 'result.json').read_text())
    require(result['status'] == 'complete', 'run is incomplete')
    sources = {name: source_location(name, sha) for name, sha in result['source_sha256'].items()}
    for name, expected in result['result_file_sha256'].items():
        require(Path(name).name == name, 'invalid result filename')
        require(digest(folder / name) == expected, f'output hash mismatch: {name}')
    inputs = json.loads((folder / 'inputs.json').read_text())
    source_location('market_data.py', inputs['source_code_sha256'])
    source = Path(inputs['source'])
    if not source.is_file():
        source = HERE.parents[2] / 'Class3/data/hourly' / source.name
    require(digest(source) == inputs['source_sha256'] == result['data_sha256'], 'data hash mismatch')
    require(result['asset'] == source.stem, 'asset is mislabelled')
    require(result['assets'] == 1, 'single-asset run must have assets=1')
    model = result['model']
    require(model == inputs['model'], 'input/result models disagree')
    n = model['steps']
    with source.open(newline='') as stream:
        raw_rows = list(csv.DictReader(stream))
    require(len(raw_rows) == inputs['source_rows'], 'wrong source row count')
    selected = raw_rows[-n - 1:]
    prices = [float(row['close']) for row in selected]
    times = [datetime.fromisoformat(row['timestamp_utc'].replace('Z', '+00:00')) for row in selected]
    require(len(selected) == n + 1 == inputs['selected_prices'], 'wrong window length')
    require(times[0].isoformat() == inputs['start_utc'] and times[-1].isoformat() == inputs['end_utc'], 'wrong window dates')
    require(prices[0] == model['spot'] == model['strike'], 'wrong initial price/strike')
    require(prices[-1] == inputs['final_close'], 'wrong final close')
    returns = [math.log(b / a) for a, b in zip(prices, prices[1:])]
    mean = math.fsum(returns) / n
    std = math.sqrt(math.fsum((r - mean)**2 for r in returns) / (n - 1))
    close = lambda a, b: math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-14)
    require(close(mean, model['mean_log_return']) and close(std, model['log_return_std']), 'wrong sample return calibration')
    years = (times[-1] - times[0]).total_seconds() / SECONDS_PER_YEAR
    require(close(years, model['years']), 'wrong elapsed years')
    require(close(math.exp(std), model['up']) and close(1 / model['up'], model['down']), 'wrong move factors')
    require(close(math.exp(model['annual_rate'] * years / n), model['gross_rate']), 'wrong interest factor')
    require(0 < model['down'] < model['gross_rate'] < model['up'], 'invalid no-arbitrage factors')
    require(close((model['gross_rate'] - model['down']) / (model['up'] - model['down']), model['probability_up']), 'wrong q')
    hours = [(b - a).total_seconds() / 3600 for a, b in zip(times, times[1:])]
    require(all(h >= 1 and h.is_integer() for h in hours), 'invalid timestamp spacing')
    require(int(sum(hours)) - n == inputs['missing_hours'], 'wrong missing-hours count')
    require(sum(h != 1 for h in hours) == inputs['non_hourly_intervals'], 'wrong gap count')
    require(max(hours) == inputs['maximum_interval_hours'], 'wrong maximum gap')

    with (folder / 'boundary.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == n + 1 == result['boundary_entries'], 'wrong boundary length')
    first = None
    log_up, log_down = math.log(model['up']), math.log(model['down'])
    if 'node_prices' in result['protocol'] and model['down'] == 1 / model['up']:
        log_down = -log_up
    for t, (row, price, timestamp) in enumerate(zip(rows, prices, times)):
        require(int(row['t']) == t and row['timestamp_utc'] == timestamp.isoformat(), f'wrong date/index at {t}')
        require(float(row['observed_close']) == price, f'wrong observed price at {t}')
        threshold = float(row['exercise_boundary']) if row['exercise_boundary'] else None
        crossed = False
        if threshold is not None:
            require(math.isfinite(threshold) and 0 < threshold < model['strike'], f'invalid boundary at {t}')
            j = (math.log(threshold / model['spot']) - t * log_down) / (log_up - log_down)
            require(abs(j - round(j)) < 1e-6 and -1e-6 <= j <= t + 1e-6, f'boundary is not a lattice node at {t}')
            crossed = price <= threshold
        require(int(row['at_or_below_boundary']) == int(crossed), f'wrong crossing flag at {t}')
        if crossed and first is None:
            first = dict(t=t, timestamp_utc=timestamp.isoformat(), observed_price=price,
                         boundary=threshold, payoff=model['strike'] - price, at_expiry=t == n)
    require(first == result['first_exercise'], 'wrong first crossing/payoff')
    timing = json.loads((folder / 'timing.json').read_text())
    memory = json.loads((folder / 'memory.json').read_text())
    require(timing['put_value'] == result['put_value'], 'timing/result price mismatch')
    require(timing['first_exercise'] == first, 'timing crossing mismatch')
    require(timing['seconds'] == result['seconds'] > 0, 'timing mismatch')
    require(not timing['tracing_enabled'] and timing['repeats'] == 1, 'unexpected timing protocol')
    require(memory['peak_traced_bytes'] == result['peak_traced_bytes'] >= memory['current_traced_bytes'] >= 0, 'memory mismatch')
    require(result['peak_traced_KiB'] == result['peak_traced_bytes'] / 1024, 'wrong memory units')
    require(memory['agrees_with_timing_call'] and memory['repeats'] == 1, 'invalid separate memory call')
    require(math.isfinite(result['put_value']) and 0 <= result['put_value'] <= model['strike'], 'invalid positive-rate put value')
    with (folder / 'summary.csv').open(newline='') as stream:
        summary = list(csv.DictReader(stream))
    require(len(summary) == 1, 'wrong number of summary rows')
    row = summary[0]
    require(row['asset'] == result['asset'] and int(row['N']) == n and int(row['assets']) == 1, 'wrong summary identity')
    require(row.get('engine', 'python') == result.get('engine', 'python'), 'wrong engine label')
    require(float(row['put_value']) == result['put_value'] and float(row['seconds']) == result['seconds'], 'summary numeric mismatch')
    require(int(row['peak_traced_bytes']) == result['peak_traced_bytes'], 'summary memory mismatch')
    require(row['exercise_utc'] == (first['timestamp_utc'] if first else 'never'), 'summary exercise mismatch')
    require((float(row['payoff']) == first['payoff']) if first else row['payoff'] == '', 'summary payoff mismatch')
    return {'run': str(folder.relative_to(HERE)), 'status': 'verified', 'N': n,
            'rows_checked': len(rows), 'result_sha256': digest(folder / 'result.json'),
            'verified_sources': sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        runs = [verify_run(path.parent) for path in sorted((HERE / 'results').rglob('result.json'))]
        report = {'runs': runs, 'verifier_sha256': digest(Path(__file__)),
                  'limit': 'checks saved evidence consistency and lattice membership; independent numerical policy checks are separate'}
        rendered = json.dumps(report, indent=2) + '\n'
        if args.output:
            output = args.output.resolve()
            require(output.is_relative_to(HERE), 'output must stay inside Class3')
            with output.open('x') as stream:
                stream.write(rendered)
        print(rendered, end='')
    except (ValueError, OSError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
