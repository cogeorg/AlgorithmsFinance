"""Saved-file analysis gates and Streamlit's real application smoke test."""
import math
import json
from pathlib import Path
import sys

import pandas as pd
import pyarrow as pa
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '04_dashboard'))
import saved_results as saved
import views

TABS = ['Final selection', 'Overview', 'Scaling', 'Original vs revised & variants',
        'Throughput & latency', 'Memory', 'Correctness',
        'Bottleneck explained', 'Method & data']

PRIMARY_CAPTION = "Each bar: the version's primary full-protocol session. Bars from different sessions are not a head-to-head; the binding same-session comparison is in the table."
SESSION_CAPTION = 'Absolute times shift by about 10 % between sessions on the same laptop, for both versions alike; the ratio stays at about 0.87-0.89. Therefore versions are compared within one session, and the binding decision uses the same-session rematch.'


@pytest.fixture(scope='module')
def bundle():
    return saved.load_bundle(saved.head())


def test_official_headlines_match_committed_csvs(bundle):
    got = saved.official_geomeans(bundle).set_index('version')
    for version, role in [('B1','candidates'),('B2','candidates'),('B3','candidates'),('B3r','baseline')]:
        rows = bundle['tables'][role]['summary']
        rows = rows[(rows.version == version) & (rows.experiment == 'official')
                    & (rows['size'] == 100000) & (rows.phase == 'replay')]
        assert len(rows) == 15 and set(rows.status) == {'ok'}
        expected = math.exp(math.fsum(math.log(v) for v in rows.median_s) / 15)
        assert got.loc[version, 'geomean_s'] == pytest.approx(expected, rel=1e-12)
        assert got.loc[version, 'cells'] == 15


def test_stopped_a_is_bound_only_not_a_time(bundle):
    limits = saved.replay_limits(bundle)
    raw = bundle['tables']['baseline']['stops']
    expected = raw[(raw.version == 'A') & (raw.phase == 'replay')
                   & (raw.reason == 'phase_time_limit')].case_id.nunique()
    assert len(limits) == expected == 13
    assert set(limits.bound_s) == {600}
    assert limits.time_label.str.startswith('> 600 s').all()


@pytest.mark.parametrize('fault', ['duplicate', 'missing', 'nan', 'stopped', 'not_run'])
def test_bad_cells_never_enter_medians(fault):
    summary = pd.DataFrame([dict(case_id='x', version='A', phase='replay', status='ok',
        median_s=3., completed_repeats=5, repeats_requested=5)])
    timing = pd.DataFrame([dict(case_id='x', version='A', phase='replay', status='ok',
        repeat=i, seconds=i+1., warmup=False) for i in range(5)])
    cells = pd.DataFrame([dict(case_id='x', version='A', mode='timing', status='ok')])
    if fault == 'duplicate': timing = pd.concat([timing, timing.iloc[:1]], ignore_index=True)
    if fault == 'missing': timing = timing.iloc[:4]
    if fault == 'nan': timing.loc[0,'seconds'] = float('nan')
    if fault in ('stopped','not_run'): cells.loc[0,'status'] = fault
    got = saved.validate_summary(summary, timing, cells).iloc[0]
    assert not got.complete and pd.isna(got.median_s)


def test_fit_uses_measured_points_only():
    rows = pd.DataFrame([dict(version='A', size=n, median_s=n*n, complete=True)
                         for n in (10,100,1000)] +
                        [dict(version='A', size=10000, median_s=float('nan'), complete=False)])
    fit = saved.fit_exponents(rows).iloc[0]
    assert fit.exponent == pytest.approx(2.) and fit.points == 3
    assert fit.min_size == 10 and fit.max_size == 1000


