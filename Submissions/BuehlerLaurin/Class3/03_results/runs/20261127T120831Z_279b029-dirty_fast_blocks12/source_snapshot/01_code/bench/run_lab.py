"""Required workload grid, separate timing/memory/artifact runs, raw evidence.

Run from the exercise root: python run.py bench.run_lab
Never mutates git or course data. All workloads use the tested public pipeline.
"""
import csv
import hashlib
import json
import math
import shutil
import sys
import time
from pathlib import Path
from bench.harness import new_run_dir,time_repeats,peak_traced_bytes,run_with_timeout
from amput import METHODS
from amput.pipeline import analyze_many,analyze,summarize
from amput.data import load_calibrate


def csv_rows(path,rows):
    if not rows: return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def boundary_csv(path,analysis):
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f); writer.writerow(['t','timestamp_utc','observed_close','boundary','near_tie'])
        for t,(utc,p,b,near) in enumerate(zip(analysis.window.timestamps,analysis.window.prices,analysis.result.boundary,analysis.result.near_ties)):
            writer.writerow([t,utc,p,b,near])


def source_hashes(root):
    paths=list((root/'01_code').rglob('*.py'))+list((root/'02_tests').glob('*.py'))+[root/'SPEC.md']
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def main():
    root=Path.cwd(); source=root.parents[2]/'Class3/data/hourly'
    paths=sorted(source.glob('*.csv')); assert len(paths)==40
    btc=source/'BTCUSDT.csv'
    d=new_run_dir(tag='fast_blocks12')
    (root/'03_results/LATEST.txt').write_text(d.as_posix()+'\n',encoding='utf-8')
    hashes=source_hashes(root)
    (d/'source_sha256.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
    tests=sorted((root/'05_evidence').glob('*tests-green-B.txt'))[-1]
    shutil.copyfile(tests,d/'tests.txt')
    protocol=dict(warmup=1,repeats=5,statistic='median',timing='whole public pipeline; file reads included; warm caches expected',
                  memory='separate tracemalloc primary whole run; secondary max of separately measured pricing calls including boundary',
                  process='one process, sequential assets, compact summaries retained; boundary CSV serialization excluded',
                  source='human commit plus dirty source hashes; no claim of clean-commit official status',growth_limit_s=60)
    (d/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf-8')
    summary=[]; timing=[]; memory=[]; phases=[]
    jobs=[('BTC1y','1y',[btc],'A'),('BTC1y','1y',[btc],'B'),('BTC5y','5y',[btc],'B'),
          ('ALL1y','1y',paths,'B'),('ALL5y','5y',paths,'B')]
    print('RUN DIRECTORY: '+d.as_posix(),flush=True)
    for name,window,assets,version in jobs:
        label=f'{name}_{version}'
        print(f'START timing {label}: {len(assets)} assets, warm-up + 5 repeats',flush=True)
        def check(rows):
            assert len(rows)==len(assets)
            assert all(r['status']=='ok' and math.isfinite(r['value']) and 0<=r['value']<=r['K']*(1+1e-12) for r in rows),rows
        raw=time_repeats(lambda:None,lambda _:analyze_many(assets,window,version),warmup=1,repeats=5,check=check)
        (d/f'{label}_timing.json').write_text(json.dumps(raw,indent=2)+'\n',encoding='utf-8')
        for i,seconds in enumerate(raw['run_s']):
            timing.append(dict(version=version,workload=name,seed=0,size=window,phase='total',repeat=i,seconds=seconds,status='ok',repeats_requested=5))
        csv_rows(d/'timing.csv',timing)
        if version=='A':
            summary.append(dict(workload=name,version=version,window=window,N=8760,assets=1,
                                seconds=raw['run_median_s'],peak_bytes='',pricing_peak_bytes='',status='ok',repeats=5))
            csv_rows(d/'summary.csv',summary)
            print(f'COMPLETE {label}: median {raw["run_median_s"]:.6f}s (timing-only reference for ratio)',flush=True)
            continue
        print(f'DONE timing {label}: median {raw["run_median_s"]:.6f}s; START primary tracemalloc',flush=True)
        primary=peak_traced_bytes(lambda:None,lambda _:analyze_many(assets,window,version),include_setup=True)
        memory.append(dict(version=version,workload=name,window=window,measure='primary_whole_run',**primary))
        csv_rows(d/'memory.csv',memory)
        print(f'DONE primary memory {label}: {primary["peak_bytes"]} bytes; START artifact + isolated pricing memory runs',flush=True)
        details=[]; secondaries=[]
        directory=d/(label+'_boundaries'); directory.mkdir()
        method=METHODS[('baseline','A') if version=='A' else ('fast','B')]
        for index,path in enumerate(assets,1):
            # Phase instrumentation is a separate run, never the median timing.
            t0=time.perf_counter(); w=load_calibrate(path,window); t1=time.perf_counter()
            result=method(*w.params); t2=time.perf_counter()
            from amput.data import first_exercise
            from amput.pipeline import Analysis
            exercise=first_exercise(w.prices,w.timestamps,result.boundary,w.params[1]); t3=time.perf_counter()
            a=Analysis(w,result,exercise)
            details.append(summarize(path,window,a))
            phases.append(dict(workload=name,version=version,symbol=path.stem,window=window,parse_calibrate_s=t1-t0,price_s=t2-t1,exercise_s=t3-t2,instrumentation_only=True))
            boundary_csv(directory/(path.stem+'.csv'),a)
            # Drop artifact arrays before tracing; calibrated input is pre-existing.
            del a,result
            isolated=peak_traced_bytes(lambda:w.params,lambda args:method(*args),include_setup=False)
            secondaries.append(isolated['peak_bytes'])
            memory.append(dict(version=version,workload=name,window=window,symbol=path.stem,measure='secondary_pricing',**isolated))
            print(f'  {label} {index}/{len(assets)} {path.stem}: value={details[-1]["value"]:.10g}, isolated peak={isolated["peak_bytes"]}',flush=True)
            del w
        csv_rows(d/(label+'_assets.csv'),details)
        csv_rows(d/'memory.csv',memory); csv_rows(d/'phase_instrumentation.csv',phases)
        ns=[r['N'] for r in details]
        summary.append(dict(workload=name,version=version,window=window,N=ns[0] if len(set(ns))==1 else f'{min(ns)}..{max(ns)}',assets=len(assets),
                            seconds=raw['run_median_s'],peak_bytes=primary['peak_bytes'],pricing_peak_bytes=max(secondaries),status='ok',repeats=5))
        csv_rows(d/'summary.csv',summary)
        print(f'COMPLETE {label}',flush=True)
    growth=[]
    for version in ['A','B']:
        for n in [1000,2000,4000,8000]:
            output=d/f'growth_{version}_{n}.json'
            cmd=[sys.executable,'-B','run.py','bench.growth_cell','--version',version,'--n',str(n),'--out',str(output)]
            print(f'START growth {version} N={n}, 60 s whole-cell limit',flush=True)
            status=run_with_timeout(cmd,60)
            (d/f'growth_{version}_{n}.log').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
            row=dict(version=version,N=n,status=status['status'],seconds='',repeats_requested=5,limit_s=60)
            if status['status']=='ok':
                cell=json.loads(output.read_text(encoding='utf-8')); row['seconds']=cell['run_median_s']
            growth.append(row); csv_rows(d/'growth.csv',growth)
            print(f'DONE growth {version} N={n}: {row["status"]}, seconds={row["seconds"]}',flush=True)
    assert source_hashes(root)==hashes,'Source changed during measurement'
    print('BENCHMARK GRID COMPLETE: '+d.as_posix(),flush=True)


if __name__=='__main__':
    main()
