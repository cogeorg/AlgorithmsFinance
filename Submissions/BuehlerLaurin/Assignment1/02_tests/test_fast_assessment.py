"""Decision boundary checks from synthetic saved rows, not benchmark timings."""
from copy import deepcopy
import pytest
from bench.assess_fast import performance_gate


def rows(ratio):
    base = []
    for scenario in ('buildup','crowded','mixed','sweep','cancel_churn'):
        for seed in (42,43,44):
            base.append(dict(case_id=f'{scenario}-{seed}', experiment='official', size='100000',
                seed=str(seed), input_sha256=f'{scenario}-{seed}-hash', median_s=1.0,
                status='ok', phase='replay', completed_repeats='5', repeats_requested='5'))
    base.append(dict(base[0], case_id='other-size', size='1000', median_s=1.0))
    trial = [dict(r, median_s=ratio) for r in base]
    return base, trial, {r['case_id'] for r in base}


@pytest.mark.parametrize('ratio,accepted', [(0.90, True), (0.901, False), (1.0, False)])
def test_ten_percent_time_reduction_is_required(ratio, accepted):
    a,b,ids = rows(ratio)
    assert performance_gate(a,b,ids)['performance_pass'] is accepted


@pytest.mark.parametrize('slowdown,accepted', [(1.05, True), (1.05001, False)])
def test_no_five_percent_loss_anywhere_even_outside_score(slowdown, accepted):
    a,b,ids = rows(0.80)
    b[-1]['median_s'] = slowdown
    result = performance_gate(a,b,ids)
    assert result['performance_pass'] is accepted
    assert result['official_100k_ratio'] == pytest.approx(0.8)


@pytest.mark.parametrize('fault', ['missing','stopped','partial','hash','duplicate'])
def test_incomplete_or_unmatched_data_cannot_promote(fault):
    a,b,ids = rows(0.8)
    if fault == 'missing': b.pop()
    elif fault == 'stopped': b[0]['status'] = 'stopped'
    elif fault == 'partial': b[0]['completed_repeats'] = '4'
    elif fault == 'hash': b[0]['input_sha256'] = 'different'
    else: b.append(deepcopy(b[0]))
    assert performance_gate(a,b,ids)['performance_pass'] is False
