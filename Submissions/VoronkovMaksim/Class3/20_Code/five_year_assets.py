"""Full-history crypto pricing, eight processes, incremental results."""
from concurrent.futures import ProcessPoolExecutor, as_completed
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
import winreg

import numpy as np
from calibrate import read_prices
from price_american_put_numpy import PriceAmericanPutB

FIELDS=['asset','observations','periods','start_utc','end_utc','non_hourly_intervals',
        'missing_hourly_slots','S0','strike','volatility','u','d','R','q','price',
        'pricing_seconds','status','error']


def worker(path):
    path=Path(path)
    row={'asset':path.stem,'status':'failed'}
    try:
        rows=read_prices(path)
        n=len(rows)-1
        if n<2:
            raise ValueError('Fewer than three observations')
        gaps=[(b[0]-a[0]).total_seconds()/3600 for a,b in zip(rows,rows[1:])]
        s=statistics.stdev(math.log(b[1]/a[1]) for a,b in zip(rows,rows[1:]))
        u=math.exp(s); d=1/u
        years=(rows[-1][0]-rows[0][0]).total_seconds()/(365.25*86400)
        R=math.exp(.04*years/n)
        if not 0<d<R<u:
            raise ValueError('No-arbitrage condition failed')
        q=(R-d)/(u-d); S0=rows[0][1]
        row.update(observations=len(rows),periods=n,start_utc=rows[0][0].isoformat(),
                   end_utc=rows[-1][0].isoformat(),non_hourly_intervals=sum(g!=1 for g in gaps),
                   missing_hourly_slots=sum(max(0,math.floor(g)-1) for g in gaps),
                   S0=S0,strike=S0,volatility=s,u=u,d=d,R=R,q=q)
        start=time.perf_counter()
        price=PriceAmericanPutB(S0,S0,u,d,R,n)
        row['pricing_seconds']=time.perf_counter()-start
        if not math.isfinite(price) or price<0:
            raise ValueError('Option value is negative or nonfinite')
        row.update(price=price,status='completed')
    except Exception as exc:
        row['error']=f'{type(exc).__name__}: {exc}'
    return row


def main():
    root=Path(__file__).resolve().parents[1]
    files=sorted(p for p in (root/'00_Instructor'/'Class3'/'data'/'hourly').glob('*.csv') if p.stem!='SP500')
    if len(files)!=40:
        raise SystemExit(f'Expected 40 supplied assets; found {len(files)}')
    cpus=getattr(os,'process_cpu_count',os.cpu_count)() or 1
    if cpus<8:
        raise SystemExit(f'Only {cpus} logical CPUs available; 8 workers exceed limit')
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
        cpu=winreg.QueryValueEx(key,'ProcessorNameString')[0]
    out=root/'40_Results'/'five_year_assets'
    out.mkdir(exist_ok=False)
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    meta={'assets_total':len(files),'workers':8,'logical_cpus_available':cpus,'cpu_model':cpu,
          'platform':platform.platform(),'python':sys.version,'numpy':np.__version__,
          'method':'all available observations; sample log-return volatility; T=elapsed seconds/365.25 days; same formulas as one-year',
          'timing':'batch wall time includes process startup, data loading, calibration, pricing and result collection',
          'timeout':'none: existing ProcessPoolExecutor runner has no per-asset timeout',
          'source_hashes':hashes,'pricer_sha256':hashlib.sha256((root/'20_Code'/'price_american_put_numpy.py').read_bytes()).hexdigest(),
          'thread_environment':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
          'completed':0,'failed':0,'status':'running'}
    meta_path=out/'metadata.json'
    meta_path.write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    started=time.perf_counter()
    with (out/'results.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();f.flush()
        with ProcessPoolExecutor(max_workers=8) as pool:
            futures={pool.submit(worker,str(p)):p.stem for p in files}
            for future in as_completed(futures):
                try:
                    row=future.result()
                except Exception as exc:
                    row={'asset':futures[future],'status':'failed','error':f'{type(exc).__name__}: {exc}'}
                writer.writerow(row); f.flush()
                meta[row['status']]+=1
                meta['elapsed_batch_seconds']=time.perf_counter()-started
                meta_path.write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
                print(f"{row['asset']}: {row['status']} ({meta['completed']+meta['failed']}/40)",flush=True)
    meta['batch_runtime_seconds']=time.perf_counter()-started
    meta['attempted']=meta['completed']+meta['failed']
    meta['changed_inputs']=[p.name for p in files if hashlib.sha256(p.read_bytes()).hexdigest()!=hashes[p.name]]
    meta['status']='completed' if meta['attempted']==40 and not meta['failed'] and not meta['changed_inputs'] else 'completed_with_errors'
    meta_path.write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:meta[k] for k in ('attempted','completed','failed','batch_runtime_seconds','status','changed_inputs')},indent=2),flush=True)


if __name__=='__main__':
    main()