def test_loader_restricts_paths_and_uses_a_fixed_commit(bundle):
    store = bundle['store']
    if saved.head() is not None:
        assert isinstance(store,saved.CommittedStore) and not isinstance(store,saved.DiskStore)
        assert len(store.revision) == 40
    else:
        assert isinstance(store,saved.DiskStore)
        assert store.revision is None
        app = AppTest.from_file(str(ROOT/'04_dashboard/app.py'),default_timeout=120).run()
        assert not app.exception,[e.message for e in app.exception]
        banner = 'Reading files from disk (no git checkout): values are not verified against a commit.'
        assert banner in [w.value for w in app.warning]
        assert app.main.children[0].value == banner
    with pytest.raises(ValueError): store.text('01_code/lob/book_a.py')
    with pytest.raises(ValueError): store.text('03_results/runs/../../README.md')
    assert store.text('05_evidence/not_a_committed_evidence_file.txt') is None
    assert 'Final Version B: B3r' in bundle['selection']


def test_regression_long_committed_git_blob_path(bundle):
    assert bundle['rematch']['decision'] == 'rejected'
    assert bundle['rematch']['scenario_losses'][0]['workload'] == 'dead_slot_rebuild'
    assert bundle['rematch']['official_100k_ratio'] == pytest.approx(.8731749844948045)


def test_b1_counter_example_is_measured(bundle):
    shown = saved.observations(bundle,'counts',candidate_versions=('B1',))
    shown = shown[shown.version.eq('B1') & shown.workload.eq('far_end_flicker') & shown.counter.eq('price_list_shifts')]
    raw = bundle['tables']['baseline']['counts']
    raw = raw[raw.version.eq('B1') & raw.workload.eq('far_end_flicker') & raw.counter.eq('price_list_shifts')]
    assert len(shown) == len(raw) > 0
    assert shown.value.tolist() == raw.value.tolist()


def test_all_tabs_render_and_headlines_match_csv(bundle,monkeypatch):
    import socket
    local_connect = socket.socket.connect
    def no_external_network(sock,address):
        # Windows asyncio builds its internal socketpair using loopback TCP.
        if sock.family == getattr(socket,'AF_UNIX',None) or address[0] in ('127.0.0.1','::1'):
            return local_connect(sock,address)
        raise AssertionError('dashboard attempted an external network connection')
    monkeypatch.setattr(socket.socket,'connect',no_external_network)
    app = AppTest.from_file(str(ROOT / '04_dashboard/app.py'), default_timeout=120).run()
    assert not app.exception, [e.message for e in app.exception]
    assert [t.label for t in app.tabs] == TABS
    for tab in app.tabs:
        assert len(tab.dataframe) + len(tab.markdown) + len(tab.metric) > 0, tab.label
    metrics = {m.label:m.value for m in app.metric}
    geo = saved.official_geomeans(bundle).set_index('version').loc['B3r','geomean_s']
    assert metrics['B3r official 100k geomean'] == f'{geo:.4f} s'
    assert metrics['A replay limits'] == str(len(saved.replay_limits(bundle)))
    assert any('cancel_churn' in m.value and 'A is faster' in m.value for m in app.markdown)
    overview = next(t for t in app.tabs if t.label == 'Overview')
    assert len(overview.metric) == 3 and len(overview.dataframe) == 1
    assert len(overview.get('vega_lite_chart')) == 1
    # Streamlit's markdown renderer strips surrounding whitespace.
    assert any(m.value == bundle['selection'].strip() for m in app.tabs[0].markdown)
    assert not overview.expander


def test_fast_rematch_score_is_from_same_session_csv(bundle):
    raw = bundle['tables']['rematch']['summary']
    raw = raw[raw.phase.eq('replay') & raw.experiment.eq('official') & raw['size'].eq(100000)]
    times = raw.pivot(index='case_id',columns='version',values='median_s')
    assert len(times) == 15
    ratio = math.exp(sum(math.log(v) for v in times.B3r_fast / times.B3r) / len(times))
    assert ratio == pytest.approx(bundle['rematch']['official_100k_ratio'],rel=1e-12)


