"""Nine views of committed evidence; no experiment can be started here."""
import hashlib
import math
import xml.etree.ElementTree as ET

import altair as alt
import pandas as pd
import streamlit as st

import saved_results as saved
from charting import reference_data, line_plot

TABS = ['Final selection', 'Overview', 'Scaling', 'Original vs revised & variants', 'Throughput & latency',
        'Memory', 'Correctness', 'Bottleneck explained', 'Method & data']

PRIMARY_CAPTION = "Each bar: the version's primary full-protocol session. Bars from different sessions are not a head-to-head; the binding same-session comparison is in the table."
SESSION_CAPTION = 'Absolute times shift by about 10 % between sessions on the same laptop, for both versions alike; the ratio stays at about 0.87-0.89. Therefore versions are compared within one session, and the binding decision uses the same-session rematch.'


class Dashboard:
    def __init__(self, bundle):
        self.b = bundle
        self.t = bundle['tables']
        self.base = self.t['baseline']['validated']
        self.pairs = saved.a_vs_b(bundle)

    def source(self, roles=('baseline',)):
        suffix = '' if self.b['store'].revision else ' (recorded; disk files not commit-verified)'
        return ' · '.join(f'03_results/runs/{saved.RUNS[r]} | commit {self.b["envs"][r]["git_commit"]}{suffix}' for r in roles)

    def table(self, frame, roles=('baseline',), note=None):
        st.caption(note or self.source(roles))
        st.dataframe(frame, hide_index=True, width='stretch')

    def chart(self, frame, x, y, xlabel, ylabel, roles=('baseline',), series='version',
              logx=False, logy=False, references=False, point=None, takeaway=None):
        st.caption(self.source(roles))
        d = frame.copy()
        if not d.empty:
            d = d[pd.to_numeric(d[y], errors='coerce').notna()]
            if logx: d = d[d[x].gt(0)]
            if logy: d = d[d[y].gt(0)]
        if d.empty:
            st.info('Not measured: no completed positive observations for this selection.')
            return
        st.altair_chart(line_plot(d,x,y,xlabel,ylabel,series,logx,logy,references),width='stretch')
        if logx and logy:
            axes = 'Both axes are log-scaled: power laws become straight lines; slope is the growth exponent.'
        elif logx or logy:
            axes = ('The x-axis' if logx else 'The y-axis')+' is log-scaled to show orders of magnitude; the other axis is linear.'
        else:
            axes = 'Both axes are linear, so equal distances mean equal absolute changes.'
        if point is None:
            if y == 'current_bytes':
                point = 'One point is a recorded tracemalloc sample for one version, case and seed.'
            elif y == 'value':
                point = 'One point is a count from a separate diagnostic worker, not a timing median.'
            else:
                point = 'One point is one seed/case: a median of five repeats (large A: its declared single trial).'
        if takeaway is None:
            if y == 'value':
                takeaway = 'The increase in recorded work explains the time scaling shown nearby.'
            elif y == 'events_per_s':
                takeaway = 'Higher is faster throughput; the saved cancel_churn cells show that A can still win.'
            else:
                takeaway = 'Compare versions only at the same workload, size and seed.'
        guide = (' Dashed linear/quadratic guides share a measured small-size anchor; they are references, not measured or extrapolated timings.'
                 if references and logx and logy else '')
        st.caption(f'How to read: x = {xlabel}; y = {ylabel}. {axes} {point}{guide} Takeaway: {takeaway}')

    def document_source(self, name):
        snapshot = self.b['store'].revision or 'disk files (not commit-verified)'
        st.caption(f'{name} · snapshot {snapshot}')

    def final_selection(self):
        st.header('Final selection: B = B3r')
        st.markdown('The binding decision and its qualifications are preserved below.')
        candidates = saved.selection_candidates(self.b)
        bars, outcomes = st.columns([2,3])
        with bars:
            self.candidate_chart(candidates,roles=('candidates','baseline','cross'),primary=True)
            self.session_effect_chart()
        with outcomes:
            self.table(saved.selection_table(self.b),roles=tuple(saved.RUNS))
            st.caption('Primary rows retain each version\'s original session, including the older cross-session fast comparison. The last row is the binding same-session rematch and its rejection.')
            self.document_source('00_docs/FINAL_SELECTION.md')
        st.subheader('Full final selection record')
        self.document_source('00_docs/FINAL_SELECTION.md')
        st.markdown(self.b['selection'])

    def candidate_chart(self, candidates,roles=('candidates','baseline'),primary=False):
        candidates = candidates[['version','geomean_s','cells','run','commit']].copy()
        st.caption(self.source(roles))
        st.altair_chart(alt.Chart(candidates).mark_bar().encode(
            x=alt.X('version:N',title='Version',sort=candidates.version.tolist()),
            y=alt.Y('geomean_s:Q',title='Official 100k geometric-mean replay time (s)'),
            color='version:N',tooltip=['version','geomean_s','cells','run','commit']),width='stretch')
        st.caption(PRIMARY_CAPTION if primary else 'How to read: x = version (categories); y = replay time (s), linear. One bar is the geometric mean of the 15 official 100k cell medians (five repeats per seed/case). Takeaway: B3r keeps competitive speed while addressing the reported robustness failures; speed alone did not select B.')

    def session_effect_chart(self):
        st.subheader('Session effect: B3r vs B3r_fast')
        st.caption(self.source(('baseline','cross','rematch')))
        d = saved.session_effect(self.b)
        d = d[d.geomean_s.notna()]
        if d.empty:
            st.info('Not measured: no complete official 100k pair.')
            return
        order = ['Primary sessions (different sessions)','Same session, alternating order (binding)']
        x = alt.X('comparison:N',title='Recorded comparison',sort=order,
                  axis=alt.Axis(labelAngle=0,labelExpr="datum.label === 'Primary sessions (different sessions)' ? ['Primary sessions', '(different sessions)'] : ['Same session, alternating order', '(binding)']"))
        y = alt.Y('geomean_s:Q',title='Official 100k geometric-mean replay time (s)',scale=alt.Scale(zero=True))
        bars = alt.Chart(d).mark_bar().encode(x=x,y=y,xOffset='version:N',color='version:N',
            tooltip=['comparison','version','geomean_s','ratio','run','commit'])
        labels = d.groupby('comparison',sort=False).agg(geomean_s=('geomean_s','max'),ratio=('ratio','first')).reset_index()
        labels['ratio_label'] = labels.ratio.map(lambda r:f'fast/B3r = {r:.3f}')
        text = alt.Chart(labels).mark_text(dy=-12,fontWeight='bold').encode(x=x,y=y,text='ratio_label:N')
        st.altair_chart((bars+text).properties(height=250),width='stretch')
        st.caption(SESSION_CAPTION)

    def overview(self):
        st.header('Thirty-second summary')
        st.markdown('[Final selection](?tab=Final%20selection) | [Raw repeats](?tab=Method%20%26%20data&view=raw#raw-repeats) | [Workload settings](?tab=Method%20%26%20data&view=settings#workload-settings)')
        st.caption(self.source())
        c1,c2,c3 = st.columns(3)
        geo = saved.official_geomeans(self.b).set_index('version')
        c1.metric('B3r official 100k geomean',f'{geo.loc["B3r","geomean_s"]:.4f} s')
        c2.metric('A replay limits',str(len(saved.replay_limits(self.b))))
        small = self.pairs[self.pairs.experiment.eq('official') & self.pairs['size'].eq(10000)
                           & self.pairs.workload.ne('cancel_churn')]
        speedups = small.groupby('workload').speedup.median()
        c3.metric('10k speedup range (non-churn)',f'{speedups.min():.0f}-{speedups.max():.0f}x')
        st.caption('Speedup range: workload medians across seeds of A/B3r, excluding cancel_churn.')
        st.markdown('**A is faster on cancel_churn.** Final B is B3r; it does not win every workload.')
        compact = saved.overview_speedups(self.b).pivot(index='workload',columns='size',values='label')
        compact.columns = [f'{int(n):,} events' for n in compact.columns]
        self.table(compact.reset_index())
        st.caption('Median A/B3r speedup across seeds: > marks a replay-limit lower bound, never an invented A time. A at 100k uses a single trial per seed; 1k/10k use five-repeat medians. Missing inputs remain unavailable.')
        scenario = st.selectbox('Summary chart scenario',sorted(compact.index),key='overview_scenario')
        source = self.base[self.base.experiment.eq('official') & self.base.workload.eq(scenario)
                           & self.base.phase.eq('replay') & self.base.version.isin(['A','B3r']) & self.base.complete]
        points = source.groupby(['version','size','run','commit']).median_s.median().reset_index()
        points['workload'] = scenario
        self.chart(points,'size','median_s','Incoming events (count)','Replay time (s)',logx=True,logy=True,
                   point='One point is the median across the available recorded seed medians; stopped A points are absent.',
                   takeaway='A wins on cancel_churn; growing-book scenarios show why the revised structures help.')

    def scaling(self):
        st.header('Construction, replay and individual-sale scaling')
        s = self.base
        axes = st.radio('Scaling axes',['log-log','linear axes'],horizontal=True,key='scale_axes')
        logarithmic = axes == 'log-log'
        scenario = st.selectbox('Official scenario',sorted(s[s.experiment.eq('official')].workload.unique()),key='scale_scenario')
        phase = st.selectbox('Phase (seconds)',['replay','construction','parse','total'],key='scale_phase')
        d = s[s.version.isin(['A','B3r']) & s.experiment.eq('official') & s.workload.eq(scenario) & s.phase.eq(phase)]
        takeaway = ('A wins here with a small live book.' if scenario == 'cancel_churn' else
                    'Compare the recorded growth with the linear/quadratic guides; B3r avoids A\'s repeated scans.')
        if not logarithmic and scenario != 'cancel_churn':
            takeaway = 'Compare absolute time growth across the measured sizes; B3r avoids repeated order-list scans.'
        if phase == 'construction': takeaway = 'This is empty-book setup; the Q7 view below measures actual book construction.'
        self.chart(d[d.complete],'size','median_s','Incoming events (count)',f'{phase} time (s)',
                   logx=logarithmic,logy=logarithmic,references=True,takeaway=takeaway)
        self.table(saved.fit_exponents(d))
        st.caption('OLS log(time) vs log(size), after median across seed medians; only completed sizes in the stated min/max range. No extrapolated points. A: warm-up + 5 at 1k/10k, single trial at 100k. Empty-book construction is separate; official LIMIT insertion work is in replay.')
        self.table(d[['workload','size','seed','version','phase','median_s','status','timing_protocol','run','commit']])
        st.subheader('Q7 liquidation: construction/reset and individual sells')
        qp = st.radio('Q7 phase',['construction','replay'],horizontal=True,key='liq_phase')
        q = s[s.experiment.eq('liquidation') & s.phase.eq(qp) & s.version.isin(['A','B3r'])].copy()
        q['series'] = q.version+' / '+q.workload
        self.chart(q[q.complete],'size','median_s','Orders in initial bid book (count)',
                   'Book construction (s)' if qp == 'construction' else 'Individual market sell (s)',
                   series='series',logx=logarithmic,logy=logarithmic,references=True,
                   takeaway='The 10/100/200% sales are separate trials; construction/reset is never hidden in the sale time.')
        self.table(q[['workload','size','seed','percent','version','phase','median_s','requested_sell_qty_units','status','run','commit']])
        self.table(saved.a_vs_b(self.b,qp).query('experiment == "liquidation"'))
        st.caption('10/100/200% sells; fresh bid book per repeat. Sale includes matching, state updates and fill-list construction. A above 10k: not measured (declared scope).')
        st.subheader('Official 1M attempts')
        self.table(self.pairs[self.pairs.experiment.eq('million')])
        st.caption('A: single trial without warm-up. A replay limits are > 600 s, not invented medians.')
        with st.expander('Queue concentration: four versus 1,000 levels'):
            self.table(s[s.experiment.eq('queue') & s.phase.eq('replay')])
        with st.expander('All recorded phases, including stopped cells'): self.table(s)

    def variants(self):
        st.header('Original vs revised & variants')
        part = st.selectbox('A vs B3r experiment',sorted(self.pairs.experiment.unique()),key='compare_part')
        self.table(self.pairs[self.pairs.experiment.eq(part)])
        st.subheader('B1 / B2 / B3 / B3r · ratio to best on the same input')
        geos = saved.official_geomeans(self.b)
        self.table(geos,roles=('candidates','baseline'))
        self.candidate_chart(geos)
        v = saved.variants(self.b)
        vp = st.selectbox('Variant experiment',['official','adversarial','post_attack'],key='variant_part')
        chosen = v[v.experiment.eq(vp)]
        self.table(chosen[['case_id','workload','size','seed','version','median_s','ratio_to_best','status','registration','run','commit']],roles=('candidates','baseline'))
        st.caption('Per-seed ratios, official at 100k. Candidate/B3r sessions differ; these are historical selection measurements, not a controlled rematch. Missing cells never enter the best time.')
        st.subheader('Robustness outcome and declared spike qualification')
        self.document_source('00_docs/FINAL_SELECTION.md')
        st.markdown(section(self.b['selection'],'## 2. Phase 4 result','## 4. Controlled'))
        st.subheader('B3r_fast: faster, but rejected')
        rematch = self.b['rematch']; loss = rematch['scenario_losses'][0]
        st.markdown(f'**Same-session: faster (official 100k ratio {rematch["official_100k_ratio"]:.3f}) but rejected by the pre-registered rule ({loss["workload"]}, size {loss["size"]:,}, ratio {loss["median_seed_ratio"]:.3f}). Final B stays {rematch["final_version"]}.** [Selection →](?document=selection)')
        rm = self.t['rematch']['validated'].query('phase == "replay"')
        same_grid = rm[rm.experiment.eq('official') & rm['size'].eq(100000) & rm.complete]
        same_geos = same_grid.groupby(['version','run','commit']).median_s.agg(
            cells='count',geomean_s=lambda s:math.exp(sum(map(math.log,s))/len(s))).reset_index()
        same_geos.loc[same_geos.cells.ne(15),'geomean_s'] = float('nan')
        self.table(same_geos,roles=('rematch',))
        self.table(rm[['case_id','version','workload','size','seed','median_s','status','run','commit']],roles=('rematch',))
        self.table(pd.DataFrame(rematch['scenarios']),roles=('rematch',))
        st.caption('Same session, alternating whole version cells; warm-up + 5. Geometric-mean ratio ≤ 0.90 and every scenario median OF seed ratios ≤ 1.05. One binding attempt, no further measurement.')
        st.subheader('Historical cross-session comparison (unchanged)')
        cross = self.b['cross']
        st.caption(self.source(('baseline','cross')))
        st.markdown(f'Outcome: **{cross["decision"]}**. Official 100k ratio **{cross["official_100k_ratio"]:.6f}**. Original per-cell bound; two unusually fast reference cells confounded it. The same-session per-scenario method was fixed before the binding rematch.')
        self.table(pd.DataFrame(cross['losses']),roles=('baseline','cross'))

    def latency(self):
        st.header('Throughput & processing latency')
        original = self.t['candidates']['validated']
        original = original[original.version.isin(['B1','B2','B3'])]
        fast = self.t['rematch']['validated']
        through = pd.concat([self.base,original,fast[fast.version.eq('B3r_fast')]],ignore_index=True)
        through = through[through.phase.eq('replay') & through.complete].copy()
        through['events_per_s'] = through.replayed_events / through.median_s
        tp = st.selectbox('Throughput experiment',sorted(through.experiment.unique()),key='through_part')
        selected = through[through.experiment.eq(tp)]
        tw = st.selectbox('Throughput workload',sorted(selected.workload.unique()),key='through_workload')
        self.chart(selected[selected.workload.eq(tw)],'size','events_per_s','Input size / scenario driver (count)',
                   'Replay throughput (events/s)',roles=('candidates','baseline','rematch'),logx=True,logy=True)
        self.table(selected[['case_id','version','workload','size','seed','replayed_events','median_s','events_per_s','run','commit']],roles=('candidates','baseline','rematch'))
        coverage = saved.coverage(self.b)
        self.table(coverage[coverage.experiment.eq(tp) & coverage['mode'].eq('timing') & coverage.status.ne('ok')])
        st.caption('Events/s = replayed events / completed replay seconds (large A: single trial). No throughput for stopped/not_run cells.')
        lat = saved.observations(self.b,'latency')
        spike = lat[lat.version.eq('B3r') & lat.workload.eq('spike_purge_at_threshold') & lat.segment.eq('all') & lat.event_type.eq('ALL')]
        st.caption(self.source())
        st.warning(f'Algorithmic spike — spike_purge_at_threshold: maximum recorded B3r latency {spike.max_ns.max()/1e6:.3f} ms. This declared heap-purge cost is distinct from runtime GC pauses. FINAL_SELECTION reports the literal 3x-filter qualification explicitly.')
        case = st.selectbox('Latency case (exact size and seed)',sorted(lat.case_id.unique()),key='lat_case',
                            format_func=lambda c:('Algorithmic spike: ' if 'spike_purge_at_threshold' in c else '')+c)
        lc = lat[lat.case_id.eq(case)]
        et = st.selectbox('Event type',sorted(lc.event_type.unique()),key='lat_type')
        self.table(lc[lc.event_type.eq(et)][['case_id','version','event_type','segment','n','p50_ns','p95_ns','p99_ns','max_ns','convention','run','commit']])
        st.caption('Nearest-rank recorded quantiles in ns; early/late compare uninterrupted submission bursts. Closed-loop service time excludes network and queueing, is not 1/throughput and does not establish overload capacity.')
        seg = st.selectbox('Histogram segment',sorted(lc.segment.unique()),key='lat_segment')
        hist = saved.observations(self.b,'latency_histogram')
        hist = hist[hist.case_id.eq(case) & hist.event_type.eq(et) & hist.segment.eq(seg)]
        st.caption(self.source())
        if not hist.empty:
            positive = hist[hist.bin_lo_ns.gt(0)]
            plot,note = st.columns([3,2])
            with plot:
                st.altair_chart(alt.Chart(positive).mark_bar(opacity=.55).encode(
                    x=alt.X('bin_lo_ns:Q',title='Processing latency histogram bin (ns)',scale=alt.Scale(type='log')),
                    x2='bin_hi_ns:Q',y=alt.Y('count:Q',title='Events in bin (count)'),color='version:N',
                    tooltip=['version','bin_lo_ns','bin_hi_ns','count','run','commit']).properties(height=310),width='stretch')
                st.caption('How to read: x = latency bin bounds (ns), logarithmic to span orders of magnitude; y = recorded events (count), linear. Each bar is one saved bin for this case, seed, event type, segment and version, not a five-repeat median. Takeaway: rare tail events differ from typical latency; compare early/late separately.')
            with note:
                st.info("Rare maxima of tens of milliseconds in large runs can come from Python's generation-2 garbage collection, rather than book logic: ATK-P7 traced such pauses with GC callbacks. GC was enabled equally for all versions. This attribution concerns the observed GC pauses, not every outlier (the report also records allocation costs). The B3r heap-purge spike marked above is a separate, algorithmic and declared cost.")
                self.document_source('07_attack/ATTACK_REPORT.md')
            if len(positive) != len(hist): st.info('Zero-start bins appear in the raw table, not on a logarithmic axis.')
            with st.expander('Exact histogram bins (not reconstructed from quantiles)'): self.table(hist)
        else: st.info('Histogram not measured for this selection.')
        cov = saved.coverage(self.b)
        self.table(cov[cov.case_id.eq(case) & cov['mode'].eq('latency')])

    def memory(self):
        st.header('Traced memory: growth and post-cancellation state')
        st.markdown('tracemalloc is traced Python allocation, **not RSS, native memory or asymptotic auxiliary space**. Peak and curve runs are separate; inclusion flags are retained.')
        mem = saved.observations(self.b,'memory',candidate_versions=('B1','B2','B3'))
        curve = mem[mem.measure.eq('curve') & mem.status.eq('ok')]
        workloads = sorted(curve.workload.unique())
        wl = st.selectbox('Memory workload',workloads,index=workloads.index('drift'),key='mem_workload')
        sizes = sorted(curve[curve.workload.eq(wl)]['size'].unique())
        size = st.selectbox('Memory input size',sizes,index=len(sizes)-1,key='mem_size')
        available = curve[curve.workload.eq(wl) & curve['size'].eq(size)]
        seed = st.selectbox('Memory seed',sorted(available.seed.unique()),key='mem_seed')
        yaxis = st.radio('Memory y-axis',['linear','log y-axis'],horizontal=True,key='mem_axis')
        mc = available[available.seed.eq(seed)]
        b3,others = st.columns(2)
        for panel,frame,title in [(b3,mc[mc.version.eq('B3')],'B3: history retained in stale heap keys'),
                                  (others,mc[mc.version.ne('B3')],'Other versions, including final B3r')]:
            with panel:
                st.subheader(title)
                self.chart(frame,'processed','current_bytes','Events processed (count)',
                           'Retained traced allocation (bytes)',roles=('candidates','baseline'),logy=yaxis == 'log y-axis',
                           takeaway='B3 retains stale heap keys under drift; B3r rebuilds the heap and fixes that history-dependent growth.')
        st.caption('Independent panels have independent y-scales; there is no dual y-axis. A logarithmic y-axis omits nonpositive samples from the plot only; all samples stay in the tables.')
        final = mc.loc[mc.groupby(['run','case_id','version']).processed.idxmax()]
        st.subheader('Final curve sample: state after churn')
        self.table(final[['case_id','version','processed','current_bytes','peak_bytes','live_orders','price_levels','heap_entries','stale_heap_prices','includes','run','commit']],roles=('candidates','baseline'))
        st.caption('Choose buildup/crowded for insertion growth, cancel_churn_memory for post-cancellation state, and drift for B3 vs B3r. Retained state differs from historical peak.')
        st.subheader('Peak by scenario and peak per live order')
        peaks = saved.memory_peaks(self.b)
        self.table(peaks[['case_id','version','workload','size','seed','peak_bytes','max_sampled_live_orders','peak_bytes_per_sampled_live_order','includes','run','commit']],roles=('candidates','baseline'))
        st.caption('Peak/order uses max live orders sampled on the same curve, not the final almost-empty book. Sampled normalization is not exact auxiliary bytes/order. Zero/unknown denominators stay missing. Curves exclude input/results/sample buffers; peak includes construction/current result, as recorded in includes.')
        cov = saved.coverage(self.b)
        self.table(cov[cov.workload.eq(wl) & cov['size'].eq(size) & cov['mode'].eq('memory') & cov.status.ne('ok')])

    def correctness(self):
        st.header('Correctness outcomes')
        proof = self.b['correctness']; store = self.b['store']
        note = f'05_evidence/final-b-registry-verification.json · captured commit {proof.get("commit","not recorded")} (dirty tested source; exact SHA in proof); no benchmark run'
        outcomes = []
        for suite in proof.get('suites',[]):
            text = store.text(suite['path'])
            verified = bool(text) and hashlib.sha256(text.encode()).hexdigest() == suite['sha256']
            outcomes.append(dict(suite=suite['suite'],tests=suite['tests'],outcome='passed; XML hash verified' if verified else 'evidence missing/hash differs',evidence=suite['path']))
        self.table(pd.DataFrame(outcomes),note=note)
        standard = next((s for s in proof.get('suites',[]) if s['suite'] == 'standard'),{})
        counts = standard.get('per_file',{})
        xml = store.text(standard.get('path','05_evidence/missing.xml')) or '<testsuites/>'
        cases = list(ET.fromstring(xml).iter('testcase'))
        own = {c.attrib['name'].split('[',1)[1].rsplit('-',1)[0] for c in cases if
               c.attrib.get('name','').startswith('test_final_b_matches_b3r_after_every_event[') and 'worked_example' not in c.attrib['name']}
        outcomes = [dict(check='Mutants killed',count=counts.get('test_mutants',0)-len(proof.get('registry',{}))-1,outcome='named kills; remaining cases are real-version controls'),
                    dict(check='A vs version stateful machines',count=sum(v for k,v in counts.items() if k.startswith('TestDifferential_')),outcome='after every event'),
                    dict(check='B3r vs fast stateful machine',count=counts.get('TestFastDifferential',0),outcome='passed'),
                    dict(check='Own datasets',count=len(own),outcome='B/B3r plain + counted; independent expected files'),
                    dict(check='Worked example',count=sum('test_final_b_matches_b3r_after_every_event[worked_example' in c.attrib.get('name','') for c in cases),outcome='plain + counted; expected result and contracts')]
        self.table(pd.DataFrame(outcomes),note=note)
        st.subheader('Per-worker result/book checks against A')
        self.table(pd.concat([self.t[r]['checks'] for r in saved.RUNS],ignore_index=True),roles=tuple(saved.RUNS))
        st.caption('Sampled result/book checks, not an independent reference over every benchmark event. Missing checks stay missing; stopped workers are not correctness passes.')
        st.subheader('Independent reference checks · attributed to the reviewer')
        self.document_source('00_docs/FINAL_SELECTION.md')
        st.markdown(section(self.b['selection'],'## 3. Revision','## 5. What'))
        with st.expander('Attack outcomes and limitations · ATTACK_REPORT.md'):
            self.document_source('07_attack/ATTACK_REPORT.md')
            st.markdown(self.b['attack'])
        with st.expander('Committed evidence index'):
            self.document_source('05_evidence/INDEX.md')
            st.markdown(store.text('05_evidence/INDEX.md') or 'Evidence index not committed.')

    def bottleneck(self):
        st.header('Bottleneck explained · code, counters and measured scaling')
        st.subheader('A: full-side rescan for each maker fill')
        st.caption(self.source())
        st.code('''# Excerpts: lob/book_a.py, _best_index and _match; omissions marked
for i, order in enumerate(orders):
    # ... choose best price, keeping earliest position on a tie ...
while remaining > 0:
    i = self._best_index(opposite, opposite_side)
    # ... fill and update remaining quantity ...
    if maker["qty_units"] == 0:
        del opposite[i]''',language='python')
        st.markdown('For **F fills** and **B live orders**, successful rescans cost **O(F·B)**; with final lookup and validation, O((F+1)(B+1)) worst case. Full sweep: F proportional to B, hence quadratic. Deletion also moves O(B) references. The measured slope supports this code argument; it does not prove it.')
        cnt = saved.observations(self.b,'counts',candidate_versions=('B1',))
        scans = cnt[cnt.version.eq('A') & cnt.experiment.eq('liquidation') & cnt.workload.eq('liquidation_100pct') & cnt.phase.eq('replay') & cnt.counter.eq('orders_scanned')]
        self.chart(scans,'size','value','Orders in bid book (count)','Maker-selection entries scanned (count)',logx=True,logy=True)
        self.table(scans[['case_id','version','size','seed','replayed_events','counter','value','run','commit']])
        lt = self.base[self.base.version.eq('A') & self.base.experiment.eq('liquidation') & self.base.workload.eq('liquidation_100pct') & self.base.phase.eq('replay')]
        self.table(saved.fit_exponents(lt))
        st.caption('A time exponent uses only the measured supplementary range through 10k. No 100k A result is extrapolated. A single sale can scan many entries.')
        st.subheader('B1: far-end insertion in a sorted price list')
        st.caption(self.source())
        st.code('''# Excerpt: lob/book_b.py, _rest (new level)
i = bisect_left(side.prices, side.sign * price)
if self.counters is not None:
    self.counters.price_list_shifts += len(side.prices) - i
side.prices.insert(i, side.sign * price)''',language='python')
        st.markdown('Bisect is O(log P), but insert shifts O(P) references. far_end_flicker repeats insert/cancel against a deep book: O(P) each, O(P²) when flicker count grows with P. B3r uses heap prices with the declared amortized rebuild.')
        shifts = cnt[cnt.version.eq('B1') & cnt.workload.eq('far_end_flicker') & cnt.phase.eq('replay') & cnt.counter.eq('price_list_shifts')]
        self.chart(shifts,'size','value','Live levels / flickers (count)','Price-list references shifted (count)',logx=True,logy=True)
        self.table(shifts[['case_id','version','size','seed','counter','value','run','commit']])
        v = saved.variants(self.b)
        self.table(saved.fit_exponents(v[v.version.eq('B1') & v.workload.eq('far_end_flicker')]))


    def raw_repeat_view(self):
        st.subheader('Raw repeats',anchor='raw-repeats')
        role = st.selectbox('Source run',list(saved.RUNS),index=list(saved.RUNS).index('baseline'),
                            format_func=lambda r:saved.RUNS[r],key='raw_role')
        raw = self.t[role]['timing']
        case = st.selectbox('Case',sorted(raw.case_id.unique()),key='raw_case')
        choices = sorted(raw[raw.case_id.eq(case)].version.unique())
        version = st.selectbox('Version',choices,index=choices.index('B3r') if 'B3r' in choices else 0,key='raw_version')
        phases = sorted(raw[raw.case_id.eq(case) & raw.version.eq(version)].phase.unique())
        phase = st.selectbox('Raw phase',phases,index=phases.index('replay') if 'replay' in phases else 0,key='raw_phase')
        rows = saved.raw_repeats(self.b,role,case,version,phase)
        repeats,statistic = st.columns([3,1])
        with repeats:
            self.table(rows[['case_id','version','phase','row_kind','repeat','seconds','warmup','status','repeats_requested','run','commit']],roles=(role,))
        with statistic:
            st.caption(self.source((role,)))
            summary = self.t[role]['validated']
            summary = summary[summary.case_id.eq(case) & summary.version.eq(version) & summary.phase.eq(phase)]
            if len(summary) == 1 and summary.iloc[0].complete:
                row = summary.iloc[0]
                if row.repeats_requested == 1:
                    st.metric('Selected single trial (s)',f'{row.median_s:.6g}')
                else:
                    st.metric('Selected median (s)',f'{row.median_s:.6g}')
                st.caption(f'{int(row.completed_repeats)}/{int(row.repeats_requested)} measured repeats; warm-up excluded.')
            else:
                status = summary.iloc[0].status if len(summary) else 'not measured'
                st.info(f'Median unavailable: {status}. No failed or missing repeat is filled.')
        st.caption('Every saved repeat appears above in seconds, including the marked warm-up. The adjacent statistic uses only a complete valid measured set; large A remains a single trial.')
        with st.expander('Other raw tables and all original columns'):
            name = st.selectbox('Saved table',[n for n in self.t[role] if n != 'validated'],key='raw_table')
            self.table(self.t[role][name],roles=(role,))

    def method(self):
        st.header('Method & data')
        st.markdown('Inputs generated/parsed outside replay; fresh book per repeat. B: warm-up + five repeats. Parsing/construction/replay/total separate. Timing, latency, tracemalloc and counters use independent workers.')
        self.raw_repeat_view()
        st.subheader('Workload settings',anchor='workload-settings')
        self.table(saved.workload_settings(self.b),roles=tuple(saved.RUNS))
        st.caption('Per-case/version settings include protocol and own/supplied origin. Generator commands are reconstructed from saved parameters, never executed. SHA-256 values are recorded input archive hashes, not hashes of newly generated files.')
        with st.expander('Per-seed A vs B3r detail (original table)'):
            self.table(self.pairs[self.pairs.experiment.isin(['official','million'])][
                ['workload','size','seed','A_time','B3r_s','speedup_label','A_protocol','run','commit']])
        with st.expander('Completed vs requested repeats; stopped / invalid / missing'):
            self.table(self.base[['case_id','version','phase','status','completed_repeats','repeats_requested','complete','run','commit']])
            cov = saved.coverage(self.b)
            self.table(cov[cov.status.ne('ok')])
            st.caption('not_run is a recorded skip. Larger supplementary A cells are not measured (declared scope); no values are filled.')
        env = [dict(role=r,run=saved.RUNS[r],commit=e['git_commit'],python=e['python'],gc=e.get('gc_policy'),
                    limit_s=e.get('per_replay_limit_s'),traced_limit_bytes=e.get('traced_peak_limit_bytes'),source_sha256=e.get('source_sha256')) for r,e in self.b['envs'].items()]
        self.table(pd.DataFrame(env),roles=tuple(saved.RUNS))
        for role in saved.RUNS:
            with st.expander('Environment: '+role):
                st.caption(self.source((role,))); st.json(self.b['envs'][role])
        st.subheader('Declared deviations and decisions: saved spec snapshot')
        st.caption(self.source())
        spec = self.b['snapshots']['baseline']
        st.markdown(section(spec,'### Declared baseline scope deviation'))
        with st.expander('D1-D4: rebuild, memory judgement, input fix and added-case fairness'):
            st.caption(self.source())
            st.markdown(section(spec,'## Post-attack decisions D1-D4','### Declared baseline scope'))
        st.caption('Bounds require phase_time_limit on replay; subprocess/setup/partial failures have no replay bound. Stopped/not_run/not-measured cells are never filled or extrapolated.')


