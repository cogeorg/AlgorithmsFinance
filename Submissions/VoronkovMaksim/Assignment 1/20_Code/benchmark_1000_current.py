"""Small current-version comparison using the existing benchmark worker."""
import csv
import hashlib
import json
import multiprocessing as mp
import platform
import statistics
import time
from pathlib import Path

from targeted_benchmark import run

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ('buildup', 'crowded', 'mixed', 'sweep', 'cancel_churn')
SEEDS = (42, 43, 44)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    mp.freeze_support()
    out = ROOT / '40_Results' / ('current_1000_' + time.strftime('%Y%m%d_%H%M%S'))
    out.mkdir()
    paths = ('order_book_v1.py', 'order_book_v2.py', 'targeted_benchmark.py',
             'generate_orders.py', 'benchmark_1000_current.py')
    meta = {'python': platform.python_version(), 'platform': platform.platform(),
            'machine': platform.machine(), 'processor': platform.processor(),
            'code_sha256': {p: sha(ROOT / '20_Code' / p) for p in paths},
            'events': 1000, 'seeds': list(SEEDS), 'levels': 1000,
            'timeout_seconds': 120, 'memory_limit': 'not enforced',
            'method': 'Existing targeted_benchmark worker; one warm-up, five timed repeats, '
                      'fresh books, 100-event progress updates included, parsing separate; '
                      'correctness compared after every event in a separate run.'}
    (out / 'environment.json').write_text(json.dumps(meta, indent=2)+'\n', encoding='utf-8')
    fields = ['version','scenario','events','seed','levels','input_sha256','phase','repeat',
              'status','processed','elapsed_seconds','read_parse_seconds','reason','median_seconds','throughput']
    with (out / 'runs.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for scenario in SCENARIOS:
            for seed in SEEDS:
                path = ROOT / '10_Data' / 'full_benchmark_inputs' / f'{scenario}_1000_seed{seed}.jsonl.gz'
                base = dict(scenario=scenario, events=1000, seed=seed, levels=1000, input_sha256=sha(path))
                status, done, seconds, extra, reason, parse = run(path, 'correctness', 'both')
                writer.writerow(dict(base, version='both', phase='correctness', repeat=0, status=status,
                                     processed=done, elapsed_seconds=seconds, read_parse_seconds=parse, reason=reason))
                f.flush()
                if status != 'completed':
                    raise RuntimeError(f'Comparison incomplete: {scenario} seed {seed}: {status} {reason}')
                for version in ('A', 'B'):
                    attempts = []
                    for repeat in range(6):
                        status, done, seconds, extra, reason, parse = run(path, 'replay', version)
                        attempts.append((repeat,status,done,seconds,reason,parse))
                        if status != 'completed':
                            break
                    completed = [r[3] for r in attempts if r[0] and r[1] == 'completed']
                    median = statistics.median(completed) if len(completed)==5 else ''
                    for repeat,status,done,seconds,reason,parse in attempts:
                        writer.writerow(dict(base,version=version,phase='warmup' if repeat==0 else 'replay',
                                             repeat=repeat,status=status,processed=done,elapsed_seconds=seconds,
                                             read_parse_seconds=parse,reason=reason,median_seconds=median,
                                             throughput=1000/median if median and repeat else ''))
                    f.flush()
                    print(scenario,seed,version,attempts[-1][1],flush=True)
    print('Results:',out,flush=True)


if __name__ == '__main__':
    main()
