"""Analysis of saved evidence. Prefer committed blobs; label a no-Git fallback.

Adapted from aif-exercise/assets/dashboard_app.py: incomplete/invalid cells
are quarantined before aggregation. Each measured seed retains its identity.
"""
from functools import lru_cache
from io import StringIO
import json
import math
from pathlib import Path, PurePosixPath
import re
import statistics
import subprocess

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'Submissions/BuehlerLaurin/Assignment1/'
RUNS = {
    'candidates': '20261122T012525Z_5eaeb03_phase4',
    'baseline': '20261122T130145Z_00bb1ad_phase4_b3r_20261122',
    'cross': '20261122T200528Z_8a22753_phase4_b3r_fast_20261122',
    'rematch': '20261122T210801Z_e4fd928_phase4_b3r_fast_rematch_20261122',
}


def head():
    try:
        return subprocess.run(['git','rev-parse','HEAD'], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError,subprocess.CalledProcessError):
        return None


def check_path(relative):
    parts = PurePosixPath(relative).parts
    if ('..' in parts or '\\' in relative or relative.startswith('/') or not
        (relative.startswith('03_results/runs/') or relative.startswith('05_evidence/')
         or relative in ('00_docs/FINAL_SELECTION.md','07_attack/ATTACK_REPORT.md'))):
        raise ValueError('dashboard data path outside the allowlist')


