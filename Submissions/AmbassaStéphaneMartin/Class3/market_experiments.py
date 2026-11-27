"""Opt-in PriceAmericanPut market runs; NumPy accelerates the same recurrence.

Contracts are at the money (K=S0), as specified by the lab. Original scalar
interfaces and their strict consecutive-hour input gate remain unchanged.
"""
import argparse
import csv
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
from time import perf_counter

from american_put import _finite_float
from benchmark_pricing import process_peak_memory
from exercise_policy import PutExerciseResult, first_observed_exercise
from market_calibration import calibrate_binomial
from market_test_support import load_prepared_window, require_hourly_window

ROOT = Path(__file__).resolve().parent
GROUPS = {
    'bitcoin_one_year': ('one_year', False),
    'bitcoin_full_history': ('full_history', False),
    'all_assets_one_year': ('one_year', True),
    'all_assets_full_history': ('full_history', True),
}


def price_atm_put(S0, u, d, R, N):
    """Return the lab's ATM put price and boundary in O(N^2) time/O(N) space.

    Only the current date's row is stored. NumPy evaluates its independent
    node operations together, preserving the existing continuation formula,
    strict exercise decisions and floating-point stock representation.
    """
    import numpy as np

    S0, u, d, R = (_finite_float(value, name)
                   for value, name in ((S0,'S0'),(u,'u'),(d,'d'),(R,'R')))
    if S0 <= 0 or not 0 < d < R < u:
        raise ValueError('Require S0>0 and 0<d<R<u.')
    if isinstance(N,bool) or not isinstance(N,int) or N < 0:
        raise ValueError('N must be a nonnegative integer, excluding booleans and floats.')
    if N == 0:
        return PutExerciseResult(0.0,(None,))
    q, p = (R-d)/(u-d), (u-R)/(u-d)
    j = np.arange(N+1,dtype=np.float64)
    up, down = j*math.log(u), j*math.log(d)
    work = up+down[::-1]
    continuation = np.empty(N+1)
    mask = np.empty(N+1,dtype=bool)
    boundary = [None]*(N+1)

    def record(t, last):
        log_moneyness = math.fsum((float(up[last]),float(down[t-last])))
        stock = math.exp(math.fsum((math.log(S0),log_moneyness)))
        if stock >= S0:
            stock = math.nextafter(S0,0.0)
        if stock <= 0 or not math.isfinite(stock):
            raise OverflowError('Exercise boundary is outside the positive finite float range.')
        boundary[t] = stock

    try:
        with np.errstate(over='raise',invalid='raise',divide='raise',under='ignore'):
            np.minimum(work,0,out=work)
            np.expm1(work,out=work)
            work *= -S0
            values = work.copy()
            np.greater(values,0,out=mask)
            if mask.any():
                record(N,N-int(mask[::-1].argmax()))
            for t in range(N-1,-1,-1):
                n = t+1
                c, value, h = continuation[:n], values[:n], work[:n]
                if q <= p:
                    np.subtract(values[1:n+1],value,out=c)
                    c *= q
                    c += value
                else:
                    np.subtract(value,values[1:n+1],out=c)
                    c *= p
                    c += values[1:n+1]
                c /= R
                # K=S0 makes log moneyness the sum of just two products;
                # their binary64 sum matches math.fsum on these two terms.
                np.add(up[:n],down[t::-1],out=h)
                np.minimum(h,0,out=h)
                np.expm1(h,out=h)
                h *= -S0
                if R > 1:
                    np.greater(h,c,out=mask[:n])
                    if mask[:n].any():
                        record(t,t-int(mask[:n][::-1].argmax()))
                np.maximum(h,c,out=value)
    except FloatingPointError as exc:
        raise OverflowError('Option value exceeds the finite float range.') from exc
    return PutExerciseResult(float(values[0]),tuple(boundary))


