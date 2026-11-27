"""Review dashboard for the saved benchmark results (AGENTS.md section 8).

    python -m streamlit run dashboard/app.py                # from 01_code/; reads ../02_results/<run_id>/
    RESULTS_DIR=path/to/results python -m streamlit run dashboard/app.py

(`python -m streamlit` rather than the `streamlit` launcher: some Windows
application-control policies block streamlit.exe.)

It only reads saved files (cached with st.cache_data) and never runs a benchmark.
The Spot check tab calls the algorithms on small inputs typed by the reviewer
(correctness only, nothing is timed).
"""
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:  # `streamlit run` only adds dashboard/ to sys.path
    sys.path.insert(0, str(PROJECT_DIR))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from benchmarks.environment import git_info, source_fingerprint  # noqa: E402
from dashboard import data  # noqa: E402
from search_algos import METHODS, get_method  # noqa: E402

SUBMISSION_DIR = "Submissions/BonackerMaurice/01_code"
METHOD_COLORS = {"linear": "#2a78d6", "binary": "#eb6834", "hash": "#1baf7a"}  # colour = method
SEGMENTS = data.SEGMENTS
TITLES = data.SEGMENT_TITLES
MIME = {".csv": "text/csv", ".json": "application/json", ".xml": "application/xml",
        ".txt": "text/plain"}


@st.cache_data(show_spinner=False)
def load_run(path: str, stamp: tuple) -> dict:
    """All saved files of one run; `stamp` changes when a file changes."""
    return data.load_run(path)


@st.cache_data(ttl=60, show_spinner=False)
def checked_out_git() -> dict:
    """Git state of the code this dashboard is running from (not of the run)."""
    return git_info(PROJECT_DIR)


@st.cache_data(ttl=60, show_spinner=False)
def checked_out_source() -> dict:
    """Fingerprint of the measured code as checked out now (compare with the run's)."""
    return source_fingerprint(PROJECT_DIR)


# --- small display helpers ------------------------------------------------------------

def num(fmt="%.3g", **kwargs):
    return st.column_config.NumberColumn(format=fmt, **kwargs)


def in_unit(df, unit_size, columns=("median_s", "min_s", "max_s")):
    return df.assign(**{c.replace("_s", ""): df[c] / unit_size for c in columns})


def select(df, q, scenario):
    return df[(df["q"] == q) & (df["scenario"] == scenario)]


def current_only(df, current):
    return df[[current.get(m) == v for m, v in zip(df["method"], df["version"])]]


def hit_rate_text(run, q, scenario, short=False) -> str:
    ds = run["datasets"]
    source = select(ds if ds is not None else run["summary"], q, scenario)
    realized = sorted(set(source["realized_hit_rate"]))
    target = sorted(set(source["target_hit_rate"])) if ds is not None else realized
    text = ("hit rate " if short else "realized hit rate ") + ", ".join(f"{r:.2f}" for r in realized)
    if target != realized:
        text += (" (target " + ", ".join(f"{t:.2f}" for t in target)
                 + (")" if short else ", rounded half up)"))
    return text


def first_hit_caption(run, q, scenario):
    """Where linear search finds its hits: mean first-occurrence position / n (datasets.csv)."""
    ds = run["datasets"]
    if ds is None or "mean_first_hit_frac" not in ds.columns:
        return
    sel = select(ds, q, scenario).dropna(subset=["mean_first_hit_frac"]).sort_values("n")
    if sel.empty:
        st.caption("Linear search: no present queries in this selection, so every query scans "
                   "all n elements.")
        return
    values = ", ".join(f"{v:.3f} (n = {n:,})" for n, v in zip(sel["n"], sel["mean_first_hit_frac"]))
    st.caption("Linear search stops at the first occurrence of a present query. Mean first "
               f"occurrence position / n (mean_first_hit_frac): {values}.")


def time_chart(df, title, dash_versions=False, spread=True):
    """Median time vs n on log-log axes; one line per method/version; min-max as rules.

    No legend inside the chart (segment_charts draws one shared legend line above
    the three charts): in narrow columns a legend leaves too little room for the plot.
    """
    unit, size = data.pick_unit(df["median_s"])
    d = in_unit(df, size)[["n", "method", "version", "label", "median", "min", "max", "repeats",
                           "overhead"]]
    methods = [m for m in METHOD_COLORS if m in set(d["method"])]
    y_title = f"median {unit} per call (log scale)"
    y = alt.Y("median:Q", title=y_title, scale=alt.Scale(type="log"))
    scale = alt.Scale(domain=methods, range=[METHOD_COLORS[m] for m in methods])
    color = alt.Color("method:N", legend=None, scale=scale)
    base = alt.Chart(d).encode(
        x=alt.X("n:Q", title="array length n (log scale)", scale=alt.Scale(type="log"),
                axis=alt.Axis(values=sorted(d["n"].unique().tolist()), format=",d")),
        color=color, detail="label:N")
    line = base.mark_line(strokeWidth=2)
    if dash_versions:
        line = line.encode(strokeDash=alt.StrokeDash(
            "version:N", legend=None, scale=alt.Scale(domain=["v1", "v2"], range=[[6, 4], [1, 0]])))
    tooltip = [alt.Tooltip("label:N", title="method"), alt.Tooltip("n:Q", format=","),
               alt.Tooltip("median:Q", format=".4~g", title=f"median ({unit})"),
               alt.Tooltip("min:Q", format=".4~g", title=f"min ({unit})"),
               alt.Tooltip("max:Q", format=".4~g", title=f"max ({unit})"),
               alt.Tooltip("repeats:Q"),
               alt.Tooltip("overhead:N", title=f"within {data.OVERHEAD_FACTOR}x harness overhead")]
    points = base.mark_point(size=60, opacity=1, strokeWidth=2).encode(
        y=y, tooltip=tooltip, stroke=alt.Stroke("method:N", legend=None, scale=scale),
        fill=alt.condition(alt.datum.overhead, alt.value("transparent"),
                           alt.Fill("method:N", legend=None, scale=scale)))
    layers = [line.encode(y=y), points]
    if spread:
        layers.insert(0, base.mark_rule(strokeWidth=2, opacity=0.5).encode(
            y=alt.Y("min:Q", title=y_title, scale=alt.Scale(type="log")), y2="max:Q"))
    return alt.layer(*layers).properties(
        height=280, padding={"top": 12, "left": 5, "right": 5, "bottom": 5},
        title=alt.TitleParams(title, anchor="start", fontSize=13))


