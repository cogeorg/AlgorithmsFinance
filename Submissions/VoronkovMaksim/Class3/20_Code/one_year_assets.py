"""Sequential one-year American put pricing for the supplied market data."""
import argparse
import csv
from datetime import timedelta
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time

import numpy as np
from calibrate import read_prices
from price_american_put_numpy import PriceAmericanPutB

FIELDS = ['asset','start_utc','end_utc','periods','S0','strike','volatility','u','d','R','q',
          'price','pricing_seconds','status','data_quality','error']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('hourly_dir', type=Path, help='Instructor hourly CSV directory')
    parser.add_argument('--sp500', type=Path, help='Optional personal-use S&P CSV')
    args = parser.parse_args()
    files = [(p.stem, p, False) for p in sorted(args.hourly_dir.glob('*.csv')) if p.stem != 'SP500']
    if args.sp500:
        files.append(('SP500', args.sp500, True))
    if not files:
        raise SystemExit('No input CSV files found')
    root = Path(__file__).resolve().parents[1]
    result_path = root/'40_Results'/'one_year_assets.csv'
    meta_path = root/'40_Results'/'one_year_assets_metadata.json'
    if result_path.exists() or meta_path.exists():
        raise SystemExit('Results already exist; preserve them before running')
    start_batch = time.perf_counter()
    counts = {'completed': 0, 'failed': 0}
    metadata = {'assets_total':len(files), 'counts':counts, 'batch_status':'running',
                'method':'Last 8761 observations for hourly crypto; last calendar year for optional S&P. Consecutive available closes are steps; actual elapsed time / 365.25 defines T.',
                'batch_runtime_definition':'wall time including loading, calibration, pricing and output writing',
                'numpy':np.__version__, 'python':sys.version, 'platform':platform.platform(),
                'source_hashes':{}, 'version_B_sha256':hashlib.sha256((root/'20_Code'/'price_american_put_numpy.py').read_bytes()).hexdigest(),
                'sp500_personal_use_only':bool(args.sp500)}
    def save_metadata():
        metadata['batch_runtime_seconds'] = time.perf_counter()-start_batch
        meta_path.write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    with result_path.open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS); writer.writeheader(); f.flush()
        with meta_path.open('x', encoding='utf-8') as meta:
            json.dump(metadata,meta,indent=2)
        for asset, path, is_sp in files:
            row = {'asset':asset, 'status':'failed'}
            try:
                rows = read_prices(path)
                if not rows:
                    raise ValueError('No observations')
                metadata['source_hashes'][asset] = hashlib.sha256(path.read_bytes()).hexdigest()
                notes = []
                if is_sp:
                    end = rows[-1][0]
                    try:
                        cutoff = end.replace(year=end.year-1)
                    except ValueError:
                        cutoff = end.replace(year=end.year-1, day=28)
                    if rows[0][0] > cutoff:
                        raise ValueError('File does not cover a full calendar year')
                    rows = [r for r in rows if cutoff <= r[0] <= end]
                    notes.append('S&P trading-hour gaps; personal use only')
                else:
                    if len(rows) < 8761:
                        notes.append('fewer than 8761 observations available')
                    rows = rows[-8761:]
                n = len(rows)-1
                if n < 2:
                    raise ValueError('Fewer than three valid observations')
                gaps = [(b[0]-a[0]).total_seconds()/3600 for a,b in zip(rows,rows[1:])]
                irregular = sum(g != 1 for g in gaps)
                missing = sum(max(0, math.floor(g)-1) for g in gaps)
                if irregular:
                    notes.append(f'{irregular} non-hourly intervals; {missing} missing full-hour slots')
                years = (rows[-1][0]-rows[0][0]).total_seconds()/(365.25*86400)
                s = statistics.stdev(math.log(b[1]/a[1]) for a,b in zip(rows,rows[1:]))
                u = math.exp(s); d = 1/u; R = math.exp(.04*years/n)
                if not 0 < d < R < u:
                    raise ValueError('No-arbitrage condition failed')
                q = (R-d)/(u-d)
                S0 = rows[0][1]
                row.update(start_utc=rows[0][0].isoformat(),end_utc=rows[-1][0].isoformat(),
                           periods=n,S0=S0,strike=S0,volatility=s,u=u,d=d,R=R,q=q,
                           data_quality='; '.join(notes) if notes else 'none')
                started = time.perf_counter()
                price = PriceAmericanPutB(S0,S0,u,d,R,n)
                seconds = time.perf_counter()-started
                if not math.isfinite(price) or price < 0:
                    raise ValueError('Option price is nonfinite or negative')
                row.update(price=price,pricing_seconds=seconds,status='completed')
                counts['completed'] += 1
            except (OSError, ValueError, OverflowError, ArithmeticError) as exc:
                row['error'] = str(exc)
                counts['failed'] += 1
            writer.writerow(row); f.flush()
            save_metadata()
            print(f"{asset}: {row['status']} ({counts['completed']+counts['failed']}/{len(files)})", flush=True)
    metadata['batch_status'] = 'completed'
    save_metadata()
    print(json.dumps({'counts':counts,'assets_total':len(files),'batch_runtime_seconds':metadata['batch_runtime_seconds']}, indent=2))


if __name__ == '__main__':
    main()