def experiment_calibration(window, *, gap_policy='strict'):
    """Calibrate hourly data, or explicitly approximate observed intervals.

    The opt-in approximation retains every observed close/return and uses
    actual elapsed T divided by N for the model's constant period duration.
    It is not claimed to restore a missing hourly close.
    """
    if gap_policy not in ('strict','observed-intervals'):
        raise ValueError('Unknown gap policy.')
    dates = window.timestamps
    if len(window.prices) < 3 or len(window.prices) != len(dates):
        raise ValueError('Require at least three aligned observations.')
    if any(not isinstance(t,datetime) or t.utcoffset()!=timedelta(0) for t in dates):
        raise ValueError('Require UTC-aware datetimes.')
    intervals = [(b-a).total_seconds()/3600 for a,b in zip(dates,dates[1:])]
    if any(h < 1 or not h.is_integer() for h in intervals):
        raise ValueError('Require increasing observations on the hourly UTC grid.')
    elapsed = (dates[-1]-dates[0]).total_seconds()/3600
    missing = int(sum(h-1 for h in intervals))
    if not missing or gap_policy == 'strict':
        years = require_hourly_window(window)
        convention = 'consecutive_hourly'
    else:
        years = elapsed/8760
        convention = 'observed_intervals_approximation'
    model = calibrate_binomial(window.prices,T=years,annual_rate=0.04)
    info = {'T':years,'elapsed_hours':elapsed,'mean_period_hours':elapsed/model.N,
            'missing_hours':missing,'gap_count':sum(h>1 for h in intervals),
            'max_interval_hours':max(intervals),'time_convention':convention}
    return model, info


def utc_label(stamp):
    return stamp.isoformat().replace('+00:00','Z') if stamp is not None else None