def legend_line(df, dash_versions):
    """One legend for a row of charts: colour = method, dashed = v1 (original)."""
    labels = dict(zip(df["method"], df["label"])) if not dash_versions else {}
    items = [f'<span style="color:{METHOD_COLORS[m]}; font-size:1.2em">&#9679;</span> '
             f'{labels.get(m, m)}' for m in METHOD_COLORS if m in set(df["method"])]
    if dash_versions:
        items.append("solid line = v2 (revised), dashed line = v1 (original)")
    st.markdown("&nbsp;&nbsp;&nbsp;".join(items), unsafe_allow_html=True)


def segment_charts(df, run, q, scenario, dash_versions=False):
    """Three charts side by side: prepare, query batch, total."""
    legend_line(df, dash_versions)
    for col, segment in zip(st.columns(3), SEGMENTS):
        d = df[df["segment"] == segment]
        d = d.assign(overhead=data.near_overhead(d, run["config"]))  # on the measured batch time
        title = TITLES[segment]
        if d.empty:
            col.info(f"No {segment} rows.")
            continue
        # Second title line instead of a subtitle: subtitles are barely legible in dark mode.
        lines = [title, f"q = {q} · {scenario} · {hit_rate_text(run, q, scenario, short=True)}"]
        col.altair_chart(time_chart(d, lines, dash_versions), width="stretch")
    st.caption(f"Hollow points: median within {data.OVERHEAD_FACTOR}× the harness overhead of "
               "its segment (overhead-dominated, see Details → Definitions).")


# --- sections ------------------------------------------------------------------------

def provenance_tab(run):
    cfg, env = run["config"], run["env"] or {}
    git, timer = env.get("git") or {}, env.get("timer") or {}
    ram = env.get("ram_bytes")
    packages = ", ".join(f"{k} {v}" for k, v in (env.get("packages") or {}).items())
    phases = "; ".join(f"{name}: {p.get('status')} ({p.get('finished_utc', '?')})"
                       for name, p in (cfg.get("phases") or {}).items())
    source = env.get("source") or {}
    tree = {True: "DIRTY (uncommitted changes)", False: "clean",
            None: "UNKNOWN (git unavailable at run time)"}[git.get("dirty")]
    unchanged = {True: "yes (fingerprint recomputed at the end of the run)",
                 False: "NO: the measured code changed during the run",
                 None: "not recorded"}[cfg.get("source_unchanged")]
    rows = [
        ("run_id", cfg.get("run_id")),
        ("status", cfg.get("status", "not recorded (older run format)")),
        ("commit", git.get("commit") or "unknown (git unavailable or run outside git)"),
        ("branch", git.get("branch")),
        ("working tree", tree),
        ("source fingerprint", f"sha256 {source['sha256']} over {source.get('files')} .py files "
                               f"in {', '.join(source.get('dirs', []))}" if source.get("sha256")
                               else "not recorded (older run format)"),
        ("code unchanged during run", unchanged),
        ("started (UTC)", env.get("timestamp_utc")),
        ("finished (UTC)", cfg.get("finished_utc", "not finished")),
        ("benchmark command", cfg.get("command")),
        ("phases", phases or "none recorded"),
        ("Python", f"{env.get('python_version')} ({env.get('python_implementation')}, "
                   f"{env.get('python_build')})"),
        ("OS", env.get("platform")),
        ("CPU", f"{env.get('cpu')} ({env.get('cpu_count_logical')} logical cores, "
                f"{env.get('machine')})"),
        ("RAM", f"{ram / 2**30:.1f} GiB" if ram else "not recorded (psutil not installed)"),
        ("timer", f"{timer.get('function')} via {timer.get('implementation')}, resolution "
                  f"{data.format_seconds(timer.get('resolution_s'))}, "
                  f"monotonic={timer.get('monotonic')}"),
        ("packages", packages),
    ]
    if not run["env"]:
        st.warning("environment.json is missing from this run.")
    st.table(pd.DataFrame(rows, columns=["item", "value"]).astype(str), hide_header=True,
             hide_index=True)
    if git.get("dirty_files"):
        with st.expander(f"Uncommitted files at run time ({len(git['dirty_files'])})"):
            st.code("\n".join(git["dirty_files"]), language="text")

    here = checked_out_git()
    if git.get("commit") and here.get("commit") and here["commit"] != git["commit"]:
        st.info(f"This dashboard runs from commit `{here['short']}`, but the run measured "
                f"`{git.get('short')}`. The saved results are unaffected; the spot check "
                "uses the checked-out code.")
    if source.get("sha256"):
        now = checked_out_source()
        if now["sha256"] == source["sha256"]:
            st.success("The checked-out code (" + ", ".join(source.get("dirs", []))
                       + ") has the same source fingerprint as the measured code.")
        else:
            st.info(f"The checked-out code's source fingerprint (`{now['sha256'][:12]}…`) differs "
                    f"from the measured code's (`{source['sha256'][:12]}…`): you are not looking "
                    "at the code that produced these numbers.")


def reproduce_commands(run):
    cfg, git = run["config"], (run["env"] or {}).get("git") or {}
    tests = (cfg.get("tests") or {}).get("summary") or "see Details → Tests"
    commit = git.get("commit") or "<commit unknown>"
    st.code(f"# from a clone of the course repository\n"
            f"git checkout {commit}\n"
            f"cd {SUBMISSION_DIR}\n"
            f"python -m pip install -r requirements.txt\n"
            f"python -m pytest                  # this run recorded: {tests}\n"
            f"python -m tests.mutation_check    # every mutant should be KILLED\n"
            f"python -c \"from benchmarks.environment import source_fingerprint as f; "
            f"print(f('.')['sha256'])\"  # should print the run's source fingerprint",
            language="bash")
    st.code(f"{(cfg.get('command') or 'python -m benchmarks.run').strip()}"
            f"    # new ../02_results/<run_id>/; close other heavy programs first\n"
            f"python -m streamlit run dashboard/app.py", language="bash")
    st.caption("A rerun gets a new run_id, and absolute times depend on the machine. Compare "
               "ratios (v1 / v2), slopes and the order of the methods rather than raw seconds. "
               "Without --quick, the benchmark runs the full grid and takes a while.")


