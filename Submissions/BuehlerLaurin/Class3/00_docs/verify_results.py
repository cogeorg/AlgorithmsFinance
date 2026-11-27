"""Verify saved Block 2 artifacts without repricing; execute via evidence.py."""
import csv
import hashlib
import json
import math
from pathlib import Path


def read_csv(path):
    with path.open(newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))


def main():
    root=Path.cwd()
    d=root/(root/'03_results/LATEST.txt').read_text(encoding='utf-8').strip()
    summary=read_csv(d/'summary.csv')
    assert len(summary)==5
    expected={('BTC1y','A'):1,('BTC1y','B'):1,('BTC5y','B'):1,('ALL1y','B'):40,('ALL5y','B'):40}
    for row in summary:
        assert row['status']=='ok' and int(row['repeats'])==5
        assert int(row['assets'])==expected[(row['workload'],row['version'])]
        assert int(row['N'])==(8760 if row['window']=='1y' else 43822)
        assert float(row['seconds'])>0
        if row['version']=='B':
            assert int(row['peak_bytes'])>0 and int(row['pricing_peak_bytes'])>0
    timing=read_csv(d/'timing.csv')
    assert len(timing)==25
    assert len({(r['workload'],r['version'],r['repeat']) for r in timing})==25
    count=0; nodes=0
    for name,window,number in [('BTC1y','1y',1),('BTC5y','5y',1),('ALL1y','1y',40),('ALL5y','5y',40)]:
        details=read_csv(d/(name+'_B_assets.csv'))
        assert len(details)==number
        for row in details:
            assert row['status']=='ok'
            n=int(row['N']); K=float(row['K'])
            assert 0<=float(row['value'])<=K*(1+1e-12)
            path=d/(name+'_B_boundaries')/(row['symbol']+'.csv')
            first=None; seen=0
            with path.open(newline='',encoding='utf-8') as f:
                for t,point in enumerate(csv.DictReader(f)):
                    assert int(point['t'])==t
                    if t==0:
                        assert point['boundary']==''
                        assert point['timestamp_utc']==row['first_utc']
                    if point['boundary']!='':
                        boundary=float(point['boundary'])
                        assert math.isfinite(boundary) and 0<=boundary<K
                        observed=float(point['observed_close'])
                        if first is None and observed<=boundary:
                            first=(t,point['timestamp_utc'],K-observed)
                    seen+=1
                assert seen==n+1 and point['timestamp_utc']==row['last_utc']
            if first is None:
                assert row['exercise_t']==row['exercise_utc']==row['payoff']==''
            else:
                assert int(row['exercise_t'])==first[0] and row['exercise_utc']==first[1]
                assert abs(float(row['payoff'])-first[2])<=1e-12*max(1,K)
            count+=1; nodes+=seen
    # The initial full BTC A/B comparison established the saved initial B
    # boundary equals A. Recompare every layer after the lattice revision.
    original=root/'03_results/runs/20261127T120831Z_279b029-dirty_fast_blocks12'
    old=read_csv(original/'BTC1y_B_boundaries/BTCUSDT.csv')
    new=read_csv(d/'BTC1y_B_boundaries/BTCUSDT.csv')
    reference=json.loads((root/'00_docs/BTC1Y_DIFFERENTIAL.json').read_text(encoding='utf-8'))
    current=read_csv(d/'BTC1y_B_assets.csv')[0]
    K=float(current['K']); exceptions=[]
    assert abs(float(current['value'])-reference['A'])<=1e-9*max(1,K)
    assert len(old)==len(new)==8761
    for x,y in zip(old,new):
        a,b=x['boundary'],y['boundary']
        if a==b or (a and b and abs(float(a)-float(b))<=1e-10*max(1,K)):
            continue
        assert x['near_tie']=='True' or y['near_tie']=='True'
        exceptions.append(dict(t=x['t'],A=a,B=b))
    (d/'BTC1y_A_B_FINAL_COMPARISON.json').write_text(json.dumps(dict(A=reference['A'],B=float(current['value']),boundary_exceptions=exceptions),indent=2)+'\n',encoding='utf-8')
    recorded=json.loads((d/'source_sha256.json').read_text(encoding='utf-8'))
    for rel,digest in recorded.items():
        source=d/'SPEC_at_measurement.md' if rel=='SPEC.md' and (d/'SPEC_at_measurement.md').exists() else root/rel
        assert hashlib.sha256(source.read_bytes()).hexdigest()==digest,rel
    growth=read_csv(d/'growth.csv')
    assert len(growth)==8
    for row in growth:
        assert row['status'] in ('ok','stopped')
        assert (float(row['seconds'])>0) if row['status']=='ok' else row['seconds']==''
    print(f'ARTIFACT CHECK: PASS ({count} asset results; {nodes} boundary rows; earliest exercise verified from all saved paths)')
    print(f'FINAL BTC1y A/B: PASS (value delta={abs(float(current["value"])-reference["A"]):.12g}, boundary exceptions={len(exceptions)})')
    print('SOURCE HASHES: PASS (current implementation/tests; measured SPEC snapshot); five workload rows, 25 timing repeats and eight growth cells accounted for')


if __name__=='__main__':
    main()
