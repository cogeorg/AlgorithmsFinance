"""Comparative benchmark. Each replay runs in a killable child process."""
import csv
import gzip
import hashlib
import json
import math
import multiprocessing as mp
import os
import platform
import statistics
import time
import tracemalloc
from pathlib import Path

from generate_orders import events as generate_events, write_stream
from order_book_v1 import OrderBook as BookA
from order_book_v2 import OrderBook as BookB

ROOT = Path(__file__).resolve().parents[1]
LIMIT = 120.0  # Wall-clock limit after the worker is ready, identical for all phases.
SCENARIOS = ('buildup', 'crowded', 'mixed', 'sweep', 'cancel_churn')


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def row_writer(path, fields):
    f = path.open('w', newline='', encoding='utf-8')
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    return f, writer


def stats(values):
    ordered = sorted(values)
    return (statistics.median(ordered), ordered[math.ceil(.95*len(ordered))-1],
            ordered[math.ceil(.99*len(ordered))-1])


def worker(conn, progress, path, phase, version):
    try:
        start = time.perf_counter()
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            events = [json.loads(line) for line in f]
        parse_seconds = time.perf_counter() - start
        conn.send(('ready', parse_seconds))
        if conn.recv() != 'go':
            return
        books = [BookA(), BookB()] if phase == 'correctness' else [BookA() if version == 'A' else BookB()]
        book = books[0]
        groups = {}
        peak_orders = peak_levels = rebuilds = 0
        if phase == 'memory':
            tracemalloc.start()
            if version == 'B':
                original = book._rebuild_if_needed
                def counted(side):
                    nonlocal rebuilds
                    levels, heap, _, _ = book._structures(side)
                    if len(heap) > 3 * len(levels):
                        rebuilds += 1
                    original(side)
                book._rebuild_if_needed = counted
        start = time.perf_counter()
        for i, event in enumerate(events):
            # Report completed batches; on timeout this is a lower bound, up to 99 events behind.
            if i % 100 == 0:
                progress.value = i
            if phase == 'latency':
                t = time.perf_counter()
                result = book.process_event(event)
                dt = time.perf_counter() - t
                groups.setdefault(event['type'], []).append(dt)
                if event['type'] == 'LIMIT' and i < len(events)//10:
                    groups.setdefault('early_10_percent', []).append(dt)
                if event['type'] == 'LIMIT' and i >= len(events)-len(events)//10:
                    groups.setdefault('late_10_percent', []).append(dt)
            else:
                result = book.process_event(event)
            if result['status'] == 'rejected':
                raise ValueError(str(result))
            if phase == 'correctness':
                other = books[1].process_event(event)
                if result != other:
                    raise AssertionError(f'event {i+1}: results differ: {result!r} vs {other!r}')
                if len(events) <= 1000 and book.inspect_book() != books[1].inspect_book():
                    raise AssertionError(f'event {i+1}: book differs')
            if phase == 'memory':
                if version == 'A':
                    orders = book.orders
                    count = len(orders)
                    levels = len({(o['side'], o['price_ticks']) for o in orders})
                else:
                    count = len(book.orders_by_id)
                    levels = len(book.bids_by_price) + len(book.asks_by_price)
                peak_orders = max(peak_orders, count)
                peak_levels = max(peak_levels, levels)
        elapsed = time.perf_counter() - start
        progress.value = len(events)
        extra = {}
        if phase == 'correctness':
            if book.inspect_book() != books[1].inspect_book():
                raise AssertionError('final books differ')
        elif phase == 'memory':
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            extra.update(current_bytes=current, peak_bytes=peak, peak_orders=peak_orders,
                         peak_levels=peak_levels, end_orders=count, end_levels=levels)
            if version == 'B':
                heap = len(book.bid_heap)+len(book.ask_heap)
                extra.update(heap_entries=heap, stale_entries=heap-levels, rebuilds=rebuilds)
        elif phase == 'latency':
            extra['latencies'] = {name: (len(v), *stats(v)) for name, v in groups.items()}
        conn.send(('completed', elapsed, extra))
    except BaseException as exc:
        conn.send(('failed', repr(exc)))
    finally:
        conn.close()


def run(path, phase, version):
    parent, child = mp.Pipe()
    progress = mp.Value('i', 0, lock=False)
    process = mp.Process(target=worker, args=(child, progress, path, phase, version))
    process.start()
    child.close()
    # Loading is outside the replay deadline and is measured separately.
    if not parent.poll(60):
        process.terminate(); process.join()
        return 'failed', 0, 0.0, {}, 'input loading exceeded 60 seconds', ''
    message = parent.recv()
    if message[0] != 'ready':
        process.join()
        return 'failed', 0, 0.0, {}, str(message), ''
    parse_seconds = message[1]
    parent.send('go')
    start = time.perf_counter()
    if not parent.poll(LIMIT):
        elapsed = time.perf_counter()-start
        processed = progress.value
        process.terminate(); process.join()
        return 'stopped', processed, elapsed, {}, '120-second wall-clock limit; processed count is a lower bound', parse_seconds
    message = parent.recv()
    elapsed = time.perf_counter()-start
    process.join()
    if message[0] == 'failed':
        return 'failed', progress.value, elapsed, {}, message[1], parse_seconds
    return 'completed', progress.value, message[1], message[2], '', parse_seconds


