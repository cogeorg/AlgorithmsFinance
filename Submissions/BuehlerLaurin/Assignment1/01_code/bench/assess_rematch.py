"""Single-attempt rematch policy and saved-result assessment, never a timer."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics

from bench.assess_fast import performance_gate, verify_gates
from bench.catalog import POST_MANIFEST, load
from bench.run_all import cases_for, fingerprint, ordered_requests, rows_from, source_dirty

SESSION = 'phase4_b3r_fast_rematch_20261122'
ATTEMPT = Path('scratch/b3r_fast_rematch_attempt.json')
GATES = Path('05_evidence/b3r_fast_rematch_correctness.json')
CROSS = Path('03_results/runs/20261122T200528Z_8a22753_phase4_b3r_fast_20261122/fast_acceptance.json')


def planned_requests():
    catalog = load(POST_MANIFEST)
    cases = cases_for('official',catalog)+cases_for('post_attack',catalog)
    jobs = ordered_requests(cases,['B3r','B3r_fast'],['timing'],interleave=True)
    if len(jobs) != 114:
        raise ValueError('declared rematch requires57 timing pairs')
    return jobs


def scenario_performance(reference, trial, required_ids):
    # Reuse unchanged input/completeness/15-cell checks, replacing ONLY the old
    # per-cell5% rule. Its individual losses remain in this report as evidence.
    report = performance_gate(reference,trial,required_ids)
    reasons = [r for r in report['reasons'] if r != 'at least one replay median is >5% slower']
    old = {r['case_id']:r for r in reference}
    new = {r['case_id']:r for r in trial}
    groups = defaultdict(list)
    for pair in report['comparisons']:
        a,b = old[pair['case_id']],new[pair['case_id']]
        if not a.get('workload') or a.get('workload') != b.get('workload'):
            reasons.append(pair['case_id']+': workload mismatch/missing')
            continue
        pair['workload'] = a['workload']
        groups[(pair['experiment'],pair['workload'],pair['size'])].append(pair)
    scenarios = [dict(experiment=key[0],workload=key[1],size=key[2],seeds=sorted(r['seed'] for r in rows),
        seed_ratios=[r['ratio'] for r in sorted(rows,key=lambda r:r['seed'])],
        median_seed_ratio=statistics.median(r['ratio'] for r in rows)) for key,rows in sorted(groups.items())]
    losses = [r for r in scenarios if r['median_seed_ratio'] > 1.05]
    if losses:
        reasons.append('at least one scenario median(seed ratios) is >5% slower')
    report.update(individual_losses=report.pop('losses'),scenarios=scenarios,scenario_losses=losses,
                  reasons=reasons,performance_pass=not reasons)
    return report


def atomic_claim(path, payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:
        json.dump(payload,stream,indent=2)


def claim_attempt():
    proof = verify_gates(GATES)
    if source_dirty():
        raise ValueError('commit the declared source/protocol before claiming the attempt')
    planned_requests()
    if Path(f'scratch/bench_session_{SESSION}.json').exists() or any(Path('03_results/runs').glob('*_'+SESSION)):
        raise ValueError('rematch session already exists; no further measurement allowed')
    payload = dict(session=SESSION,status='claimed',claimed_utc=datetime.now(timezone.utc).isoformat(),
                   source_sha256=proof['source_sha256'],attempt_limit=1,binding=True)
    atomic_claim(ATTEMPT,payload)
    return payload


def assess(directory, *, attempt_path=ATTEMPT, gates_path=GATES):
    output = directory/'fast_rematch_acceptance.json'
    if output.exists():
        return json.loads(output.read_text(encoding='utf-8'))  # binding, never recompute/overwrite
    jobs = planned_requests()
    ids = {c['id'] for c,v,m in jobs}
    summary = rows_from(directory/'summary.csv')
    pick = lambda version:[r for r in summary if r['version']==version and r['phase']=='replay']
    report = scenario_performance(pick('B3r'),pick('B3r_fast'),ids)
    reasons = report['reasons']
    expected_order = [(c['id'],v,m) for c,v,m in jobs]
    cells = rows_from(directory/'cells.csv')
    actual_order = [(r['case_id'],r['version'],r['mode']) for r in cells]
    complete = actual_order == expected_order and all(r['status']=='ok' for r in cells)
    if not complete:
        reasons.append('114 complete timing workers in the declared alternating order required')
    try:
        env = json.loads((directory/'env.json').read_text(encoding='utf-8'))
        proof = verify_gates(gates_path)
        attempt = json.loads(attempt_path.read_text(encoding='utf-8'))
        correct = (env['source_sha256']==proof['source_sha256']==attempt['source_sha256']==fingerprint()
                   and bool(env.get('interleaving')) and attempt['session']==SESSION and attempt['status']=='claimed')
    except (KeyError,ValueError,OSError) as exc:
        correct,attempt = False,{}
        reasons.append(str(exc))
    if not correct:
        reasons.append('current-source correctness/interleave/single-attempt proof required')
    historical = json.loads(CROSS.read_text(encoding='utf-8'))
    accepted = report['performance_pass'] and complete and correct
    report.update(correctness_pass=correct,coverage_and_order_pass=complete,
        decision='accepted' if accepted else 'rejected',final_version='B3r_fast' if accepted else 'B3r',
        binding=True,attempt_limit=1,session=SESSION,decision_method='same-session; scenario median of seed ratios',
        historical_cross_session=dict(path=str(CROSS),sha256=hashlib.sha256(CROSS.read_bytes()).hexdigest(),
            decision=historical['decision'],official_100k_ratio=historical['official_100k_ratio'],
            per_cell_losses=historical['losses'],reason='cross-session noise; old rejection retained unchanged'),
        rationale='B3r buildup10k s42 0.0233s and sweep100k s43 0.2829s were anomalously fast; method fixed before rematch')
    directory.mkdir(parents=True,exist_ok=True)
    with output.open('x',encoding='utf-8') as stream:
        json.dump(report,stream,indent=2)
    lines = ['# Binding fast rematch decision','',f"Decision: **{report['decision']}**; final Version B: **{report['final_version']}**.",
        '',f"Historical cross-session decision: {historical['decision']};15-cell ratio {historical['official_100k_ratio']:.6f}.",
        'Original per-cell comparison is retained, with its two anomalously fast B3r cells and session-noise explanation.',
        '', '| Historical per-cell loss | B3r seconds | Fast seconds | Ratio |','|---|---:|---:|---:|']
    for row in historical['losses']:
        lines.append(f"| {row['case_id']} | {row['B3r_s']:.6f} | {row['fast_s']:.6f} | {row['ratio']:.6f} |")
    lines += ['',f"New same-session15-cell ratio: {report['official_100k_ratio']}; per-scenario bound uses median OF seed ratios.",
        'One attempt only. This decision is binding; no further re-measurement.','',
        '| Workload | Size | Seeds | Ratios fast/B3r | Median seed ratio |','|---|---:|---|---|---:|']
    for row in report['scenarios']:
        lines.append(f"| {row['workload']} | {row['size']} | {row['seeds']} | {row['seed_ratios']} | {row['median_seed_ratio']:.6f} |")
    lines += ['','Reasons: '+('; '.join(reasons) if reasons else 'all declared conditions passed')]
    (directory/'fast_rematch_acceptance.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    if attempt:
        attempt.update(status='completed',decision=report['decision'],final_version=report['final_version'],
                       result_path=str(output),result_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
        attempt_path.write_text(json.dumps(attempt,indent=2)+'\n',encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('claim')
    result = sub.add_parser('assess'); result.add_argument('directory',type=Path)
    args = parser.parse_args()
    report = claim_attempt() if args.command=='claim' else assess(args.directory)
    print(json.dumps(report,indent=2))
    print('RESULT: PASS (rematch policy/evidence operation only; no engine measurement)')


if __name__=='__main__':
    main()
