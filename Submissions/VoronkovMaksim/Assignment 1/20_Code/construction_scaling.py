"""Measure construction of non-crossing books, with separate correctness checks."""
import csv
import hashlib
import json
import multiprocessing as mp
import platform
import random
import statistics
import time
from pathlib import Path

from order_book_v1 import OrderBook as BookA
from order_book_v2 import OrderBook as BookB

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
LIMIT = 30.0
SIZES = (100, 1000, 5000, 10000)


def generate(size, levels):
    prices = [i % levels for i in range(size)]
    random.Random(SEED + size).shuffle(prices)
    quantities = random.Random(SEED + size + 100000)
    return [{'seq': i+1, 'event_id': f'e{i+1}', 'type': 'LIMIT', 'order_id': f'b{i+1}',
             'side': 'BUY', 'price_ticks': 6000000-prices[i],
             'qty_units': quantities.randint(1,100)*1000000} for i in range(size)]


def verify(events, expected_levels):
    books = (BookA(), BookB())
    original = [event.copy() for event in events]
    prices = set()
    for event in events:
        for book in books:
            result = book.process_event(event)
            assert result == {'event_id': event['event_id'], 'order_id': event['order_id'],
                              'status': 'resting', 'unfilled_qty_units': event['qty_units'], 'fills': []}
        prices.add(event['price_ticks'])
    assert events == original
    states = [book.inspect_book() for book in books]
    assert states[0] == states[1]
    expected = [{'order_id': e['order_id'], 'side': e['side'], 'price_ticks': e['price_ticks'],
                 'qty_units': e['qty_units'], 'arrival_seq': e['seq']}
                for e in sorted(original, key=lambda e: (-e['price_ticks'], e['seq']))]
    assert states[0] == expected and len(states[0]) == len(events) and len(prices) == expected_levels
    return len(states[0]), len(prices)


def worker(path, version, connection, progress):
    try:
        events = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        connection.send(('ready',))
        if connection.recv() != 'go':
            return
        start = time.perf_counter()
        book = BookA() if version == 'A' else BookB()
        for i, event in enumerate(events, 1):
            book.process_event(event)
            if i % 100 == 0:
                progress.value = i
        seconds = time.perf_counter()-start
        progress.value = len(events)
        connection.send(('completed', seconds))
    except BaseException as exc:
        connection.send(('failed', repr(exc)))
    finally:
        connection.close()


def timed(path, version):
    parent, child = mp.Pipe()
    progress = mp.Value('i', 0, lock=False)
    proc = mp.Process(target=worker, args=(path, version, child, progress))
    proc.start()
    child.close()
    if not parent.poll(60):
        proc.terminate(); proc.join()
        return 'failed', 0, '', 'input loading exceeded 60 seconds'
    message = parent.recv()
    if message[0] != 'ready':
        proc.join()
        return 'failed', 0, '', str(message)
    parent.send('go')
    start = time.perf_counter()
    if not parent.poll(LIMIT):
        elapsed = time.perf_counter()-start
        count = progress.value
        proc.terminate(); proc.join()
        return 'stopped', count, elapsed, '30-second wall-clock limit; count is last 100-event checkpoint'
    message = parent.recv()
    proc.join()
    if message[0] != 'completed':
        return 'failed', progress.value, time.perf_counter()-start, str(message)
    return 'completed', progress.value, message[1], ''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    mp.freeze_support()
    out = ROOT/'40_Results'/('construction_scaling_'+time.strftime('%Y%m%d_%H%M%S'))
    out.mkdir()
    (out/'inputs').mkdir()
    meta = {'seed': SEED, 'python': platform.python_version(), 'platform': platform.platform(),
            'machine': platform.machine(), 'processor': platform.processor(), 'timeout_seconds': LIMIT,
            'source_sha256': {name:digest(ROOT/'20_Code'/name) for name in
                              ('order_book_v1.py','order_book_v2.py','construction_scaling.py')},
            'input_generation': 'price indices cycle through all levels then shuffle; quantities use a separate seeded RNG',
            'timer_boundary': 'book initialization and event processing included; input loading, validation and verification excluded',
            'overhead': 'one shared progress write per 100 completed events is included in timed replay',
            'counts': 'ID lookup calls inferred from accepted submissions; no actual internal comparisons instrumented; N*(N-1)/2 is theoretical for unique IDs in Version A'}
    (out/'environment.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    fields = ['version','configuration','orders','price_levels','seed','input_sha256','phase','repeat',
              'status','completed_orders','elapsed_seconds','median_seconds','orders_per_second',
              'final_orders','final_levels','reason']
    ops_fields = ['configuration','orders','price_levels','seed','input_sha256','submitted',
                  'new_levels','existing_level_submissions','duplicate_id_lookup_calls',
                  'a_theoretical_prior_order_comparisons','verification']
    with (out/'timings.csv').open('w',encoding='utf-8',newline='') as f, (out/'operation_counts.csv').open('w',encoding='utf-8',newline='') as of:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader()
        ow=csv.DictWriter(of,fieldnames=ops_fields); ow.writeheader()
        for size in SIZES:
            for config,levels in (('concentrated',4),('dispersed',min(size,1000))):
                events=generate(size,levels)
                path=out/'inputs'/f'{config}_{size}_seed{SEED}.jsonl'
                path.write_text(''.join(json.dumps(event,separators=(',',':'))+'\n' for event in events),encoding='utf-8',newline='\n')
                checksum=digest(path)
                final_orders,final_levels=verify(events,levels)
                base=dict(configuration=config,orders=size,price_levels=levels,seed=SEED,input_sha256=checksum)
                ow.writerow(dict(base,submitted=size,new_levels=levels,existing_level_submissions=size-levels,
                                 duplicate_id_lookup_calls=size,a_theoretical_prior_order_comparisons=size*(size-1)//2,
                                 verification='passed'))
                of.flush()
                for version in ('A','B'):
                    attempts=[]
                    for repeat in range(6):
                        status,done,seconds,reason=timed(path,version)
                        attempts.append((repeat,status,done,seconds,reason))
                        if status != 'completed':
                            break
                    repeats=[a[3] for a in attempts if a[0]>0 and a[1]=='completed']
                    median=statistics.median(repeats) if len(repeats)==5 else ''
                    for repeat,status,done,seconds,reason in attempts:
                        writer.writerow(dict(base,version=version,phase='warmup' if repeat==0 else 'construction',
                                             repeat=repeat,status=status,completed_orders=done,elapsed_seconds=seconds,
                                             median_seconds=median if repeat else '',
                                             orders_per_second=size/median if median and repeat else '',
                                             final_orders=final_orders,final_levels=final_levels,reason=reason))
                    f.flush()
                    print(size,config,version,attempts[-1][1], 'median',median,flush=True)
    print('Results:',out,flush=True)


if __name__ == '__main__':
    main()
