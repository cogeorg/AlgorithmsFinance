"""Per-tab numerical cross-checks of saved files, not new measurements."""
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pandas as pd

sys.path.insert(0,'04_dashboard')
import saved_results as s

b = s.load_bundle(s.head())
records = []


def emit(tab, description, value, unit, role, file, case=None):
    row = dict(tab=tab, description=description, value=value, unit=unit,
               run=s.RUNS[role], commit=b['envs'][role]['git_commit'], file=file, case=case)
    records.append(row)
    print(json.dumps(row))


def select(frame, **filters):
    for key,value in filters.items():
        frame = frame[frame[key].eq(value)]
    return frame


base = b['tables']['baseline']
summary = base['summary']
for row in s.official_geomeans(b).itertuples():
    emit('Final selection',row.version+' official100k geometric mean',float(row.geomean_s),
         's','baseline' if row.version == 'B3r' else 'candidates','summary.csv')
assert b['rematch']['decision'] == 'rejected'
assert b['cross']['decision'] == 'tried and rejected'
raw = select(summary,version='B3r',experiment='official',size=100000,phase='replay')
g = math.exp(sum(math.log(v) for v in raw.median_s)/len(raw))
shown = s.official_geomeans(b).set_index('version').loc['B3r','geomean_s']
assert len(raw) == 15 and math.isclose(g,shown,rel_tol=1e-12)
emit('Overview','B3r official100k 15-cell geometric mean',g,'s','baseline','summary.csv')
stops = select(base['stops'],version='A',phase='replay',reason='phase_time_limit')
assert stops.case_id.nunique() == len(s.replay_limits(b)) == 13
emit('Overview','A phase replay limits',len(stops),'cases','baseline','stops.csv')
losses = s.a_vs_b(b).query('experiment == "official" and workload == "cancel_churn"')
assert losses.speedup.lt(1).all()
emit('Overview','cancel_churn A/B3r minimum measured ratio',float(losses.speedup.min()),'ratio','baseline','summary.csv')
compact = s.overview_speedups(b)
assert len(compact) == 15
for row in compact.itertuples():
    emit('Overview',f'{row.workload}/{row.size} seed-median A/B3r ({row.kind})',
         row.label,'ratio label','baseline','summary.csv + stops.csv')

scale = select(summary,version='A',experiment='official',workload='buildup',phase='replay',status='ok')
points = scale.groupby('size').median_s.median()
exp = math.log(points.iloc[-1]/points.iloc[0])/math.log(points.index[-1]/points.index[0])
fit = s.fit_exponents(select(base['validated'],version='A',experiment='official',workload='buildup',phase='replay')).iloc[0]
assert math.isclose(exp,fit.exponent,rel_tol=1e-12)
emit('Scaling','A buildup measured exponent (1k to10k)',exp,'dimensionless','baseline','summary.csv')
for phase in ('construction','replay'):
    row = select(summary,version='B3r',experiment='liquidation',size=10000,seed=42,percent=100,phase=phase).iloc[0]
    timed = select(base['timing'],version='B3r',case_id=row.case_id,phase=phase,status='ok')
    timed = timed[~timed.warmup.astype(str).str.lower().eq('true')]
    assert math.isclose(float(timed.seconds.median()),row.median_s,rel_tol=1e-12)
    emit('Scaling','Q7 100% sale '+phase,float(row.median_s),'s','baseline','timing.csv',row.case_id)
million = select(summary,version='B3r',experiment='million',workload='mixed',phase='replay').iloc[0]
emit('Scaling','Completed B3r 1M mixed replay',float(million.median_s),'s','baseline','summary.csv',million.case_id)

v = select(s.variants(b),workload='deep_book',size=100000,seed=42)
assert v.input_sha256.nunique() == 1 and len(v) == 4
ratio = float(v.loc[v.version.eq('B1'),'median_s'].iloc[0]/v.median_s.min())
assert math.isclose(ratio,float(v.loc[v.version.eq('B1'),'ratio_to_best'].iloc[0]),rel_tol=1e-12)
emit('Original vs revised & variants','B1 deep_book / best B (cross-session)',ratio,'ratio','candidates','summary.csv',v.case_id.iloc[0])
rm = b['tables']['rematch']['summary'].query('phase == "replay"')
grid = select(rm,experiment='official',size=100000).pivot(index='case_id',columns='version',values='median_s')
ratio = math.exp(sum(math.log(v) for v in grid.B3r_fast/grid.B3r)/len(grid))
assert math.isclose(ratio,b['rematch']['official_100k_ratio'],rel_tol=1e-12)
emit('Original vs revised & variants','Same-session official fast/B3r score',ratio,'ratio','rematch','summary.csv')
one = select(rm,workload='dead_slot_rebuild',size=1000).set_index('version').median_s
ratio = float(one['B3r_fast']/one['B3r'])
assert math.isclose(ratio,b['rematch']['scenario_losses'][0]['median_seed_ratio'],rel_tol=1e-12)
emit('Original vs revised & variants','Binding 1k loss fast/B3r',ratio,'ratio','rematch','summary.csv')