def correctness_tab(run):
    cfg, tests = run["config"], run["tests"]
    if tests is None:
        st.info("tests.xml is not part of this run (made with --skip-tests?).")
    else:
        c = tests["counts"]
        cols = st.columns(5)
        for col, (label, key) in zip(cols, [("passed", "passed"), ("failed", "failed"),
                                            ("skipped", "skipped"), ("errors", "error"),
                                            ("total", "total")]):
            col.metric(label, c[key], border=True)
        summary = (cfg.get("tests") or {})
        if c["failed"] or c["error"]:
            st.error(f"{c['failed']} failed and {c['error']} errors in this run's test suite.")
        elif c["total"]:
            st.success(f"All {c['passed']} tests passed in this run"
                       + (f" ({c['skipped']} skipped)." if c["skipped"] else "."))
        st.caption(f"Parsed from tests.xml (pytest JUnit XML). pytest summary line saved in "
                   f"run.json: `{summary.get('summary', 'n/a')}`, exit code "
                   f"{summary.get('exit_code', 'n/a')}.")

        table = tests["table"]
        keys = [m["key"] for m in cfg.get("methods", [])]
        token = table["test"].str.extract(r"\[([A-Za-z0-9_]+)[-\]]")[0]
        per_method = table[token.isin(keys)].assign(key=token)
        if not per_method.empty:
            st.markdown("**Same tests for every method/version** (tests parametrized by method):")
            counts = pd.crosstab(per_method["key"], per_method["outcome"]).reindex(keys)
            st.dataframe(counts.fillna(0).astype(int))

        with st.expander(f"Per-test results ({len(table)} tests)"):
            left, right = st.columns([1, 2])
            outcomes = left.multiselect("Outcome", sorted(table["outcome"].unique()),
                                        default=sorted(table["outcome"].unique()))
            text = right.text_input("Name contains", "")
            shown = table[table["outcome"].isin(outcomes)
                          & table["test"].str.contains(text, regex=False)]
            st.dataframe(shown, hide_index=True,
                         column_config={"time_s": num("%.3f", label="time (s)")})
        if run["tests_txt"]:
            with st.expander("pytest console output (tests.txt)"):
                st.code(run["tests_txt"], language="text")

    st.subheader("Does the suite catch wrong code? Mutation check")
    st.markdown(
        "Passing tests are evidence, not proof. `tests/mutation_check.py` swaps one function "
        "of one method for a deliberately buggy version (in memory, no file changes), reruns "
        "`tests/test_search.py` in a fresh process and reports whether the suite fails "
        "(**KILLED**) or not (**SURVIVED**, which would mean a missing test). Its result is not "
        "saved in the run; run it yourself:")
    st.code("python -m tests.mutation_check", language="bash")
    try:
        from tests.mutation_check import MUTANTS
        st.dataframe(pd.DataFrame([(name, key, attr) for name, (key, attr, _) in MUTANTS.items()],
                                  columns=["mutant", "method", "function replaced"]),
                     hide_index=True)
        st.caption(f"Expected output: {len(MUTANTS)}/{len(MUTANTS)} mutants killed.")
    except Exception as exc:  # the module is optional for viewing results
        st.caption(f"(could not list the mutants: {exc})")


def definitions_tab(run):
    cfg, raw = run["config"], run["raw"]
    grid, defs = cfg.get("grid", {}), cfg.get("definitions", {})
    repeats = grid.get("repeats", "?")
    st.info(f"**Every time is seconds per call**: per `prepare(ids)`, per **complete batch** of "
            f"q queries, or per prepare + batch. Per-query values are **derived** as batch / q "
            f"and labelled *derived* wherever they appear. Each reported value is the **median "
            f"of {repeats} repeats**; min and max of the repeats are kept as the spread.")
    noop, noop_lambda = cfg.get("noop_call_s"), cfg.get("noop_lambda_call_s")
    timer = (run["env"] or {}).get("timer") or {}
    factor = grid.get("id_space_factor", "?")
    settings = [
        ("repeats", f"{repeats} per (dataset, method, version, segment); method order rotates"),
        ("min_measure_seconds", f"{grid.get('min_measure_seconds')} s per measurement"),
        ("seed", grid.get("seed")),
        ("duplicate policy", f"{grid.get('duplicate_policy')} (IDs drawn from [0, {factor}·n))"),
        ("array lengths n", ", ".join(f"{n:,}" for n in grid.get("sizes", []))),
        ("query counts q", ", ".join(str(q) for q in grid.get("query_counts", []))),
        ("scenarios", ", ".join(grid.get("scenarios", []))),
        ("noop_call_s (overhead of prepare and query)",
         f"{data.format_seconds(noop)} per call (not subtracted)" if noop else "not recorded"),
        ("noop_lambda_call_s (overhead of total)",
         f"{data.format_seconds(noop_lambda)} per call (not subtracted)" if noop_lambda
         else "not recorded (older run: noop_call_s is used for total)"),
        ("timer resolution", data.format_seconds(timer.get("resolution_s"))),
        ("units", cfg.get("units")),
    ]
    st.table(pd.DataFrame(settings, columns=["setting", "value"]).astype(str), hide_header=True,
             hide_index=True)
    if noop:
        st.caption(f"These are the noise floor of the timing loop and its wrapper. Medians within "
                   f"{data.OVERHEAD_FACTOR}× of their segment's value (for example linear v2 "
                   f"prepare, which does no work) measure call overhead, not the algorithm; the "
                   f"tables flag them as overhead-dominated and the charts draw them hollow.")

    st.subheader("Definitions (from run.json)")
    order = ["prepare", "query", "total", "elapsed_s", "repeats", "datasets", "gc", "excluded",
             "memory", "noop_call_s"]  # any other keys follow in file order
    for key in order + [k for k in defs if k not in order]:
        if key in defs:
            st.markdown(f"- **{key}**: {defs[key]}")

    if raw is not None:
        with st.expander("calls_per_measurement chosen by calibration (from timings_raw.csv)"):
            calls = raw.groupby(["label", "segment"])["calls_per_measurement"].agg(["min", "max"])
            calls = (calls["min"].map("{:,}".format) + " – " + calls["max"].map("{:,}".format))
            st.dataframe(calls.unstack("segment").reindex(columns=list(SEGMENTS)))
            st.caption("Each measurement repeats the call this many times and divides the "
                       "elapsed time by the count (min – max over all datasets).")

    st.subheader("Inputs (datasets.csv)")
    ds = run["datasets"]
    if ds is None:
        st.info("datasets.csv is missing from this run.")
        return
    st.dataframe(ds, hide_index=True, column_config={
        "target_hit_rate": num("%.2f"), "realized_hit_rate": num("%.2f"),
        "mean_first_hit_frac": num("%.3f", help="Mean first-occurrence index of the present "
                                                "queries as a fraction of n (empty: no hits).")})
    same_array = ds.groupby("n")["array_sha256"].nunique().eq(1).all()
    if same_array:
        st.success("For every n, all q and scenarios use the identical array "
                   "(one array_sha256 per n). Every method and version gets the same inputs.")
    else:
        st.error("Different arrays for the same n: the inputs are not comparable.")
    combos = [(q, s) for q in grid.get("query_counts", []) for s in grid.get("scenarios", [])]
    present = set(zip(ds["q"], ds["scenario"]))
    skipped = [f"q = {q} {s}" + (" (one query cannot be half present)" if q == 1 and s == "mixed"
                                 else "") for q, s in combos if (q, s) not in present]
    if skipped:
        st.caption("Not measured: " + "; ".join(skipped) + ".")
    off = ds[ds["target_hit_rate"] != ds["realized_hit_rate"]]
    if not off.empty:
        st.caption("Target and realized hit rate differ for: " + ", ".join(off["dataset_id"])
                   + ". The number of present queries is q × target, rounded half up.")
    st.caption("Regenerate any dataset and compare its checksums (same seed, same machine-"
               "independent generator):")
    st.code("python -m datagen.generator --n 1000 --q 100 --scenario mixed", language="bash")


