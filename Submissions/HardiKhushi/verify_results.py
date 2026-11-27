"""Verify saved sample counts, summary statistics, source hashes, and links."""

from collections import defaultdict
import csv
import hashlib
from html.parser import HTMLParser
from itertools import product
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def verify(directory=HERE):
    directory = Path(directory)
    results = directory / 'results'
    metadata = json.loads((results / 'environment.json').read_text())
    settings = metadata['settings']

    def read(name):
        with (results / name).open(newline='', encoding='utf-8') as handle:
            return list(csv.DictReader(handle))

    timing, memory = read('timing.csv'), read('memory.csv')
    raw_timing, raw_memory = read('timing_raw.csv'), read('memory_raw.csv')
    time_index = {row['case_id']: row for row in timing}
    mem_index = {row['case_id']: row for row in memory}
    assert len(time_index) == len(timing) == len(memory) == len(mem_index)
    assert set(time_index) == set(mem_index)
    expected_workloads = set(product(settings['sizes'], settings['query_counts'],
                                     settings['scenarios'], settings['duplicate_policies']))
    observed = defaultdict(set)
    for row in timing:
        other = mem_index[row['case_id']]
        for key in ('run_id', 'case_id', 'algorithm', 'version', 'n', 'queries',
                    'scenario', 'duplicate_policy', 'seed', 'hit_rate', 'code_version'):
            assert row[key] == other[key]
        assert row['run_id'] == metadata['run_id']
        assert row['code_version'] == metadata['code_version']
        workload = (int(row['n']), int(row['queries']), row['scenario'], row['duplicate_policy'])
        observed[workload].add((row['algorithm'], row['version']))
    variants = set(product(('linear', 'binary', 'set'), ('original', 'revised')))
    assert set(observed) == expected_workloads
    assert all(value == variants for value in observed.values())
    assert len(timing) == metadata['configuration_count'] == 6 * len(expected_workloads)
    assert metadata['workload_count'] == len(expected_workloads)
    time_groups, memory_groups = defaultdict(list), defaultdict(list)
    for row in raw_timing:
        assert row['run_id'] == metadata['run_id']
        assert row['phase'] in ('prepare', 'query', 'total')
        assert row['case_id'] in time_index
        assert int(row['executions']) > 0
        assert math.isclose(float(row['per_execution_ms']),
                            float(row['elapsed_batch_ms']) / int(row['executions']), rel_tol=1e-12)
        assert math.isfinite(float(row['per_execution_ms'])) and float(row['per_execution_ms']) > 0
        time_groups[(row['case_id'], row['phase'])].append(row)
    for row in raw_memory:
        assert row['run_id'] == metadata['run_id'] and row['case_id'] in mem_index
        assert 0 <= int(row['current_bytes']) <= int(row['peak_bytes'])
        memory_groups[row['case_id']].append(row)
    repeats = settings['repeats']
    for case_id, summary in time_index.items():
        for phase in ('prepare', 'query', 'total'):
            group = time_groups[(case_id, phase)]
            assert sorted(int(row['repeat']) for row in group) == list(range(1, repeats + 1))
            values = [float(row['per_execution_ms']) for row in group]
            for label, function in (('median', statistics.median), ('min', min), ('max', max)):
                assert math.isclose(float(summary[f'{label}_{phase}_ms']), function(values), rel_tol=1e-12)
        group = memory_groups[case_id]
        assert sorted(int(row['repeat']) for row in group) == list(range(1, repeats + 1))
        for metric in ('current', 'peak'):
            values = [int(row[f'{metric}_bytes']) for row in group]
            for label, function in (('median', statistics.median), ('min', min), ('max', max)):
                assert float(mem_index[case_id][f'{label}_{metric}_bytes']) == function(values)
    assert len(raw_timing) == len(timing) * 3 * repeats
    assert len(raw_memory) == len(memory) * repeats
    hashes = metadata['source_sha256']
    for name, digest in hashes.items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == digest, f'Source changed: {name}'
    bundle_hash = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    assert bundle_hash == metadata['code_version']
    archive = directory / 'archive' / 'pre_revision'
    for name, digest in json.loads((archive / 'snapshot_manifest.json').read_text()).items():
        assert hashlib.sha256((archive / name).read_bytes()).hexdigest() == digest, f'Archive changed: {name}'

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.targets = []
        def handle_starttag(self, tag, attrs):
            if tag == 'a':
                self.targets.append(dict(attrs)['href'])
    parser = Links()
    html = (directory / 'dashboard.html').read_text()
    parser.feed(html)
    assert '__DATA_JSON__' not in html
    assert all((directory / target).is_file() for target in parser.targets)
    print(f'PASS: {len(timing)} configurations, {len(raw_timing)} timing samples, {len(raw_memory)} memory samples.')
    print('PASS: raw divisions, medians/min/max, full workload matrix, run IDs, source/archive hashes, dashboard links.')


if __name__ == '__main__':
    verify()
