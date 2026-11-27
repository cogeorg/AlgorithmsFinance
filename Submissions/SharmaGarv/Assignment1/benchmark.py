"""Bounded reproducible experiments. Run from this directory: python benchmark.py.

Input gzip generation and parsing are outside engine timers. No third party
packages. Raw records are flushed individually so interrupted runs are visible.
"""
import argparse
import cProfile
import gc
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import pstats
import statistics
import subprocess
import sys
import time
import tracemalloc
import unittest

from generate_orders import events, write_stream
from orderbook import BaselineBook, RevisedBook
from replay import load

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'
ENGINES = {'A': BaselineBook, 'B': RevisedBook}
SCENARIOS = ['buildup', 'crowded', 'mixed', 'sweep', 'cancel_churn']


class LimitReached(Exception):
    pass


def source_fingerprint():
    digest = hashlib.sha256()
    paths = list(ROOT.glob('*.py')) + list((ROOT / 'tests').glob('*.py'))
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode() + b'\0' + path.read_bytes())
    return digest.hexdigest()


def percentile(values, p):
    """Nearest rank: sorted[max(1, ceil(p*n))-1]."""
    return sorted(values)[max(1, math.ceil(p * len(values))) - 1] if values else None


def replay(book, rows, seconds, latency=False, memory=False):
    start = time.perf_counter()
    deadline = start + seconds
    active_peak = price_peak = fill_count = 0
    latencies = []
    samples = []
    result = None
    checkpoints = {0, len(rows)//4, len(rows)//2, 3*len(rows)//4, len(rows)-1}
    try:
        for i, event in enumerate(rows):
            if i % 256 == 0 and time.perf_counter() > deadline:
                raise LimitReached()
            if latency:
                stamp = time.perf_counter()
            result = book.process(event)
            if latency:
                latencies.append(time.perf_counter() - stamp)
                stats = book.stats()
                active_peak = max(active_peak, stats['active_orders'])
                price_peak = max(price_peak, stats['price_levels'])
                fill_count += len(result.get('fills', []))
            if (latency or memory) and i in checkpoints:
                sample = dict(event=i+1, **book.stats())
                if memory:
                    sample['current_bytes'], sample['peak_bytes'] = tracemalloc.get_traced_memory()
                samples.append(sample)
    except LimitReached:
        return dict(status='stopped', completed_events=i, elapsed_seconds=time.perf_counter()-start,
                    limit_seconds=seconds, samples=samples)
    elapsed = time.perf_counter() - start
    value = dict(status='ok', completed_events=len(rows), elapsed_seconds=elapsed,
                 final_active_orders=len(book.active), final_price_levels=sum(map(len, book.prices.values())))
    if latency:
        value.update(active_order_peak=active_peak, price_level_peak=price_peak, fill_count=fill_count,
                     latency_median_seconds=statistics.median(latencies),
                     latency_p95_seconds=percentile(latencies, .95),
                     latency_p99_seconds=percentile(latencies, .99),
                     latency_begin_median_seconds=statistics.median(latencies[:min(1000,len(latencies))]),
                     latency_end_median_seconds=statistics.median(latencies[-min(1000,len(latencies)):]),
                     latency_histogram=histogram(latencies), samples=samples)
    if memory:
        value.update(samples=samples)
    return value


def histogram(values):
    edges = [1e-6, 2e-6, 5e-6, 1e-5, 2e-5, 5e-5, 1e-4, 2e-4, 5e-4, 1e-3, 1e-2]
    counts = [0] * (len(edges)+1)
    import bisect
    for v in values:
        counts[bisect.bisect_left(edges, v)] += 1
    return dict(upper_seconds=edges + [None], counts=counts)


def append(record):
    with (RESULTS / 'raw.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, allow_nan=False) + '\n')


def run_stream(version, scenario, seed, size, path, limit):
    engine = ENGINES[version]
    base = dict(version=version, scenario=scenario, seed=seed, event_count=size,
                levels=1000, source_sha256=source_fingerprint())
    rows = None
    for repeat in range(5):
        start = time.perf_counter()
        parsed = load(path)
        elapsed = time.perf_counter()-start
        append(dict(base, phase='parse', repeat=repeat, status='ok', elapsed_seconds=elapsed))
        if rows is None:
            rows = parsed
        else:
            del parsed
    warmup = engine()
    for event in rows[:min(500, size)]:
        warmup.process(event)
    del warmup
    for repeat in range(5):
        gc.collect()
        book = engine()
        result = replay(book, rows, limit)
        result['throughput_events_per_second'] = size/result['elapsed_seconds'] if result['status']=='ok' else None
        append(dict(base, phase='replay', repeat=repeat, **result))
        del book
    gc.collect()
    book = engine()
    append(dict(base, phase='latency', repeat=0, **replay(book, rows, limit, latency=True)))
    del book
    gc.collect()
    tracemalloc.start()
    book = engine()
    result = replay(book, rows, limit, memory=True)
    result['traced_current_bytes'], result['traced_peak_bytes'] = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    append(dict(base, phase='memory', repeat=0, **result))


def fixed_rows(n, levels, seed):
    import random
    rng = random.Random(seed)
    return [dict(seq=i+1, event_id=f'e{i}', type='LIMIT', order_id=f'b{i}', side='BUY',
                 price_ticks=6000000-rng.randrange(levels), qty_units=100000000)
            for i in range(n)]


def liquidation(version, n, levels, seed, limit):
    rows = fixed_rows(n, levels, seed)
    engine = ENGINES[version]
    total = n * 100000000
    # Each fraction/repeat receives a freshly constructed book.
    for fraction, qty in [('10%', max(1, total//10)), ('100%', total), ('200%', 2*total)]:
        for repeat in range(5):
            gc.collect()
            book = engine()
            construction = replay(book, rows, limit)
            base = dict(version=version, scenario='liquidation', seed=seed, event_count=n,
                        levels=levels, fraction=fraction, requested_qty_units=qty,
                        repeat=repeat, source_sha256=source_fingerprint())
            append(dict(base, phase='construction', **construction))
            if construction['status'] != 'ok':
                append(dict(base, phase='sale', status='stopped', reason='construction limit',
                            limit_seconds=limit))
                continue
            event = dict(seq=n+1, event_id='sale', type='MARKET_SELL', order_id='sale', qty_units=qty)
            start = time.perf_counter()
            # The outer worker supplies a hard process deadline; individual sales
            # cannot be interrupted inside matching without changing engine code.
            result = book.FillMarketSell(event)
            elapsed = time.perf_counter()-start
            fills = result['fills']
            valid = (sum(f['qty_units'] for f in fills) == min(qty, total)
                     and result['unfilled_qty_units'] == max(0, qty-total)
                     and [(f['price_ticks'], rows[int(f['maker_id'][1:])]['seq']) for f in fills]
                     == sorted([(f['price_ticks'], rows[int(f['maker_id'][1:])]['seq']) for f in fills],
                               key=lambda x: (-x[0], x[1])))
            append(dict(base, phase='sale', status='ok' if elapsed <= limit else 'over_limit',
                        elapsed_seconds=elapsed, limit_seconds=limit, correctness=valid,
                        fill_count=len(fills), maker_orders_touched=len(fills),
                        price_levels_visited=len({f['price_ticks'] for f in fills}),
                        unfilled_qty_units=result['unfilled_qty_units'],
                        remaining_bid_qty_units=book.bid_quantity))


def diagnostics():
    for scenario in SCENARIOS:
        rows = list(events(scenario, 1000, 42, 1000))
        for version, engine in ENGINES.items():
            b = engine(counters=True)
            for e in rows:
                b.process(e)
            append(dict(version=version, scenario=scenario, seed=42, event_count=1000,
                        phase='operations', status='ok', counts=b.counters, **b.stats()))
    for version, engine in ENGINES.items():
        for levels in [4, 1000]:
            book = engine(counters=True)
            for event in fixed_rows(1000, levels, 42):
                book.process(event)
            book.FillMarketSell(dict(seq=1001, event_id='sale', type='MARKET_SELL',
                                     order_id='sale', qty_units=10**15))
            append(dict(version=version, scenario='liquidation', seed=42, event_count=1000,
                        levels=levels, phase='operations', status='ok', counts=book.counters))
    profile = cProfile.Profile()
    for version, engine in ENGINES.items():
        rows = fixed_rows(3000, 1000, 42)
        book = engine()
        for event in rows:
            book.process(event)
        profile = cProfile.Profile()
        profile.enable()
        book.FillMarketSell(dict(seq=3001, event_id='sale', type='MARKET_SELL', order_id='sale', qty_units=10**15))
        profile.disable()
        stream = io.StringIO()
        pstats.Stats(profile, stream=stream).sort_stats('cumulative').print_stats(25)
        (RESULTS / f'profile_{version}.txt').write_text(stream.getvalue(), encoding='utf-8')


def run_tests():
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    (RESULTS / 'tests_final.txt').write_text(stream.getvalue(), encoding='utf-8')
    (RESULTS / 'correctness.json').write_text(json.dumps(dict(
        tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), success=result.wasSuccessful(), source_sha256=source_fingerprint(),
        command='python -B -m unittest discover -s tests -v'), indent=2), encoding='utf-8')
    if not result.wasSuccessful():
        raise SystemExit(stream.getvalue())


def summarize():
    raw = [json.loads(s) for s in (RESULTS / 'raw.jsonl').read_text(encoding='utf-8').splitlines()]
    groups = {}
    for r in raw:
        if r.get('phase') in ['replay','parse','construction','sale']:
            key = tuple(r.get(k) for k in ['version','scenario','seed','event_count','levels','phase','fraction'])
            groups.setdefault(key, []).append(r)
    summary = []
    for key, records in groups.items():
        good = [r['elapsed_seconds'] for r in records if r['status']=='ok']
        summary.append(dict(zip(['version','scenario','seed','event_count','levels','phase','fraction'],key),
                            successful_repeats=len(good), attempted_repeats=len(records),
                            status='ok' if len(good)==5 else 'incomplete',
                            median_seconds=statistics.median(good) if len(good)==5 else None))
    (RESULTS / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')


def parent(args):
    RESULTS.mkdir(exist_ok=True)
    if (RESULTS / 'raw.jsonl').exists():
        raise SystemExit('results/raw.jsonl already exists; use a fresh project copy for another full run')
    run_tests()
    metadata = dict(recorded_at_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                    python=sys.version, executable=sys.executable, machine=platform.machine(),
                    processor=platform.processor(), operating_system=platform.platform(),
                    cpu_count=os.cpu_count(), dependencies='Python standard library only',
                    source_sha256=source_fingerprint(), seeds=[42,43,44],
                    scenarios=SCENARIOS, event_counts=[1000,10000,100000], levels=1000,
                    repeats=5, warmup_events=500, phase_limit_seconds=args.limit,
                    hard_worker_limit_seconds=90, million_worker_limit_seconds=45,
                    million_attempt=dict(scenario='buildup', seed=42, event_count=1000000),
                    gc='enabled; collect before each replay; no parallel experiments',
                    percentile='nearest rank ceil(p*n), p=.95/.99',
                    memory_boundary='tracemalloc begins after input preloading, includes book, transient fills, checkpoint samples and runner allocations; excludes preloaded input and native/process RSS; no saved trade history',
                    timing_boundary='perf_counter replay includes validation, dispatch, matching, updates and result construction; input parse and generation excluded; deadline checked every 256 events',
                    clock=time.get_clock_info('perf_counter').__dict__, datasets=[])
    for scenario in SCENARIOS:
        for seed in [42,43,44]:
            for size in [1000,10000,100000]:
                path = ROOT / 'data' / f'{scenario}_{size}_seed{seed}.jsonl.gz'
                stamp = time.perf_counter()
                write_stream(path, events(scenario,size,seed,1000))
                metadata['datasets'].append(dict(scenario=scenario,seed=seed,event_count=size,
                    levels=1000,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    generation_seconds=time.perf_counter()-stamp,
                    command=f'python generate_orders.py --scenario {scenario} --events {size} --levels 1000 --seed {seed} --out data/{path.name}'))
                for version in ENGINES:
                    print(f'{version} {scenario} seed={seed} M={size}',flush=True)
                    launch(['--worker','stream','--version',version,'--scenario',scenario,
                            '--seed',str(seed),'--size',str(size),'--path',str(path),'--limit',str(args.limit)],90,
                           dict(version=version,scenario=scenario,seed=seed,event_count=size))
                # Generated data are reproducible; only starter samples are delivered.
                path.unlink()
    for version in ENGINES:
        for n in [1000,10000]:
            for levels in [4,1000]:
                for seed in [42,43,44]:
                    print(f'{version} liquidation B={n} P-range={levels} seed={seed}',flush=True)
                    launch(['--worker','sale','--version',version,'--size',str(n),
                            '--levels',str(levels),'--seed',str(seed),'--limit',str(args.limit)],90,
                           dict(version=version,scenario='liquidation',seed=seed,event_count=n,levels=levels))
    path = ROOT / 'data' / 'buildup_1000000_seed42.jsonl.gz'
    print('Generating million-event attempt',flush=True)
    write_stream(path, events('buildup',1000000,42,1000))
    metadata['datasets'].append(dict(scenario='buildup',seed=42,event_count=1000000,levels=1000,
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        command=f'python generate_orders.py --scenario buildup --events 1000000 --levels 1000 --seed 42 --out data/{path.name}'))
    for version in ENGINES:
        print(f'{version} million-event attempt',flush=True)
        launch(['--worker','stream','--version',version,'--scenario','buildup','--seed','42',
                '--size','1000000','--path',str(path),'--limit',str(args.limit)],45,
               dict(version=version,scenario='buildup',seed=42,event_count=1000000))
    path.unlink()
    (RESULTS / 'environment.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    diagnostics()
    summarize()
    print('Benchmark complete',flush=True)


def launch(arguments, timeout, identity):
    try:
        result = subprocess.run([sys.executable,'-B',str(ROOT/'benchmark.py')] + arguments,
                                timeout=timeout,capture_output=True,text=True,cwd=ROOT)
        if result.returncode:
            append(dict(identity,phase='worker',status='error',stderr=result.stderr,returncode=result.returncode))
    except subprocess.TimeoutExpired:
        append(dict(identity,phase='worker',status='stopped',limit_seconds=timeout,
                    reason='hard worker deadline; unrecorded phases were not completed'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker',choices=['stream','sale'])
    parser.add_argument('--version',choices=['A','B'])
    parser.add_argument('--scenario',default='buildup')
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--size',type=int,default=1000)
    parser.add_argument('--levels',type=int,default=1000)
    parser.add_argument('--path')
    parser.add_argument('--limit',type=float,default=3)
    args=parser.parse_args()
    if args.worker=='stream':
        run_stream(args.version,args.scenario,args.seed,args.size,args.path,args.limit)
    elif args.worker=='sale':
        liquidation(args.version,args.size,args.levels,args.seed,args.limit)
    else:
        parent(args)


if __name__=='__main__':
    main()
