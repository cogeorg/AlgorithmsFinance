"""Fresh-process measurements for the four requested lab workloads."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import numpy as np
from american_put import PriceAmericanPut, calibrate, price_calibrated, first_crossing

ROOT=Path(__file__).resolve().parent

def iso(epoch):
    return datetime.fromtimestamp(int(epoch),timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def load(path,horizon):
    with path.open(newline='') as stream:
        rows=list(csv.DictReader(stream))
    times=np.array([int(datetime.fromisoformat(r['timestamp_utc'].replace('Z','+00:00')).timestamp()) for r in rows],dtype=np.int64)
    closes=np.array([float(r['close']) for r in rows])
    if horizon in ('year','8760'):
        if len(closes)<8761: raise ValueError('Insufficient observations for 8760 steps')
        times,closes=times[-8761:],closes[-8761:]
    return times,closes

def write_csv(path,rows):
    with path.open('w',newline='') as out:
        writer=csv.DictWriter(out,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def worker(scope,horizon,workers):
    out=ROOT/'results'
    out.mkdir(exist_ok=True)
    run=f'{scope}_{horizon}'
    files=sorted((ROOT/'work/data/hourly').glob('*.csv'))
    if scope == 'btc': files=[p for p in files if p.stem=='BTCUSDT']
    expected=1 if scope=='btc' else 40
    if len(files)!=expected: raise RuntimeError('Run fetch_data.py first')
    # Warm compilation explicitly excluded from timed pricing. Peak RSS still
    # includes imports, compilation and data, since it is process high-water RSS.
    warm_start=time.perf_counter()
    PriceAmericanPut(100,100,1.2,.8,1.05,2)
    warm_seconds=time.perf_counter()-warm_start
    begin=time.perf_counter()
    inputs=[]
    for path in files:
        times,closes=load(path,horizon)
        inputs.append((path.stem,times,closes,calibrate(times,closes)))
    load_seconds=time.perf_counter()-begin
    def calculate(item):
        symbol,times,closes,p=item
        start=time.perf_counter()
        price,boundary=price_calibrated(p)
        seconds=time.perf_counter()-start
        hit=first_crossing(closes,boundary,p['K'])
        row=dict(symbol=symbol,price=price,**p,start=iso(times[0]),end=iso(times[-1]),
                 pricing_seconds=seconds,exercise_index=hit['index'] if hit else '',
                 exercise_timestamp=iso(times[hit['index']]) if hit else 'never',
                 exercise_spot=hit['spot'] if hit else '',
                 exercise_boundary=hit['boundary'] if hit else '',
                 exercise_payoff=hit['payoff'] if hit else '',
                 terminal_payoff=max(0.,p['K']-float(closes[-1])))
        return row,boundary
    start=time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        computed=list(pool.map(calculate,inputs))
    elapsed=time.perf_counter()-start
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes=int(peak if sys.platform=='darwin' else peak*1024)
    rows=[r for r,b in computed]
    write_csv(out/f'{run}_prices.csv',rows)
    # Persist every requested boundary, aligned to all original observations.
    for (symbol,times,closes,p),(row,boundary) in zip(inputs,computed):
        with gzip.open(out/f'{run}_{symbol}_boundary.csv.gz','wt',newline='') as stream:
            writer=csv.writer(stream)
            writer.writerow(['index','timestamp_utc','observed_close','exercise_boundary'])
            for i in range(len(times)):
                writer.writerow([i,iso(times[i]),closes[i],boundary[i] if np.isfinite(boundary[i]) else ''])
    summary=dict(run=run,assets=len(rows),N_min=min(r['N'] for r in rows),N_max=max(r['N'] for r in rows),
                 seconds=elapsed,peak_memory_bytes=peak_bytes,peak_memory_MiB=peak_bytes/1024**2,
                 load_calibrate_seconds=load_seconds,jit_warmup_seconds=warm_seconds,
                 workers=workers,python=sys.version.split()[0],platform=platform.platform(),
                 memory_definition='Fresh-process lifetime peak RSS, including imports/JIT/data; measured before output serialization',
                 timing_definition='Pricing and crossing scan wall time; excludes JIT, loading/calibration and result serialization',
                 full_tree_bytes_per_largest_asset=8*((max(r['N'] for r in rows)+1)*(max(r['N'] for r in rows)+2)//2),
                 rolling_value_and_boundary_bytes_per_largest_asset=16*(max(r['N'] for r in rows)+1))
    (out/f'{run}_measurement.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary),flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scope',choices=['btc','all'])
    parser.add_argument('--horizon',choices=['year','full','8760'])
    parser.add_argument('--workers',type=int,default=4)
    args=parser.parse_args()
    if args.workers<1: parser.error('workers must be positive')
    if args.scope:
        if not args.horizon: parser.error('--horizon required')
        worker(args.scope,args.horizon,min(args.workers,1 if args.scope=='btc' else 40))
        return
    for scope,horizon in [('btc','year'),('btc','full'),('all','year'),('all','full')]:
        subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--scope',scope,'--horizon',horizon,'--workers',str(args.workers)],check=True,cwd=ROOT)
    measurements=[json.loads(p.read_text()) for p in sorted((ROOT/'results').glob('*_measurement.json'))]
    write_csv(ROOT/'results/runs.csv',[{k:r[k] for k in ('run','assets','N_min','N_max','seconds','peak_memory_MiB','workers')} for r in measurements])

if __name__=='__main__': main()
