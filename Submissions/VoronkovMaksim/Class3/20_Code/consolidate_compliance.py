"""Build a concise table from the recorded process-RSS measurements."""
import csv
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
measurements=root/'40_Results'/'rss_compliance'
output=root/'40_Results'/'required_results.csv'
report=root/'50_Docs'/'REQUIRED_RESULTS.md'
if output.exists() or report.exists(): raise SystemExit('Output already exists')
specs=[('BTC one year','btc_one'),('BTC full history','btc_full'),('40 assets one year','batch_one'),('40 assets five years','batch_full')]
rows=[]
for label,mode in specs:
    with (measurements/f'{mode}_rss.json').open(encoding='utf-8') as f: item=json.load(f)
    if item['status']!='completed': raise ValueError(f'{mode} did not complete')
    periods=item.get('periods',item.get('periods_min'))
    if item.get('periods_max',periods)!=periods: raise ValueError('Report must show a period range')
    rows.append({'workload':label,'implementation':'NumPy B','periods_per_asset':periods,
                 'assets':item['assets'],'workers':item.get('workers',1),'runtime_seconds':item['runtime_seconds'],
                 'peak_aggregate_rss_bytes':item['peak_aggregate_rss_bytes'],'status':item['status']})
with output.open('x',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
with report.open('x',encoding='utf-8') as f:
    f.write('# Required results — Version B\n\n')
    f.write('| Workload | Implementation | Periods per asset | Assets | Workers | Runtime (s) | Peak aggregate RSS (MiB) | Status |\n|---|---|---:|---:|---:|---:|---:|---|\n')
    for r in rows:
        f.write(f"| {r['workload']} | {r['implementation']} | {r['periods_per_asset']} | {r['assets']} | {r['workers']} | {r['runtime_seconds']:.3f} | {r['peak_aggregate_rss_bytes']/1048576:.2f} | {r['status']} |\n")
    f.write('\nThese measurements are separate Version B reruns for RSS evidence. BTC runtimes time pricing only; batch runtimes include loading, calibration, process startup, pricing and collection. RSS is the maximum sampled sum of the child workload process and all descendants, including startup and data loading, sampled approximately every 50 ms. It excludes the monitoring process, can miss short peaks and can count shared pages more than once. Single-process and multi-process sums are not comparable as unique physical memory.\n\n')
    f.write('Historical Version A one-year peak traced allocation was 458,832 bytes; full-history tracing was terminated without a peak. Python-traced allocations and process RSS measure different things and must not be compared as equivalent. Full-history inputs have one missing hourly observation, retained as a two-hour gap between consecutive available closes.\n')
print('Consolidated CSV and Markdown saved.')