def same_code_control(speed, methods):
    """(method, prepare rows) for a method whose v1 and v2 share the prepare function, else None.

    Identical code on identical arrays: the spread of its v1/v2 ratio is the noise band.
    """
    for method in methods:
        try:
            same_code = get_method(method, "v1").prepare is get_method(method, "v2").prepare
        except KeyError:
            same_code = False
        ctrl = speed[(speed["method"] == method) & (speed["segment"] == "prepare")]
        if same_code and not ctrl.empty:
            return method, ctrl
    return None


def headline(summary):
    """The dataset the overview reports: largest n, largest q, mixed if measured."""
    n, q = summary["n"].max(), summary["q"].max()
    measured = set(summary.loc[summary["q"] == q, "scenario"])
    scenario = "mixed" if "mixed" in measured else sorted(measured)[0]
    return n, q, scenario


def overview_tab(run):
    cfg, env = run["config"], run["env"] or {}
    git, tests, summary = env.get("git") or {}, run["tests"], run["summary"]
    current = cfg.get("current", {})

    cols = st.columns(4)
    cols[0].metric("Measured commit", git.get("short") or "unknown", border=True)
    cols[1].metric("Working tree", {True: "dirty", False: "clean"}.get(git.get("dirty"), "unknown"),
                   border=True)
    cols[2].metric("Run status", cfg.get("status", "not recorded"), border=True)
    if tests is not None:
        c = tests["counts"]
        cols[3].metric("Tests", f"{c['passed']} / {c['total']} passed", border=True)
        if c["failed"] or c["error"]:
            st.error(f"{c['failed']} failed and {c['error']} errors in this run's test suite "
                     "(Details → Tests).")
        else:
            st.success(f"All {c['passed']} tests passed in this run, with the same tests for every "
                       "method and version. The mutation check (command below) shows they catch "
                       "deliberately wrong code.")
    else:
        cols[3].metric("Tests", "not in run", border=True)

    if summary is None:
        st.info("timings_summary.csv is not part of this run.")
    else:
        n, q, scenario = headline(summary)
        sel = current_only(select(summary, q, scenario), current)
        sel = sel[sel["n"] == n]
        slopes = data.scaling_table(summary, q, scenario, cfg)
        rows = []
        for method in METHOD_COLORS:
            d = sel[sel["method"] == method]
            if d.empty:
                continue
            t = dict(zip(d["segment"], d["median_s"]))
            s = slopes[(slopes["method"] == method) & (slopes["version"] == current.get(method))
                       & (slopes["segment"] == "query")] if not slopes.empty else slopes
            rows.append({"method": d["label"].iloc[0],
                         **{TITLES[seg]: data.format_seconds(t[seg]) if seg in t else "–"
                            for seg in SEGMENTS},
                         "query batch grows like": (f"n^{s['fitted_slope'].iloc[0]:.2f}"
                                                    if len(s) else "–")})
        st.subheader("Key results")
        st.table(pd.DataFrame(rows), hide_index=True)
        repeats = cfg.get("grid", {}).get("repeats", "?")
        st.caption(f"Current versions, n = {n:,}, q = {q}, {scenario} "
                   f"({hit_rate_text(run, q, scenario, short=True)}). Median of {repeats} "
                   "repeats, time per call; Total = a fresh prepare plus the whole batch. "
                   "The growth exponent is the fitted log–log slope over all n. Other n, q and "
                   "scenarios: Runtime tab.")

        methods = data.two_version_methods(cfg)
        if methods:
            speed = data.speedup_table(summary, methods)
            lines = []
            for method in methods:
                s = speed[(speed["method"] == method) & (speed["segment"] == "query")]
                if s.empty:
                    continue
                at = s[(s["n"] == n) & (s["q"] == q) & (s["scenario"] == scenario)]
                head = f"**{at['speedup'].iloc[0]:.2f}×** here, " if len(at) else ""
                lines.append(f"- **{method}** query batch: {head}{s['speedup'].min():.2f}–"
                             f"{s['speedup'].max():.2f}× over all {len(s)} datasets (median "
                             f"{s['speedup'].median():.2f}); v2 faster in "
                             f"{int((s['speedup'] > 1).sum())} of {len(s)}.")
            control = same_code_control(speed, methods)
            if control:
                m, ctrl = control
                lines.append(f"- **Noise band:** {m} prepare is identical code in v1 and v2, yet "
                             f"its ratio ranges {ctrl['speedup'].min():.2f}–"
                             f"{ctrl['speedup'].max():.2f}×. A single ratio inside this band is "
                             "not evidence on its own; consistency across datasets is.")
            st.subheader("Revision: speed-up v1 (original) → v2 (revised)")
            st.markdown("\n".join(lines))
            st.caption("Speed-up = median v1 / median v2; > 1 means v2 is faster. Curves: Runtime "
                       "tab (compare toggle). Every ratio: Details → v1 vs v2 numbers. Why: "
                       "00_docs/REVISIONS.md.")

    st.subheader("Reproduce")
    reproduce_commands(run)
    st.caption("Everything else (environment, per-test results, definitions, datasets and "
               "checksums, memory, raw repeats, downloads) is in the Details tab.")


