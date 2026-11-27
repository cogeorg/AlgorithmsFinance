"""Build results/dashboard.html from the SAVED CSV results (does not rerun experiments).

Usage:  python3 dashboard.py      then open results/dashboard.html in a browser.
Charts use Chart.js from a CDN, so viewing needs an internet connection.
"""
import csv
import json
import os
import statistics
from collections import defaultdict

R = "results"


def load(name):
    path = os.path.join(R, name)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


timing = load("timing.csv")
latency = load("latency.csv")
memory = load("memory.csv")
liq = load("liquidation.csv")
correct = load("correctness.csv")
env = json.load(open(os.path.join(R, "environment.json"))) if os.path.exists(os.path.join(R, "environment.json")) else {}

# ---- replay scaling: median over repeats, then median over seeds; stopped runs marked
groups = defaultdict(list)
stopped = set()
for row in timing:
    if row["phase"] != "replay":
        continue
    key = (row["version"], row["scenario"], int(row["events"]))
    if row["status"] == "ok":
        groups[key + (row["seed"],)].append(float(row["elapsed_s"]))
    else:
        stopped.add(key)
per_seed = defaultdict(list)
for (v, s, n, seed), vals in groups.items():
    per_seed[(v, s, n)].append(statistics.median(vals))
sizes = sorted({int(r["events"]) for r in timing})
scenarios = sorted({r["scenario"] for r in timing})


def series(version, scenario, metric):
    out = []
    for n in sizes:
        vals = per_seed.get((version, scenario, n))
        if not vals:
            out.append(None)
            continue
        med = statistics.median(vals)
        out.append(med if metric == "time" else n / med)
    return out


scaling = {s: {v: series(v, s, "time") for v in "AB"} for s in scenarios}
throughput = {s: {v: series(v, s, "tput") for v in "AB"} for s in scenarios}

lat_rows = [r for r in latency if r["window"] == "all"]
lat_window = [r for r in latency if r["scenario"] == "buildup" and r["status"] == "ok"]
mem_rows = memory
liq_ok = [r for r in liq if r["status"] == "ok"]
liq_summary = defaultdict(list)
for r in liq_ok:
    liq_summary[(r["version"], int(r["events"]), int(r["pct"]))].append(r)


