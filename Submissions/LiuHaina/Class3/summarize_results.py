"""Validate saved measurements and generate the submission table."""
import csv
import gzip
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def main():
    output=ROOT/'results'
    summaries=[]
    assets={p.stem for p in (ROOT/'work/data/hourly').glob('*.csv')}
    for scope,horizon in [('btc','year'),('btc','full'),('all','year'),('all','full')]:
        name=f'{scope}_{horizon}'
        meta=json.loads((output/f'{name}_measurement.json').read_text())
        with (output/f'{name}_prices.csv').open() as stream:
            rows=list(csv.DictReader(stream))
        assert {r['symbol'] for r in rows} == ({'BTCUSDT'} if scope=='btc' else assets)
        assert len(rows)==meta['assets']
        assert meta['seconds']>0 and meta['peak_memory_bytes']>0
        for row in rows:
            N=int(row['N'])
            if horizon=='year': assert N==8760
            assert 0<=float(row['price'])<=float(row['K'])
            assert 0<float(row['q'])<1
            with gzip.open(output/f"{name}_{row['symbol']}_boundary.csv.gz",'rt') as stream:
                reader=csv.DictReader(stream)
                first=None
                count=0
                for state in reader:
                    assert int(state['index'])==count
                    count+=1
                    if state['exercise_boundary']:
                        b=float(state['exercise_boundary'])
                        assert math.isfinite(b) and 0<=b<float(row['K'])
                        spot=float(state['observed_close'])
                        if first is None and spot<=b:
                            first=state
                assert count==N+1
            if first is None:
                assert row['exercise_timestamp']=='never'
            else:
                assert first['timestamp_utc']==row['exercise_timestamp']
                assert int(first['index'])==int(row['exercise_index'])
                assert math.isclose(float(row['K'])-float(first['observed_close']),float(row['exercise_payoff']),abs_tol=1e-9)
        summaries.append(meta)
    for horizon in ('year','full'):
        def read(scope):
            with (output/f'{scope}_{horizon}_prices.csv').open() as f:
                return next(r for r in csv.DictReader(f) if r['symbol']=='BTCUSDT')
        a,b=read('btc'),read('all')
        for key in a:
            if key!='pricing_seconds': assert a[key]==b[key],(key,a[key],b[key])
    lines=['# Class 3 lab results','',
           '| Run | Assets | Actual N (min–max) | Pricing seconds | Peak RSS (MiB) | Workers |',
           '|---|---:|---:|---:|---:|---:|']
    for r in summaries:
        lines.append(f"| {r['run']} | {r['assets']} | {r['N_min']}–{r['N_max']} | {r['seconds']:.4f} | {r['peak_memory_MiB']:.2f} | {r['workers']} |")
    lines+=['','Seconds cover pricing plus boundary-crossing scans; JIT, loading/calibration and writing files are excluded. Separate JIT and loading/calibration timings are in each measurement JSON; serialization time was not measured. Peak RSS includes imports, JIT and loaded data, measured before output serialization in a fresh child process; it is not just tree storage. Runs execute sequentially; asset computations within each 40-asset run use four threads.','',
            '| BTC window | Put value (USDT) | First boundary crossing (UTC) | Payoff (USDT) |','|---|---:|---|---:|']
    for horizon in ('year','full'):
        with (output/f'btc_{horizon}_prices.csv').open() as f: r=next(csv.DictReader(f))
        payoff=f"{float(r['exercise_payoff']):.4f}" if r['exercise_payoff'] else '—'
        lines.append(f"| {horizon} | {float(r['price']):.4f} | {r['exercise_timestamp']} | {payoff} |")
    lines+=['','All 40 prices, calibration inputs, window dates, actual step counts, missing-hour counts and crossing outcomes appear in `results/all_year_prices.csv` and `results/all_full_prices.csv`. Every date’s boundary is saved in the corresponding compressed CSV.','',
            'One-year windows use the final 8,761 observations (8,760 steps). Full windows use every supplied row; missing exchange hours remain missing. T uses actual elapsed UTC time divided by 365 days, so five calendar years including a leap day can exceed 5.0 ACT/365 years.','',
            'Memory scaling: the largest full tree would require approximately '+f"{max(r['full_tree_bytes_per_largest_asset'] for r in summaries)/1024**3:.2f}"+' GiB for one float64 value at every node, before stock prices, boundaries or Python overhead. Rolling values plus boundaries require only '+f"{max(r['rolling_value_and_boundary_bytes_per_largest_asset'] for r in summaries)/1024**2:.3f}"+' MiB per active asset. No memory limit was hit in these four runs; this implementation removes the quadratic storage requirement, while retaining quadratic running time. This is an analytical full-tree estimate, not a measured out-of-memory experiment.','']
    (ROOT/'RESULTS.md').write_text('\n'.join(lines))
    (output/'validation.json').write_text(json.dumps({'passed':True,'runs':4,'priced_contracts':82,'boundaries_checked':82,'checks':['asset coverage','N and prices','all saved boundary rows','first crossing and payoff','BTC batch parity']},indent=2)+'\n')
    print('Validated all 82 contracts and complete boundary series; wrote RESULTS.md')

if __name__=='__main__': main()
