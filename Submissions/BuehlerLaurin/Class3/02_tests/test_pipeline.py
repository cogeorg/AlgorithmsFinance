from amput.pipeline import analyze,analyze_many
from amput.a import price_with_boundary
from amput.data import load_calibrate,first_exercise


def make_csv(path,prices):
    path.write_text('timestamp_utc,close\n'+''.join(f'2026-01-01T0{i}:00:00Z,{p}\n' for i,p in enumerate(prices)),encoding='utf-8')


def test_timed_pipeline_equals_public_methods(tmp_path):
    p=tmp_path/'good.csv'; make_csv(p,[100,110,99,101])
    w=load_calibrate(p,'5y')
    direct=price_with_boundary(*w.params)
    result=analyze(p,'5y','A')
    assert result.result.value==direct.value
    assert result.result.boundary==direct.boundary
    assert result.exercise==first_exercise(w.prices,w.timestamps,direct.boundary,100)


def test_batch_records_error_and_continues(tmp_path):
    bad=tmp_path/'bad.csv'; good=tmp_path/'good.csv'
    make_csv(bad,[100,100,100]); make_csv(good,[100,110,99])
    rows=analyze_many([bad,good],'5y','A')
    assert [r['status'] for r in rows]==['error','ok']
    assert rows[0]['error'] and rows[1]['N']==2
