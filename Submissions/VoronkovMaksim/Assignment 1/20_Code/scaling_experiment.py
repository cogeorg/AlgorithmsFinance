"""Targeted 100,000-event single attempts with durable progress snapshots."""
import csv
import gzip
import hashlib
import json
import multiprocessing as mp
import platform
import statistics
import time
from pathlib import Path

from order_book_v1 import OrderBook as BookA
from order_book_v2 import OrderBook as BookB

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / '40_Results' / 'full_comparison_20261123_171219'
TARGET = ROOT / '40_Results' / 'targeted_comparison_20261123_175037'
INPUTS = ROOT / '10_Data' / 'full_benchmark_inputs'
SCENARIOS = ('buildup', 'crowded', 'mixed', 'sweep', 'cancel_churn')
SEEDS = (42, 43, 44)
LIMIT = 120.0


def read(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def worker(path, version, connection):
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            events = [json.loads(line) for line in f]
        if len(events) != 100000:
            raise ValueError('input does not contain 100,000 events')
        book = BookA() if version == 'A' else BookB()
        connection.send(('ready',))
        if connection.recv() != 'go':
            return
        start = time.perf_counter()
        for count, event in enumerate(events, 1):
            result = book.process_event(event)
            if result['status'] == 'rejected':
                raise ValueError(f'event {count}: {result}')
            if count % 1000 == 0:
                connection.send(('progress', count, time.perf_counter() - start))
        connection.send(('completed', len(events), time.perf_counter() - start))
    except BaseException as exc:
        connection.send(('failed', repr(exc)))
    finally:
        connection.close()


def run(path, version, progress_writer, progress_file, scenario, seed):
    parent, child = mp.Pipe()
    process = mp.Process(target=worker, args=(path, version, child))
    process.start()
    child.close()
    if not parent.poll(60):
        process.terminate(); process.join()
        return dict(status='failed', elapsed_seconds='', completed_events=0, reason='input load exceeded 60 seconds')
    message = parent.recv()
    if message[0] != 'ready':
        process.join()
        return dict(status='failed', elapsed_seconds='', completed_events=0, reason=str(message))
    parent.send('go')
    start = time.perf_counter()
    last_count, last_elapsed = 0, 0.0
    while True:
        remaining = LIMIT - (time.perf_counter() - start)
        if remaining <= 0:
            if parent.poll():
                message = parent.recv()
            else:
                elapsed = time.perf_counter() - start
                process.terminate(); process.join()
                return dict(status='stopped', elapsed_seconds=elapsed, completed_events=last_count,
                            last_snapshot_seconds=last_elapsed, reason='120-second wall-clock limit; last confirmed snapshot')
        elif parent.poll(min(remaining, .25)):
            message = parent.recv()
        elif not process.is_alive():
            process.join()
            return dict(status='failed', elapsed_seconds=time.perf_counter()-start,
                        completed_events=last_count, reason=f'worker exited {process.exitcode}')
        else:
            continue
        if message[0] == 'progress':
            last_count, last_elapsed = message[1:]
            progress_writer.writerow(dict(version=version, scenario=scenario, seed=seed,
                                          completed_events=last_count, elapsed_seconds=last_elapsed))
            progress_file.flush()
        elif message[0] == 'completed':
            process.join()
            return dict(status='completed', completed_events=message[1], elapsed_seconds=message[2], reason='')
        else:
            process.join()
            return dict(status='failed', completed_events=last_count,
                        elapsed_seconds=time.perf_counter()-start, reason=str(message))


def main():
    mp.freeze_support()
    prev = read(PREVIOUS/'runs.csv')
    target = read(TARGET/'runs.csv')
    prior_env = json.loads((PREVIOUS/'environment.json').read_text())
    target_env = json.loads((TARGET/'environment.json').read_text())
    sources = {x:hash_file(ROOT/'20_Code'/x) for x in ('order_book_v1.py','order_book_v2.py','generate_orders.py','scaling_experiment.py')}
    assert sources['order_book_v1.py'] == target_env['code_sha256']['order_book_v1.py']
    assert sources['order_book_v2.py'] == target_env['code_sha256']['order_book_v2.py']
    assert sources['generate_orders.py'] == prior_env['code_sha256']['generate_orders.py']
    assert prior_env['generator_levels'] == target_env['generator_levels'] == 1000
    out = ROOT/'40_Results'/('scaling_100000_'+time.strftime('%Y%m%d_%H%M%S'))
    out.mkdir()
    meta = dict(timeout_seconds=LIMIT, no_memory_limit=True, python=platform.python_version(),
                platform=platform.platform(), machine=platform.machine(), processor=platform.processor(),
                code_sha256=sources, historical_b_sha256=prior_env['code_sha256']['order_book_v2.py'],
                historical_source=str(PREVIOUS.relative_to(ROOT)), baseline_source=str(TARGET.relative_to(ROOT)),
                inputs='10_Data/full_benchmark_inputs; 100000 events; levels=1000; seeds 42,43,44',
                timing='inputs preloaded; fresh book; perf_counter; no warmup; one attempt; IPC progress after every 1000 completed events included',
                historical_method='five-repeat median; 10-second limit; shared progress write each event; pre-validation-harmonization code',
                correctness='historical 100000-event comparisons: 12 stopped and three cancellation-churn checks completed on earlier code; no new correctness run',
                models='linear=10*matching 10000 median; quadratic=100*matching 10000 median; hypothetical, not a range')
    (out/'environment.json').write_text(json.dumps(meta, indent=2)+'\n',encoding='utf-8')
    fields=['scenario','seed','events','input_sha256','a_status','a_seconds','a_processed','a_fraction',
            'a_last_snapshot_seconds','a_throughput','a_reason','b_status','b_seconds','b_throughput',
            'historical_b_median_seconds','historical_b_sha256','a_10000_median_seconds','linear_estimate_seconds',
            'quadratic_estimate_seconds','speedup_measured','speedup_lower_bound','correctness_status']
    with (out/'attempts.csv').open('w',encoding='utf-8',newline='') as af, (out/'progress.csv').open('w',encoding='utf-8',newline='') as pf:
        writer=csv.DictWriter(af,fieldnames=fields); writer.writeheader()
        pw=csv.DictWriter(pf,fieldnames=['version','scenario','seed','completed_events','elapsed_seconds']); pw.writeheader()
        for scenario in SCENARIOS:
            for seed in SEEDS:
                path=INPUTS/f'{scenario}_100000_seed{seed}.jsonl.gz'
                checksum=hash_file(path)
                history=[r for r in prev if r['scenario']==scenario and r['events']=='100000' and r['seed']==str(seed)
                         and r['version']=='B' and r['phase']=='replay' and r['status']=='completed']
                assert len(history)==5 and all(r['input_sha256']==checksum and r['levels']=='1000' for r in history)
                old_b=statistics.median(float(r['elapsed_seconds']) for r in history)
                assert all(abs(float(r['median_seconds'])-old_b)<1e-10 for r in history)
                base=[r for r in target if r['scenario']==scenario and r['seed']==str(seed) and r['events']=='10000'
                      and r['version']=='A' and r['phase']=='replay' and r['status']=='completed']
                assert len(base)==5
                a10=statistics.median(float(r['elapsed_seconds']) for r in base)
                assert all(abs(float(r['median_seconds'])-a10)<1e-10 for r in base)
                print('Starting',scenario,seed,flush=True)
                b=run(path,'B',pw,pf,scenario,seed)
                a=run(path,'A',pw,pf,scenario,seed)
                asec=a['elapsed_seconds']; bsec=b['elapsed_seconds']
                row=dict(scenario=scenario,seed=seed,events=100000,input_sha256=checksum,
                         a_status=a['status'],a_seconds=asec,a_processed=a['completed_events'],
                         a_fraction=a['completed_events']/100000,a_last_snapshot_seconds=a.get('last_snapshot_seconds',''),
                         a_throughput=100000/asec if a['status']=='completed' else '',a_reason=a['reason'],
                         b_status=b['status'],b_seconds=bsec,b_throughput=100000/bsec if b['status']=='completed' else '',
                         historical_b_median_seconds=old_b,historical_b_sha256=prior_env['code_sha256']['order_book_v2.py'],
                         a_10000_median_seconds=a10,linear_estimate_seconds=10*a10,quadratic_estimate_seconds=100*a10,
                         speedup_measured=asec/bsec if a['status']=='completed' and b['status']=='completed' else '',
                         speedup_lower_bound=a['last_snapshot_seconds']/bsec if a['status']=='stopped' and b['status']=='completed' else '',
                         correctness_status='100000 event comparison previously stopped; not reverified')
                writer.writerow(row); af.flush()
                print('Finished',scenario,seed,'A',a['status'],a['completed_events'],'B',b['status'],flush=True)
    print('Results:',out,flush=True)


if __name__ == '__main__':
    main()