def test_selection_primary_bars_binding_table_and_session_effect(bundle):
    app = AppTest.from_file(str(ROOT/'04_dashboard/app.py'),default_timeout=120).run()
    assert not app.exception,[e.message for e in app.exception]
    tab = app.tabs[0]
    plots = tab.get('vega_lite_chart')
    assert len(plots) == 2
    def datasets(chart):
        return [pa.ipc.open_stream(d.data.data).read_all().to_pandas() for d in chart.proto.datasets]
    primary = next(d for d in datasets(plots[0]) if 'version' in d)
    assert primary.version.tolist() == ['B1','B2','B3','B3r','B3r_fast']
    frames = [d.value for d in tab.dataframe if 'geomean_s' in d.value]
    assert len(frames) == 1
    shown = frames[0]
    assert len(shown) == 6 and shown.version.eq('B3r_fast').sum() == 1
    assert not shown.isna().any().any()
    assert not shown.astype(str).isin(['None','nan','<NA>']).any().any()
    for version,role in [('B1','candidates'),('B2','candidates'),('B3','candidates'),
                         ('B3r','baseline'),('B3r_fast','cross')]:
        row = primary[primary.version.eq(version)].iloc[0]
        raw = bundle['tables'][role]['summary'].query(
            'phase == "replay" and experiment == "official" and size == 100000 and version == @version')
        assert len(raw) == 15
        expected = math.exp(sum(map(math.log,raw.median_s))/15)
        assert row.geomean_s == pytest.approx(expected,rel=1e-12)
        assert row.run == saved.RUNS[role] and row.commit == bundle['envs'][role]['git_commit']
        table_row = shown[shown.version.eq(version)].iloc[0]
        assert table_row.geomean_s == f'{expected:.4f}'
        assert table_row.run == row.run and table_row.commit == row.commit
        assert table_row.outcome == ('final B' if version == 'B3r' else
            'faster; rejected by the pre-registered rule' if version == 'B3r_fast' else 'excluded')
    binding = shown.iloc[-1]
    assert binding.version == 'B3r_fast vs B3r, same session (binding)'
    assert binding.geomean_s == '' and binding.ratio == '0.873'
    assert '25 of 27' in binding.detail and '26 of 27' in binding.detail
    assert 'dead_slot_rebuild 1k (1.068)' in binding.detail
    assert binding.run == saved.RUNS['rematch'] and binding.commit == bundle['envs']['rematch']['git_commit']
    assert shown[shown.version.eq('B3r_fast')].ratio.iloc[0] == '0.887'
    assert set(shown.run) == set(saved.RUNS.values())
    effects = next(d for d in datasets(plots[1]) if 'version' in d)
    assert len(effects) == 4
    for label,roles,record in [
        ('Primary sessions (different sessions)',{'B3r':'baseline','B3r_fast':'cross'},'cross'),
        ('Same session, alternating order (binding)',{'B3r':'rematch','B3r_fast':'rematch'},'rematch')]:
        pair = effects[effects.comparison.eq(label)].set_index('version')
        assert set(pair.index) == set(roles)
        for version,role in roles.items():
            raw = bundle['tables'][role]['summary'].query(
                'phase == "replay" and experiment == "official" and size == 100000 and version == @version')
            assert pair.loc[version,'geomean_s'] == pytest.approx(math.exp(sum(map(math.log,raw.median_s))/15))
            assert pair.loc[version,'run'] == saved.RUNS[role]
            assert pair.loc[version,'commit'] == bundle['envs'][role]['git_commit']
        assert pair.loc['B3r_fast','geomean_s']/pair.loc['B3r','geomean_s'] == pytest.approx(bundle[record]['official_100k_ratio'])
    labels = next(d for d in datasets(plots[1]) if 'ratio_label' in d)
    assert set(labels.ratio_label) == {'fast/B3r = 0.887','fast/B3r = 0.873'}
    spec = json.loads(plots[1].proto.spec)
    assert spec['layer'][0]['encoding']['xOffset']['field'] == 'version'
    captions = [c.value for c in tab.caption]
    assert PRIMARY_CAPTION in captions and SESSION_CAPTION in captions
    assert not any('older scenario-count wording' in c for c in captions)


def test_histogram_is_a_distribution_not_rebuilt_from_percentiles(bundle):
    h = saved.observations(bundle,'latency_histogram')
    q = saved.observations(bundle,'latency')
    case = 'official_buildup_1000_s42_l1000'
    h = h[h.case_id.eq(case) & h.event_type.eq('ALL') & h.segment.eq('all')]
    q = q[q.case_id.eq(case) & q.event_type.eq('ALL') & q.segment.eq('all')]
    totals = h.groupby('version')['count'].sum()
    pd.testing.assert_series_equal(totals.sort_index(),q.set_index('version').n.sort_index(),check_names=False)
    assert len(h) > 4