def values_table(df, q) -> pd.DataFrame:
    """Median per call for each method/version and size: prepare, batch, per query, total."""
    measures = [("prepare", "Prepare", 1), ("query", f"Batch of {q} queries", 1),
                ("query", "Per query (derived = batch / q)", q), ("total", "Total", 1)]
    if q == 1:
        measures = [m for m in measures if m[2] == 1]
    rows = []
    for _, g in data.sort_rows(df).groupby(["method", "version"], sort=False):
        for segment, name, divisor in measures:
            s = g[g["segment"] == segment]
            if not s.empty:
                rows.append({"method": g["label"].iloc[0], "measure": name,
                             **{f"n = {n:,}": data.format_seconds(t / divisor)
                                for n, t in zip(s["n"], s["median_s"])}})
    return pd.DataFrame(rows)


def runtime_tab(run, q, scenario):
    summary, cfg = run["summary"], run["config"]
    current = cfg.get("current", {})
    methods = data.two_version_methods(cfg)
    compare = st.toggle("Compare original (v1) and revised (v2)", key="compare",
                        disabled=not methods)
    sel = select(summary, q, scenario)
    if not compare:
        st.markdown("Current versions: " + ", ".join(f"**{m} {v}**" for m, v in current.items())
                    + ". Median of the repeats on log–log axes; vertical bars show the min–max "
                    "of the repeats. Change q and the scenario in the sidebar.")
        segment_charts(current_only(sel, current), run, q, scenario)
        first_hit_caption(run, q, scenario)
    else:
        descriptions = {m["key"]: m["description"] for m in cfg.get("methods", [])}
        for method in methods:
            st.subheader(f"{method}: v1 (original) vs v2 (revised)")
            st.markdown(f"- **v1**: {descriptions.get(method + '_v1', '')}\n"
                        f"- **v2**: {descriptions.get(method + '_v2', '')}")
            segment_charts(sel[sel["method"] == method], run, q, scenario, dash_versions=True)
        first_hit_caption(run, q, scenario)

    st.subheader("Values: median time per call")
    shown = sel[sel["method"].isin(methods)] if compare else current_only(sel, current)
    st.dataframe(values_table(shown, q), hide_index=True)
    st.caption(f"q = {q}, {scenario}; median of the repeats. Total = a fresh prepare plus the "
               "whole batch, measured directly, so it can differ from prepare + batch by the "
               "noise (about ±25%). Linear v2 prepare does no work: its tens of nanoseconds are "
               "call overhead. Every repeat: Details → Raw data & downloads.")

    st.subheader("Growth with n: fitted log–log slope (time ∝ n^slope)")
    table = data.scaling_table(summary, q, scenario, cfg)
    if table.empty or summary["n"].nunique() < 2:
        st.info("At least two array lengths are needed for a slope.")
        return
    if not compare:
        table = current_only(table, current)
    table["cell"] = [f"{s:.2f}   (expected {e})" for s, e in
                     zip(table["fitted_slope"], table["expected"])]
    pivot = table.pivot_table(index="label", columns="segment", values="cell", aggfunc="first",
                              sort=False)
    pivot = pivot.reindex(columns=[s for s in SEGMENTS if s in pivot.columns])
    st.table(pivot.rename(columns=TITLES).rename_axis(None, axis=1).rename_axis("method"))
    st.caption("About 1 means time grows linearly with n, about 0 means constant. The expected "
               "values are bands, not pass/fail thresholds (n log n, log n and cache effects)."
               + (" With q = 1 the query batch is a single lookup close to the call overhead, so "
                  "its slope is unreliable; prefer q = 100." if q == 1 else "")
               + " Local slopes and every q and scenario: Details → Scaling slopes.")


def revision_details(run):
    summary, cfg = run["summary"], run["config"]
    methods = data.two_version_methods(cfg)
    if not methods:
        st.info("No method has both a v1 and a v2 in this run.")
        return
    speed = data.speedup_table(summary, methods)
    st.subheader("Speed-up = median v1 / median v2")
    st.caption("> 1 means v2 is faster, < 1 means v1 is faster. All q and scenarios; per "
               "complete batch (the ratio is the same per query).")
    pivot = speed.pivot_table(index=["method", "segment", "q", "scenario"], columns="n",
                              values="speedup", aggfunc="first")
    pivot.columns = [f"n = {n:,}" for n in pivot.columns]
    pivot = data.sort_rows(pivot.reset_index())
    st.dataframe(pivot, hide_index=True,
                 column_config={c: num("%.2f") for c in pivot.columns if c.startswith("n =")})

    band = None
    control = same_code_control(speed, methods)
    if control:
        method, ctrl = control
        band = (ctrl["speedup"].min(), ctrl["speedup"].max())
        st.subheader(f"Same-code control: {method} prepare")
        st.markdown(
            f"{method} v1 and v2 call the **identical** prepare function "
            f"(`{get_method(method, 'v1').prepare.__module__}."
            f"{get_method(method, 'v1').prepare.__name__}`), and for each n every dataset uses "
            f"the identical array. Their prepare ratio would be exactly 1.00 without noise, so "
            f"its spread shows how large a v1/v2 difference this run can produce by chance.")
        cols = st.columns(4)
        cols[0].metric("median ratio", f"{ctrl['speedup'].median():.3f}", border=True)
        cols[1].metric("lowest", f"{band[0]:.3f}", border=True)
        cols[2].metric("highest", f"{band[1]:.3f}", border=True)
        cols[3].metric("datasets", len(ctrl), border=True)
        st.caption(f"Rough guide: speed-ups between {band[0]:.2f} and {band[1]:.2f} are within "
                   f"the noise of this control. The control measures 'sorted()' calls; much "
                   f"shorter calls (for example q = 1 query batches) can be noisier. "
                   f"(Shared code checked in the checked-out search_algos/registry.py.)")

    with st.expander("Detail: medians, min–max and noise indicators per row"):
        unit, size = data.pick_unit(speed["median_s_v1"])
        detail = speed.assign(**{c.replace("_s_", f" ({unit}) "): speed[c] / size
                                 for c in speed.columns if "_s_" in c})
        detail = detail.drop(columns=[c for c in speed.columns if "_s_" in c])
        detail["overhead-dominated"] = (data.near_overhead(speed, cfg, "median_s_v1")
                                        | data.near_overhead(speed, cfg, "median_s_v2"))
        if band:
            detail["inside control band"] = detail["speedup"].between(*band)
        st.dataframe(detail, hide_index=True, column_config={
            "speedup": num("%.3f"), **{c: num("%.4g") for c in detail.columns if f"({unit})" in c},
            "ranges_overlap": st.column_config.CheckboxColumn(
                "v1/v2 min–max overlap", help="The repeats' ranges overlap: weak evidence of a "
                                              "real difference.")})


