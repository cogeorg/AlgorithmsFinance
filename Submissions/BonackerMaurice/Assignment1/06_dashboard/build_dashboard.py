"""Build 06_dashboard/dashboard.html from saved results only.

Usage (from Assignment1/):
    python 06_dashboard/build_dashboard.py

Reads ONLY files in 05_results/ (it never replays or benchmarks anything).
Final benchmark (04_benchmarks/run_benchmark.py):
    benchmark_run.json, environment.json     provenance, limits, definitions
    benchmark_summary.csv                    median / min / max per cell
    benchmark_results.csv                    every raw repeat (+ memory rows)
    concentration_check.csv                  price-time check, 4 vs 1,000 levels
    latency_summary.csv, latency_quantiles.csv, latency_by_type.csv
    memory_end_state.csv, memory_samples.csv
    opcounts.csv
Latency and memory rerun (run_benchmark.py --latency-memory):
    benchmark_run_latency_memory.json, environment_latency_memory.json
Correctness: tests_by_case.csv + tests_by_case_run.json (commit and code state
of the test run; 04_benchmarks/export_test_results.py), differential_tests.csv.
The only other thing it reads is the checked-out code, to say whether it is
the code that was measured (source fingerprint).
Writes one self-contained HTML file; charts are PNGs embedded as base64.
"""

import base64
import csv
import html
import io
import json
import statistics
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "05_results"
OUT = Path(__file__).resolve().parent / "dashboard.html"

BTC = 100_000_000

# Fixed colour and label per version (never by rank). Colour = version everywhere.
VERSION_ORDER = ["a", "b_sorted", "b_heap"]
VERSION_COLORS = {"a": "#2a78d6", "b_sorted": "#eb6834", "b_heap": "#1baf7a"}
VERSION_LABELS = {"a": "Version A", "b_sorted": "Version B-sorted",
                  "b_heap": "Version B-heap"}
SCENARIO_ORDER = ["buildup", "crowded", "mixed", "sweep", "cancel_churn"]


def label(version):
    return VERSION_LABELS.get(version, f"Version {version}")


# ----- loading ------------------------------------------------------------------

def read_csv(name):
    path = RESULTS / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def read_json(name):
    path = RESULTS / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# ----- formatting helpers ---------------------------------------------------------

def versions_in(rows):
    present = {r["version"] for r in rows} - {"none", "all"}
    return [v for v in VERSION_ORDER if v in present] + sorted(present - set(VERSION_ORDER))


def scenarios_in(rows):
    present = {r["scenario"] for r in rows}
    ordered = [s for s in SCENARIO_ORDER if s in present]
    return ordered + sorted(present - set(ordered))


def btc(units):
    units = int(units)
    return f"{units // BTC:,}.{units % BTC:08d}"


def fmt_time(seconds):
    if seconds < 1e-3:
        return f"{seconds * 1e6:.1f} µs"
    if seconds < 1:
        return f"{seconds * 1e3:.2f} ms"
    return f"{seconds:.2f} s"


def fmt_bytes(n):
    n = float(n)
    if n >= 2 ** 20:
        return f"{n / 2 ** 20:.2f} MiB"
    return f"{n / 2 ** 10:.1f} KiB"


def html_table(header, rows):
    head = "".join(f"<th>{html.escape(str(h))}</th>" for h in header)
    body = "\n".join("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in row)
                     + "</tr>" for row in rows)
    return f"<table>\n<tr>{head}</tr>\n{body}\n</table>"


def details(summary, inner):
    return f"<details><summary>{html.escape(summary)}</summary>\n{inner}\n</details>"


def figure_to_img(fig, alt):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return f'<img alt="{html.escape(alt)}" src="data:image/png;base64,{data}">'


def style_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(color="#e5e5e5", linewidth=0.8)
    ax.set_axisbelow(True)


# ----- aggregation over seeds -------------------------------------------------------

def seed_groups(summary, experiment, phase):
    """(version, scenario, levels, M, sale_pct) -> summary rows, one per seed."""
    groups = {}
    for r in summary:
        if r["experiment"] == experiment and r["phase"] == phase:
            key = (r["version"], r["scenario"], int(r["levels"]), int(r["dataset_events"]),
                   r["sale_pct"])
            groups.setdefault(key, []).append(r)
    return groups


def aggregate(rows):
    """A cell over its seeds. Plotted only if EVERY seed finished (no bias towards
    the seeds that happened to finish)."""
    ok = [r for r in rows if r["status"] == "ok"]
    out = {"seeds": len(rows), "ok_seeds": len(ok), "ok": len(ok) == len(rows)}
    if out["ok"]:
        out["median"] = statistics.median(float(r["median_seconds"]) for r in ok)
        out["lo"] = min(float(r["min_seconds"]) for r in ok)
        out["hi"] = max(float(r["max_seconds"]) for r in ok)
        tp = [float(r["throughput_events_per_s"]) for r in ok if r["throughput_events_per_s"]]
        out["throughput"] = statistics.median(tp) if tp else None
    out["statuses"] = sorted({r["status"] for r in rows})
    return out


def not_ok_text(agg):
    what = "stopped" if "stopped" in agg["statuses"] else "/".join(agg["statuses"])
    return f"{what} ({agg['seeds'] - agg['ok_seeds']} of {agg['seeds']} seeds)"