def main():
    mp.freeze_support()
    out = ROOT / '40_Results' / ('targeted_comparison_' + time.strftime('%Y%m%d_%H%M%S'))
    out.mkdir()
    inputs = ROOT / '10_Data' / 'full_benchmark_inputs'
    inputs.mkdir(exist_ok=True)
    common = ['scenario', 'events', 'seed', 'levels', 'input_sha256']
    f, writer = row_writer(out/'runs.csv', common + ['version','phase','repeat','status','processed',
                           'elapsed_seconds','read_parse_seconds','reason','median_seconds','throughput'])
    lf, lw = row_writer(out/'latency.csv', common + ['version','group','samples','median_us','p95_us','p99_us'])
    mf, mw = row_writer(out/'memory.csv', common + ['version','status','processed','peak_bytes','current_bytes',
                            'peak_orders','peak_levels','end_orders','end_levels','heap_entries','stale_entries','rebuilds','reason'])
    metadata = dict(limit_seconds=LIMIT, input_load_limit_seconds=60, memory_limit='not enforced',
                    python=platform.python_version(), platform=platform.platform(), machine=platform.machine(),
                    processor=platform.processor(), dependencies='Python standard library',
                    code_sha256={name:fingerprint(ROOT/'20_Code'/name) for name in
                                 ('order_book_v1.py','order_book_v2.py','generate_orders.py','targeted_benchmark.py')},
                    input_generator='generate_orders.py', generator_levels=1000,
                    replay_progress='one shared progress write per 100 completed events; timed replay includes this small overhead; timeout count is a lower bound',
                    memory_boundary='input preloaded before tracing; live book, returned output and instrumentation included; not total process memory')
    (out/'environment.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    for scenario in SCENARIOS:
        for count in (10000,):
            for seed in (42,43,44):
                path = (ROOT/'10_Data'/f'{scenario}_10000.jsonl.gz' if count == 10000 and seed == 42
                        else inputs/f'{scenario}_{count}_seed{seed}.jsonl.gz')
                if not path.exists():
                    write_stream(path, generate_events(scenario, count, seed, 1000))
                base = dict(scenario=scenario, events=count, seed=seed, levels=1000, input_sha256=fingerprint(path))
                correctness = run(path, 'correctness', 'both')
                status, done, elapsed, extra, reason, parse = correctness
                writer.writerow(dict(base, version='both', phase='correctness', repeat=0, status=status,
                                     processed=done, elapsed_seconds=elapsed, read_parse_seconds=parse, reason=reason))
                f.flush()
                if status == 'failed':
                    print('Correctness failure:', base, reason, flush=True)
                    continue
                for version in ('A','B'):
                    raw = []
                    for repeat in range(6):
                        status, done, elapsed, extra, reason, parse = run(path, 'replay', version)
                        raw.append((repeat,status,done,elapsed,reason,parse))
                        if status != 'completed':
                            break
                    completed = [x[3] for x in raw if x[0] > 0 and x[1] == 'completed']
                    med = statistics.median(completed) if len(completed) == 5 else ''
                    for rep,status,done,elapsed,reason,parse in raw:
                        writer.writerow(dict(base, version=version, phase='warmup' if rep == 0 else 'replay',
                                             repeat=rep, status=status, processed=done, elapsed_seconds=elapsed,
                                             read_parse_seconds=parse, reason=reason, median_seconds=med,
                                             throughput=count/med if med and rep else ''))
                    for phase in ('latency','memory'):
                        status, done, elapsed, extra, reason, parse = run(path, phase, version)
                        writer.writerow(dict(base, version=version, phase=phase, repeat=0, status=status,
                                             processed=done, elapsed_seconds=elapsed, read_parse_seconds=parse, reason=reason))
                        if phase == 'latency' and status == 'completed':
                            for group,(n,median,p95,p99) in extra['latencies'].items():
                                lw.writerow(dict(base, version=version, group=group, samples=n, median_us=median*1e6,
                                                 p95_us=p95*1e6, p99_us=p99*1e6))
                        if phase == 'memory':
                            mw.writerow(dict(base, version=version, status=status, processed=done, reason=reason,
                                             **{k:v for k,v in extra.items() if k != 'latencies'}))
                    f.flush(); lf.flush(); mf.flush()
                    print(scenario, count, seed, version, 'replay', raw[-1][1], 'correctness', correctness[0], flush=True)
    f.close(); lf.close(); mf.close()
    print('Results:', out, flush=True)


if __name__ == '__main__':
    main()