def scaling_tab(run, q, scenario):
    summary = run["summary"]
    sizes = sorted(summary["n"].unique())
    st.markdown(
        "Slope of the least-squares line through log10(median time) against log10(n): time ∝ "
        "n^slope. About 1 means linear growth, about 0 means constant. Over n = 1,000–100,000, "
        "O(n log n) gives a little more than 1 and O(log n) a little more than 0, and cache "
        "effects add to both, so the **expected** column gives bands, not pass/fail thresholds. "
        f"Fitted over n = {', '.join(f'{n:,}' for n in sizes)}; local slopes between "
        "neighbouring n show curvature.")
    table = data.scaling_table(summary, q, scenario, run["config"])
    if table.empty or len(sizes) < 2:
        st.info("At least two array lengths are needed for a slope.")
        return
    table["note"] = [f"a median within {data.OVERHEAD_FACTOR}× harness overhead: slope biased "
                     "towards 0" if flag else "" for flag in table["near_overhead"]]
    table["smallest median"] = table["smallest_median_s"].map(data.format_seconds)
    table["max_rel_spread"] *= 100
    first = ["label", "segment", "fitted_slope"]
    local = [c for c in table.columns if c.startswith("local")]
    table = table[first + local + ["expected", "why", "smallest median", "max_rel_spread",
                                   "note"]]
    st.markdown(f"**q = {q}, scenario {scenario}, {hit_rate_text(run, q, scenario)}**")
    st.dataframe(table, hide_index=True, column_config={
        "fitted_slope": num("%.2f", label="fitted slope"),
        **{c: num("%.2f") for c in local},
        "max_rel_spread": num("%.0f%%", label="max (max−min)/median",
                              help="Largest relative spread of the repeats over the n values."),
    })
    st.caption("The slopes are evidence, not proof: few sizes, few repeats, one machine. "
               "With q = 1 the query batch is a single lookup of a few hundred nanoseconds for "
               "binary and hash, close to the per-call overhead, so its slope mostly reflects "
               "overhead and noise and is unreliable; prefer the largest q for the query segment.")
    with st.expander("Fitted slopes for every q and scenario"):
        slopes = data.all_slopes(summary)
        st.dataframe(slopes, hide_index=True,
                     column_config={c: num("%.2f") for c in slopes.columns if c.startswith("q=")})


def memory_tab(run, q, scenario):
    mem, defs = run["memory"], run["config"].get("definitions", {})
    if mem is None:
        st.info("memory.csv is not part of this run (made with --skip-memory?).")
        return
    st.markdown(f"**What is measured:** {defs.get('memory', 'see benchmarks/memory.py')}")
    raw_bytes = st.toggle("Show bytes instead of KiB", key="memory_bytes")
    unit, size = ("bytes", 1) if raw_bytes else ("KiB", 1024)
    sel = select(mem, q, scenario)
    if sel.empty:
        st.info(f"No memory rows for q = {q}, scenario {scenario}.")
        return
    cols = ["prepare_current_bytes", "prepare_peak_bytes", "total_current_bytes",
            "total_peak_bytes"]
    table = sel[["method", "version", "label", "n"]].assign(
        **{c.replace("_bytes", ""): sel[c] / size for c in cols},
        output_list=(sel["total_current_bytes"] - sel["prepare_current_bytes"]) / size,
        bytes_per_element=sel["prepare_current_bytes"] / sel["n"])
    table = data.sort_rows(table).drop(columns=["method", "version"])
    fmt = "%d" if raw_bytes else "%.1f"
    st.markdown(f"**q = {q}, scenario {scenario}** · values in **{unit}**"
                + ("" if raw_bytes else " (1 KiB = 1024 bytes)"))
    st.dataframe(table, hide_index=True, column_config={
        **{c.replace("_bytes", ""): num(fmt, label=f"{c.replace('_bytes', '')} ({unit})")
           for c in cols},
        "output_list": num(fmt, label=f"total − prepare current ({unit})",
                           help="Roughly the output list of q bools."),
        "bytes_per_element": num("%.1f", label="prepare current per element (bytes)"),
    })
    base = run["config"].get("memory_baseline")
    if base:
        st.markdown("**Harness baseline** (a no-op method traced the same way; not subtracted): "
                    + ", ".join(f"{k.replace('_bytes', '')} {v:,} bytes" for k, v in base.items()))
    st.caption("*_peak is the highest traced size since tracing started, *_current what is "
               "still allocated at that moment. linear v2 prepares nothing, so its prepare "
               "values are about 0 by design.")


