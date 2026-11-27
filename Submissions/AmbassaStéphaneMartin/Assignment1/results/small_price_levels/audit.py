"""Audit saved sale metrics against integer price-time matching of source inputs."""
import ast
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
import benchmark as bm
from order_book import BaselineOrderBook

snapshot=json.loads((Path(__file__).parent/'before_checks.json').read_text(encoding='utf-8'))
protected=snapshot['protected']
test_result=snapshot['test_result']
old_tests=snapshot['old_tests']

def original_methods(source):
    return {(cls.name,method.name):ast.dump(method,include_attributes=False)
            for cls in ast.parse(source).body if isinstance(cls,ast.ClassDef)
            for method in cls.body if isinstance(method,ast.FunctionDef)}

old,new=original_methods(old_tests),original_methods((root/'test_benchmark.py').read_text(encoding='utf-8'))
assert all(new.get(key)==body for key,body in old.items())
changed=[name for name,digest in protected.items() if bm.sha256(root/name)!=digest]
assert not changed,changed
assert test_result['exit_code']==0
head=subprocess.check_output(['git','rev-parse','HEAD'],encoding='utf-8',cwd=root).strip()
assert head.startswith('3f97e5e')
report=dict(status='passed',reviewed_head=head,correctness=test_result,
            original_benchmark_methods_unchanged=len(old),added_benchmark_methods=len(new)-len(old),
            protected_files_verified=len(protected),protected_sha256=protected,
            metric='price_levels_visited: number of distinct executed prices in one sale',
            primary_boundary='Calculated only after replay_seconds has stopped',
            campaigns={},representative_sales=[])

for directory_name in ('smoke_price_levels','small_price_levels'):
    directory=root/'results'/directory_name
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    raw=[json.loads(line) for line in (directory/'raw.jsonl').read_text(encoding='utf-8').splitlines()]
    summaries=[json.loads(line) for line in (directory/'summaries.jsonl').read_text(encoding='utf-8').splitlines()]
    assert manifest['status']=='complete'
    assert manifest['environment']['git_head']==head
    assert manifest['environment']['git_dirty'] is True
    for name,digest in manifest['environment']['source_sha256'].items():
        assert bm.sha256(root/name)==digest,(directory_name,name)
    assert set(manifest['phases'])=={'io','timing','latency','memory','diagnostics'}
    assert manifest['repetitions']==5
    assert all(row['status']=='complete' for row in raw+summaries)
    expected_by_case={}
    for case in manifest['workloads']:
        events,_=bm.load_events(case['source']['path'],128*1024**2,case['source_event_count'])
        assert bm.sha256(case['source']['path'])==case['source']['sha256']
        assert case['source']['reused']
        assert case['seed']==42
        assert case['requested_count']==(1000 if directory_name=='smoke_price_levels' else 120)
        if case['sale_percent'] is not None:
            depth=sum(event['qty_units'] for event in events)
            quotient,remainder=divmod(depth*case['sale_percent'],100)
            requested=quotient+int(remainder!=0)
            assert type(requested) is int
            remaining=requested
            maker_fills=levels=0
            previous_price=None
            # Independent oracle: consume sorted input quantities without engine calls.
            for order in sorted(events,key=lambda event:(-event['price_ticks'],event['seq'])):
                assert order['type']=='LIMIT' and order['side']=='BUY'
                if remaining==0:
                    break
                maker_fills+=1
                if order['price_ticks']!=previous_price:
                    levels+=1
                    previous_price=order['price_ticks']
                remaining-=min(remaining,order['qty_units'])
            expected_by_case[case['case_id']]=dict(fill_count=maker_fills,
                price_levels_visited=levels,unfilled_qty_units=remaining,
                requested_sale_qty_units=requested)
            report['representative_sales'].append(dict(case_id=case['case_id'],**expected_by_case[case['case_id']]))
        else:
            book=BaselineOrderBook()
            fills=residual=cancelled=0
            for event in events:
                result=book.process_event(event)
                assert result['status']!='rejected'
                fills+=len(result.get('fills',[]))
                residual+=result.get('unfilled_qty_units',0)
                cancelled+=result.get('cancelled_qty_units',0)
            expected_by_case[case['case_id']]=dict(fill_count=fills,
                price_levels_visited=None,unfilled_qty_units=residual,cancelled_qty_units=cancelled)
    groups={}
    applicable_raw=0
    for row in raw:
        assert 'price_levels_visited' in row
        groups.setdefault((row['case_id'],row['version'],row['phase']),[]).append(row)
        applicable=(row['sale_percent'] is not None and row['phase'] in ('timing','diagnostics'))
        expected=expected_by_case[row['case_id']]
        if applicable:
            applicable_raw+=1
            assert type(row['price_levels_visited']) is int
            for key,value in expected.items():
                assert row[key]==value,(row['case_id'],row['version'],row['phase'],key,row[key],value)
        else:
            assert row['price_levels_visited'] is None
            if row['phase']=='diagnostics':
                for key,value in expected.items():
                    assert row[key]==value
    for summary in summaries:
        group=groups[(summary['case_id'],summary['version'],summary['phase'])]
        assert len(group)==(5 if summary['phase'] in ('io','timing','memory') else 1)
        assert summary['expected_repetitions']==summary['completed_repetitions']==len(group)
        for key in ('price_levels_visited','fill_count','unfilled_qty_units'):
            values=[row[key] for row in group if row[key] is not None]
            assert summary[key]==(statistics.median(values) if len(values)==len(group) else None)
    comparisons=bm.validate_diagnostics(summaries)
    assert comparisons==manifest['diagnostic_comparisons']
    assert len(comparisons)==len(manifest['workloads'])
    assert all(check['status']=='passed' for check in comparisons)
    # Worker checkpoints must agree with the exported raw records too.
    checkpoint_rows=[]
    for path in sorted((directory/'workers').glob('*.json')):
        if path.name.endswith(('.job.json','.latencies.json')):
            continue
        checkpoint=json.loads(path.read_text(encoding='utf-8'))
        checkpoint_rows.extend(checkpoint['rows'])
    assert checkpoint_rows==raw
    report['campaigns'][directory_name]=dict(status=manifest['status'],
        raw_rows=len(raw),summary_rows=len(summaries),phase_jobs=len(summaries),
        diagnostic_comparisons_passed=len(comparisons),applicable_price_level_raw_rows=applicable_raw,
        all_source_hashes_current=True,git_head=head,git_dirty=True,
        benchmark_sha256=manifest['environment']['source_sha256']['benchmark.py'])

audit_path=root/'results'/'small_price_levels'/'verification.json'
if audit_path.exists():
    assert json.loads(audit_path.read_text(encoding='utf-8'))==report
else:
    bm.write_json(audit_path,report)
print(json.dumps({key:report[key] for key in ('status','protected_files_verified','campaigns','representative_sales')},indent=2))

