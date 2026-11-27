"""Measure four requested Version B workloads using sampled process-tree RSS."""
from concurrent.futures import ProcessPoolExecutor
import csv
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import psutil
from price_american_put_numpy import PriceAmericanPutB
from parallel_benchmark import worker as one_year_worker
from five_year_assets import worker as full_worker

root=Path(__file__).resolve().parents[1]
output=root/'40_Results'/'rss_compliance'
data=root/'00_Instructor'/'Class3'/'data'/'hourly'


def child(mode, path):
    if mode in ('btc_one','btc_full'):
        filename='bitcoin_last_year_summary.json' if mode=='btc_one' else 'bitcoin_full_history.json'
        with (root/'40_Results'/filename).open(encoding='utf-8-sig') as f: params=json.load(f)
        args=tuple(params[k] for k in ('S0','K','u','d','R','N'))
        start=time.perf_counter(); price=PriceAmericanPutB(*args); runtime=time.perf_counter()-start
        old=params['price_usdt_per_btc'] if mode=='btc_one' else params['operations']['pricing']['price_usdt_per_btc']
        if not math.isfinite(price) or abs(price-old)>1e-4: raise ValueError('Price differs from prior result')
        result={'status':'completed','assets':1,'periods':args[-1],'runtime_seconds':runtime,'price':price}
    else:
        files=sorted(p for p in data.glob('*.csv') if p.stem!='SP500')
        if len(files)!=40: raise ValueError('Expected 40 assets')
        fn=one_year_worker if mode=='batch_one' else full_worker
        start=time.perf_counter()
        with ProcessPoolExecutor(max_workers=8) as pool:
            rows=list(pool.map(fn,map(str,files)))
        runtime=time.perf_counter()-start
        previous=root/'40_Results'/('one_year_crypto.csv' if mode=='batch_one' else 'five_year_assets/results.csv')
        with previous.open(encoding='utf-8-sig',newline='') as f: old={r['asset']:r for r in csv.DictReader(f) if r['asset']!='SP500'}
        errors=[]
        for r in rows:
            if r['status']!='completed' or r['asset'] not in old:
                errors.append(f"{r['asset']}: failed or missing"); continue
            previous_row=old[r['asset']]
            n=r.get('N',r.get('periods'))
            if int(previous_row['periods'])!=n or abs(float(previous_row['price'])-r['price'])>1e-4:
                errors.append(f"{r['asset']}: differs from saved result")
        if errors: raise ValueError('; '.join(errors))
        result={'status':'completed','assets':len(rows),'periods_min':min(r.get('N',r.get('periods')) for r in rows),
                'periods_max':max(r.get('N',r.get('periods')) for r in rows),'runtime_seconds':runtime,
                'workers':8,'prices_match_previous':True}
    Path(path).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


def run():
    output.mkdir(exist_ok=False)
    summary=[]
    for mode in ('btc_one','btc_full','batch_one','batch_full'):
        child_result=output/f'{mode}_workload.json'
        print(f'Measuring {mode}...',flush=True)
        proc=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--child',mode,str(child_result)],stdout=subprocess.DEVNULL)
        peak=0; samples=0
        parent=psutil.Process(proc.pid)
        while proc.poll() is None:
            try:
                processes=[parent]+parent.children(recursive=True)
                total=0
                for process in processes:
                    try: total+=process.memory_info().rss
                    except (psutil.NoSuchProcess,psutil.AccessDenied): pass
                peak=max(peak,total);samples+=1
            except (psutil.NoSuchProcess,psutil.AccessDenied): pass
            time.sleep(.05)
        if proc.returncode!=0 or not child_result.exists():
            result={'status':'failed','exit_code':proc.returncode}
        else:
            result=json.loads(child_result.read_text(encoding='utf-8'))
        result.update(workload=mode,peak_aggregate_rss_bytes=peak,samples=samples,
                      sampling_interval_seconds=.05,psutil_version=psutil.__version__)
        with (output/f'{mode}_rss.json').open('x',encoding='utf-8') as f:
            json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
        summary.append(result)
        print(json.dumps(result),flush=True)
    print('RSS measurements finished.',flush=True)


if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1]=='--child': child(sys.argv[2],sys.argv[3])
    elif len(sys.argv)==1: run()
    else: raise SystemExit('Usage: python rss_compliance.py')