def test_dashboard_interactive_views_render(bundle):
    app = AppTest.from_file(str(ROOT / '04_dashboard/app.py'),default_timeout=120).run()
    app.selectbox(key='scale_phase').select('construction')
    app.radio(key='liq_phase').set_value('replay')
    app.selectbox(key='variant_part').select('post_attack')
    app.selectbox(key='mem_workload').select('cancel_churn_memory')
    app.radio(key='scale_axes').set_value('linear axes')
    app.radio(key='mem_axis').set_value('log y-axis')
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    scaling = next(t for t in app.tabs if t.label == 'Scaling')
    for chart in scaling.get('vega_lite_chart'):
        spec = json.loads(chart.proto.spec)
        assert 'layer' not in spec
        assert spec['encoding']['x']['scale']['type'] == 'linear'
        assert spec['encoding']['y']['scale']['type'] == 'linear'
    memory = next(t for t in app.tabs if t.label == 'Memory')
    assert len(memory.get('vega_lite_chart')) == 2
    for chart in memory.get('vega_lite_chart'):
        assert json.loads(chart.proto.spec)['encoding']['y']['scale']['type'] == 'log'
    app.selectbox(key='lat_case').select('official_buildup_10000_s42_l1000')
    app.run()
    app.selectbox(key='lat_segment').select('early')
    app.run()
    assert not app.exception, [e.message for e in app.exception]


def test_subprocess_timeouts_do_not_create_replay_bounds(bundle):
    raw = bundle['tables']['baseline']['stops'].copy()
    raw['reason'] = 'subprocess_wall_time_limit'
    fake = {'tables':{'baseline':{'stops':raw}}}
    assert saved.replay_limits(fake).empty


def test_compact_overview_is_seed_median_with_explicit_bounds(bundle):
    assert hasattr(saved,'overview_speedups')
    shown = saved.overview_speedups(bundle).set_index(['workload','size'])
    assert len(shown) == 15
    raw = bundle['tables']['baseline']['summary']
    a = raw[raw.version.eq('A') & raw.phase.eq('replay') & raw.experiment.eq('official')]
    b = raw[raw.version.eq('B3r') & raw.phase.eq('replay') & raw.experiment.eq('official')]
    limits = saved.replay_limits(bundle).set_index('case_id').bound_s
    for (workload,size),rows in b.groupby(['workload','size']):
        matches = a[a.case_id.isin(rows.case_id)].set_index('case_id')
        if matches.status.eq('ok').all():
            ratios = [matches.loc[r.case_id,'median_s']/r.median_s for r in rows.itertuples()]
            assert shown.loc[(workload,size),'kind'] == 'measured'
        else:
            ratios = [limits[r.case_id]/r.median_s for r in rows.itertuples()]
            assert shown.loc[(workload,size),'label'].startswith('> ')
            assert shown.loc[(workload,size),'kind'] == 'lower bound'
        assert shown.loc[(workload,size),'median_speedup'] == pytest.approx(pd.Series(ratios).median())
        if shown.loc[(workload,size),'kind'] == 'lower bound':
            displayed = float(shown.loc[(workload,size),'label'].split()[1].removesuffix('x'))
            assert displayed <= pd.Series(ratios).median()


def test_reference_lines_are_labelled_power_law_guides():
    assert hasattr(views,'reference_data') and hasattr(views,'line_plot')
    frame = pd.DataFrame(dict(version=['A','A','A'],size=[10,100,1000],median_s=[.1,1,10]))
    guides = views.reference_data(frame,'size','median_s')
    assert set(guides.guide) == {'linear (slope 1)','quadratic (slope 2)'}
    for name,power in [('linear (slope 1)',1),('quadratic (slope 2)',2)]:
        points = guides[guides.guide.eq(name)].sort_values('size')
        assert points.median_s.iloc[-1]/points.median_s.iloc[0] == pytest.approx(
            (points['size'].iloc[-1]/points['size'].iloc[0])**power)
    log = views.line_plot(frame,'size','median_s','Events (count)','Time (s)',logx=True,logy=True,references=True).to_dict()
    assert len(log['layer']) == 2 and 'strokeDash' in log['layer'][1]['encoding']
    assert log['layer'][0]['encoding']['x']['scale']['type'] == 'log'
    linear = views.line_plot(frame,'size','median_s','Events (count)','Time (s)',references=True).to_dict()
    assert 'layer' not in linear and linear['encoding']['y']['scale']['type'] == 'linear'