def plot_vs_m(groups, panels, title, ylabel, alt, ncols=3):
    """Small multiples: one panel per (title, scenario, levels, pct); colour = version.
    Point = median over seeds of the per-seed medians; bar = min..max of all
    timed repeats of all seeds. A cell that did not finish in every seed is text."""
    n = len(panels) + 1                                  # + legend panel
    nrows = -(-n // ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(11, 3.1 * nrows), squeeze=False,
                             sharex=True)
    axes = axes.ravel()
    versions = [v for v in VERSION_ORDER if any(k[0] == v for k in groups)]
    stopped_items = []
    for ax, (ptitle, scenario, levels, pct) in zip(axes, panels):
        notes = []
        for version in versions:
            cells = sorted((k[3], aggregate(rows)) for k, rows in groups.items()
                           if k[0] == version and k[1] == scenario and k[2] == levels
                           and k[4] == pct)
            ok = [(m, a) for m, a in cells if a["ok"]]
            if ok:
                xs = [m for m, _ in ok]
                ys = [a["median"] for _, a in ok]
                err = [[a["median"] - a["lo"] for _, a in ok],
                       [a["hi"] - a["median"] for _, a in ok]]
                ax.errorbar(xs, ys, yerr=err, marker="o", markersize=4, linewidth=2,
                            capsize=3, color=VERSION_COLORS[version], label=label(version))
            for m, a in cells:
                if not a["ok"]:
                    notes.append(f"{label(version)}, M = {m:,}: {not_ok_text(a)}")
                    stopped_items.append(f"{ptitle}: {label(version)}, M = {m:,}: "
                                         f"{not_ok_text(a)}")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(ptitle, loc="left", fontsize=10)
        style_axes(ax)
        if notes:
            ax.text(0.98, 0.03, "\n".join(notes), transform=ax.transAxes, ha="right",
                    va="bottom", fontsize=7, color="#555555")
    for ax in axes[len(panels):]:
        ax.axis("off")
    handles, labels_ = [], []
    for ax in axes[:len(panels)]:
        for h, lab in zip(*ax.get_legend_handles_labels()):
            if lab not in labels_:
                handles.append(h)
                labels_.append(lab)
    axes[len(panels)].legend(handles, labels_, loc="center", frameon=False)
    fig.supxlabel("events M (log scale)", fontsize=10)
    fig.supylabel(ylabel, fontsize=10)
    fig.suptitle(title, x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    img = figure_to_img(fig, alt)
    if stopped_items:
        items = "\n".join(f"<li>{html.escape(s)}</li>" for s in stopped_items)
        img += ("\n<p>Not plotted (no value, never estimated; a line ends at its last "
                f"point measured in every seed):</p>\n<ul>\n{items}\n</ul>")
    return img


# ----- sections: final benchmark -----------------------------------------------------

def current_fingerprint():
    sys.path.insert(0, str(ROOT / "04_benchmarks"))
    try:
        from bench_common import source_fingerprint
        return source_fingerprint()
    except Exception:                                    # noqa: BLE001
        return None


def code_match(run, now):
    """'yes', 'unknown', or 'NO' plus the files that differ from the measured code."""
    if not now:
        return "unknown"
    if now["sha256"] == run.get("source_sha256_start"):
        return "yes"
    old, new = run.get("source_files") or {}, now["files"]
    parts = [("changed since the run", sorted(f for f in old.keys() & new.keys()
                                              if old[f] != new[f])),
             ("added", sorted(new.keys() - old.keys())),
             ("removed", sorted(old.keys() - new.keys()))]
    detail = "; ".join(f"{k}: {', '.join(v)}" for k, v in parts if v)
    return f"NO ({detail}). The results describe the measured commit." if detail else "NO"


def rerun_rows(run, env, rerun, renv, now):
    """Provenance of a separate latency and memory run, next to the full run."""
    git = rerun["git"]
    differs = [name for name in ("python", "packages", "os") if (env or {}).get(name)
            != (renv or {}).get(name)]
    if (env or {}).get("machine") != (renv or {}).get("machine"):
        differs.append("machine or power state")
    phases = ", ".join(f"{p['name']} {p['seconds']:.0f} s" for p in rerun["phases"])
    return [
        ["measured commit", f"{git.get('commit')} (branch {git.get('branch')})"],
        ["command", rerun["command"]],
        ["code committed and clean at start", "yes" if git.get("code_clean") else "NO"],
        ["code unchanged during the run", "yes" if rerun.get("source_unchanged") else "NO"],
        ["checked-out code = measured code", code_match(rerun, now)],
        ["engines (lob_a, lob_b_*, validation) = full run", engines_match(run, rerun)],
        ["run status", f"{rerun['status']} ({phases})"],
        ["started / finished (UTC)", f"{rerun['started_utc']} / {rerun['finished_utc']}"],
        ["machine, power state, OS, Python, packages vs the full run",
         "the same" if not differs else "DIFFERENT: " + ", ".join(differs)],
    ]


def engines_match(run, rerun):
    old, new = run.get("source_files") or {}, rerun.get("source_files") or {}
    names = [f for f in sorted(old.keys() | new.keys())
             if "03_code/lob_" in f or f.endswith("03_code/validation.py")]
    diff = [f for f in names if old.get(f) != new.get(f)]
    return "unknown" if not names else "yes (same checksums)" if not diff else \
        "NO: " + ", ".join(diff)


def section_provenance(run, env, rerun, renv):
    if not run:
        return "<h2>Provenance</h2>\n<p>No benchmark run saved (05_results/benchmark_run.json).</p>"
    git, s = run["git"], run["settings"]
    now = current_fingerprint()
    machine = env["machine"] if env else {}
    rows = [
        ["measured commit", f"{git.get('commit')} (branch {git.get('branch')})"],
        ["code committed and clean at start", "yes" if git.get("code_clean") else "NO"],
        ["whole repository clean at start", "yes" if git.get("tree_clean") else "no"],
        ["code unchanged during the run", "yes" if run.get("source_unchanged") else "NO"],
        ["checked-out code = measured code", code_match(run, now)],
        ["run status", run["status"]],
        ["started / finished (UTC)", f"{run['started_utc']} / {run['finished_utc']}"],
        ["tests before the run", ", ".join(f"{v} {k}" for k, v in
                                           (run.get("tests") or {}).get("counts", {}).items())],
        ["time limit", f"{s['time_limit_s_per_replay']:g} s per single replay, build or "
                       "sell (stopped steps are recorded, never estimated)"],
        ["repeats", f"{s['warmups']} warm-up + {s['repeats']} timed; median, min, max"],
        ["GC policy", s["gc_policy"]],
        ["machine", f"{machine.get('cpu')}, {machine.get('logical_cpus')} logical CPUs, "
                    f"{(machine.get('ram_bytes') or 0) / 2**30:.1f} GiB RAM, "
                    f"on AC power: {machine.get('on_ac_power')}"],
        ["software", f"Python {env['python']['version']} on {env['os']['platform']}; "
                     f"pytest {env['packages']['pytest']}, matplotlib "
                     f"{env['packages']['matplotlib']}; engine: standard library only"
         if env else ""],
        ["clock", f"perf_counter = {env['perf_counter']['implementation']}, resolution "
                  f"{env['perf_counter']['resolution_s']:g} s" if env else ""],
    ]
    terms = {**run["definitions"], **((rerun or {}).get("definitions") or {})}
    defs = html_table(["term", "definition"], sorted(terms.items()))
    second = ""
    if rerun:
        second = ("<p><b>Latency and memory come from a later, separate run</b> (per-type "
                  "latency, memory sampled with the returned output). It replaced only the "
                  "latency and memory rows; everything else is from the full run above.</p>\n"
                  + html_table(["", ""], rerun_rows(run, env, rerun, renv, now)) + "\n")
    return ("<h2>Provenance</h2>\n<p>Full benchmark run:</p>\n" + html_table(["", ""], rows)
            + "\n" + second +
            "<p>Reproduce (from Assignment1/): <code>python -m pip install -r "
            "requirements.txt</code>, then <code>python 04_benchmarks/run_benchmark.py</code> "
            "(regenerates the data; checksums in benchmark_datasets.csv), then "
            "<code>python 06_dashboard/build_dashboard.py</code>. Latency and memory only: "
            "<code>python 04_benchmarks/run_benchmark.py --latency-memory</code>.</p>\n"
            "<p><b>Limitation:</b> latency, memory and operation counts were measured on "
            "seed 42 only; timing covers seeds 42, 43 and 44.</p>\n"
            + details("Measurement definitions (saved with the runs)", defs))


def test_run_label(tests, now):
    """Which commit and code state the test table comes from."""
    info = read_json("tests_by_case_run.json")
    passed = sum(r["result"] == "pass" for r in tests)
    if not info:
        return (f"<p><b>Test cases: {passed} of {len(tests)} pass.</b> Commit unknown "
                "(05_results/tests_by_case_run.json is missing).</p>")
    dirty = info.get("uncommitted_code_files") or []
    core = [f for f in dirty if f.startswith(("02_tests/", "03_code/"))
            or f in ("pytest.ini", "requirements.txt")]
    if not dirty:
        state = "Code committed and clean at that time"
    else:
        state = ("Uncommitted code files at that time: " + ", ".join(dirty) + "; tests and "
                 "engines (02_tests, 03_code, pytest.ini, requirements.txt) "
                 + ("NOT as committed" if core else "as committed"))
    same = ("unknown" if not now else
            "yes" if now["sha256"] == info.get("source_sha256") else "NO")
    return (f"<p><b>Test cases, run on commit {html.escape(str(info['commit'])[:7])}</b> "
            f"(branch {html.escape(str(info.get('branch')))}, "
            f"{info['finished_utc'].replace('T', ' ').replace('+00:00', '')} UTC, "
            f"Python {info['python']}, pytest {info['pytest']}): <b>{passed} of {len(tests)} "
            f"pass</b>. Command: <code>{html.escape(info['command'])}</code>. "
            f"{html.escape(state)}. Checked-out code = tested code: {same}. "
            "This test run is separate from the benchmark run (see Provenance). "
            "n/a = not defined for that version (white-box tests of one variant); "
            "a cell with several cases counts every parameter case of that test.</p>")


def section_correctness(run):
    tests = read_csv("tests_by_case.csv")
    parts = ["<h2>Correctness</h2>"]
    if tests:
        versions = versions_in(tests)
        has_none = any(r["version"] == "none" for r in tests)
        cases = {}
        for r in tests:
            cases.setdefault((r["test"], r["source"]), {}).setdefault(
                r["version"], []).append(r["result"])

        def cell(results):
            ok = results.count("pass")
            if len(results) == 1:
                return results[0]
            return (f"pass ({ok} cases)" if ok == len(results)
                    else f"FAIL: {ok} of {len(results)} pass")

        header = (["test", "source of expected values"] + [label(v) for v in versions]
                  + (["no engine needed"] if has_none else []))
        rows = []
        for (test, source), by_version in cases.items():
            cols = [cell(by_version[v]) if v in by_version
                    else cell(by_version["all"]) if "all" in by_version else "n/a"
                    for v in versions]
            if has_none:
                cols.append(cell(by_version["none"]) if "none" in by_version else "")
            rows.append([test, source] + cols)
        parts.append(test_run_label(tests, current_fingerprint()))
        parts.append(html_table(header, rows))

    diff = read_csv("differential_tests.csv")
    if diff:
        total = lambda k: sum(int(r[k]) for r in diff)  # noqa: E731
        bad = sum(r["result"] != "pass" for r in diff)
        parts.append(
            f"<p>Differential test (differential_tests.csv): {len(diff)} seeded random "
            f"streams, {total('events'):,} events, results and books compared after every "
            f"event across A, B-sorted and B-heap: {total('mismatching_events')} "
            f"mismatching events, {total('invariant_failures')} invariant failures, "
            f"{bad} failed streams.</p>")

    bench_commit = str(((run or {}).get("git") or {}).get("commit"))[:7]
    conc = read_csv("concentration_check.csv")
    if conc:
        header = ["stream", "versions", "events", "book checkpoints", "mismatches",
                  "invariant failures", "full sale: fills", "price levels",
                  "max fills at one price", "price-time check", "result"]
        rows = [[r["dataset"], r["versions"].replace(";", ", "), r["events"],
                 r["book_checkpoints"], r["mismatches"], r["invariant_failures"],
                 r["sale_fills"], r["sale_price_levels"], r["max_fills_at_one_price"],
                 r["sale_check"], r["result"]] for r in conc]
        fails = sum(r["result"] != "pass" for r in conc)
        parts.append("<p>Queue concentration check (concentration_check.csv, from the "
                     f"benchmark run at commit {html.escape(bench_commit)}): results "
                     "compared after every event, books and invariants at 10 checkpoints; "
                     "then a 100% sale through the queues, checked against the price-time "
                     f"oracle (invariants.check_event). {len(conc) - fails} of {len(conc)} "
                     "streams pass. Version A takes part up to M = 10,000.</p>")
        parts.append(details("Concentration check, every stream", html_table(header, rows)))

    results = read_csv("benchmark_results.csv")
    if results:
        measured = [r for r in results if r["run_kind"] == "timing"
                    and r["phase"] in ("replay", "build", "sell")
                    and r["status"] in ("ok", "mismatch")]
        mism = [r for r in measured if r["status"] == "mismatch"]
        parts.append(f"<p>Checks after every timed replay, build and sale of the benchmark "
                     f"run at commit {html.escape(bench_commit)} (fill count and "
                     f"final book size vs the dataset manifest; conservation of the sold "
                     f"quantity): {len(measured) - len(mism):,} of {len(measured):,} "
                     f"measurements agree, {len(mism)} mismatches.</p>")
    return "\n".join(parts)


def section_replay(summary):
    groups = seed_groups(summary, "replay", "replay")
    panels = [(s, s, 1000, "") for s in scenarios_in(summary)]
    img = plot_vs_m(groups, panels, "Full-stream replay time vs events (5 scenarios)",
                    "replay time (seconds, log scale)", "replay time vs M")
    return ("<h2>Replay scaling: construction and full streams</h2>\n"
            "<p>Engine replay of preloaded events on a fresh book (parsing excluded, "
            "reported separately). buildup and crowded are the submission flood "
            "(book construction: every event rests); the others are full mixed "
            "streams. Point = median over seeds 42, 43, 44 of each seed's 5-repeat "
            "median; error bar = fastest to slowest of all 15 timed repeats. "
            "Units: seconds.</p>\n" + img)


def section_throughput(summary):
    rows = []
    for experiment in ("replay", "million"):
        groups = seed_groups(summary, experiment, "replay")
        keys = sorted({(k[1], k[3]) for k in groups},
                      key=lambda x: (SCENARIO_ORDER.index(x[0]) if x[0] in SCENARIO_ORDER
                                     else 99, x[1]))
        for scenario, m in keys:
            cols = []
            for v in VERSION_ORDER:
                g = [rs for k, rs in groups.items() if k[0] == v and k[1] == scenario
                     and k[3] == m]
                if not g:
                    cols.append("")
                    continue
                a = aggregate(g[0])
                cols.append(f"{a['throughput']:,.0f}" if a["ok"] else not_ok_text(a))
            seeds = "43" if experiment == "million" else "42, 43, 44"
            rows.append([scenario, f"{m:,}", seeds] + cols)
    parse = seed_groups(summary, "replay", "parse")
    parse_rows = []
    for m in sorted({k[3] for k in parse}):
        vals = [float(r["median_seconds"]) / m for k, rs in parse.items() if k[3] == m
                for r in rs if r["status"] == "ok"]
        if vals:
            parse_rows.append(f"M = {m:,}: {statistics.median(vals) * 1e6:.1f} µs per event")
    return ("<h2>Throughput</h2>\n<p>events / median replay seconds (median over the "
            "seeds), in events per second. Higher is better. 'stopped (k of n seeds)': "
            "the replay exceeded the time limit in k seeds, so no throughput is "
            "reported.</p>\n"
            + html_table(["scenario", "events M", "seeds"] + [label(v) for v in VERSION_ORDER],
                         rows)
            + "\n<p>Reading and parsing (gzip + JSON, all scenarios and versions, median): "
            + "; ".join(parse_rows) + ".</p>")


def verdict(s, h):
    """Compare two 5-repeat ranges. Overlap = no reliable difference."""
    if float(s["max_seconds"]) < float(h["min_seconds"]):
        return "B-sorted"
    if float(h["max_seconds"]) < float(s["min_seconds"]):
        return "B-heap"
    return "overlap"


def section_sorted_vs_heap(summary):
    workloads = []
    for scenario in SCENARIO_ORDER:
        workloads.append((f"replay {scenario}", "replay", "replay", scenario, 1000, None))
    workloads.append(("replay mixed, 1M events", "million", "replay", "mixed", 1000, None))
    workloads.append(("liquidation: build", "liquidation", "build", "sweep", 1000, None))
    for pct in ("10", "100", "200"):
        workloads.append((f"liquidation: sell {pct}%", "liquidation", "sell", "sweep", 1000,
                          pct))
    for levels in (4, 1000):
        for phase in ("build", "sell"):
            workloads.append((f"concentration L{levels}: {phase}", "concentration", phase,
                              "buildup", levels, None))
    index = {}
    for r in summary:
        if r["version"] in ("b_sorted", "b_heap") and r["status"] == "ok":
            key = (r["experiment"], r["phase"], r["scenario"], int(r["levels"]),
                   int(r["dataset_events"]), r["sale_pct"], r["seed"])
            index.setdefault(key, {})[r["version"]] = r
    rows = []
    totals = {"B-sorted": 0, "B-heap": 0, "overlap": 0}
    for name, exp, phase, scenario, levels, pct in workloads:
        for m in sorted({k[4] for k in index if k[0] == exp and k[1] == phase}):
            counts = {"B-sorted": 0, "B-heap": 0, "overlap": 0}
            ratios = []
            for k, pair in index.items():
                if (k[0], k[1], k[2], k[3], k[4]) != (exp, phase, scenario, levels, m):
                    continue
                if pct is not None and k[5] != pct:
                    continue
                if len(pair) < 2:
                    continue
                s, h = pair["b_sorted"], pair["b_heap"]
                counts[verdict(s, h)] += 1
                ratios.append(float(h["median_seconds"]) / float(s["median_seconds"]))
            if not ratios:
                continue
            for k in totals:
                totals[k] += counts[k]
            rows.append([name, f"{m:,}", len(ratios), counts["B-sorted"], counts["B-heap"],
                         counts["overlap"], f"{statistics.median(ratios):.2f}"])
    n = sum(totals.values())
    return ("<h2>B-sorted vs B-heap: is there a reliable winner?</h2>\n"
            "<p>For each cell (workload, M, seed; liquidation builds also per sale size) "
            "the 5 timed repeats of each variant give a range from fastest to slowest. "
            "A variant counts as faster only when its slowest repeat beats the other's "
            "fastest repeat; otherwise the ranges overlap and there is no reliable "
            "difference. Ratio = B-heap median / B-sorted median (above 1: B-sorted "
            f"faster). Over all {n} comparisons: B-sorted faster in {totals['B-sorted']}, "
            f"B-heap faster in {totals['B-heap']}, overlap in {totals['overlap']}.</p>\n"
            + html_table(["workload", "events M", "comparisons", "B-sorted faster",
                          "B-heap faster", "ranges overlap", "median ratio heap/sorted"],
                         rows))


def section_liquidation(summary, datasets):
    groups = {}           # panel key in the sale_pct slot: "build" or "sell <pct>"
    for k, rows in seed_groups(summary, "liquidation", "build").items():
        if k[4] == "10":   # builds for the other sale sizes are the same workload
            groups[k[:4] + ("build",)] = rows
    for k, rows in seed_groups(summary, "liquidation", "sell").items():
        groups[k[:4] + (f"sell {k[4]}",)] = rows
    panels =[("build (first 80% of sweep)", "sweep", 1000, "build"),
              ("sell 10%", "sweep", 1000, "sell 10"), ("sell 100%", "sweep", 1000, "sell 100"),
              ("sell 200%", "sweep", 1000, "sell 200")]
    img = plot_vs_m(groups, panels, "Large liquidation: book build and one market sale",
                    "seconds (log scale)", "liquidation times vs M", ncols=3)
    table = []
    sells = {(int(r["dataset_events"]), r["sale_pct"], r["version"]): r for r in summary
             if r["experiment"] == "liquidation" and r["phase"] == "sell" and r["seed"] == "42"}
    for (m, pct, v), r in sorted(sells.items(), key=lambda x: (x[0][0], int(x[0][1]),
                                                               VERSION_ORDER.index(x[0][2]))):
        ds = datasets.get(f"sweep_M{m}_seed42_L1000", {})
        table.append([f"{m:,}", ds.get("build_bid_orders", ""),
                      ds.get("build_bid_price_levels", ""), f"{pct}%", label(v),
                      btc(r["requested_qty_units"]) if r["requested_qty_units"] else "",
                      r["fills"], r["makers_touched"], r["price_levels_visited"],
                      btc(r["unfilled_qty_units"]) if r["unfilled_qty_units"] else "",
                      fmt_time(float(r["median_seconds"])) if r["status"] == "ok"
                      else r["status"]])
    return ("<h2>Large liquidation</h2>\n<p>Book = first 80% of each sweep file (LIMIT "
            "events only, they never cross). Each sale size runs on its own freshly built "
            "book in every repeat; build and sale are timed separately. The sale time "
            "includes validation, matching, state updates and building the fill list. "
            "The build panel shows the build for the 10% sale (the builds for the other "
            "sizes are identical). A stopped build stops all three sales of that book.</p>\n"
            + img + "\n"
            + details("Sale details, seed 42 (counts are the same for every version)",
                      html_table(["M", "bid orders", "bid levels", "sale", "version",
                                  "requested (BTC)", "fills", "makers touched",
                                  "price levels visited", "unfilled (BTC)",
                                  "median sale time"], table)))


def section_concentration(summary, datasets):
    rows = []
    for phase in ("build", "sell"):
        groups = seed_groups(summary, "concentration", phase)
        for m in sorted({k[3] for k in groups}):
            for levels in (4, 1000):
                cols = []
                for v in VERSION_ORDER:
                    g = groups.get((v, "buildup", levels, m, "100"))
                    if not g:
                        cols.append("")
                        continue
                    a = aggregate(g)
                    cols.append(fmt_time(a["median"]) if a["ok"] else not_ok_text(a))
                rows.append([phase if phase == "build" else "sell 100%", f"{m:,}", levels]
                            + cols)
    twins = sorted(d["dataset"] + " = " + d["identical_events_to"] for d in datasets.values()
                   if d["kind"] == "concentrated" and d["identical_events_to"])
    finding = (f"<p><b>Finding:</b> <code>buildup --levels 4</code> produces exactly the same "
               f"event file as <code>crowded</code> (same sha256) for every M and seed "
               f"({len(twins)} of {sum(d['kind'] == 'concentrated' for d in datasets.values())} "
               "files). The generator draws buildup prices with randrange(levels) and crowded "
               "prices with randrange(4); everything else is drawn identically. So the "
               "4-level build repeats the crowded replay; the 100% sale and the correctness "
               "check are what this experiment adds.</p>") if twins else ""
    return ("<h2>Queue concentration: 4 vs 1,000 prices per side</h2>\n"
            "<p>buildup with the same event count M and seed, generated with --levels 4 "
            "and --levels 1000 (the individual orders differ because the random draws "
            "diverge; the count of resting orders is the same). Build = the whole stream; "
            "then one market sale of 100% of the bids, on a fresh book every repeat. "
            "Median over seeds 42–44 of the 5-repeat medians.</p>\n"
            + html_table(["phase", "events M", "levels per side"]
                         + [label(v) for v in VERSION_ORDER], rows) + "\n" + finding)


def latency_by_type_table():
    """Small per-type table: one row per (file, event type), one column per version."""
    rows = read_csv("latency_by_type.csv")
    if not rows:
        return ""
    cells, counts, differ = {}, {}, 0
    for r in rows:
        key = (int(r["events"]), r["scenario"], r["event_type"])
        if r["status"] == "stopped":
            cells[key + (r["version"],)] = "stopped"
        elif int(r["count"]):
            differ += counts.setdefault(key, int(r["count"])) != int(r["count"])
            cells[key + (r["version"],)] = " / ".join(
                f"{int(r[k]) / 1000:.1f}" for k in ("p50_ns", "p95_ns", "p99_ns", "max_ns"))
    types = list(dict.fromkeys(r["event_type"] for r in rows))
    order = sorted(counts, key=lambda k: (k[0], SCENARIO_ORDER.index(k[1]), types.index(k[2])))
    table = [[k[1], f"{k[0]:,}", k[2], f"{counts[k]:,}"]
             + [cells.get(k + (v,), "") for v in VERSION_ORDER] for k in order]
    never = [t for t in types if not any(k[2] == t for k in counts)]
    bad = [r for r in rows if r["status"] not in ("ok", "stopped")]
    return ("\n<p>Per event type (µs): <b>median / p95 / p99 / max</b>. Every timed event has "
            "exactly one type; LIMIT traded = at least one fill, also if a residual rests. "
            "The counts are the same in every version and agree with the dataset manifest"
            + (f" (NOT in {len(bad) + differ} rows)" if bad or differ else "")
            + ". Types that do not occur in a file are left out"
            + (f"; no file contains events of type {', '.join(never)}" if never else "")
            + ".</p>\n"
            + html_table(["scenario", "M", "event type", "count"]
                         + [label(v) for v in VERSION_ORDER], table))


def section_latency(source):
    summ = read_csv("latency_summary.csv")
    quant = read_csv("latency_quantiles.csv")
    if not summ:
        return "<h2>Processing latency</h2>\n<p>No latency results saved.</p>"
    small = min(int(r["events"]) for r in summ)
    scen = scenarios_in([r for r in summ if int(r["events"]) == small])
    fig, axes = plt.subplots(2, 3, figsize=(11, 6.2), squeeze=False, sharex=True)
    axes = axes.ravel()
    for ax, scenario in zip(axes, scen):
        for v in VERSION_ORDER:
            pts = sorted((float(r["percentile"]), int(r["latency_ns"])) for r in quant
                         if r["version"] == v and r["scenario"] == scenario
                         and int(r["events"]) == small and r["segment"] == "all"
                         and float(r["percentile"]) >= 50)
            if pts:
                ax.plot([p for p, _ in pts], [y / 1000 for _, y in pts], linewidth=2,
                        color=VERSION_COLORS[v], label=label(v))
        ax.set_yscale("log")
        ax.set_title(f"{scenario} (M = {small:,})", loc="left", fontsize=10)
        style_axes(ax)
    for ax in axes[len(scen):]:
        ax.axis("off")
    h, lab = axes[0].get_legend_handles_labels()
    axes[len(scen)].legend(h, lab, loc="center", frameon=False)
    fig.supxlabel("percentile of events (nearest rank), 50 to 100", fontsize=10)
    fig.supylabel("per-event processing time (µs, log scale)", fontsize=10)
    fig.suptitle("Per-event processing latency distribution (upper half), seed 42",
                 x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    img = figure_to_img(fig, "latency distributions")

    def cell(r, k):
        return f"{int(r[k]) / 1000:.1f}" if r["status"] == "ok" else r["status"]

    table = []
    for r in summ:
        if r["segment"] == "all":
            table.append([r["scenario"], f"{int(r['events']):,}", label(r["version"]),
                          cell(r, "p50_ns"), cell(r, "p95_ns"), cell(r, "p99_ns"),
                          cell(r, "max_ns")])
    burst = []
    for r in summ:
        if r["scenario"] == "buildup" and r["segment"] != "all":
            burst.append([f"{int(r['events']):,}", label(r["version"]), r["segment"],
                          cell(r, "p50_ns"), cell(r, "p95_ns"), cell(r, "p99_ns")])
    over = sorted({r["timer_overhead_ns"] for r in summ if r["timer_overhead_ns"]})
    return ("<h2>Processing latency (separate instrumentation run)</h2>\n"
            f"<p>{source}</p>\n"
            "<p>perf_counter_ns() around each process_event call, after one warm-up replay; "
            "GC disabled during the replay. This is algorithm processing latency only: no "
            "queueing or network delay, and no claim about real-time capacity. It is not "
            "derived from throughput. Percentiles: nearest rank. Clock resolution 100 ns "
            f"(QueryPerformanceCounter); median timer overhead {', '.join(over)} ns.</p>\n"
            + img + "\n<p>All events (µs):</p>\n"
            + html_table(["scenario", "M", "version", "p50", "p95", "p99", "max"], table)
            + "\n<p>Submission burst (buildup): first vs last 1,000 events, as the book "
              "grows from empty to M resting orders (µs):</p>\n"
            + html_table(["M", "version", "events", "p50", "p95", "p99"], burst)
            + latency_by_type_table()
            + "\n<p>One instrumented replay per cell (not repeated), so compare orders of "
              "magnitude, not small differences: single events (max, p99 of rare types) are "
              "noisy.</p>")


def section_memory(source):
    end = read_csv("memory_end_state.csv")
    samples = read_csv("memory_samples.csv")
    if not end:
        return "<h2>Memory</h2>\n<p>No memory results saved.</p>"
    big = max(int(r["events"]) for r in end)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, scenario, title in ((axes[0], "buildup", "book growth during insertion"),
                                (axes[1], "cancel_churn", "after many cancellations")):
        notes, series = [], {}
        for v in VERSION_ORDER:
            pts = [(int(r["event_index"]), int(r["traced_current_bytes"])) for r in samples
                   if r["version"] == v and r["scenario"] == scenario
                   and int(r["events"]) == big]
            if pts:
                series[v] = pts
            elif any(r["version"] == v and r["scenario"] == scenario
                     and int(r["events"]) == big and r["status"] != "ok" for r in end):
                notes.append(f"{label(v)}: stopped (time limit)")
        top = max((y for pts in series.values() for _, y in pts), default=0)
        unit, div = ("MiB", 2 ** 20) if top >= 2 ** 20 else ("KiB", 2 ** 10)
        for v, pts in series.items():
            ax.plot([x for x, _ in pts], [y / div for _, y in pts], linewidth=2,
                    color=VERSION_COLORS[v], label=label(v))
        pair = [series.get("b_sorted"), series.get("b_heap")]
        if all(pair) and len(pair[0]) == len(pair[1]) and all(
                abs(ys - yh) <= 0.01 * max(ys, yh) for (_, ys), (_, yh) in zip(*pair)):
            notes.append("B-sorted and B-heap differ by at most 1%\n(the lines overlap)")
        ax.set_title(f"{scenario}, M = {big:,}: {title}", loc="left", fontsize=10)
        ax.set_xlabel("events processed")
        ax.set_ylabel(f"traced memory ({unit})")
        ax.set_ylim(bottom=0)
        style_axes(ax)
        if notes:
            ax.text(0.98, 0.3, "\n".join(notes), transform=ax.transAxes, ha="right",
                    fontsize=8, color="#555555")
        ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3)
    fig.tight_layout()
    img = figure_to_img(fig, "traced memory over the replay")

    table = []
    for r in sorted(end, key=lambda r: (int(r["events"]), SCENARIO_ORDER.index(r["scenario"]),
                                        VERSION_ORDER.index(r["version"]))):
        if r["status"] != "ok":
            table.append([f"{int(r['events']):,}", r["scenario"], label(r["version"]),
                          "stopped"] + [""] * 8)
            continue
        live = int(r["live_orders"])
        per = f"{int(r['traced_current_bytes']) / live:,.0f}" if live else ""
        table.append([f"{int(r['events']):,}", r["scenario"], label(r["version"]),
                      fmt_bytes(r["traced_peak_bytes"]), fmt_bytes(r["traced_current_bytes"]),
                      per, r["live_orders"], r["price_levels"], r["queue_entries"],
                      r["dead_queue_entries"], r["index_entries"], r["stale_index_entries"]])
    ok = [r for r in end if r["status"] == "ok"]
    more = sum(int(r["traced_with_output_bytes"]) > int(r["traced_current_bytes"])
               for r in ok if r.get("traced_with_output_bytes"))
    return ("<h2>Memory (separate tracemalloc run, seed 42)</h2>\n"
            f"<p>{source}</p>\n"
            "<p>Events are loaded before tracing starts, so the input is NOT included. "
            "Included: the book (orders, price levels, FIFO queues, price index) and the "
            "returned result and fill list of the current event, which stays referenced "
            "while the sample is read and is released before the next event. The charts "
            "and the peak therefore hold the book plus one event's output; 'traced at end' "
            "is after the last output is released. Read with the last output still "
            f"referenced, the end value is larger in {more} of {len(ok)} cells (an output "
            "without fills fits into CPython's free lists, which tracemalloc counts either "
            "way). No history is stored. Traced bytes are Python allocations "
            "seen by tracemalloc; they are not the algorithm's auxiliary space (a count of "
            "retained entries, shown on the right) and not process memory (which also holds "
            "the interpreter, the preloaded events and allocator caches).</p>\n" + img + "\n"
            + html_table(["M", "scenario", "version", "traced peak", "traced at end",
                          "bytes per live order (end)", "live orders", "price levels",
                          "queue entries (A: list entries)", "dead queue entries", "index entries",
                          "stale index entries"], table))


def section_opcounts():
    rows = read_csv("opcounts.csv")
    if not rows:
        return "<h2>Operation counts</h2>\n<p>No operation counts saved.</p>"
    pivot = {}
    for r in rows:
        if r["status"] == "ok":
            pivot.setdefault((r["version"], r["scenario"], int(r["events"])), {})[
                r["counter"]] = r
    keys = sorted({(k[1], k[2]) for k in pivot},
                  key=lambda x: (x[1], SCENARIO_ORDER.index(x[0])))
    a_rows, b_rows = [], []
    for scenario, m in keys:
        a = pivot.get(("a", scenario, m))
        if a:
            a_rows.append([scenario, f"{m:,}", a["is_live_scanned"]["per_event"],
                           a["best_index_scanned"]["per_event"],
                           a["cancel_scanned"]["per_event"], a["orders_scanned"]["per_event"],
                           a["orders_scanned"]["max_in_one_event"]])
        for v in ("b_sorted", "b_heap"):
            b = pivot.get((v, scenario, m))
            if b:
                b_rows.append([scenario, f"{m:,}", label(v), b["best_price_calls"]["per_event"],
                               b["queue_pops"]["per_event"], b["dead_entries_popped"]["total"],
                               b["levels_created"]["total"],
                               b["levels_removed_by_match"]["total"],
                               b["levels_removed_by_cancel"]["total"],
                               b["heap_stale_pops"]["total"], b["heap_rebuilds"]["total"],
                               b["deque_compactions"]["total"]])
    return ("<h2>Operation counts (separate diagnostic run, seed 42, not timed)</h2>\n"
            "<p>Counting subclasses of the engines (the engine code is unchanged). "
            "Version A: list elements visited per event. Version B: index and queue "
            "work.</p>\n"
            + html_table(["scenario", "M", "duplicate-id scan / event",
                          "best-order scan / event", "cancel scan / event",
                          "orders scanned / event", "max in one event"], a_rows)
            + "\n" + html_table(["scenario", "M", "version", "best-price calls / event",
                                 "queue pops / event", "dead entries popped",
                                 "levels created", "levels removed by matching",
                                 "levels removed by cancel", "stale heap pops",
                                 "heap rebuilds", "deque compactions"], b_rows))


def main():
    run = read_json("benchmark_run.json")
    env = read_json("environment.json")
    rerun = read_json("benchmark_run_latency_memory.json")
    renv = read_json("environment_latency_memory.json")
    used = rerun or run
    source = (f"Measured at commit {html.escape(str(used['git'].get('commit'))[:7])} on "
              f"{used['started_utc'][:10]} ("
              + ("separate latency and memory run" if rerun else "full run")
              + ", see Provenance), seed 42.") if used else ""
    summary = read_csv("benchmark_summary.csv")
    if not summary:
        raise SystemExit("05_results/benchmark_summary.csv is missing: run the benchmark first")
    datasets = {d["dataset"]: d for d in read_csv("benchmark_datasets.csv")}
    sections = [section_provenance(run, env, rerun, renv), section_correctness(run),
                section_replay(summary), section_throughput(summary),
                section_sorted_vs_heap(summary), section_liquidation(summary, datasets),
                section_concentration(summary, datasets), section_latency(source),
                section_memory(source), section_opcounts()]
    warn = ""
    if any(r["status"] != "complete" or not r["git"].get("code_clean")
           or not r.get("source_unchanged") for r in (run, rerun) if r):
        warn = ("<p class='warn'>Warning: a run is not a complete run of committed, "
                "unchanged code. See Provenance.</p>")
    body = "\n\n".join(sections)
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Order book benchmark</title>
<style>
body {{ font-family: sans-serif; max-width: 1100px; margin: 2em auto; padding: 0 16px;
        background: #ffffff; color: #1a1a1a; line-height: 1.4; }}
table {{ border-collapse: collapse; font-size: 0.85em; margin-bottom: 1em; display: block;
         overflow-x: auto; }}
th, td {{ border: 1px solid #ccc; padding: 3px 8px; text-align: right; }}
th {{ background: #f4f4f4; }}
img {{ max-width: 100%; }}
code {{ background: #f4f4f4; padding: 0 3px; }}
details {{ margin-bottom: 1em; }}
.warn {{ background: #fff3cd; border: 1px solid #e0c060; padding: 6px 10px; }}
</style>
</head>
<body>
<h1>Limit order book: benchmark results</h1>
<p>Built from files in 05_results/ only (it reruns nothing). Synthetic teaching data
from the course generator, not exchange records. Versions: A (one list, scans),
B-sorted and B-heap (dict + FIFO queues per price; sorted key list vs heap).</p>
{warn}
{body}
</body>
</html>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
