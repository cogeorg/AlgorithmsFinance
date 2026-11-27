"""Indicative Version A measurements. Run from any directory with Python."""
import csv
import gzip
import hashlib
import json
import math
import platform
import statistics
import time
import tracemalloc
from pathlib import Path

from order_book_v1 import OrderBook

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ('buildup', 'crowded', 'mixed', 'sweep', 'cancel_churn')
OUT = ROOT / '40_Results' / ('diagnostic_v1_' + time.strftime('%Y%m%d_%H%M%S'))
OUT.mkdir()


def save(name, rows):
    with (OUT / name).open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def percentile(values, p):
    return sorted(values)[math.ceil(p * len(values)) - 1]


def replay(events):
    book = OrderBook()
    start = time.perf_counter()
    for event in events:
        result = book.process_event(event)
        if result['status'] == 'rejected':
            raise ValueError(result)
    return book, time.perf_counter() - start


timings, latency, memory = [], [], []
for scenario in SCENARIOS:
    for count in (1000, 10000):
        suffix = 'diagnostic_1000_seed42' if count == 1000 else '10000'
        path = ROOT / '10_Data' / f'{scenario}_{suffix}.jsonl.gz'
        start = time.perf_counter()
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            events = [json.loads(line) for line in f]
        read_time = time.perf_counter() - start
        assert len(events) == count
        replay(events)  # warm-up
        durations, states = [], []
        for repeat in range(1, 6):
            book, elapsed = replay(events)
            durations.append(elapsed)
            states.append(book.inspect_book())
            assert elapsed >= 0
        assert all(state == states[0] for state in states)
        median = statistics.median(durations)
        for repeat, elapsed in enumerate(durations, 1):
            timings.append(dict(version='Version A', scenario=scenario, events=count, seed=42,
                                repeat=repeat, elapsed_seconds=elapsed, median_seconds=median,
                                throughput_events_per_second=count / median, read_parse_seconds=read_time))
        groups = {}
        book = OrderBook()
        for i, event in enumerate(events):
            start = time.perf_counter()
            result = book.process_event(event)
            elapsed = time.perf_counter() - start
            assert result['status'] != 'rejected'
            groups.setdefault(event['type'], []).append(elapsed)
            if scenario == 'buildup' and (i < count // 10 or i >= count - count // 10):
                groups.setdefault('early_10_percent' if i < count // 10 else 'late_10_percent', []).append(elapsed)
        for group, values in groups.items():
            latency.append(dict(version='Version A', scenario=scenario, events=count, seed=42,
                                group=group, samples=len(values), median_us=statistics.median(values)*1e6,
                                p95_us=percentile(values, .95)*1e6, p99_us=percentile(values, .99)*1e6))
        tracemalloc.start()
        book = OrderBook()
        peak_orders = peak_levels = 0
        for event in events:
            result = book.process_event(event)
            assert result['status'] != 'rejected'
            peak_orders = max(peak_orders, len(book.orders))
            peak_levels = max(peak_levels, len({(o['side'], o['price_ticks']) for o in book.orders}))
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert book.inspect_book() == states[0]
        memory.append(dict(version='Version A', scenario=scenario, events=count, seed=42,
                           peak_traced_bytes=peak, end_traced_bytes=current,
                           end_active_orders=len(book.orders), peak_active_orders=peak_orders,
                           peak_price_levels=peak_levels))
        print(scenario, count, 'median', round(median, 4), flush=True)

save('timing.csv', timings)
save('latency.csv', latency)
save('memory.csv', memory)

# Equal-size books isolate queue concentration; build and reset outside sell timing.
diagnostics = []
for levels in (4, 1000):
    for fraction in (10, 100, 200):
        for repeat in range(1, 6):
            book = OrderBook()
            start = time.perf_counter()
            for i in range(1000):
                book.process_event(dict(seq=i+1, event_id=f'e{i}', type='LIMIT', order_id=f'b{i}',
                                        side='BUY', price_ticks=6000000-(i % levels), qty_units=10))
            construction = time.perf_counter() - start
            event = dict(seq=1001, event_id='sell', type='MARKET_SELL', order_id='sell',
                         qty_units=10000*fraction//100)
            start = time.perf_counter()
            result = book.process_event(event)
            elapsed = time.perf_counter() - start
            fills = result['fills']
            diagnostics.append(dict(version='Version A', test='sell', initial_orders=1000,
                                    price_levels=levels, percent=fraction, repeat=repeat,
                                    construction_seconds=construction, elapsed_seconds=elapsed,
                                    fills=len(fills), visited_prices=len({f['price_ticks'] for f in fills}),
                                    unfilled_qty=result['unfilled_qty_units']))
for size in (10, 1000):
    for repeat in range(1, 6):
        book = OrderBook()
        for i in range(size):
            book.process_event(dict(seq=i+1, event_id=f'e{i}', type='LIMIT', order_id=f'b{i}',
                                    side='BUY', price_ticks=100, qty_units=1))
        event = dict(seq=size+1, event_id='cancel', type='CANCEL', target_order_id=f'b{size-1}')
        start = time.perf_counter()
        result = book.process_event(event)
        elapsed = time.perf_counter()-start
        assert result['status'] == 'cancelled'
        diagnostics.append(dict(version='Version A', test='cancel_last', initial_orders=size,
                                price_levels=1, percent='', repeat=repeat, construction_seconds='',
                                elapsed_seconds=elapsed, fills=0, visited_prices=0, unfilled_qty=0))
save('diagnostics.csv', diagnostics)
metadata = dict(python=platform.python_version(), platform=platform.platform(), machine=platform.machine(),
                processor=platform.processor(), seed=42, levels=1000, timing='perf_counter',
                v1_sha256=hashlib.sha256((ROOT/'20_Code'/'order_book_v1.py').read_bytes()).hexdigest(),
                input_sha256={f'{s}_{n}': hashlib.sha256((ROOT/'10_Data'/f"{s}_{'diagnostic_1000_seed42' if n == 1000 else '10000'}.jsonl.gz").read_bytes()).hexdigest() for s in SCENARIOS for n in (1000,10000)})
(OUT/'environment.json').write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
print('Results:', OUT, flush=True)