def test_raw_repeat_view_preserves_warmup_and_every_measured_value(bundle):
    assert hasattr(saved,'raw_repeats')
    case = 'official_buildup_1000_s42_l1000'
    shown = saved.raw_repeats(bundle,'baseline',case,'B3r','replay')
    raw = bundle['tables']['baseline']['timing']
    raw = raw[raw.case_id.eq(case) & raw.version.eq('B3r') & raw.phase.eq('replay')]
    assert len(shown) == 6 and shown.row_kind.eq('warm-up').sum() == 1
    assert shown.row_kind.eq('measured').sum() == 5
    pd.testing.assert_frame_equal(shown[raw.columns].reset_index(drop=True),raw.reset_index(drop=True))
    stopped = saved.raw_repeats(bundle,'baseline','official_buildup_100000_s42_l1000','A','replay')
    assert stopped.status.eq('stopped').all() and stopped.seconds.isna().all()


def test_workload_settings_keep_protocol_origin_and_checksums(bundle):
    assert hasattr(saved,'workload_settings')
    settings = saved.workload_settings(bundle)
    assert {'generator_command','timing_protocol','own','data_origin','input_sha256','percent','levels','seed'} <= set(settings)
    assert settings.input_sha256.str.len().eq(64).all()
    assert set(settings.data_origin) == {'own','supplied'}
    assert settings[settings.version.eq('A') & settings['size'].eq(100000)].timing_protocol.str.contains('single').all()


def test_method_raw_view_and_clarity_captions(bundle):
    app = AppTest.from_file(str(ROOT/'04_dashboard/app.py'),default_timeout=120).run()
    app.selectbox(key='raw_role').select('baseline')
    app.run()
    app.selectbox(key='raw_case').select('official_buildup_1000_s42_l1000')
    app.run()
    app.selectbox(key='raw_version').select('B3r')
    app.run()
    assert not app.exception,[e.message for e in app.exception]
    method = next(t for t in app.tabs if t.label == 'Method & data')
    assert any(h.value == 'Raw repeats' for h in method.subheader)
    assert any(h.value == 'Workload settings' for h in method.subheader)
    pairs = saved.a_vs_b(bundle)
    original_detail = pairs[pairs.experiment.isin(['official','million'])][
        ['workload','size','seed','A_time','B3r_s','speedup_label','A_protocol','run','commit']]
    base = bundle['tables']['baseline']['validated']
    original_completeness = base[['case_id','version','phase','status','completed_repeats',
                                  'repeats_requested','complete','run','commit']]
    coverage = saved.coverage(bundle)
    for original in [original_detail,original_completeness,coverage[coverage.status.ne('ok')]]:
        match = [d.value for d in method.dataframe if list(d.value.columns) == list(original.columns)]
        assert len(match) == 1
        # Streamlit/Arrow normalizes object string columns to pandas strings.
        # Compare every value/row/column, independent of serialization dtype.
        pd.testing.assert_frame_equal(match[0].reset_index(drop=True),
                                      original.reset_index(drop=True),check_dtype=False)
    median = bundle['tables']['baseline']['summary'].query(
        'case_id == "official_buildup_1000_s42_l1000" and version == "B3r" and phase == "replay"').median_s.iloc[0]
    assert {m.label:m.value for m in method.metric}['Selected median (s)'] == f'{median:.6g}'
    captions = [c.value for c in app.caption]
    assert sum(c.startswith('How to read:') or c in (PRIMARY_CAPTION,SESSION_CAPTION)
               for c in captions) >= len(app.get('vega_lite_chart'))
    assert any('generation-2' in item.value for item in app.info)
    assert any('Algorithmic spike' in item.value for item in app.warning)
