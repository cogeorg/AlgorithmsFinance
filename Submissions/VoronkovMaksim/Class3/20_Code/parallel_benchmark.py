"""Sequential and process-pool comparison of one-year crypto option pricing."""
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time

import numpy as np
from calibrate import read_prices
from price_american_put_numpy import PriceAmericanPutB


def worker(path):
    path = Path(path)
    try:
        rows = read_prices(path)[-8761:]
        n = len(rows)-1
        if n < 2:
            raise ValueError('Insufficient observations')
        s = statistics.stdev(math.log(b[1]/a[1]) for a,b in zip(rows,rows[1:]))
        u = math.exp(s); d = 1/u
        years = (rows[-1][0]-rows[0][0]).total_seconds()/(365.25*86400)
        R = math.exp(.04*years/n)
        if not 0 < d < R < u:
            raise ValueError('No-arbitrage condition failed')
        q = (R-d)/(u-d)
        S0 = rows[0][1]
        price = PriceAmericanPutB(S0,S0,u,d,R,n)
        if not math.isfinite(price) or price < 0:
            raise ValueError('Invalid option price')
        return {'asset':path.stem, 'status':'completed', 'N':n, 'S0':S0, 'u':u, 'd':d, 'R':R, 'q':q, 'price':price}
    except Exception as exc:
        return {'asset':path.stem, 'status':'failed', 'error':f'{type(exc).__name__}: {exc}'}


def compare(seq, parallel):
    base = {r['asset']:r for r in seq}
    other = {r['asset']:r for r in parallel}
    errors = []
    for asset in sorted(set(base) | set(other)):
        if asset not in base or asset not in other:
            errors.append(f'{asset}: missing from one batch'); continue
        a,b = base[asset],other[asset]
        if a['status'] != 'completed' or b['status'] != 'completed':
            errors.append(f'{asset}: failed'); continue
        if any(a[k] != b[k] for k in ('N','S0','u','d','R','q')) or abs(a['price']-b['price']) > 1e-4:
            errors.append(f'{asset}: parameters or price differ')
    return errors


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root/'00_Instructor'/'Class3'/'data'/'hourly'
    files = sorted(p for p in directory.glob('*.csv') if p.stem != 'SP500')
    if len(files) != 40:
        raise SystemExit(f'Expected 40 crypto files, found {len(files)}')
    cpu = getattr(os, 'process_cpu_count', os.cpu_count)() or 1
    if cpu < 4:
        raise SystemExit(f'Only {cpu} logical CPUs available; cannot run requested 4-worker configuration')
    output = root/'40_Results'/'parallel_one_year'
    output.mkdir(exist_ok=False)
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    meta = {'logical_cpus_available':cpu, 'processor':platform.processor(), 'platform':platform.platform(),
            'python':sys.version, 'numpy':np.__version__, 'warmup':'one asset, sequential, before timed batches',
            'method':'last 8761 observations, sample log volatility, T=elapsed seconds/365.25 days; total wall time includes loading, calibration, pool startup, pricing and collection',
            'version_B_sha256':hashlib.sha256((root/'20_Code'/'price_american_put_numpy.py').read_bytes()).hexdigest(),
            'input_sha256':hashes, 'thread_environment':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}}
    (output/'environment.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print('Warming up one asset...',flush=True)
    warm = worker(str(files[0]))
    if warm['status'] != 'completed':
        raise RuntimeError(f'Warm-up failed: {warm}')
    base = None; base_time = None
    fields = ['workers','completed_assets','runtime_seconds','assets_per_second','speedup_vs_sequential','status']
    with (output/'summary.csv').open('x',encoding='utf-8',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=fields); writer.writeheader(); f.flush()
        for count in (1,2,4):
            print(f'Starting {count}-worker batch...',flush=True)
            start = time.perf_counter()
            if count == 1:
                results = [worker(str(p)) for p in files]
            else:
                with ProcessPoolExecutor(max_workers=count) as pool:
                    results = list(pool.map(worker, map(str,files)))
            elapsed = time.perf_counter()-start
            if base is None:
                base, base_time = results, elapsed
            errors = compare(base,results)
            completed = sum(r['status']=='completed' for r in results)
            status = 'completed' if completed==40 and not errors else 'failed'
            detail = {'workers':count,'elapsed_seconds':elapsed,'results':results,'comparison_errors':errors}
            with (output/f'workers_{count}.json').open('x',encoding='utf-8') as detail_file:
                json.dump(detail,detail_file,indent=2,allow_nan=False); detail_file.write('\n')
            row = {'workers':count,'completed_assets':completed,'runtime_seconds':elapsed,
                   'assets_per_second':completed/elapsed,'speedup_vs_sequential':base_time/elapsed,'status':status}
            writer.writerow(row); f.flush()
            print(json.dumps(row),flush=True)
    changed = [p.name for p in files if hashlib.sha256(p.read_bytes()).hexdigest() != hashes[p.name]]
    (output/'input_verification.json').write_text(json.dumps({'changed_inputs':changed},indent=2)+'\n',encoding='utf-8')
    if changed:
        raise RuntimeError(f'Inputs changed during benchmark: {changed}')


if __name__ == '__main__':
    main()