def section(text, start, end=None):
    part = text[text.find(start):] if start in text else 'Not recorded in this committed source.'
    return part.split(end)[0] if end else part


def main():
    b = saved.load_bundle(saved.head())
    st.set_page_config(page_title='AIF · Limit order book',page_icon='◈',layout='wide')
    if b['store'].revision is None:
        st.warning('Reading files from disk (no git checkout): values are not verified against a commit.')
    st.title('Limit order book · evidence explorer')
    st.caption('Assignment 1 / FIN71055 · Saved observations, explicit limits, reproducible decisions')
    st.sidebar.header('Committed evidence')
    st.sidebar.code(b['store'].revision[:12] if b['store'].revision else 'Disk files · unverified')
    st.sidebar.caption('HEAD snapshot only. No working-tree CSVs, engine execution or network fetches.'
                       if b['store'].revision else 'Allowlisted disk files. No commit verification, engine execution or network fetches.')
    st.sidebar.markdown('[Final selection](?document=selection)')
    st.sidebar.info('B = B3r. Historical labels are preserved.')
    view = Dashboard(b)
    functions = [view.final_selection,view.overview,view.scaling,view.variants,view.latency,view.memory,view.correctness,view.bottleneck,view.method]
    requested = st.query_params.get('tab','Final selection')
    if st.query_params.get('document') == 'selection': requested = 'Final selection'
    selected = requested if requested in TABS else 'Final selection'
    for tab, render in zip(st.tabs(TABS,default=selected),functions):
        with tab: render()