def raw_tab(run):
    raw, summary = run["raw"], run["summary"]
    if raw is not None:
        st.subheader("Raw repeats (timings_raw.csv)")
        cols = st.columns(6)
        filters = {}
        for col, name in zip(cols, ["method", "version", "segment", "n", "q", "scenario"]):
            options = sorted(raw[name].unique().tolist())
            filters[name] = col.multiselect(name, options, default=options, key=f"raw_{name}")
        shown = raw
        for name, chosen in filters.items():
            shown = shown[shown[name].isin(chosen)]
        unit, size = data.pick_unit(shown["elapsed_s"]) if len(shown) else ("µs", 1e-6)
        shown = shown.assign(elapsed=shown["elapsed_s"] / size)
        st.dataframe(shown.drop(columns=["key", "label"]), hide_index=True, column_config={
            "elapsed_s": num("%.6e", label="elapsed_s (seconds per call)"),
            "elapsed": num("%.4g", label=f"elapsed ({unit})"),
            "realized_hit_rate": num("%.2f")})
        st.caption(f"{len(shown):,} of {len(raw):,} rows. elapsed_s is seconds per call "
                   "(measurement time / calls_per_measurement).")
    if summary is not None:
        st.subheader("Spread of each median (timings_summary.csv)")
        unit, size = data.pick_unit(summary["median_s"])
        spread = in_unit(summary, size).assign(
            rel_spread=(summary["max_s"] - summary["min_s"]) / summary["median_s"] * 100,
            overhead=data.near_overhead(summary, run["config"]))
        st.dataframe(spread.drop(columns=["key", "median_s", "min_s", "max_s"]), hide_index=True,
                     column_config={**{c: num("%.4g", label=f"{c} ({unit})")
                                       for c in ("median", "min", "max")},
                                    "rel_spread": num("%.1f%%", label="(max−min)/median"),
                                    "realized_hit_rate": num("%.2f"),
                                    "overhead": st.column_config.CheckboxColumn(
                                        "overhead-dominated")})

    st.subheader("Files of this run")
    left, right = st.columns(2)
    with left.expander("environment.json"):
        st.json(run["env"] or {}, expanded=True)
    with right.expander("run.json"):
        st.json(run["config"], expanded=True)
    buttons = st.columns(4)
    for i, name in enumerate(run["files"]):
        path = Path(run["dir"]) / name
        buttons[i % 4].download_button(f"Download {name}", path.read_bytes(), file_name=name,
                                       mime=MIME.get(path.suffix, "application/octet-stream"),
                                       key=f"download_{name}", on_click="ignore")


PRESETS = {
    "Slide example: [7, 11, 7] with [11, 9, 7] → [True, False, True]": ("7, 11, 7", "11, 9, 7"),
    "Empty array": ("", "1, 2, 3"),
    "Empty queries": ("5, 3, 8", ""),
    "One entry": ("42", "42, 41, 43"),
    "Duplicates, unsorted, negative IDs": ("5, -3, 5, 0, 9, -3, 2, 2", "-3, 0, 4, 9, 5, 10, -4, 2"),
    "Big integers": ("123456789012345678901234567890, -1, 0", "123456789012345678901234567890, 1"),
    "At the cap: 10,000 IDs 0..9,999": (" ".join(map(str, range(10_000))),
                                        "-1, 0, 5000, 9999, 10000"),
    "Invalid: decimal in the array (expect TypeError)": ("1, 2.5, 3", "2"),
    "Invalid: bool as a query (expect TypeError)": ("0, 1", "True"),
    "Invalid: text in the queries (expect TypeError)": ("1, 2, 3", "1, two"),
}


def _apply_preset():
    st.session_state.spot_ids, st.session_state.spot_queries = PRESETS[st.session_state.spot_preset]
    st.session_state.pop("spot_result", None)


def spot_check_tab():
    here = checked_out_git()
    st.markdown(
        "Try your own input: type an ID array and queries (integers separated by commas or "
        f"spaces, at most {data.MAX_SPOT_ELEMENTS:,} each) or pick a preset, then compare every "
        "method/version with the reference `[q in list(ids) for q in queries]`.")
    st.caption("Each method runs through `Method.__call__` (validation, prepare, query) on its "
               "own copy of the input. Non-integer tokens are passed on as float, bool or str, "
               "so invalid input should raise TypeError. Nothing is timed. Runs the checked-out "
               f"code (commit {here.get('short') or 'unknown'}"
               f"{', with uncommitted changes' if here.get('dirty') else ''}).")
    first = next(iter(PRESETS))
    st.session_state.setdefault("spot_ids", PRESETS[first][0])
    st.session_state.setdefault("spot_queries", PRESETS[first][1])
    st.selectbox("Preset", list(PRESETS), key="spot_preset", on_change=_apply_preset)
    left, right = st.columns(2)
    left.text_area("ID array", key="spot_ids", height=100)
    right.text_area("Queries", key="spot_queries", height=100)
    clicked = st.button("Run all methods", key="spot_run", type="primary")
    if clicked or "spot_result" not in st.session_state:
        try:
            ids = data.parse_values(st.session_state.spot_ids, "ID array")
            queries = data.parse_values(st.session_state.spot_queries, "queries")
        except ValueError as exc:
            st.session_state.spot_result = {"error": str(exc)}
        else:
            with st.spinner("Running every method (linear search is O(n·q))..."):
                st.session_state.spot_result = {"ids": ids, "queries": queries,
                                                **data.run_spot_check(METHODS, ids, queries)}
    show_spot_result(st.session_state.spot_result)


