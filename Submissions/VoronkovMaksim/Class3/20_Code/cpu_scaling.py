"""Three sequential benchmark repetitions across seven process counts."""
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
import winreg

import numpy as np
from parallel_benchmark import worker, compare

WORKERS = [1, 2, 4, 6, 8, 12, 16]


def main():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root = Path(__file__).resolve().parents[1]
    files = sorted(p for p in (root/'00_Instructor'/'Class3'/'data'/'hourly').glob('*.csv') if p.stem != 'SP500')
    if len(files) != 40:
        raise SystemExit(f'Expected 40 files, got {len(files)}')
    cpus = getattr(os, 'process_cpu_count', os.cpu_count)() or 1
    if cpus < max(WORKERS):
        raise SystemExit(f'Only {cpus} logical CPUs available; 16 workers exceed limit')
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
        model = winreg.QueryValueEx(key, 'ProcessorNameString')[0]
    out = root/'40_Results'/'cpu_scaling_one_year'
    out.mkdir(exist_ok=False)
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    metadata = {'cpu_model':model, 'logical_cpus_available':cpus, 'python':sys.version,
                'numpy':np.__version__, 'platform':platform.platform(), 'workers':WORKERS, 'repetitions':3,
                'warmup':'one sequential asset before all batches', 'source_hashes':hashes,
                'pricer_sha256':hashlib.sha256((root/'20_Code'/'price_american_put_numpy.py').read_bytes()).hexdigest(),
                'worker_sha256':hashlib.sha256((root/'20_Code'/'parallel_benchmark.py').read_bytes()).hexdigest(),
                'thread_environment':{k:os.environ.get(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')},
                'timing':'wall time including data loading, calibration, pool startup, pricing and collection; reporting excluded',
                'historical_reference':'../parallel_one_year/summary.csv', 'status':'running'}
    (out/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    print('Warm-up...',flush=True)
    if worker(str(files[0]))['status'] != 'completed':
        raise RuntimeError('Warm-up failed')
    baseline = None
    raw = []
    with (out/'raw_times.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['workers','repeat','runtime_seconds','completed','status','errors'])
        writer.writeheader(); f.flush()
        for count in WORKERS:
            for repeat in range(1,4):
                print(f'Starting {count} workers, repeat {repeat}...',flush=True)
                start=time.perf_counter()
                if count == 1:
                    results=[worker(str(p)) for p in files]
                else:
                    with ProcessPoolExecutor(max_workers=count) as pool:
                        results=list(pool.map(worker,map(str,files)))
                elapsed=time.perf_counter()-start
                if baseline is None:
                    baseline=results
                errors=compare(baseline,results)
                completed=sum(r['status']=='completed' for r in results)
                if completed != 40:
                    errors.append(f'Only {completed} assets completed')
                row={'workers':count,'repeat':repeat,'runtime_seconds':elapsed,'completed':completed,
                     'status':'failed' if errors else 'completed','errors':'; '.join(errors)}
                with (out/f'workers_{count}_repeat_{repeat}.json').open('x',encoding='utf-8') as detail:
                    json.dump({'timing':row,'results':results,'comparison_errors':errors},detail,indent=2,allow_nan=False)
                writer.writerow(row); f.flush(); raw.append(row)
                print(json.dumps(row),flush=True)
                if errors:
                    raise RuntimeError('Correctness check failed; see saved results')
    base=statistics.median(r['runtime_seconds'] for r in raw if r['workers']==1)
    summary=[]
    for count in WORKERS:
        median=statistics.median(r['runtime_seconds'] for r in raw if r['workers']==count)
        speed=base/median
        row={'workers':count,'median_seconds':median,'speedup':speed,'efficiency':speed/count,
             'marginal_time_saving_seconds':'','marginal_speedup_per_worker':'','empirical_speedup_curvature':''}
        if summary:
            prev=summary[-1]
            row['marginal_time_saving_seconds']=prev['median_seconds']-median
            row['marginal_speedup_per_worker']=(speed-prev['speedup'])/(count-prev['workers'])
            if len(summary)>1:
                prevprev=summary[-2]
                midpoint=(count+prev['workers'])/2
                prev_midpoint=(prev['workers']+prevprev['workers'])/2
                row['empirical_speedup_curvature']=(row['marginal_speedup_per_worker']-prev['marginal_speedup_per_worker'])/(midpoint-prev_midpoint)
        summary.append(row)
    with (out/'summary.csv').open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0])); writer.writeheader(); writer.writerows(summary)
    changed=[p.name for p in files if hashlib.sha256(p.read_bytes()).hexdigest()!=hashes[p.name]]
    metadata['changed_inputs']=changed
    metadata['status']='completed' if not changed else 'input_changed'
    (out/'environment.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    fig,(ax1,ax2)=plt.subplots(1,2,figsize=(11,7))
    ax1.plot(WORKERS,[r['median_seconds'] for r in summary],marker='o'); ax1.set(title='Median batch runtime',xlabel='Workers',ylabel='Seconds',xticks=WORKERS); ax1.grid(alpha=.25)
    ax2.plot(WORKERS,[r['speedup'] for r in summary],marker='o',label='Observed'); ax2.plot(WORKERS,WORKERS,'--',label='Ideal linear'); ax2.set(title='Speedup',xlabel='Workers',ylabel='Speedup',xticks=WORKERS); ax2.grid(alpha=.25); ax2.legend()
    table=[[str(r['workers']),f"{r['efficiency']:.3f}", '—' if r['marginal_speedup_per_worker']=='' else f"{r['marginal_speedup_per_worker']:.3f}"] for r in summary]
    fig.subplots_adjust(bottom=.35,wspace=.3)
    table_ax = fig.add_axes([.18,.02,.64,.25]); table_ax.axis('off')
    table_ax.table(cellText=table,colLabels=['Workers','Efficiency','Marginal speedup / worker'],cellLoc='center',bbox=[0,0,1,1])
    fig.savefig(out/'cpu_scaling.png',dpi=150); plt.close(fig)
    print('Completed. '+json.dumps(summary),flush=True)
    if changed:
        raise RuntimeError('Input files changed during benchmark')


if __name__=='__main__':
    main()
