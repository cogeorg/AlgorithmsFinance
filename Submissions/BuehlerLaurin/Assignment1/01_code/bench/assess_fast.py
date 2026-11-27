"""Saved-result acceptance gate; never runs an engine or timing experiment."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from bench.catalog import POST_MANIFEST, load
from bench.run_all import cases_for, fingerprint, mode_applies, rows_from


def performance_gate(reference, trial, required_ids):
    reasons, pairs = [], []
    def index(rows, label):
        result = {}
        for row in rows:
            key = row['case_id']
            if key in result:
                reasons.append(f'{label}: duplicate {key}')
            result[key] = row
        if set(result) != set(required_ids):
            reasons.append(f'{label}: missing/unexpected cases')
        return result
    old, new = index(reference, 'B3r'), index(trial, 'fast')
    for key in sorted(required_ids):
        if key not in old or key not in new:
            continue
        a, b = old[key], new[key]
        if any(r.get('status') != 'ok' or str(r.get('completed_repeats')) != '5'
               or str(r.get('repeats_requested')) != '5' for r in (a,b)):
            reasons.append(f'{key}: incomplete/stopped repeats')
            continue
        metadata = ('input_sha256','experiment','size','seed','levels','events','replayed_events','percent','prefill_events','driver_n')
        if any(str(a.get(k, '')) != str(b.get(k, '')) for k in metadata):
            reasons.append(f'{key}: input/settings mismatch')
            continue
        try:
            seconds_a, seconds_b = float(a['median_s']), float(b['median_s'])
            assert seconds_a > 0 and seconds_b > 0 and math.isfinite(seconds_a) and math.isfinite(seconds_b)
        except (ValueError, TypeError, AssertionError):
            reasons.append(f'{key}: invalid elapsed time')
            continue
        ratio = seconds_b/seconds_a
        pairs.append(dict(case_id=key, experiment=a['experiment'], size=int(a['size']), seed=int(a['seed']),
                          B3r_s=seconds_a, fast_s=seconds_b, ratio=ratio))
    score = [r for r in pairs if r['experiment'] == 'official' and r['size'] == 100000]
    score_log = math.fsum(math.log(r['ratio']) for r in score)
    ratio = math.exp(score_log/15) if len(score) == 15 else None
    if len(score) != 15 or {r['seed'] for r in score} != {42,43,44}:
        reasons.append('15 official100k seed42/43/44 cells required')
    elif score_log > 15*math.log(0.90):
        reasons.append('less than10% reduction in geometric-mean replay time')
    losses = [r for r in pairs if r['ratio'] > 1.05]
    if losses:
        reasons.append('at least one replay median is >5% slower')
    return dict(performance_pass=not reasons, official_100k_ratio=ratio, reasons=reasons,
                compared=len(pairs), losses=losses, comparisons=pairs)


def record_gates(standard, attack, output):
    report = {'source_sha256': fingerprint(), 'G1': True, 'G2': True, 'G3': True, 'evidence': []}
    for label, path in (('standard', standard), ('attack', attack)):
        cases = list(ET.parse(path).iter('testcase'))
        if not cases or any(c.find(k) is not None for c in cases for k in ('failure','error','skipped')):
            raise ValueError('gate suite must be nonempty and wholly green: '+label)
        names = [c.get('name', '') for c in cases]
        classes = [c.get('classname', '') for c in cases]
        if label == 'standard':
            required = ('test_g1_exhaustive_validator_corpus','test_g1_hypothesis_arbitrary_json',
                        'test_g2_all_supplied_and_own_every_event','test_g2_all_attack_stream_families')
            if not all(any(n.startswith(prefix) for n in names) for prefix in required):
                raise ValueError('G1/G2 evidence missing')
            if not any('TestFastDifferential' in c for c in classes) or not any('TestDifferential_B3r_fast' in c for c in classes):
                raise ValueError('both stateful gates required')
            if not any(c.endswith('test_mutants') for c in classes) or len(cases) < 700:
                raise ValueError('full standard suite/mutants required')
        elif not any('B3r_fast' in n for n in names):
            raise ValueError('attack suite did not include B3r_fast')
        report['evidence'].append(dict(suite=label, path=str(path), cases=len(cases),
            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def verify_gates(path, source_sha=None):
    report = json.loads(path.read_text(encoding='utf-8'))
    if not all(report.get(k) is True for k in ('G1','G2','G3')):
        raise ValueError('every correctness gate is required')
    if report['source_sha256'] != (source_sha or fingerprint()):
        raise ValueError('correctness evidence belongs to different source')
    for item in report['evidence']:
        if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('correctness evidence hash changed')
    return report


def compare(reference, trial, gates_path):
    catalog = load(POST_MANIFEST)
    cases = cases_for('official', catalog)+cases_for('post_attack', catalog)
    ids = {c['id'] for c in cases if mode_applies(c, 'timing')}
    pick = lambda directory, version: [r for r in rows_from(directory/'summary.csv')
        if r['version'] == version and r['phase'] == 'replay' and r['experiment'] in ('official','post_attack')]
    report = performance_gate(pick(reference, 'B3r'), pick(trial, 'B3r_fast'), ids)
    env = json.loads((trial/'env.json').read_text(encoding='utf-8'))
    try:
        verify_gates(gates_path, env['source_sha256'])
        report['correctness_pass'] = True
    except (ValueError, KeyError, OSError) as exc:
        report['correctness_pass'] = False
        report['reasons'].append(str(exc))
    cell_keys = {(c['id'], mode) for c in cases for mode in ('timing','latency','memory','counts') if mode_applies(c, mode)}
    actual = rows_from(trial/'cells.csv')
    keys = {(r['case_id'], r['mode']) for r in actual if r['version'] == 'B3r_fast' and r['status'] == 'ok'}
    complete = keys == cell_keys and len(actual) == len(cell_keys)
    if not complete:
        report['reasons'].append('full236-worker observation coverage required')
    accepted = report['performance_pass'] and report['correctness_pass'] and complete
    report.update(reference=str(reference), trial=str(trial), decision='eligible for adoption' if accepted else 'tried and rejected',
                  final_version='B3r_fast' if accepted else 'B3r')
    (trial/'fast_acceptance.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    gate = sub.add_parser('record-gates')
    gate.add_argument('standard', type=Path); gate.add_argument('attack', type=Path); gate.add_argument('--out', type=Path, required=True)
    check = sub.add_parser('verify-gates'); check.add_argument('path', type=Path)
    result = sub.add_parser('compare')
    result.add_argument('reference', type=Path); result.add_argument('trial', type=Path); result.add_argument('--gates', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'record-gates':
        report = record_gates(args.standard, args.attack, args.out)
    elif args.command == 'verify-gates':
        report = verify_gates(args.path)
    else:
        report = compare(args.reference, args.trial, args.gates)
    print(json.dumps(report, indent=2))
    print('RESULT: PASS (saved evidence analysis only; no engine or timing run executed)')


if __name__ == '__main__':
    main()
