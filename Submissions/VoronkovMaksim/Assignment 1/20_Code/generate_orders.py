#!/usr/bin/env python3
"""Independent synthetic teaching data: no exchange records or matching solution.

Example: python 20_Code/generate_orders.py --scenario mixed --events 1000000 --seed 42 --out 10_Data/million.jsonl.gz
Prices are integer cents; quantity is in units of 0.00000001 BTC.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import platform
import random

SCENARIOS = ('buildup', 'crowded', 'mixed', 'sweep', 'cancel_churn')

def events(scenario, count, seed, levels):
    rng = random.Random(seed)
    submitted = []
    bid_units = 0
    last_id = None
    sweep_start = max(1, count * 4 // 5)
    for seq in range(1, count + 1):
        event_id = f'e{seq:09d}'
        row = {'seq': seq, 'event_id': event_id}
        if scenario == 'cancel_churn' and seq % 2 == 0:
            row.update(type='CANCEL', target_order_id=last_id)
        elif scenario == 'sweep' and seq > sweep_start:
            remaining_events = count - sweep_start
            quantity = (bid_units * 2 + 1 if seq == count else
                        max(1, bid_units // max(1, remaining_events)) * rng.randint(1, 3))
            row.update(type='MARKET_SELL', order_id=event_id, qty_units=quantity)
        else:
            u = rng.random()
            if scenario == 'mixed' and submitted and u < .25:
                row.update(type='CANCEL', target_order_id=rng.choice(submitted))
            elif scenario == 'mixed' and u < .40:
                row.update(type='MARKET_SELL', order_id=event_id,
                           qty_units=rng.randint(1, 2000) * 1000000)
            else:
                side = 'BUY' if scenario == 'cancel_churn' else rng.choice(('BUY', 'SELL'))
                depth = rng.randrange(4 if scenario == 'crowded' else levels)
                price = 6000000 - depth if side == 'BUY' else 6000100 + depth
                # Some mixed orders cross the spread, exercising both book sides.
                if scenario == 'mixed' and rng.random() < .15:
                    price = 6000100 + levels if side == 'BUY' else 6000000 - levels
                quantity = rng.randint(1, 100) * 1000000
                row.update(type='LIMIT', order_id=event_id, side=side,
                           price_ticks=price, qty_units=quantity)
                submitted.append(event_id)
                last_id = event_id
                if side == 'BUY':
                    bid_units += quantity
        yield row

def write_stream(path, rows):
    """Stable gzip header allows byte-identical regeneration in one environment."""
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as compressed:
            for row in rows:
                compressed.write((json.dumps(row, separators=(',', ':')) + '\n').encode())

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scenario', choices=SCENARIOS, default='mixed')
    p.add_argument('--events', type=int, default=10000)
    p.add_argument('--levels', type=int, default=1000)
    p.add_argument('--seed', type=int, default=42)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.events < 1 or not 1 <= a.levels < 6000000:
        p.error('events must be positive; levels must be between 1 and 5999999')
    a.out.parent.mkdir(parents=True, exist_ok=True)
    write_stream(a.out, events(a.scenario, a.events, a.seed, a.levels))
    meta = dict(synthetic=True, calibrated_to_exchange_data=False,
                scenario=a.scenario, events=a.events, seed=a.seed, levels=a.levels,
                python=platform.python_version(), generator='random.Random',
                price_tick_usd='0.01', quantity_unit_btc='0.00000001',
                compressed_bytes=a.out.stat().st_size,
                sha256=hashlib.sha256(a.out.read_bytes()).hexdigest())
    a.out.with_suffix(a.out.suffix + '.metadata.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps(meta))

if __name__ == '__main__':
    main()