class CommittedStore:
    """git show is read-only; working-tree files (including dirty CSVs) are ignored."""
    def __init__(self, revision):
        if not re.fullmatch(r'[0-9a-f]{40}', revision):
            raise ValueError('a full committed revision is required')
        self.revision = revision

    @lru_cache(maxsize=80)
    def text(self, relative):
        check_path(relative)
        # The trailing -- forces revision syntax. Without it, Windows Git may
        # stat the long SHA:path as a filename and fail before resolving a blob.
        cp = subprocess.run(['git','show',f'{self.revision}:{PREFIX}{relative}','--'],
                            cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        if cp.returncode == 0:
            return cp.stdout
        # With explicit revision syntax, an absent optional blob is reported
        # as "bad revision" rather than "path does not exist in" on Windows.
        if ('does not exist in' in cp.stderr or 'exists on disk, but not in' in cp.stderr
                or 'bad revision' in cp.stderr):
            return None
        raise RuntimeError(cp.stderr.strip())

    def json(self, path):
        text = self.text(path)
        return json.loads(text) if text else {}


class DiskStore(CommittedStore):
    """ZIP/copied-submission fallback; metadata is not commit-verified."""
    def __init__(self, root):
        self.revision = None
        self.root = Path(root).resolve()

    @lru_cache(maxsize=80)
    def text(self, relative):
        check_path(relative)
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('dashboard data path resolves outside the submission')
        return path.read_text(encoding='utf-8') if path.is_file() else None


def validate_summary(summary, timing, cells):
    """Trust neither a partial summary nor a duplicated raw repeat.

    Values are recomputed only when all requested raw repeats and the worker
    completed, and checked against the saved median. Missing values stay missing.
    """
    out = summary.copy()
    if out.empty:
        return out.assign(complete=pd.Series(dtype=bool))
    keys = ['case_id','version','phase']
    measured = timing[~timing.warmup.astype(str).str.lower().eq('true')].copy()
    raw_groups = {k:g for k,g in measured.groupby(keys, dropna=False)}
    worker = cells[cells['mode'].eq('timing')].set_index(['case_id','version'])
    complete, values, statuses = [], [], []
    for row in out.to_dict('records'):
        g = raw_groups.get(tuple(row[k] for k in keys), pd.DataFrame())
        req = row['repeats_requested']
        good = (row['status'] == 'ok' and not g.empty and len(g) == req
                and row['completed_repeats'] == req and set(g.repeat) == set(range(int(req)))
                and g.status.eq('ok').all() and not g.repeat.duplicated().any()
                and pd.to_numeric(g.seconds, errors='coerce').map(
                    lambda s: pd.notna(s) and math.isfinite(s) and s >= 0).all())
        wk = (row['case_id'],row['version'])
        state = worker.loc[wk,'status'] if wk in worker.index else 'missing worker'
        # Parsing is separate, but cannot certify an interrupted replay cell.
        good = good and isinstance(state,str) and state == 'ok'
        value = statistics.median(g.seconds) if good else float('nan')
        good = good and math.isclose(value,float(row['median_s']),rel_tol=1e-10,abs_tol=1e-12)
        complete.append(bool(good))
        values.append(value if good else float('nan'))
        statuses.append('ok' if good else (state if state != 'ok' else
            row['status'] if row['status'] != 'ok' else 'invalid/partial repeats'))
    out['complete'],out['median_s'],out['status'] = complete,values,statuses
    return out


@lru_cache(maxsize=2)
def load_bundle(revision=None):
    revision = revision or head()
    store = CommittedStore(revision) if revision else DiskStore(ROOT)
    tables, envs, snapshots = {}, {}, {}
    for role, run in RUNS.items():
        prefix = f'03_results/runs/{run}/'
        envs[role] = store.json(prefix+'env.json')
        commit = envs[role].get('git_commit','not recorded')
        tables[role] = {}
        files = ['summary','timing','cells','stops','checks']
        if role in ('baseline','candidates'):
            files += ['counts','memory','latency','latency_histogram']
        for name in files:
            text = store.text(prefix+name+'.csv')
            frame = pd.read_csv(StringIO(text)) if text else pd.DataFrame()
            frame['run'], frame['commit'] = run, commit
            tables[role][name] = frame
        t = tables[role]
        t['validated'] = validate_summary(t['summary'],t['timing'],t['cells'])
        snapshots[role] = store.text(prefix+'spec_snapshot.md') or ''
    return dict(store=store, tables=tables, envs=envs, snapshots=snapshots,
        selection=store.text('00_docs/FINAL_SELECTION.md') or 'Final selection not committed.',
        attack=store.text('07_attack/ATTACK_REPORT.md') or 'Attack report not committed.',
        cross=store.json(f'03_results/runs/{RUNS["cross"]}/fast_acceptance.json'),
        rematch=store.json(f'03_results/runs/{RUNS["rematch"]}/fast_rematch_acceptance.json'),
        correctness=store.json('05_evidence/final-b-registry-verification.json'))


def official_geomeans(bundle):
    out = []
    for version,role in [('B1','candidates'),('B2','candidates'),('B3','candidates'),('B3r','baseline')]:
        s = bundle['tables'][role]['validated']
        s = s[s.version.eq(version) & s.experiment.eq('official') & s['size'].eq(100000) & s.phase.eq('replay')]
        good = len(s) == 15 and s.complete.all()
        out.append(dict(version=version,cells=int(s.complete.sum()),
            geomean_s=math.exp(math.fsum(math.log(v) for v in s.median_s)/15) if good else None,
            run=RUNS[role],commit=bundle['envs'][role]['git_commit']))
    return pd.DataFrame(out)


def _session_score(bundle, role, version):
    """Fifteen complete official 100k cells, keeping the measured session."""
    d = bundle['tables'][role]['validated']
    d = d[d.phase.eq('replay') & d.experiment.eq('official') & d['size'].eq(100000)
          & d.version.eq(version)]
    good = len(d) == 15 and d.complete.all()
    return dict(geomean_s=statistics.geometric_mean(d.median_s) if good else None,
                cells=int(d.complete.sum()),run=RUNS[role],commit=bundle['envs'][role]['git_commit'])


def selection_candidates(bundle):
    """One row per version from its primary full-protocol session."""
    rows = official_geomeans(bundle).to_dict('records')
    rows.append(dict(version='B3r_fast',**_session_score(bundle,'cross','B3r_fast')))
    issues = {}
    for line in bundle['selection'].splitlines():
        fields = [p.strip() for p in line.split('|')]
        if len(fields) >= 5 and fields[1] in ('B1','B2','B3'):
            issues[fields[1]] = fields[3]
    for row in rows:
        v = row['version']
        row.update(outcome='final B' if v == 'B3r' else
                   'faster; rejected by the pre-registered rule' if v == 'B3r_fast' else 'excluded',
                   detail=issues.get(v,'Declared heap-purge tail cost; see FINAL_SELECTION')
                   if v != 'B3r_fast' else 'Older cross-session comparison to the B3r primary row: rejected.',
                   ratio=bundle['cross']['official_100k_ratio'] if v == 'B3r_fast' else None)
    return pd.DataFrame(rows)


def selection_table(bundle):
    """Five primary rows and the binding ratio; absent fields render blank."""
    rows = selection_candidates(bundle).to_dict('records')
    record = bundle['rematch']; scenarios = record['scenarios']; loss = record['scenario_losses'][0]
    faster = sum(r['median_seed_ratio'] < 1 for r in scenarios)
    within = sum(r['median_seed_ratio'] <= 1.05 for r in scenarios)
    rows.append(dict(version='B3r_fast vs B3r, same session (binding)',geomean_s=None,
                     ratio=record['official_100k_ratio'],outcome='faster; rejected by the pre-registered rule',
                     detail=f'Faster in {faster} of {len(scenarios)}; within the 5 % bound in {within} of {len(scenarios)}; '
                            f'failed on {loss["workload"]} {loss["size"]//1000}k ({loss["median_seed_ratio"]:.3f}).',
                     run=RUNS['rematch'],commit=bundle['envs']['rematch']['git_commit']))
    d = pd.DataFrame(rows)[['version','geomean_s','ratio','outcome','detail','run','commit']]
    d['geomean_s'] = d.geomean_s.map(lambda v:'' if pd.isna(v) else f'{v:.4f}')
    d['ratio'] = d.ratio.map(lambda v:'' if pd.isna(v) else f'{v:.3f}')
    return d.astype(object).where(d.notna(),'')


def session_effect(bundle):
    """Both measured pairs; absolute times and ratios keep their own sources."""
    rows = []
    for label,roles,record in [
        ('Primary sessions (different sessions)',{'B3r':'baseline','B3r_fast':'cross'},'cross'),
        ('Same session, alternating order (binding)',{'B3r':'rematch','B3r_fast':'rematch'},'rematch')]:
        for version,role in roles.items():
            rows.append(dict(comparison=label,version=version,**_session_score(bundle,role,version),
                             ratio=bundle[record]['official_100k_ratio']))
    return pd.DataFrame(rows)


def replay_limits(bundle):
    stops = bundle['tables']['baseline']['stops']
    d = stops[stops.version.eq('A') & stops.phase.eq('replay') & stops['mode'].eq('timing')
              & stops.status.eq('stopped') & stops.reason.eq('phase_time_limit')].copy()
    d = d.drop_duplicates('case_id')
    d['bound_s'] = pd.to_numeric(d.limit_s)
    d['time_label'] = d.bound_s.map(lambda s:f'> {s:g} s (stopped)')
    return d


def a_vs_b(bundle, phase='replay'):
    s = bundle['tables']['baseline']['validated']
    a = s[s.version.eq('A') & s.phase.eq(phase)].set_index('case_id')
    b = s[s.version.eq('B3r') & s.phase.eq(phase)]
    limits = replay_limits(bundle).set_index('case_id')
    out = []
    for r in b.to_dict('records'):
        ar = a.loc[r['case_id']] if r['case_id'] in a.index else None
        at = float(ar.median_s) if ar is not None and ar.complete else None
        bt = r['median_s'] if r['complete'] else None
        status = ar.status if ar is not None else ('not measured (declared scope)' if
            r['experiment'] not in ('official','million') and r['size'] > 10000 else 'not measured')
        bound = limits.loc[r['case_id'],'bound_s'] if phase == 'replay' and r['case_id'] in limits.index else None
        ratio = at/bt if at is not None and bt and bt > 0 else None
        out.append(dict(case_id=r['case_id'],experiment=r['experiment'],workload=r['workload'],
            size=r['size'],seed=r['seed'],phase=phase,A_s=at,B3r_s=bt,A_status=status,
            B3r_status=r['status'],A_time=f'{at:.6g} s' if at is not None else
            f'> {bound:g} s (stopped)' if bound is not None else status,
            speedup=ratio,speedup_label=f'{ratio:.3g}x' if ratio is not None else
            f'> {bound/bt:.3g}x (A replay limit)' if bound is not None and bt and bt > 0 else 'unavailable',
            A_protocol=ar.timing_protocol if ar is not None else status,run=r['run'],commit=r['commit']))
    return pd.DataFrame(out)


def overview_speedups(bundle):
    """Median of per-seed ratios; censored replays remain explicit bounds.

    A missing seed cannot become a measured ratio. For mixed exact/censored
    groups a strict > label is used only if a majority is provably above the
    median lower value; otherwise the conservative bound is >=.
    """
    pairs = a_vs_b(bundle)
    limits = replay_limits(bundle).set_index('case_id').bound_s
    result = []
    for (workload,size),group in pairs[pairs.experiment.eq('official')].groupby(['workload','size']):
        values = []
        for row in group.itertuples():
            if pd.notna(row.speedup):
                values.append((row.speedup,False))
            elif row.case_id in limits and pd.notna(row.B3r_s) and row.B3r_s > 0:
                values.append((limits[row.case_id]/row.B3r_s,True))
        value,kind,label = float('nan'),'unavailable','unavailable (missing/stopped input)'
        if len(values) == len(group):
            value = statistics.median(v for v,_ in values)
            if any(bound for _,bound in values):
                strict = sum(v > value or (bound and v >= value) for v,bound in values) > len(values)//2
                # Round down: rounding 1295.7 up to "> 1300" would overclaim.
                unit = 10 ** (math.floor(math.log10(value))-2)
                lower = math.floor(value/unit)*unit
                kind,label = 'lower bound',('> ' if strict else '>= ')+f'{lower:g}x'
            else:
                kind,label = 'measured',f'{value:.3g}x'
        result.append(dict(workload=workload,size=size,median_speedup=value,kind=kind,label=label,
                           seeds=','.join(map(str,sorted(group.seed))),run=group.run.iloc[0],commit=group.commit.iloc[0]))
    return pd.DataFrame(result)


def raw_repeats(bundle, role, case_id, version, phase):
    """All saved rows for one selection, including warm-up and failed attempts."""
    raw = bundle['tables'][role]['timing']
    selected = raw[raw.case_id.eq(case_id) & raw.version.eq(version) & raw.phase.eq(phase)].copy()
    selected['row_kind'] = selected.warmup.astype(str).str.lower().eq('true').map({True:'warm-up',False:'measured'})
    return selected


def workload_settings(bundle):
    meta = pd.concat([t['cells'] for t in bundle['tables'].values()],ignore_index=True)
    settings = meta.drop_duplicates(['run','case_id','version','input_sha256','timing_protocol'])[
        ['case_id','experiment','version','workload','size','events','seed','levels','own','percent',
         'driver_n','timing_protocol','input_sha256','run','commit']].copy()
    settings['data_origin'] = settings.own.astype(str).str.lower().eq('true').map({True:'own',False:'supplied'})
    settings['generator_command'] = settings.apply(generator_command,axis=1)
    return settings


def fit_exponents(rows, x='size', y='median_s', groups=('version',)):
    """OLS log(y) on log(x), after seed medians. No synthetic sizes or fit lines."""
    good = rows[rows.complete & rows[y].gt(0) & rows[x].gt(0)]
    out = []
    for key,g in good.groupby(list(groups)):
        key = key if isinstance(key,tuple) else (key,)
        points = g.groupby(x)[y].median()
        if len(points) < 2:
            continue
        lx,ly = list(map(math.log,points.index)),list(map(math.log,points))
        mx,my = statistics.mean(lx),statistics.mean(ly)
        slope = sum((a-mx)*(b-my) for a,b in zip(lx,ly))/sum((a-mx)**2 for a in lx)
        out.append(dict(zip(groups,key),exponent=slope,points=len(points),
                        min_size=min(points.index),max_size=max(points.index)))
    return pd.DataFrame(out)


def variants(bundle):
    out = []
    for role,versions,parts in [('candidates',['B1','B2','B3'],['official','adversarial']),
                              ('baseline',['B3r'],['official','adversarial','post_attack']),
                              ('baseline',['B1','B2','B3'],['post_attack'])]:
        d = bundle['tables'][role]['validated']
        d = d[d.version.isin(versions) & d.experiment.isin(parts) & d.phase.eq('replay')]
        d = d[d.experiment.ne('official') | d['size'].eq(100000)]
        out.append(d)
    d = pd.concat(out,ignore_index=True)
    best = d[d.complete].groupby('case_id').median_s.min()
    d['ratio_to_best'] = d.median_s / d.case_id.map(best)
    return d


def observations(bundle, name, versions=('A','B3r'), candidate_versions=()):
    # The baseline session also contains B1/B2/B3 post-attack comparators.
    # Their original-grid observations are in the earlier candidate session.
    baseline_versions = tuple(set(versions) | set(candidate_versions))
    frames = [bundle['tables']['baseline'][name].query('version in @baseline_versions')]
    if candidate_versions:
        frames.append(bundle['tables']['candidates'][name].query('version in @candidate_versions'))
    return pd.concat(frames,ignore_index=True)


def memory_peaks(bundle):
    d = observations(bundle,'memory',candidate_versions=('B1','B2','B3'))
    curves = d[d.measure.eq('curve')].groupby(['run','case_id','version']).live_orders.max()
    p = d[d.measure.eq('peak')].copy()
    p['max_sampled_live_orders'] = [curves.get((r.run,r.case_id,r.version),float('nan')) for r in p.itertuples()]
    p['peak_bytes_per_sampled_live_order'] = p.peak_bytes / p.max_sampled_live_orders.where(p.max_sampled_live_orders.gt(0))
    return p


def coverage(bundle):
    cells = bundle['tables']['baseline']['cells'].copy()
    b = cells[cells.version.eq('B3r')]
    keys = set(zip(cells.case_id,cells.version,cells['mode']))
    missing = []
    for r in b.to_dict('records'):
        if (r['case_id'],'A',r['mode']) not in keys:
            r.update(version='A',status='not measured (declared scope)' if
                r['experiment'] not in ('official','million') and r['size'] > 10000 else 'not measured')
            missing.append(r)
    return pd.concat([cells,pd.DataFrame(missing)],ignore_index=True)


def generator_command(row):
    """Reconstruct commands from saved settings; never execute them."""
    part,w,n,seed,levels = row['experiment'],row['workload'],int(row['size']),int(row['seed']),int(row['levels'])
    out = f' --out 06_data/generated/{row["case_id"]}.jsonl.gz'
    common = f' --seed {seed} --levels {levels}'
    if part == 'post_attack':
        return f'python run.py datagen.attack_cases --scenario {w} --n {int(row["driver_n"])}'+out
    if part in ('official','million','queue') or w == 'cancel_churn_memory':
        scenario = 'cancel_churn' if w == 'cancel_churn_memory' else 'buildup' if part == 'queue' else w
        return f'python 06_data/supplied/generate_orders.py --scenario {scenario} --events {n}'+common+out
    if part in ('churn','liquidation'):
        kind = 'liquidation' if part == 'liquidation' else 'drift'
        return f'python run.py datagen.benchmark_own --kind {kind} --size {n}'+common+out
    extras = {'deep_book':f'--orders {n*9//10} --sells {n-n*9//10}',
              'mid_queue_cancels':f'--orders {n//2} --cancels {n//4}',
              'repeated_full_sweeps':f'--orders {n//5-1} --rounds 5'}
    return f'python run.py datagen.adversarial --scenario {w} {extras[w]}'+common+out
