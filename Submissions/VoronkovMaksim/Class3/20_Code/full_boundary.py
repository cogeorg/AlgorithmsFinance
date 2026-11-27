"""Verify vector boundary and persist full-history BTC boundary."""
import csv
import json
import math
from pathlib import Path
import numpy as np
from boundary_numpy import boundary_numpy
from calibrate import read_prices

root=Path(__file__).resolve().parents[1]
out=root/'40_Results'/'bitcoin_full_boundary.csv'
verification=root/'40_Results'/'bitcoin_full_boundary_verification.json'
if out.exists() or verification.exists(): raise SystemExit('Output exists; preserve previous results')
price,b=boundary_numpy(100,100,1.2,.8,1.05,2)
if abs(price-7.9931972789)>1e-8 or not np.isnan(b[0]) or abs(b[1]-80)>1e-8 or abs(b[2]-96)>1e-8:
    raise ValueError('Two-period boundary example failed')
with (root/'40_Results'/'bitcoin_last_year_summary.json').open(encoding='utf-8-sig') as f: one=json.load(f)
args=tuple(one[k] for k in ('S0','K','u','d','R','N'))
one_price,one_boundary=boundary_numpy(*args)
with (root/'40_Results'/'bitcoin_last_year_boundary.csv').open(encoding='utf-8-sig',newline='') as f:
    previous=[float(r['boundary_usdt']) if r['boundary_usdt'] else math.nan for r in csv.DictReader(f)]
if len(previous)!=len(one_boundary) or not np.allclose(previous,one_boundary,atol=1e-4,rtol=0,equal_nan=True):
    raise ValueError('One-year boundaries disagree')
if abs(one_price-one['price_usdt_per_btc'])>1e-4: raise ValueError('One-year price differs')
print('Small tree and one-year boundaries agree; computing full history...',flush=True)
with (root/'40_Results'/'bitcoin_full_history.json').open(encoding='utf-8-sig') as f: full=json.load(f)
args=tuple(full[k] for k in ('S0','K','u','d','R','N'))
rows=read_prices(root/'00_Instructor'/'Class3'/'data'/'hourly'/'BTCUSDT.csv')
if len(rows)!=full['observations']: raise ValueError('Input count differs from saved run')
full_price,boundaries=boundary_numpy(*args)
if abs(full_price-full['operations']['pricing']['price_usdt_per_btc'])>1e-4: raise ValueError('Full-history price differs')
cross=None
for step, ((date,close),level) in enumerate(zip(rows,boundaries)):
    if not np.isnan(level) and close<=level and full['K']-close>0:
        cross={'step':step,'timestamp_utc':date.isoformat(),'price_usdt':close,'boundary_usdt':float(level),'intrinsic_payoff_usdt':full['K']-close}; break
old=full['operations']['boundary']['first_crossing']
if cross is None or cross['step']!=old['step'] or abs(cross['boundary_usdt']-old['boundary_usdt'])>1e-4:
    raise ValueError('First crossing differs from saved result')
with out.open('x',encoding='utf-8',newline='') as f:
    w=csv.writer(f); w.writerow(['step','timestamp_utc','boundary_usdt'])
    for i,((date,_),level) in enumerate(zip(rows,boundaries)):
        w.writerow([i,date.isoformat(),'' if np.isnan(level) else float(level)])
with verification.open('x',encoding='utf-8') as f:
    json.dump({'small_tree':'passed','one_year_price':one_price,'one_year_all_steps_match':True,'full_price':full_price,'full_steps':len(boundaries),'first_crossing':cross},f,indent=2,allow_nan=False);f.write('\n')
print(json.dumps({'full_steps':len(boundaries),'full_price':full_price,'first_crossing':cross}),flush=True)