case = 'official_buildup_1000_s42_l1000'
h = select(base['latency_histogram'],case_id=case,version='B3r',event_type='ALL',segment='all')
q = select(base['latency'],case_id=case,version='B3r',event_type='ALL',segment='all').iloc[0]
assert h['count'].sum() == q.n
emit('Throughput & latency','Histogram sum equals recorded n',int(h['count'].sum()),'events','baseline','latency_histogram.csv',case)
emit('Throughput & latency','Recorded p99',int(q.p99_ns),'ns','baseline','latency.csv',case)
spike = select(base['latency'],version='B3r',workload='spike_purge_at_threshold',size=100000,event_type='ALL',segment='all').iloc[0]
emit('Throughput & latency','Declared spike maximum',int(spike.max_ns),'ns','baseline','latency.csv',spike.case_id)

for role,version in [('candidates','B3'),('baseline','B3r')]:
    m = select(b['tables'][role]['memory'],version=version,workload='drift',size=1000000,seed=43,measure='curve')
    end = m.loc[m.processed.idxmax()]
    emit('Memory',version+' retained after1M drift events',int(end.current_bytes),'bytes',role,'memory.csv',end.case_id)
    emit('Memory',version+' final live orders',int(end.live_orders),'orders',role,'memory.csv',end.case_id)
peak = select(s.memory_peaks(b),case_id='official_buildup_100000_s42_l1000',version='B3r').iloc[0]
assert peak.peak_bytes_per_sampled_live_order == peak.peak_bytes/peak.max_sampled_live_orders
emit('Memory','Peak per sampled maximum live order',float(peak.peak_bytes_per_sampled_live_order),'bytes/order','baseline','memory.csv',peak.case_id)

for suite in b['correctness']['suites']:
    text = b['store'].text(suite['path'])
    assert hashlib.sha256(text.encode()).hexdigest() == suite['sha256']
    nodes = list(ET.fromstring(text).iter('testcase'))
    assert len(nodes) == suite['tests'] and all(n.find(k) is None for n in nodes for k in ('failure','error','skipped'))
    print('Correctness:',suite['suite'],len(nodes),'wholly green; XML hash verified;',suite['path'])
    records.append(dict(tab='Correctness',description=suite['suite'],value=len(nodes),unit='passed cases',
                        run='no benchmark run;05_evidence',commit=b['correctness']['commit'],file=suite['path']))

scans = select(base['counts'],version='A',workload='liquidation_100pct',size=1000,seed=42,phase='replay',counter='orders_scanned').iloc[0]
assert scans.value == 1000*1001//2
emit('Bottleneck explained','A maker selection entries scanned on100% liquidation',int(scans.value),'entries','baseline','counts.csv',scans.case_id)
shifts = select(base['counts'],version='B1',workload='far_end_flicker',size=100000,phase='replay',counter='price_list_shifts').iloc[0]
assert shifts.value == 2*100000**2
emit('Bottleneck explained','B1 far-end list movement',int(shifts.value),'references shifted','baseline','counts.csv',shifts.case_id)
env = b['envs']['baseline']
emit('Method & data','Per replay limit',env['per_replay_limit_s'],'s','baseline','env.json')
emit('Method & data','Traced peak limit',env['traced_peak_limit_bytes'],'bytes','baseline','env.json')
repeats = s.raw_repeats(b,'baseline',case,'B3r','replay')
assert len(repeats) == 6 and repeats.row_kind.eq('warm-up').sum() == 1
measured = repeats[repeats.row_kind.eq('measured')]
assert len(measured) == 5
assert math.isclose(measured.seconds.median(),select(summary,case_id=case,version='B3r',phase='replay').median_s.iloc[0],rel_tol=1e-12)
emit('Method & data','Raw repeat selector: measured median',float(measured.seconds.median()),'s','baseline','timing.csv',case)
settings = s.workload_settings(b)
assert settings.input_sha256.str.len().eq(64).all()
assert set(settings.data_origin) == {'own','supplied'}
emit('Method & data','Workload settings rows with recorded SHA-256',len(settings),'rows','baseline','cells.csv (all four runs)')
assert len(records) and len({r['tab'] for r in records}) == 9
cp = subprocess.run(['git','diff','HEAD','--','01_code','03_results','06_data','requirements.txt'],capture_output=True,text=True,check=True)
assert not cp.stdout
print('Protected engine/benchmark/data/results/dependency files unchanged; external attack work excluded.')
output = dict(snapshot_commit=b['store'].revision,created_utc=datetime.now(timezone.utc).isoformat(),
              measurements_executed=False,checks=records)
Path('05_evidence/clarity-audit.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
print('RESULT: PASS (all9 tabs cross-checked against saved files; no measurement, engine change or network fetch)')