def table(rows, cols):
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = "".join("<tr>" + "".join(f"<td>{r.get(c, '')}</td>" for c in cols) + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


liq_table_rows = []
for (v, n, pct), rs in sorted(liq_summary.items()):
    liq_table_rows.append({"version": v, "book from events": n, "sell % of bids": pct,
                           "median sell ms": f"{statistics.median(float(r['sell_s']) for r in rs) * 1000:.3f}",
                           "median build ms": f"{statistics.median(float(r['build_s']) for r in rs) * 1000:.1f}",
                           "fills": rs[0]["fills"], "makers touched": rs[0]["makers_touched"],
                           "levels visited": rs[0]["levels_visited"], "unfilled units": rs[0]["unfilled_qty"]})
for r in liq:
    if r["status"] != "ok":
        liq_table_rows.append({"version": r["version"], "book from events": r["events"],
                               "sell % of bids": r["pct"], "median sell ms": r["status"]})

stopped_list = sorted(f"Version {v}, {s}, {n:,} events" for v, s, n in stopped)

html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Order book benchmarks</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
body{{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#222}}
h1{{font-size:1.6em}} h2{{margin-top:2em;border-bottom:1px solid #ddd;padding-bottom:4px}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}} .card{{border:1px solid #e3e3e3;border-radius:8px;padding:12px}}
table{{border-collapse:collapse;font-size:.85em;margin:8px 0}} td,th{{border:1px solid #ddd;padding:4px 8px;text-align:right}}
th{{background:#f4f4f4}} .note{{color:#555;font-size:.9em}} .stop{{color:#b00}}
</style></head><body>
<h1>Limit order book: Version A (list scan) vs Version B (price levels + FIFO queues + index)</h1>
<p class="note">Loaded from saved files in <code>results/</code> (no experiments rerun). Synthetic teaching data, not exchange records.
Python {env.get('python', '?').split()[0]} on {env.get('platform', '?')}; commit {env.get('git_commit', '?')[:7]};
time limit per replay {env.get('time_limit_s', '?')} s; {env.get('repeats', '?')} repeats after 1 warm-up; values are medians over repeats, then over seeds.</p>
<p class="stop"><b>Stopped runs (exceeded the time limit, no result invented):</b> {", ".join(stopped_list) or "none"}</p>

<h2>1. Replay time vs number of events (log-log)</h2>
<p class="note">Engine replay only; JSON/gzip parsing measured separately. Missing points = stopped run.</p>
<div class="grid">{"".join(f'<div class="card"><canvas id="t_{s}"></canvas></div>' for s in scenarios)}</div>

<h2>2. Throughput (events per second of replay)</h2>
<div class="grid">{"".join(f'<div class="card"><canvas id="q_{s}"></canvas></div>' for s in scenarios)}</div>

<h2>3. Per-event processing latency (separate instrumentation run, seed 42)</h2>
<p class="note">Nearest-rank percentiles, microseconds. Algorithm processing time only: excludes queueing/network latency.
"first10pct"/"last10pct" show latency as the book grows during the buildup burst.</p>
{table(lat_rows, ["version", "scenario", "events", "p50_us", "p95_us", "p99_us", "status"])}
<h3>Buildup burst: start vs end</h3>
{table(lat_window, ["version", "events", "window", "p50_us", "p95_us", "p99_us"])}

<h2>4. Memory (tracemalloc, separate run, seed 42)</h2>
<p class="note">Peak traced bytes during replay. Preloaded input excluded; book + per-event results included; no trade history kept.
"final" = traced bytes still held at the end (e.g. after cancel churn). Traced allocation is not total process memory.</p>
<div class="card"><canvas id="mem"></canvas></div>
{table(mem_rows, ["version", "scenario", "events", "peak_traced_bytes", "final_traced_bytes", "final_active_orders", "status"])}

<h2>5. Large liquidation: one market sell against the same fresh bid book</h2>
<p class="note">Book rebuilt for every repeat (build time reported separately). Sell time includes matching, state updates and fill-list construction.</p>
{table(liq_table_rows, ["version", "book from events", "sell % of bids", "median sell ms", "median build ms", "fills", "makers touched", "levels visited", "unfilled units"])}

<h2>6. Correctness outcomes</h2>
{table(correct, ["check", "result"])}

<script>
const sizes = {json.dumps(sizes)};
const scaling = {json.dumps(scaling)};
const tput = {json.dumps(throughput)};
const mem = {json.dumps([r for r in mem_rows if r['status'] == 'ok'])};
const colors = {{A: "#d9534f", B: "#2a7ab0"}};
function lineChart(id, title, data, yTitle, log) {{
  new Chart(document.getElementById(id), {{type: "line",
    data: {{labels: sizes, datasets: ["A", "B"].map(v => ({{label: "Version " + v, data: data[v],
      borderColor: colors[v], backgroundColor: colors[v], spanGaps: false}}))}},
    options: {{plugins: {{title: {{display: true, text: title}}}},
      scales: {{x: {{type: log ? "logarithmic" : "category", title: {{display: true, text: "events (M)"}}}},
               y: {{type: log ? "logarithmic" : "linear", title: {{display: true, text: yTitle}}}}}}}}}});
}}
for (const s of Object.keys(scaling)) {{
  lineChart("t_" + s, s + ": replay time", scaling[s], "seconds (median)", true);
  lineChart("q_" + s, s + ": throughput", tput[s], "events / second", true);
}}
const memLabels = [...new Set(mem.map(r => r.scenario + " " + r.events))];
new Chart(document.getElementById("mem"), {{type: "bar",
  data: {{labels: memLabels, datasets: ["A", "B"].map(v => ({{label: "Version " + v, backgroundColor: colors[v],
    data: memLabels.map(l => {{ const r = mem.find(x => x.version === v && x.scenario + " " + x.events === l); return r ? +r.peak_traced_bytes : null; }})}}))}},
  options: {{plugins: {{title: {{display: true, text: "Peak traced bytes"}}}}, scales: {{y: {{type: "logarithmic", title: {{display: true, text: "bytes"}}}}}}}}}});
</script></body></html>"""

with open(os.path.join(R, "dashboard.html"), "w") as f:
    f.write(html)
print("Wrote results/dashboard.html")