def save_table(path, rows):
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def run_group(group, output, gap_policy):
    window_name, all_assets = GROUPS[group]
    with (ROOT/'results/window_summary.csv').open(newline='',encoding='utf-8') as stream:
        names = sorted({row['asset'] for row in csv.DictReader(stream)})
    if len(names) != 40:
        raise ValueError('Expected the 40 supplied assets.')
    assets = ['BTCUSDT'] if not all_assets else ['BTCUSDT']+[a for a in names if a!='BTCUSDT']
    rows = []
    started = perf_counter()
    for number, asset in enumerate(assets,1):
        window = load_prepared_window(asset,window_name)
        model, info = experiment_calibration(window,gap_policy=gap_policy)
        source = ROOT/'output'/window.metadata['file']
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        start = perf_counter()
        result = price_atm_put(window.prices[0],model.u,model.d,model.R,model.N)
        seconds = perf_counter()-start
        if not math.isfinite(result.price) or not 0 <= result.price <= window.prices[0]:
            raise ValueError('Invalid positive-rate option price.')
        if len(result.boundary)!=len(window.prices) or result.boundary[0] is not None:
            raise ValueError('Invalid at-the-money boundary dimensions or root decision.')
        if any(b is not None and (not math.isfinite(b) or not 0<b<window.prices[0]) for b in result.boundary):
            raise ValueError('Invalid exercise boundary.')
        decision = first_observed_exercise(window.prices,result.boundary,window.prices[0],
                                           timestamps_utc=window.timestamps)
        reference_check = ''
        if asset=='BTCUSDT' and window_name=='one_year':
            previous = json.loads((ROOT/'results/bitcoin_exercise.json').read_text())
            if previous['source_window_sha256']!=source_hash:
                raise ValueError('Reference Bitcoin input differs; revalidate the changed dataset.')
            if not math.isclose(previous['price'],result.price,rel_tol=1e-12,abs_tol=1e-10):
                raise ValueError('Vectorized Bitcoin price differs from the validated reference engine.')
            with (ROOT/'results/bitcoin_exercise_boundary.csv').open(newline='',encoding='utf-8') as stream:
                original = list(csv.DictReader(stream))
            for expected,actual in zip(original,result.boundary):
                text = expected['exercise_boundary']
                if ((not text) != (actual is None) or
                    (text and not math.isclose(float(text),actual,rel_tol=1e-12,abs_tol=1e-9))):
                    raise ValueError('Vectorized Bitcoin boundary differs from the reference engine.')
            if decision.index!=previous['exercise']['index']:
                raise ValueError('Vectorized observed exercise differs from the reference engine.')
            reference_check = 'price_all_boundaries_and_decision_match_saved_scalar_run'
        if hashlib.sha256(source.read_bytes()).hexdigest()!=source_hash:
            raise ValueError('Prepared input changed during the experiment.')
        row = {'group':group,'asset':asset,'window':window_name,'N':model.N,
               'S0':window.prices[0],'K':window.prices[0],'put_value':result.price,
               'put_value_pct_spot':100*result.price/window.prices[0],
               'exercise_kind':decision.kind,'exercise_index':decision.index,
               'exercise_utc':utc_label(decision.timestamp_utc),'payoff':decision.payoff,
               'start_utc':utc_label(window.timestamps[0]),'end_utc':utc_label(window.timestamps[-1]),
               's_per_observed_interval':model.s,'u':model.u,'d':model.d,'R':model.R,'q':model.q,
               **info,'pricing_seconds':seconds,'source_window_sha256':source_hash,
               'reference_check':reference_check}
        rows.append(row)
        if not all_assets:
            path = output/(group+'_boundary.csv')
            with path.open('w',newline='',encoding='utf-8') as stream:
                writer = csv.writer(stream,lineterminator='\n')
                writer.writerow(('observation_index','timestamp_utc','observed_close','exercise_boundary'))
                writer.writerows((i,utc_label(t),p,b) for i,(t,p,b) in
                                 enumerate(zip(window.timestamps,window.prices,result.boundary)))
        save_table(output/(group+'_assets.csv'),rows)
        print(f'{group}: {number}/{len(assets)} {asset} price={result.price:.10g} pricing={seconds:.3f}s',flush=True)
    peak, scope = process_peak_memory()
    report = {'group':group,'window':window_name,'assets':len(assets),'N':rows[0]['N'],
              'time_convention':rows[0]['time_convention'],
              'mean_period_hours':rows[0]['mean_period_hours'],'missing_hours_per_asset':rows[0]['missing_hours'],
              'pricing_seconds':sum(row['pricing_seconds'] for row in rows),
              'wall_seconds':perf_counter()-started,'process_peak_memory_bytes':peak,
              'process_peak_scope':scope,'asset_execution':'sequential in one fresh experiment process',
              'timing_scope':'pricing_seconds sums pricing calls; wall_seconds also includes loading, calibration and output',
              'memory_scope':'whole experiment process including NumPy imports and data; controller process excluded',
              'python':sys.version,'platform':platform.platform(),
              'gap_policy':gap_policy,'rows':rows}
    (output/(group+'.json')).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true',help='Execute the requested market experiments.')
    parser.add_argument('--group',choices=tuple(GROUPS),help='One group; default runs all four in fresh processes.')
    parser.add_argument('--gap-policy',choices=('strict','observed-intervals'),default='strict')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'results/experiments')
    args = parser.parse_args()
    if not args.run:
        parser.error('Use --run to execute pricing. Full history also needs an explicit gap policy.')
    output = args.output_dir.resolve()
    output.mkdir(parents=True,exist_ok=True)
    if args.group:
        run_group(args.group,output,args.gap_policy)
        return
    from prepare_data import verify_snapshot
    verify_snapshot(ROOT)
    started = perf_counter()
    for group in GROUPS:
        subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),'--run','--group',group,
                        '--gap-policy',args.gap_policy,'--output-dir',str(output)],check=True)
    reports = [json.loads((output/(group+'.json')).read_text()) for group in GROUPS]
    verify_snapshot(ROOT)
    summaries = [{key:report[key] for key in ('group','window','assets','N','time_convention',
                  'mean_period_hours','missing_hours_per_asset','pricing_seconds','wall_seconds',
                  'process_peak_memory_bytes')} for report in reports]
    save_table(output/'experiment_summary.csv',summaries)
    save_table(output/'asset_results.csv',[row for report in reports for row in report['rows']])
    import numpy as np
    combined = {'reproduce':'python -B market_experiments.py --run --gap-policy observed-intervals',
                'numpy_version':np.__version__,'total_wall_seconds':perf_counter()-started,
                'source_integrity':'all 40 raw inputs verified before and after the experiment set',
                'interpretation':'retrospective calibration on each selected historical window',
                'gap_approximation':'observations retained; one missing hour is represented by mean period T/N; no prices filled',
                'summaries':summaries}
    (output/'market_experiments.json').write_text(json.dumps(combined,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(combined,indent=2),flush=True)


if __name__=='__main__':
    main()