def show_spot_result(res):
    if "error" in res:
        st.error(res["error"])
        return
    rows = pd.DataFrame(res["rows"])
    bad = rows.loc[~rows["ok"], "label"].tolist()
    n_ids, n_q = len(res["ids"]), len(res["queries"])
    if res["valid"] and not bad:
        st.success(f"All {len(rows)} method/versions return the reference output for all {n_q} "
                   f"queries (array of {n_ids}) as a list of bools and leave the input unchanged.")
    elif res["valid"]:
        st.error("Disagreement with the reference or with the contract: " + ", ".join(bad))
    elif not bad:
        st.success("The input contains non-integer values; every method rejected it with "
                   "TypeError, as specified.")
    else:
        st.error("Invalid input, but these methods did not raise TypeError: " + ", ".join(bad))
    st.dataframe(rows.drop(columns="key").style.apply(
        lambda r: ["background-color: rgba(227, 73, 72, 0.35)" if not r["ok"] else ""] * len(r),
        axis=1), hide_index=True)

    if not res["valid"] or not n_q:
        return
    reference = res["reference"]
    labels = {m.key: m.label for m in METHODS}
    table = pd.DataFrame({"query": [repr(q) for q in res["queries"]],
                          "reference": [repr(v) for v in reference]})
    for key, out in res["outputs"].items():
        table[labels.get(key, key)] = [repr(out[i]) if i < len(out) else "missing"
                                       for i in range(n_q)]
    method_cols = [c for c in table.columns if c not in ("query", "reference")]
    differs = table[method_cols].ne(table["reference"], axis=0)
    if st.toggle("Only rows where a method disagrees", key="spot_only_bad"):
        table, differs = table[differs.any(axis=1)], differs[differs.any(axis=1)]
    st.dataframe(table.style.apply(lambda col: [
        "background-color: rgba(227, 73, 72, 0.35)" if d else "" for d in differs[col.name]]
        if col.name in method_cols else [""] * len(col)), hide_index=False)
    st.caption("Index = query position. Highlighted cells differ from the reference (compared as "
               "printed values, so 1 instead of True also counts as a disagreement).")


# --- page -----------------------------------------------------------------------------

def main():
    st.set_page_config(page_title="Search benchmark review", layout="wide")
    root = data.results_dir()
    runs = data.list_runs(root) if root.is_dir() else []
    if not runs:
        st.title("Search benchmark review")
        st.error(f"No runs found in {root}. Create one with `python -m benchmarks.run` "
                 "(or set RESULTS_DIR).")
        return

    by_path = {r["path"]: r for r in runs}
    st.sidebar.header("Run")
    path = st.sidebar.selectbox(
        "Saved run", list(by_path), index=data.default_run_index(runs), key="run",
        format_func=lambda p: by_path[p]["run_id"] + ("  (quick)" if by_path[p]["quick"] else ""),
        help="Default: the newest full (non-quick) run, else the newest run.")
    run = load_run(path, data.dir_stamp(path))
    cfg, env = run["config"], run["env"] or {}
    git = env.get("git") or {}

    st.title("Search benchmark review")
    st.caption(f"Run **{cfg.get('run_id')}** · commit `{git.get('short') or 'unknown'}` on "
               f"`{git.get('branch') or '?'}` · reads saved files only, never re-runs a benchmark")
    status = cfg.get("status")
    if status is not None and status != "complete":
        st.error(f"**Run status: {status}.** The run did not complete; its results may be "
                 "partial or wrong.")
    if cfg.get("source_unchanged") is False:
        st.error("**The measured code changed during the run** (source fingerprint differs at "
                 "the end). Do not use these results.")
    if git.get("dirty"):
        dirty = git.get("dirty_files", [])
        listed = (", ".join(f"`{f.strip()}`" for f in dirty) if len(dirty) <= 5
                  else f"{len(dirty)} (listed in Details → Provenance)")
        st.warning("**Uncommitted changes at run time (git dirty).** The commit hash does not "
                   "identify the measured code exactly; the source fingerprint (Details → Provenance) "
                   f"does. Dirty files: {listed}")
    elif run["env"] and git.get("dirty", "missing") is None:
        st.warning("**Git state unknown at run time** (git unavailable or not a repository). "
                   "The commit hash cannot identify the measured code; rely on the source "
                   "fingerprint in Details → Provenance.")
    if by_path[path]["quick"]:
        st.info("This is a quick development run (small grid, fewer repeats), not the full "
                "measurement grid.")
    if (cfg.get("tests") or {}).get("exit_code") not in (0, None):
        st.error(f"The test suite failed in this run: {cfg['tests'].get('summary')}")
    missing = [f for f in ("environment.json", "datasets.csv", "timings_raw.csv",
                           "timings_summary.csv", "memory.csv", "tests.xml") if f not in run["files"]]
    if missing:
        st.warning("Missing from this run: " + ", ".join(missing))

    summary = run["summary"]
    st.sidebar.header("Filters")
    grid = cfg.get("grid", {})
    qs = sorted(summary["q"].unique().tolist()) if summary is not None else grid.get(
        "query_counts", [])
    q = st.sidebar.selectbox("Query count q", qs, index=len(qs) - 1 if qs else None, key="q",
                             help="Applies to the Runtime tab and to Details → Scaling slopes and Memory.")
    # Only the scenarios measured for this q (e.g. q = 1 "mixed" is not part of the grid).
    measured = set(summary.loc[summary["q"] == q, "scenario"]) if summary is not None else set()
    scenarios = ([s for s in data.SCENARIO_ORDER if s in measured]
                 + sorted(measured - set(data.SCENARIO_ORDER))) or grid.get("scenarios", [])
    scenario = st.sidebar.selectbox("Scenario", scenarios, key="scenario",
                                    index=scenarios.index("mixed") if "mixed" in scenarios else 0,
                                    help="Scenarios measured for the chosen q.")
    st.sidebar.caption(f"{len(runs)} run(s) in the results folder. Times are seconds per call, "
                       "shown in the unit named on each axis or column.")

    overview, runtime, spot, details = st.tabs(["Overview", "Runtime", "Spot check",
                                                "Details for auditors"])
    with overview:
        overview_tab(run)
    with runtime:
        if summary is None or q is None:
            st.info("timings_summary.csv is not part of this run.")
        else:
            runtime_tab(run, q, scenario)
    with spot:
        spot_check_tab()
    with details:
        details_tab(run, q, scenario)


def details_tab(run, q, scenario):
    timed = run["summary"] is not None and q is not None
    sections = {
        "Provenance & environment": lambda: provenance_tab(run),
        "Tests": lambda: correctness_tab(run),
        "Definitions & inputs": lambda: definitions_tab(run),
        "v1 vs v2 numbers": lambda: revision_details(run),
        "Scaling slopes": lambda: scaling_tab(run, q, scenario),
        "Memory": lambda: memory_tab(run, q, scenario),
        "Raw data & downloads": lambda: raw_tab(run),
    }
    section = st.radio("Section", list(sections), horizontal=True, key="details",
                       label_visibility="collapsed")
    if section in ("v1 vs v2 numbers", "Scaling slopes") and not timed:
        st.info("timings_summary.csv is not part of this run.")
        return
    sections[section]()


main()
