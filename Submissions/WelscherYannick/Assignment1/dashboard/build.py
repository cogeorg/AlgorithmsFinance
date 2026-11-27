#!/usr/bin/env python3
"""Build dashboard/index.html from SAVED results only (never reruns an experiment).

All measurements are embedded as JSON; every selector in the page only changes the view.
Charts are drawn as inline SVG by the page itself: no external libraries, works offline.
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
OUT = ROOT / "dashboard" / "index.html"


def load_csv(name):
    p = RES / name
    if not p.exists():
        return []
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def load_json(name):
    p = RES / name
    return json.loads(p.read_text()) if p.exists() else None


def main():
    data = {
        "timing": load_csv("timing.csv"),
        "liquidation": load_csv("liquidation.csv"),
        "memory": load_csv("memory.csv"),
        "latency": load_json("latency.json"),
        "correctness": load_json("correctness.json"),
        "env": load_json("env.json"),
        "inputs": load_json("generated_inputs.json"),
        "liq_agree": load_json("liquidation_agreement.json"),
        "counts": load_csv("op_counts.csv"),
        "profile": load_json("profile.json"),
        "steps": load_csv("revision_steps.csv"),
        "parse": load_csv("parse.csv"),
        "mutations": load_json("mutations.json"),
        "version_c": load_json("version_c.json"),
    }
    html = TEMPLATE.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    OUT.write_text(html)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(html) // 1024} KiB)")


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>Order Book Lab</title>
<style>
/* Visual design taken from the coding-lab "Search Lab" dashboard: deep-space navy, glass cards,
   amber / cyan / rose data colours (validated there against the card surface #101B2B). */
:root {
  --bg-top:#070D17; --bg-mid:#0B1626; --bg-bottom:#0D1B2E; --surface:#101B2B;
  --ink:#E8F1F8; --ink-2:#9FB3C8; --ink-3:#6B7F95; --hairline:rgba(166,228,242,0.12);
  --amber:#B8892D; --cyan:#00A4C0; --rose:#CD718F; --amber-tint:#F2D9A6; --cyan-tint:#A6E4F2; --rose-tint:#F2BACB;
  --ok:#6FD3A8; --bad:#F2849A;
  --font:-apple-system, BlinkMacSystemFont, "SF Pro Display", "Inter", "Segoe UI", sans-serif;
  --mono:"SF Mono", ui-monospace, Menlo, monospace;
}
* { box-sizing:border-box; }
html { background:var(--bg-top); }
body { margin:0; color:var(--ink); font:14px/1.5 var(--font); min-height:100vh;
  background:
    radial-gradient(1100px 520px at 8% -8%, rgba(0,164,192,0.20), transparent 60%),
    radial-gradient(900px 480px at 100% 0%, rgba(205,113,143,0.12), transparent 60%),
    radial-gradient(800px 600px at 50% 120%, rgba(184,137,45,0.08), transparent 60%),
    linear-gradient(180deg, var(--bg-top) 0%, var(--bg-mid) 55%, var(--bg-bottom) 100%);
  background-attachment:fixed; }
.wrap { max-width:1280px; margin:auto; padding:36px 16px 56px; }
.hero { display:flex; flex-wrap:wrap; align-items:flex-end; justify-content:space-between; gap:18px; margin-bottom:18px; }
.hero h1 { font-size:2.6rem; font-weight:700; letter-spacing:-0.03em; margin:0; line-height:1.1;
  background:linear-gradient(90deg, #FFFFFF 0%, var(--cyan-tint) 55%, var(--rose-tint) 100%);
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; }
.hero .sub { color:var(--ink-2); font-size:1.02rem; margin-top:6px; max-width:760px; }
.chips { display:flex; flex-wrap:wrap; gap:8px; }
.chip { font-size:0.78rem; color:var(--ink-2); padding:6px 12px; border-radius:999px;
  background:rgba(166,228,242,0.06); border:1px solid var(--hairline); white-space:nowrap; }
.chip b { color:var(--ink); font-weight:600; }
.chip code { font-family:var(--mono); color:var(--cyan-tint); background:none; padding:0; }
.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:14px; margin:6px 0 22px; }
.kpi { position:relative; overflow:hidden; border-radius:22px; padding:18px 20px 16px;
  background:rgba(16,27,43,0.72); border:1px solid var(--hairline);
  backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px);
  box-shadow:0 12px 32px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04); }
.kpi::before { content:""; position:absolute; inset:0 0 auto 0; height:3px; background:var(--accent, var(--cyan)); opacity:.85; }
.kpi .label { font-size:0.72rem; text-transform:uppercase; letter-spacing:0.08em; color:var(--ink-3); }
.kpi .value { font-size:1.8rem; font-weight:650; letter-spacing:-0.02em; color:var(--ink); margin-top:6px; font-variant-numeric:tabular-nums; }
.kpi .note { font-size:0.8rem; color:var(--ink-2); margin-top:2px; }
.tabs { display:flex; gap:6px; background:rgba(16,27,43,0.72); padding:6px; border-radius:999px;
  border:1px solid var(--hairline); width:fit-content; max-width:100%; overflow-x:auto; margin-bottom:16px;
  position:sticky; top:10px; z-index:5; backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px); }
.tabs button { font:inherit; font-size:0.9rem; color:var(--ink-2); background:none; border:0; border-radius:999px;
  padding:6px 16px; cursor:pointer; white-space:nowrap; transition:background .2s ease, color .2s ease; }
.tabs button:hover { color:var(--ink); }
.tabs button[aria-selected="true"] { background:rgba(0,164,192,0.20); color:var(--ink); }
.panel { display:none; } .panel.active { display:block; }
.card { border-radius:24px; padding:18px 20px 16px; margin-bottom:16px; min-width:0;
  background:rgba(16,27,43,0.78); border:1px solid var(--hairline);
  backdrop-filter:blur(18px); -webkit-backdrop-filter:blur(18px);
  box-shadow:0 14px 36px rgba(0,0,0,0.38), inset 0 1px 0 rgba(255,255,255,0.04); }
.card-title { font-size:1.02rem; font-weight:620; color:var(--ink); margin:0; }
.card-sub { font-size:0.82rem; color:var(--ink-3); margin:2px 0 10px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap:16px; margin-bottom:16px; }
.grid > .card { margin-bottom:0; }
.controls { display:flex; gap:10px 18px; flex-wrap:wrap; align-items:center; font-size:0.82rem; color:var(--ink-3); }
.controls label { display:flex; gap:8px; align-items:center; }
select { font:inherit; font-size:0.86rem; color:var(--ink); background:rgba(166,228,242,0.06);
  border:1px solid var(--hairline); border-radius:999px; padding:5px 12px; }
select option { background:var(--surface); color:var(--ink); }
.context { font-size:0.82rem; color:var(--ink-3); margin:10px 0 0; line-height:1.55; }
.context b { color:var(--ink-2); font-weight:600; }
.chart { position:relative; height:310px; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; font-size:12.5px; font-variant-numeric:tabular-nums; }
th, td { border-bottom:1px solid var(--hairline); padding:6px 10px; text-align:right; white-space:nowrap; }
th:first-child, td:first-child, td.l, th.l { text-align:left; }
th { color:var(--ink-3); font-weight:600; font-size:11px; text-transform:uppercase; letter-spacing:0.06em;
  position:sticky; top:0; background:var(--surface); z-index:1; }
tbody tr:hover td { background:rgba(166,228,242,0.04); }
.ok { color:var(--ok); font-weight:600; } .bad { color:var(--bad); font-weight:600; }
.A { color:var(--amber-tint); } .B { color:var(--cyan-tint); }
code { font-family:var(--mono); font-size:0.92em; color:var(--cyan-tint); background:rgba(166,228,242,0.06); padding:1px 5px; border-radius:6px; }
.note { color:var(--ink-3); font-size:12.5px; line-height:1.55; }
#bn { color:var(--ink-2); font-size:0.9rem; line-height:1.6; }
#bn b { color:var(--ink); }
#bn ul { padding-left:20px; }
h3 { font-size:1.02rem; font-weight:620; color:var(--ink); margin:20px 0 4px; }
footer { color:var(--ink-3); font-size:0.78rem; margin-top:8px; }
@media (max-width:640px) { .hero h1 { font-size:2rem; } .wrap { padding-top:24px; } .kpi .value { font-size:1.5rem; } }
</style>
</head>
<body>
<div class="wrap">
<header class="hero">
  <div>
    <h1>Order Book Lab</h1>
    <div class="sub">A sequential BTC limit order book with price-time priority: a transparent list-scan baseline
    (Version A) against price levels with a fast path (Version B). Every number is read from saved results;
    changing a view never reruns an experiment.</div>
  </div>
  <div class="chips" id="chips"></div>
</header>
<div class="kpis" id="kpis"></div>
<nav class="tabs" role="tablist" id="tabs">
  <button role="tab" data-tab="replay">Runtime</button>
  <button role="tab" data-tab="liq">Large sell</button>
  <button role="tab" data-tab="lat">Latency</button>
  <button role="tab" data-tab="mem">Memory</button>
  <button role="tab" data-tab="bottleneck">Bottleneck &amp; revision</button>
  <button role="tab" data-tab="correct">Correctness</button>
  <button role="tab" data-tab="settings">Environment</button>
</nav>
<main>

<section class="panel" id="replay">
  <div class="card">
    <div class="controls"><label>Scenario <select id="rScen"></select></label><label>Seed <select id="rSeed"></select></label>
      <label>Size for throughput <select id="rSize"></select></label></div>
    <div class="context">Median of <b>5 timed repeats</b> after 1 warmup · fresh empty book per replay · fresh process per
      configuration · parsing timed separately (total = parse + replay) · for <code>buildup</code> and <code>crowded</code>
      the replay is the book construction · declared limit <b><span id="limit"></span> s</b> per configuration.</div>
  </div>
  <div class="grid">
    <div class="card"><div class="card-title">Replay time vs events</div>
      <div class="card-sub">seconds, median · log–log · 1,000,000 events use seed 42</div><div class="chart" id="cReplay"></div></div>
    <div class="card"><div class="card-title">Throughput</div>
      <div class="card-sub">events per second of replay · × = stopped or not attempted</div><div class="chart" id="cThru"></div></div>
  </div>
  <div class="card"><div class="card-title">All configurations</div>
    <div class="card-sub">every raw repeat in seconds · stopped runs are kept, never dropped</div>
    <div class="scroll" style="max-height:440px"><table id="timingTable"></table></div></div>
</section>

<section class="panel" id="liq">
  <div class="card">
    <div class="controls"><label>Book <select id="lBook"></select></label></div>
    <div class="context">The book is restored from a snapshot before <b>every</b> trial (reset timed separately). Sell time
      covers matching, state updates and fill-list construction. Work: fills = makers touched · L = price levels visited ·
      work steps = list entries scanned (A) or fills + levels (B). <span id="liqAgree"></span></div>
  </div>
  <div class="grid">
    <div class="card"><div class="card-title">One large market sell</div>
      <div class="card-sub">median of 5 trials · log scale · × = stopped</div><div class="chart" id="cLiq"></div></div>
    <div class="card"><div class="card-title">Work counts</div>
      <div class="card-sub">counted from the fills, independent of timing</div><div class="scroll"><table id="liqTable"></table></div></div>
  </div>
  <div class="card"><div class="card-title">Sale scaling with book size</div>
    <div class="card-sub">median sell time vs bid orders in the book (1,000 prices per side) · log–log · a missing point = stopped at the limit</div>
    <div class="chart" id="cLiqScale"></div></div>
  <div class="card"><div class="card-title">Queue concentration</div>
    <div class="card-sub">4 vs 1,000 prices per side, same order count · 100% sale</div>
    <div class="scroll"><table id="qcTable"></table></div></div>
</section>

<section class="panel" id="lat">
  <div class="card">
    <div class="controls"><label>Events <select id="tSize"></select></label><label>Seed <select id="tSeed"></select></label><label>Histogram scenario <select id="tScen"></select></label></div>
    <div class="context" id="latConv"></div>
  </div>
  <div class="grid">
    <div class="card"><div class="card-title">p50 / p95 / p99 per event</div>
      <div class="card-sub">nanoseconds · log scale · × = not attempted</div><div class="chart" id="cLat"></div></div>
    <div class="card"><div class="card-title">Latency distribution</div>
      <div class="card-sub">events per power-of-two bucket · log scale</div><div class="chart" id="cHist"></div></div>
  </div>
  <div class="card"><div class="card-title">Early vs late, by event type</div>
    <div class="card-sub">first 10% vs last 10% of the stream as the book grows</div>
    <div class="scroll"><table id="latTable"></table></div></div>
</section>

<section class="panel" id="mem">
  <div class="card">
    <div class="controls"><label>Events <select id="mSize"></select></label><label>Seed <select id="mSeed"></select></label><label>Growth curve <select id="mScen"></select></label></div>
    <div class="context"><code>tracemalloc</code>, separate from timing. <b>Replay peak</b> and <b>book after (structures)</b> trace from
      after the input is loaded: the input is excluded, but ids and ints the book keeps from the parser are then not counted.
      <b>Book after (incl. ids/ints)</b> traces from before loading and drops the input afterwards; bytes per order use it.
      No trade history is kept. Traced bytes are neither pure auxiliary space nor total process memory.</div>
  </div>
  <div class="grid">
    <div class="card"><div class="card-title">Peak and retained memory</div>
      <div class="card-sub">traced bytes · log scale</div><div class="chart" id="cMem"></div></div>
    <div class="card"><div class="card-title">Memory during the replay</div>
      <div class="card-sub">current traced bytes at 10 checkpoints · cancel_churn should stay flat</div><div class="chart" id="cGrow"></div></div>
  </div>
  <div class="card"><div class="card-title">Memory measurements</div><div class="card-sub">bytes</div>
    <div class="scroll"><table id="memTable"></table></div></div>
</section>

<section class="panel" id="bottleneck">
  <div class="card"><div class="card-title">Measured bottleneck and revision</div>
    <div class="card-sub">code, operation counts and complexity</div><div id="bn"></div></div>
</section>

<section class="panel" id="correct">
  <div class="card"><div class="card-title">Per-event correctness</div>
    <div class="card-sub">the independent oracle checks Version B after every event (price-time priority, conservation,
      cancel residuals, validation); Version A must return identical results and books after every event</div>
    <div id="unit"></div><div class="scroll"><table id="corrTable"></table></div></div>
  <div class="card"><div class="card-title">Mutation check</div><div class="card-sub">bench/run_mutations.py</div>
    <p class="note" id="mutNote"></p><div class="scroll"><table id="mutTable"></table></div></div>
</section>

<section class="panel" id="settings">
  <div class="card"><div class="card-title">Environment and settings</div><div class="card-sub">results/env.json</div>
    <div class="scroll"><table id="envTable"></table></div></div>
  <div class="card"><div class="card-title">Generated inputs</div>
    <div class="card-sub">regenerate with <code>python bench/make_data.py</code> · SHA-256 checked</div>
    <div class="scroll" style="max-height:320px"><table id="inTable"></table></div></div>
</section>
</main>
<footer>Built by <code>dashboard/build.py</code> from <code>results/</code>. Synthetic teaching data; not a production trading system.</footer>
</div>

<script type="application/json" id="data">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const COL = {A: '#B8892D', B: '#00A4C0', step: '#CD718F'};  // amber / cyan / rose from the coding-lab theme
const INK2 = '#9FB3C8', INK3 = '#6B7F95', GRID = 'rgba(159,179,200,0.10)', AXIS = 'rgba(166,228,242,0.18)', SURF = '#101B2B', BAD = '#F2849A';
const num = x => (x === '' || x === null || x === undefined) ? null : Number(x);
const med = a => { const s = a.filter(x => x !== null && !Number.isNaN(x)).sort((x, y) => x - y), n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null; };
const fmt = (x, d = 4) => x === null || x === undefined || Number.isNaN(x) ? '–' : (Math.abs(x) >= 1e5 ? Math.round(x).toLocaleString('en-US') : Number(x).toPrecision(d));
const fmtInt = x => x === null || x === undefined || x === '' ? '–' : Number(x).toLocaleString('en-US');
const uniq = a => [...new Set(a)];
const el = id => document.getElementById(id);
function opts(sel, values, labels) { el(sel).innerHTML = values.map((v, i) => `<option value="${v}">${labels ? labels[i] : v}</option>`).join(''); }
function table(id, head, rows) {
  el(id).innerHTML = '<thead><tr>' + head.map(h => `<th class="${h.startsWith('_') ? 'l' : ''}">${h.replace(/^_/, '')}</th>`).join('') + '</tr></thead><tbody>' +
    rows.map(r => '<tr>' + r.map((c, i) => `<td class="${head[i].startsWith('_') ? 'l' : ''}">${c}</td>`).join('') + '</tr>').join('') + '</tbody>';
}
// ---------- minimal inline-SVG charts (no external library) ----------
const NS = 'http://www.w3.org/2000/svg';
function linTicks(min, max, n = 5) {
  if (max === min) max = min + 1;
  const raw = (max - min) / n, mag = 10 ** Math.floor(Math.log10(raw)), r = raw / mag;
  const step = (r < 1.5 ? 1 : r < 3 ? 2 : r < 7 ? 5 : 10) * mag, t = [];
  for (let v = Math.floor(min / step) * step; v <= max + step * 0.999; v += step) t.push(+v.toPrecision(12));
  return t;
}
function logTicks(min, max) { const t = []; for (let e = Math.floor(Math.log10(min)); e <= Math.ceil(Math.log10(max)); e++) t.push(10 ** e); if (t.length < 2) t.push(t[0] * 10); return t; }
function tickLabel(v) {
  const a = Math.abs(v);
  if (a === 0) return '0';
  if (a >= 1e9) return +(v / 1e9).toPrecision(3) + 'G';
  if (a >= 1e6) return +(v / 1e6).toPrecision(3) + 'M';
  if (a >= 1e3) return +(v / 1e3).toPrecision(3) + 'k';
  if (a >= 0.01) return String(+v.toPrecision(3));
  return v.toExponential(0);
}
// o = {type: 'bar'|'line', labels (bar), datasets: [{label, color, data}], xLog, yLog, xTitle, yTitle}
// bar data: one value per label (null = missing, drawn as ×); line data: [{x, y}]
function chart(id, o) {
  const host = el(id); host.innerHTML = '';
  const W = Math.max(320, host.clientWidth || 520), H = host.clientHeight || 300;
  const m = {l: 58, r: 12, t: 30, b: 42}, pw = W - m.l - m.r, ph = H - m.t - m.b;
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`); svg.setAttribute('width', '100%'); svg.setAttribute('height', H);
  const add = (tag, attrs, text, parent = svg) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (text !== undefined) e.textContent = text; parent.appendChild(e); return e; };
  const tip = (node, text) => add('title', {}, text, node);
  const ys = [], xs = [];
  for (const d of o.datasets) for (const p of d.data) {
    if (p === null || p === undefined) continue;
    if (o.type === 'bar') { if (!o.yLog || p > 0) ys.push(p); } else if (p.y !== null && (!o.yLog || p.y > 0)) { xs.push(p.x); ys.push(p.y); }
  }
  host.appendChild(svg);
  if (!ys.length) { add('text', {x: W / 2, y: H / 2, 'text-anchor': 'middle', fill: INK3}, 'no data for this selection'); return; }
  const scale = (lo, hi, log, a0, a1) => {
    const T = log ? logTicks(lo, hi) : linTicks(Math.min(0, lo), hi);
    const f = log ? Math.log10 : (v => v), A = f(T[0]), B = f(T[T.length - 1]);
    return {T, px: v => a0 + (a1 - a0) * (f(v) - A) / ((B - A) || 1)};
  };
  const Y = scale(Math.min(...ys), Math.max(...ys), o.yLog, m.t + ph, m.t);
  Y.T.forEach(t => { const y = Y.px(t); add('line', {x1: m.l, x2: W - m.r, y1: y, y2: y, stroke: GRID}); add('text', {x: m.l - 6, y: y + 4, 'text-anchor': 'end', 'font-size': 11, fill: INK3}, tickLabel(t)); });
  if (o.yTitle) add('text', {x: 12, y: m.t + ph / 2, transform: `rotate(-90 12 ${m.t + ph / 2})`, 'text-anchor': 'middle', 'font-size': 11, fill: INK2}, o.yTitle);
  if (o.xTitle) add('text', {x: m.l + pw / 2, y: H - 4, 'text-anchor': 'middle', 'font-size': 11, fill: INK2}, o.xTitle);
  const base = m.t + ph;
  if (o.type === 'bar') {
    const g = pw / o.labels.length, k = o.datasets.length, bw = Math.max(2, g * 0.8 / k);
    o.labels.forEach((lab, i) => {
      add('text', {x: m.l + g * i + g / 2, y: base + 15, 'text-anchor': 'middle', 'font-size': o.labels.length > 10 ? 9 : 11, fill: INK2}, lab);
      o.datasets.forEach((d, j) => {
        const v = d.data[i], x = m.l + g * i + g * 0.1 + bw * j;
        if (v === null || v === undefined || (o.yLog && v <= 0)) { tip(add('text', {x: x + bw / 2, y: base - 3, 'text-anchor': 'middle', 'font-size': 10, fill: BAD}, '×'), `${d.label} · ${lab}: missing / stopped`); return; }
        const y = Y.px(v), y0 = o.yLog ? base : Y.px(0);
        tip(add('rect', {x, y: Math.min(y, y0), width: Math.max(1, bw - 1), height: Math.max(1, Math.abs(y0 - y)), rx: Math.min(3, Math.max(0, bw / 4)), fill: d.color}), `${d.label} · ${lab}: ${fmt(v)}`);
      });
    });
  } else {
    const X = scale(Math.min(...xs), Math.max(...xs), o.xLog, m.l, m.l + pw);
    X.T.forEach(t => { const x = X.px(t); add('line', {x1: x, x2: x, y1: m.t, y2: base, stroke: GRID}); add('text', {x, y: base + 15, 'text-anchor': 'middle', 'font-size': 11, fill: INK3}, tickLabel(t)); });
    for (const d of o.datasets) {
      const pts = d.data.filter(p => p && p.y !== null && (!o.yLog || p.y > 0)).sort((a, b) => a.x - b.x);
      if (!pts.length) continue;
      add('polyline', {points: pts.map(p => `${X.px(p.x)},${Y.px(p.y)}`).join(' '), fill: 'none', stroke: d.color, 'stroke-width': 2.2, 'stroke-linejoin': 'round'});
      pts.forEach(p => tip(add('circle', {cx: X.px(p.x), cy: Y.px(p.y), r: 4.5, fill: d.color, stroke: SURF, 'stroke-width': 2}), `${d.label}: x=${fmtInt(p.x)}, y=${fmt(p.y)}`));
    }
  }
  add('line', {x1: m.l, x2: m.l, y1: m.t, y2: base, stroke: AXIS});
  add('line', {x1: m.l, x2: W - m.r, y1: base, y2: base, stroke: AXIS});
  let lx = m.l;
  for (const d of o.datasets) { add('circle', {cx: lx + 5, cy: 13, r: 4.5, fill: d.color}); add('text', {x: lx + 14, y: 17, 'font-size': 11, fill: INK2}, d.label); lx += 26 + d.label.length * 6.2; }
}
const statusTag = s => s === 'ok' ? '<span class="ok">ok</span>' : `<span class="bad">${s}</span>`;

// ---------- header ----------
const E = D.env || {};
el('chips').innerHTML = [
  E.cpu ? `<span class="chip"><b>${E.cpu}</b> · ${E.cpu_count} cores</span>` : '',
  E.python ? `<span class="chip">Python <b>${E.python.split(' ')[0]}</b></span>` : '',
  E.git_commit ? `<span class="chip">timing @ <code>${E.git_commit.slice(0, 7)}</code>${E.git_dirty ? ' + changes' : ''}</span>` : '',
  '<span class="chip">stdlib only · <b>offline</b></span>',
].join('');
el('limit').textContent = (E.timing_settings || {}).config_limit_s ?? '?';

// ---------- correctness ----------
const C = D.correctness || {per_event_checks: [], unit_tests: []};
el('unit').innerHTML = `<p>Unit tests: <b class="${C.unit_tests_ok ? 'ok' : 'bad'}">${(C.unit_tests || []).join(' · ') || 'not run'}</b></p>`;
table('corrTable', ['_input', 'events', 'seed', 'accepted', 'rejected', 'fills', 'max active', 'every event', '_result'],
  C.per_event_checks.map(r => [r.input, fmtInt(r.events), r.seed, fmtInt(r.accepted), fmtInt(r.rejected), fmtInt(r.fills), fmtInt(r.max_active),
    r.checked_every_event ? 'yes' : 'no', r.ok ? '<span class="ok">pass</span>' : `<span class="bad">FAIL ${r.error}</span>`]));
const MU = (D.mutations || {}).mutations || [];
el('mutNote').innerHTML = MU.length ? `Each row injects one deliberate bug into a copy of the code and runs the unchanged test suite; a mutation counts as detected when at least one test fails. <b class="${MU.every(m => m.detected) ? 'ok' : 'bad'}">${MU.filter(m => m.detected).length} of ${MU.length} detected.</b>` : 'Not run.';
table('mutTable', ['_mutation', '_file', 'failing tests', '_detected'], MU.map(m => [m.name, `<code>${m.file}</code>`, fmtInt(m.failures), m.detected ? '<span class="ok">yes</span>' : '<span class="bad">NO</span>']));

// ---------- timing ----------
const T = D.timing;
const tkey = r => `${r.version}|${r.scenario}|${r.events}|${r.seed}`;
const cfg = {};
for (const r of T) {
  const k = tkey(r);
  cfg[k] ??= {version: r.version, scenario: r.scenario, events: +r.events, seed: +r.seed, B: num(r.active_orders_peak), P: num(r.price_levels_peak), F: num(r.fills), replay: [], parse: [], status: 'ok', note: ''};
  const c = cfg[k];
  if (r.phase === 'replay' && r.status === 'ok') c.replay.push(+r.elapsed_s);
  if (r.phase === 'replay' && r.status === 'warmup') c.warmup = +r.elapsed_s;
  if (r.phase === 'parse') c.parse.push(+r.elapsed_s);
  if (r.status === 'stopped_time_limit' || r.status === 'not_attempted' || r.status === 'failed') { c.status = r.status; c.note = r.note; }
}
const CFG = Object.values(cfg);
const PARSE = {};
for (const r of (D.parse || [])) if (r.status === 'ok') (PARSE[`${r.scenario}|${r.events}|${r.seed}`] ??= []).push(+r.elapsed_s);
const LIMIT = (E.timing_settings || {}).config_limit_s || 120;
CFG.forEach(c => {
  c.med = c.status === 'ok' ? med(c.replay) : null; c.thru = c.med ? c.events / c.med : null;
  const pr = PARSE[`${c.scenario}|${c.events}|${c.seed}`];
  c.parseMed = pr ? med(pr) : med(c.parse); c.parseN = pr ? pr.length : c.parse.length;
  c.wall = (c.warmup || 0) + c.replay.reduce((x, y) => x + y, 0) + (med(c.parse) || 0);
  c.nearLimit = c.status === 'ok' && c.wall > 0.8 * LIMIT;
});
const scen = uniq(CFG.map(c => c.scenario)), seeds = uniq(CFG.map(c => c.seed)).sort(), sizes = uniq(CFG.map(c => c.events)).sort((a, b) => a - b);
opts('rScen', scen); opts('rSeed', seeds); opts('rSize', sizes, sizes.map(fmtInt)); el('rSize').value = 10000;
function drawReplay() {
  const s = el('rScen').value, seed = +el('rSeed').value, size = +el('rSize').value;
  const ds = ['A', 'B'].map(v => ({label: 'Version ' + v, color: COL[v],
    data: CFG.filter(c => c.version === v && c.scenario === s && (c.seed === seed || c.events === 1000000) && c.med).map(c => ({x: c.events, y: c.med}))}));
  chart('cReplay', {type: 'line', datasets: ds, xLog: true, yLog: true, xTitle: 'events M (1,000,000 uses seed 42)', yTitle: 'seconds (median of 5)'});
  chart('cThru', {type: 'bar', labels: scen, yLog: true, yTitle: 'events / s', xTitle: '× = stopped or not attempted',
    datasets: ['A', 'B'].map(v => ({label: 'Version ' + v, color: COL[v],
      data: scen.map(sc => { const c = cfg[`${v}|${sc}|${size}|${seed}`]; return c && c.thru ? c.thru : null; })}))});
}
['rScen', 'rSeed', 'rSize'].forEach(id => el(id).onchange = drawReplay);
table('timingTable', ['_version', '_scenario', 'seed', 'events M', 'peak active B', 'peak levels P', 'fills F', 'parse s (median)', 'replay s (median)', 'total s', 'events/s', 'warmup s', '_raw repeats (s)', '_status'],
  CFG.sort((a, b) => a.events - b.events || a.scenario.localeCompare(b.scenario) || a.seed - b.seed || a.version.localeCompare(b.version)).map(c => [
    `<b class="${c.version}">${c.version}</b>`, c.scenario, c.seed, fmtInt(c.events), fmtInt(c.B), fmtInt(c.P), fmtInt(c.F), fmt(c.parseMed), fmt(c.med),
    c.med && c.parseMed ? fmt(c.med + c.parseMed) : '–', c.thru ? fmtInt(Math.round(c.thru)) : '–', fmt(c.warmup ?? null), c.replay.map(x => fmt(x, 3)).join(', '),
    c.status === 'ok' ? statusTag('ok') + (c.nearLimit ? ` <span class="note">close to the limit: ~${fmt(c.wall, 3)} s of ${LIMIT} s</span>` : '') : `${statusTag(c.status)} <span class="note">${c.note}</span>`]));
const near = CFG.filter(c => c.nearLimit);
el('timingTable').insertAdjacentHTML('afterend', `<p class="note">Parse = reading + gzip + JSON into a list of dicts, median of 5 repeats after 1 warmup (bench/run_parse.py; version-independent).
  ${near.length ? `Close to the ${LIMIT} s limit (whether they finish depends on machine load): ${near.map(c => `${c.version} ${c.scenario} ${fmtInt(c.events)} seed ${c.seed}`).join('; ')}.` : ''}</p>`);

// ---------- liquidation ----------
const LQ = D.liquidation;
const books = uniq(LQ.map(r => `${r.scenario}|${r.events}`));
opts('lBook', books, books.map(b => { const [s, n] = b.split('|'); return `${s} after ${fmtInt(n)} events`; }));
const saleLabel = r => (r.note.match(/sale (\S+)/) || [])[1];
const AG = (D.liq_agree || {}).identical_result_across_versions_and_trials || {};
const aRan = new Set(LQ.filter(r => r.version === 'A' && r.status === 'ok' && r.phase === 'sell').map(r => `${r.scenario}|${r.events}|${saleLabel(r)}`));
let agBoth = 0, agOnlyB = 0, agDiffer = 0;
for (const [k, v] of Object.entries(AG)) {
  const val = (v !== null && typeof v === 'object') ? v : {identical: v};
  const [s, n, lv, lab] = k.split('|');
  const compared = val.versions ? val.versions.includes('A') && val.versions.includes('B') : aRan.has(`${s}_l${lv}|${n}|${lab}`);
  if (!val.identical) agDiffer++; else if (compared) agBoth++; else agOnlyB++;
}
el('liqAgree').innerHTML = Object.keys(AG).length ? (agDiffer ? `<span class="bad">Results differ in ${agDiffer} sale configuration(s).</span>` :
  `<span class="ok">A and B returned byte-identical results in all ${agBoth} sale configurations where both finished.</span>`) +
  (agOnlyB ? ` In ${agOnlyB} configuration(s) only B finished (A stopped), so there is no A/B comparison there.` : '') : '';
function liqRows(book) {
  const out = {};
  for (const r of LQ.filter(r => `${r.scenario}|${r.events}` === book)) {
    const label = saleLabel(r);
    const k = `${r.version}|${label}`;
    out[k] ??= {version: r.version, label, req: r.requested_qty_units, sell: [], reset: [], status: 'ok', note: r.note, bids: num((r.note.match(/bid orders (\d+)/) || [])[1])};
    const o = out[k];
    if (r.status === 'ok' && r.phase === 'sell') { o.sell.push(+r.elapsed_s); Object.assign(o, {fills: r.fills, L: r.levels_visited, work: r.work_steps, unfilled: r.unfilled_qty_units, B: r.active_orders_peak, P: r.price_levels_peak}); }
    if (r.status === 'ok' && r.phase === 'reset') o.reset.push(+r.elapsed_s);
    if (r.status === 'stopped_time_limit' || r.status === 'failed') { o.status = r.status; o.note = r.note; }
    if (r.work_steps && o.work === undefined) Object.assign(o, {fills: r.fills, L: r.levels_visited, work: r.work_steps, unfilled: r.unfilled_qty_units, B: r.active_orders_peak, P: r.price_levels_peak});
  }
  return Object.values(out);
}
function drawLiq() {
  const rows = liqRows(el('lBook').value), labels = ['10%', '100%', '200%'];
  chart('cLiq', {type: 'bar', labels, yLog: true, yTitle: 'seconds (median of 5)', xTitle: 'sale size (share of bid quantity); × = stopped',
    datasets: ['A', 'B'].map(v => ({label: 'Version ' + v, color: COL[v],
      data: labels.map(l => { const o = rows.find(o => o.version === v && o.label === l); return o && o.status === 'ok' ? med(o.sell) : null; })}))});
  table('liqTable', ['_ver', '_sale', 'requested units', 'sell s', 'reset s', 'reset + sell s', 'fills F', 'levels L', 'work steps', 'unfilled', '_status', '_raw sells (s)'],
    rows.sort((a, b) => a.label.localeCompare(b.label, 'en', {numeric: true}) || a.version.localeCompare(b.version)).map(o => [
      `<b class="${o.version}">${o.version}</b>`, o.label, fmtInt(o.req),
      o.status === 'ok' ? fmt(med(o.sell)) : (o.sell.length ? `${fmt(med(o.sell))} <span class="note">(only ${o.sell.length} of 5 finished)</span>` : '–'), fmt(med(o.reset)),
      o.status === 'ok' ? fmt(med(o.sell) + med(o.reset)) : '–', fmtInt(o.fills), fmtInt(o.L), fmtInt(o.work), fmtInt(o.unfilled),
      o.status === 'ok' ? statusTag('ok') : `${statusTag(o.status)} <span class="note">${o.note}</span>`, o.sell.map(x => fmt(x, 3)).join(', ')]));
}
el('lBook').onchange = drawLiq;
function drawLiqScale() {
  const ds = [];
  for (const v of ['A', 'B']) for (const [lab, alpha] of [['10%', '88'], ['100%', 'ff']]) {
    const pts = [];
    for (const n of ['10000', '100000']) {
      const o = liqRows(`buildup_l1000|${n}`).find(o => o.version === v && o.label === lab);
      if (o && o.status === 'ok' && o.bids) pts.push({x: o.bids, y: med(o.sell)});
    }
    ds.push({label: `${v} ${lab} sale`, color: COL[v] + alpha, data: pts});
  }
  chart('cLiqScale', {type: 'line', datasets: ds, xLog: true, yLog: true, xTitle: 'bid orders in the book', yTitle: 'seconds (median of 5)'});
}
// queue concentration table
const qc = [];
for (const book of books) {
  for (const o of liqRows(book)) if (o.label === '100%') qc.push([book.replace('|', ' / ') + ' events', `<b class="${o.version}">${o.version}</b>`, fmtInt(o.B), fmtInt(o.bids), fmtInt(o.P), fmtInt(o.fills), fmtInt(o.L), fmt(med(o.reset)), o.status === 'ok' ? fmt(med(o.sell)) : statusTag(o.status), fmtInt(o.work)]);
}
const cr = CFG.filter(c => (c.scenario === 'crowded' || c.scenario === 'buildup') && c.seed === 42 && c.events <= 100000);
table('qcTable', ['_book', '_ver', 'resting orders (both sides)', 'bid orders', 'bid levels', 'fills (100% sale)', 'levels visited', 'reset s', 'sell s', 'work steps'], qc);
el('qcTable').insertAdjacentHTML('afterend', '<p class="note">Replay with 4 prices = scenario <code>crowded</code> (byte-identical to <code>buildup --levels 4</code> at 10,000 events, seed 42) vs <code>buildup</code> with 1,000 prices: ' +
  cr.map(c => `${c.version} ${c.scenario} ${fmtInt(c.events)}: ${c.med ? fmt(c.med) + ' s' : c.status}`).join('; ') + '.</p>');

// ---------- latency ----------
const LT = (D.latency || {runs: []});
el('latConv').textContent = `Timer: ${LT.timer || ''}. Percentiles: ${LT.percentile_convention || ''}. Engine processing time only (no parsing, network or queueing); reciprocal throughput is not a latency estimate.`;
const lruns = LT.runs || [];
const lsizes = uniq(lruns.map(r => r.events)).sort((a, b) => a - b);
opts('tSize', lsizes, lsizes.map(fmtInt)); opts('tScen', scen);
const lseeds = uniq(lruns.map(r => r.seed ?? 42)).sort((a, b) => a - b); opts('tSeed', lseeds);
function drawLat() {
  const n = +el('tSize').value, s = el('tScen').value, sd = +el('tSeed').value;
  const runs = lruns.filter(r => r.events === n && (r.seed ?? 42) === sd);
  const ds = [];
  for (const v of ['A', 'B']) for (const [p, alpha] of [['p50_ns', 'ff'], ['p95_ns', 'aa'], ['p99_ns', '66']])
    ds.push({label: `${v} ${p.slice(0, 3)}`, color: COL[v] + alpha,
      data: scen.map(sc => { const r = runs.find(r => r.version === v && r.scenario === sc && r.status === 'ok'); return r ? r.all[p] : null; })});
  chart('cLat', {type: 'bar', labels: scen, datasets: ds, yLog: true, yTitle: 'ns per event', xTitle: '× = not attempted'});
  const hs = runs.filter(r => r.scenario === s && r.status === 'ok');
  const keys = uniq(hs.flatMap(r => Object.keys(r.histogram_log2_ns).map(Number))).sort((a, b) => a - b);
  chart('cHist', {type: 'bar', labels: keys.map(k => k >= 10 ? `${+(2 ** k / 1000).toPrecision(3)}µs` : `${2 ** k}ns`), yLog: true,
    yTitle: 'events', xTitle: 'bucket lower edge, [2^k, 2^(k+1)) ns',
    datasets: hs.map(r => ({label: 'Version ' + r.version, color: COL[r.version] + 'cc', data: keys.map(k => r.histogram_log2_ns[k] || null)}))});
  const rows = [];
  for (const r of runs.sort((a, b) => a.scenario.localeCompare(b.scenario) || a.version.localeCompare(b.version))) {
    if (r.status !== 'ok') { rows.push([`<b class="${r.version}">${r.version}</b>`, r.scenario, 'all', '–', '–', '–', '–', statusTag(r.status)]); continue; }
    const row = (lab, x) => [`<b class="${r.version}">${r.version}</b>`, r.scenario, lab, fmtInt(x.n), fmtInt(x.p50_ns), fmtInt(x.p95_ns), fmtInt(x.p99_ns), fmtInt(x.max_ns)];
    rows.push(row('all', r.all), row('early 10%', r.early_first_10pct), row('late 10%', r.late_last_10pct));
    for (const [t, x] of Object.entries(r.by_type)) rows.push(row(t, x));
  }
  table('latTable', ['_ver', '_scenario', '_subset', 'n', 'p50 ns', 'p95 ns', 'p99 ns', 'max ns'], rows);
}
['tSize', 'tScen', 'tSeed'].forEach(id => el(id).onchange = drawLat);

// ---------- memory ----------
const MM = D.memory;
const msizes = uniq(MM.map(r => +r.events)).sort((a, b) => a - b);
opts('mSize', msizes, msizes.map(fmtInt)); opts('mScen', scen); el('mScen').value = 'cancel_churn';
const mseeds = uniq(MM.map(r => +r.seed)).sort((a, b) => a - b); opts('mSeed', mseeds);
const mget = (v, s, n, ph, sd = 42) => MM.find(r => r.version === v && r.scenario === s && +r.events === n && +r.seed === sd && r.phase === ph);
function drawMem() {
  const n = +el('mSize').value, s = el('mScen').value, sd = +el('mSeed').value;
  const ds = [];
  for (const v of ['A', 'B']) {
    ds.push({label: `${v} replay peak`, color: COL[v], data: scen.map(sc => num((mget(v, sc, n, 'replay_peak', sd) || {}).traced_peak_bytes))});
    ds.push({label: `${v} book after (incl.)`, color: COL[v] + '66', data: scen.map(sc => num((mget(v, sc, n, 'book_after_incl_input_objects', sd) || mget(v, sc, n, 'book_after', sd) || {}).traced_current_bytes))});
  }
  chart('cMem', {type: 'bar', labels: scen, datasets: ds, yLog: true, yTitle: 'traced bytes', xTitle: '× = not attempted'});
  chart('cGrow', {type: 'line', xTitle: 'events processed', yTitle: 'traced bytes (current)',
    datasets: ['A', 'B'].map(v => ({label: 'Version ' + v, color: COL[v],
      data: MM.filter(r => r.version === v && r.scenario === s && +r.events === n && +r.seed === sd && r.phase === 'checkpoint').map(r => ({x: +r.repeat, y: +r.traced_current_bytes}))}))});
  const rows = [];
  for (const sc of scen) for (const v of ['A', 'B']) {
    const pk = mget(v, sc, n, 'replay_peak', sd), af = mget(v, sc, n, 'book_after', sd), inp = mget(v, sc, n, 'input', sd), full = mget(v, sc, n, 'book_after_incl_input_objects', sd);
    if (!pk || pk.status !== 'ok' || !af) { rows.push([`<b class="${v}">${v}</b>`, sc, '–', '–', '–', '–', '–', '–', statusTag(pk ? pk.status : 'missing')]); continue; }
    const stored = num(af.active_orders_peak), after = num(af.traced_current_bytes), whole = full ? num(full.traced_current_bytes) : null;
    rows.push([`<b class="${v}">${v}</b>`, sc, fmtInt(inp && inp.traced_current_bytes), fmtInt(pk.traced_peak_bytes), fmtInt(after), fmtInt(whole), fmtInt(stored), fmtInt(af.price_levels_peak),
      stored && whole !== null ? fmtInt(Math.round(whole / stored)) : '–']);
  }
  table('memTable', ['_ver', '_scenario', 'input (excluded) B', 'replay peak B', 'book after B (structures only)', 'book after B (incl. ids/ints from parsing)', 'stored orders', 'stored levels', 'bytes / stored order (incl.)'], rows);
}
['mSize', 'mScen', 'mSeed'].forEach(id => el(id).onchange = drawMem);

// ---------- bottleneck ----------
(function () {
  const g = (v, s, n) => cfg[`${v}|${s}|${n}|42`];
  const parts = [];
  for (const s of ['buildup', 'crowded']) {
    const a1 = g('A', s, 1000), a10 = g('A', s, 10000), a100 = g('A', s, 100000), b10 = g('B', s, 10000), b100 = g('B', s, 100000);
    if (a1 && a10 && b10) parts.push(`<li><b>${s}</b>: Version A replay ${fmt(a1.med)} s at 1,000 events → ${fmt(a10.med)} s at 10,000 (×${fmt(a10.med / a1.med, 3)} for ×10 events) → ${a100 && a100.med ? fmt(a100.med) + ' s' : a100 ? a100.status.replace(/_/g, ' ') : '–'} at 100,000. Version B: ${fmt(b10.med)} s → ${b100 && b100.med ? fmt(b100.med) : '–'} s (×${b100 && b100.med ? fmt(b100.med / b10.med, 3) : '–'}).</li>`);
  }
  el('bn').innerHTML = `<p><b>Version A's linear scans.</b> Every LIMIT and MARKET_SELL first scans both lists for a duplicate live
  <code>order_id</code> (<code>_is_live</code>, O(B)), then scans the opposite list for the best price (<code>_best_index</code>, O(B<sub>side</sub>)) –
  even when nothing crosses. In <code>buildup</code> the active book grows to B ≈ M, so total replay work is Σ<sub>i</sub> O(i) = O(M²):
  ten times more events means roughly a hundred times more time. Version B replaces both scans with a dict lookup and
  <code>keys[-1]</code> (O(1)); a new price level costs a bisect plus a list insert over P ≤ 2,000 keys, so its replay grows close to linearly.</p>
  <ul>${parts.join('')}</ul>
  <h3>Revision steps of Version B (100,000 events, seed 42, median of 5 replays)</h3>
  <p class="note">Step 1 = price levels + order index (first revision). Step 2 = + fused fast-path <code>process()</code>
  (after profiling showed ~60% of step 1's time in generic validation/dispatch) and a tighter matching loop in <code>_take</code>
  (early return, bound <code>append</code>, no quantity test per iteration). Step 3 = + orders stored as 4-item lists
  instead of objects (submitted Version B). Every step returns results identical to the submitted Version B.</p>
  <div class="scroll"><table id="stepTable"></table></div>
  <h3>Version C experiment (measured, not adopted)</h3>
  <p class="note">B with a <code>deque</code> per level and lazy cancellation (<code>bench/variants/book_c_deque.py</code>):
  faster on long queues, slower under cancellation churn, keeps dead entries under mixed flow. See REPORT section 7.</p>
  <div class="scroll"><table id="cTable"></table></div>
  <h3>Profile: where the time goes (cProfile, separate run, own time per function)</h3>
  <div class="scroll"><table id="profTable"></table></div>
  <h3>Operation counts per replay (separate counting run, seed 42; exact, machine-independent)</h3>
  <div class="scroll"><table id="opTable"></table></div>
  <p><b>Large sell.</b> A rescans the remaining bid list before each fill, so its work is ≈ F·B list entries; B does O(1) per fill and
  per emptied level (F + L steps). ${liqWork()}</p>
  <p><b>Where B gains least / costs more.</b> ${notBetter()}</p>`;
  const OC = D.counts || [];
  const byKey = {};
  for (const r of OC) byKey[`${r.version}|${r.scenario}|${r.events}`] = r;
  const ocRows = [];
  for (const n of uniq(OC.map(r => +r.events)).sort((a, b) => a - b)) for (const s of scen) {
    const a = byKey[`A|${s}|${n}`], b = byKey[`B|${s}|${n}`];
    if (!b) continue;
    const as = a && a.status !== 'not_attempted' ? +a.work_steps : null, bs = +b.work_steps;
    ocRows.push([s, fmtInt(n), as === null ? statusTag('not_attempted') : fmtInt(as), as === null ? '–' : fmt(as / n, 3), fmtInt(bs), fmt(bs / n, 3),
      as === null ? '–' : fmt(as / bs, 3), `<span class="note">${b.note}</span>`]);
  }
  table('opTable', ['_scenario', 'events M', 'A list entries visited', 'A per event', 'B steps', 'B per event', 'A / B', '_B detail'], ocRows);
  const ST = D.steps || [];
  const stepNames = ['B_step1_levels', 'B_step2_fastpath', 'B_step3_lists'];
  const stMed = (v, sc) => med(ST.filter(r => r.version === v && r.scenario === sc && r.status === 'ok').map(r => +r.elapsed_s));
  table('stepTable', ['_scenario', 'step 1 ms', 'step 2 ms', 'step 3 ms', 'step 3 vs step 1', '_identical results'],
    scen.filter(sc => ST.some(r => r.scenario === sc)).map(sc => {
      const m = stepNames.map(v => stMed(v, sc));
      const ok = ST.filter(r => r.scenario === sc).every(r => r.note.startsWith('results identical'));
      return [sc, ...m.map(x => x === null ? '–' : fmt(1000 * x)), m[0] && m[2] ? `${fmt(100 * (m[2] / m[0] - 1), 3)}%` : '–', ok ? '<span class="ok">yes</span>' : '<span class="bad">NO</span>'];
    }));
  const VC = D.version_c;
  if (VC) {
    const crow = scen.map(sc => {
      const rr = VC.replay_100000.filter(r => r.scenario === sc);
      if (!rr.length) return null;
      const b = med(rr.map(r => r.B_median_s)), c = med(rr.map(r => r.C_median_s));
      return [sc, fmt(1000 * b), fmt(1000 * c), `${fmt(100 * (c / b - 1), 2)}%`, rr.map(r => fmt(r.C_over_B, 3)).join(', ')];
    }).filter(Boolean);
    for (const r of VC.sell_100pct) crow.push([`100% sale · ${r.book}`, fmt(1000 * r.B_median_s), fmt(1000 * r.C_median_s), `${fmt(100 * (r.C_over_B - 1), 2)}%`, '']);
    table('cTable', ['_workload', 'B ms', 'C ms', 'C vs B', '_C/B per seed'], crow);
  }
  const PR = (D.profile || {runs: []}).runs;
  table('profTable', ['_ver', '_scenario', 'events', 'profiled s', '_top functions by own time (share of total)'],
    PR.map(r => [`<b class="${r.version}">${r.version}</b>`, r.scenario, fmtInt(r.events), fmt(r.total_profiled_s),
      r.top.slice(0, 4).map(t => `<code>${t.function.replace(/</g, '&lt;')}</code> ${Math.round(100 * t.share_of_total)}%`).join(' · ')]));
})();
function liqWork() {
  const r = v => D.liquidation.find(x => x.version === v && x.scenario === 'buildup_l1000' && x.events === '100000' && x.note.includes('sale 100%') && x.work_steps);
  const a = r('A'), b = r('B');
  if (!a || !b) return '';
  const bids = (a.note.match(/bid orders (\d+)/) || [])[1];
  return `Example: a 100% sale against the ${fmtInt(bids)} bid orders of the book built from 100,000 buildup events
  (${fmtInt(a.active_orders_peak)} resting orders including asks) needs ${fmtInt(a.work_steps)} scanned list entries in A
  versus ${fmtInt(b.work_steps)} steps in B (${fmtInt(b.fills)} fills).`;
}
function notBetter() {
  const cc = v => cfg[`${v}|cancel_churn|10000|42`];
  const a = cc('A'), b = cc('B');
  const churn = a && b && a.med && b.med ? `On <code>cancel_churn</code> the active book stays tiny, so A's scans are cheap: at 10,000 events
    A takes ${fmt(1000 * a.med, 3)} ms and B ${fmt(1000 * b.med, 3)} ms (${a.med < b.med ? 'A is faster here' : `B is ×${fmt(a.med / b.med, 3)} faster, far less than on growing books`}).` : '';
  const m = (v, ph) => mget(v, 'buildup', 10000, ph);
  const perOrder = v => { const f = m(v, 'book_after_incl_input_objects'), s = m(v, 'book_after'); return f && s && num(s.active_orders_peak) ? num(f.traced_current_bytes) / num(s.active_orders_peak) : null; };
  const pa = perOrder('A'), pb = perOrder('B');
  const mem = `Memory: per resting order A keeps one <code>Order</code> object (72 bytes) in a list slot, while B keeps a 4-item list (88 bytes),
    an index-dict entry and an <code>OrderedDict</code> node${pa && pb ? `; measured after buildup with 10,000 events: ${fmtInt(Math.round(pa))} bytes/order in A vs ${fmtInt(Math.round(pb))} in B` : ''}.`;
  return `${churn} ${mem}`;
}

// ---------- settings ----------
const ts = E.timing_settings || {};
table('envTable', ['_key', '_value'], [
  ['Python', E.python], ['Platform', E.platform], ['CPU', `${E.cpu} (${E.cpu_count} cores)`], ['Memory', fmtInt(E.memory_bytes) + ' bytes'],
  ['Code version', `${E.git_commit}${E.git_dirty ? ' + uncommitted changes' : ''}`], ['Dependencies', E.dependencies],
  ['Timer / repeats', `${ts.timer}, ${ts.warmup_replays} warmup + ${ts.repeats} timed, median reported`],
  ['Limits', `timing and liquidation: ${ts.config_limit_s} s wall clock per configuration (fresh process each); memory: ${4 * (ts.config_limit_s || 120)} s per configuration; latency, revision steps, counts and profile have no limit and run only configurations whose timing run finished (or Version B only)`],
].map(r => r.map(x => x ?? '–')));
const ins = (D.inputs || {}).files || [];
table('inTable', ['_file', 'scenario', 'events', 'seed', 'levels', '_sha256', '_command'], ins.map(f => [f.file, f.scenario, fmtInt(f.events), f.seed, f.levels, `<code>${f.sha256.slice(0, 16)}…</code>`, `<code>${f.command}</code>`]));

// ---------- KPI tiles ----------
(function () {
  const g = (v, s, n) => cfg[`${v}|${s}|${n}|42`];
  const dur = x => x === null || x === undefined ? '–' : x >= 1 ? `${fmt(x, 3)} s` : x >= 1e-3 ? `${fmt(1e3 * x, 3)} ms` : `${fmt(1e6 * x, 3)} µs`;
  const compact = x => new Intl.NumberFormat('en', {notation: 'compact', maximumFractionDigits: 1}).format(x);
  const tiles = [];
  const a10 = g('A', 'buildup', 10000), b10 = g('B', 'buildup', 10000);
  if (a10 && b10 && a10.med && b10.med)
    tiles.push(['Growing book · 10k events', `×${fmtInt(Math.round(a10.med / b10.med))} faster`, `buildup replay: A ${dur(a10.med)} → B ${dur(b10.med)}`, COL.B]);
  const b100 = scen.map(s => g('B', s, 100000)).filter(c => c && c.thru);
  if (b100.length)
    tiles.push(['Version B throughput', `${fmt(med(b100.map(c => c.thru)) / 1e6, 3)} M/s`, `events per second, median of ${b100.length} scenarios at 100,000 events`, COL.B]);
  const m1 = g('B', 'mixed', 1000000), am1 = g('A', 'mixed', 1000000);
  if (m1 && m1.med)
    tiles.push(['One million events', dur(m1.med), `Version B, mixed flow · Version A: ${am1 ? (am1.status === 'ok' ? dur(am1.med) : am1.status.replace(/_/g, ' ')) : '–'}`, COL.B]);
  const big = v => LQ.find(r => r.version === v && r.scenario === 'buildup_l1000' && r.events === '100000' && r.note.startsWith('sale 100%') && r.work_steps);
  const sellB = LQ.filter(r => r.version === 'B' && r.scenario === 'buildup_l1000' && r.events === '100000' && r.note.startsWith('sale 100%') && r.phase === 'sell' && r.status === 'ok').map(r => +r.elapsed_s);
  const wa = big('A'), wb = big('B');
  if (sellB.length && wa && wb)
    tiles.push(['Sell the whole bid side', dur(med(sellB)), `Version B, ${fmtInt((wb.note.match(/bid orders (\d+)/) || [])[1])} bids · work A ${compact(+wa.work_steps)} vs B ${compact(+wb.work_steps)} steps`, COL.B]);
  const stopped = CFG.filter(c => c.version === 'A' && c.status !== 'ok').length;
  tiles.push(['Version A limit hits', `${stopped}`, `configurations stopped at ${LIMIT} s or skipped afterwards, all reported`, COL.A]);
  const ST2 = D.steps || [];
  const stepGain = scen.map(sc => {
    const m = v => med(ST2.filter(r => r.version === v && r.scenario === sc && r.status === 'ok').map(r => +r.elapsed_s));
    const s1 = m('B_step1_levels'), s3 = m('B_step3_lists');
    return s1 && s3 ? s3 / s1 - 1 : null;
  }).filter(x => x !== null);
  if (stepGain.length)
    tiles.push(['B revision steps 1 → 3', `${fmt(100 * med(stepGain), 2)}%`, 'replay time, median of 5 scenarios · fast path + list orders, identical results', COL.step]);
  const perOrder = v => { const f = mget(v, 'buildup', 10000, 'book_after_incl_input_objects'), b = mget(v, 'buildup', 10000, 'book_after');
    return f && b && num(b.active_orders_peak) ? num(f.traced_current_bytes) / num(b.active_orders_peak) : null; };
  const pa = perOrder('A'), pb = perOrder('B');
  if (pa && pb)
    tiles.push(['Memory per resting order', `${fmtInt(Math.round(pb))} B`, `Version B vs ${fmtInt(Math.round(pa))} B in A · buildup, 10,000 events, incl. ids/ints`, COL.A]);
  const CK = (D.correctness || {}).per_event_checks || [], MU2 = (D.mutations || {}).mutations || [];
  tiles.push(['Correctness', `${CK.filter(r => r.ok).length}/${CK.length} inputs`,
    `oracle + A = B after every event${MU2.length ? ` · ${MU2.filter(m => m.detected).length}/${MU2.length} injected bugs caught` : ''}`, '#6FD3A8']);
  el('kpis').innerHTML = tiles.map(([label, value, note, accent]) =>
    `<div class="kpi" style="--accent:${accent}"><div class="label">${label}</div><div class="value">${value}</div><div class="note">${note}</div></div>`).join('');
})();

// ---------- tabs ----------
function drawAll() { drawReplay(); drawLiq(); drawLiqScale(); drawLat(); drawMem(); }
const TABS = [...document.querySelectorAll('#tabs button')].map(b => b.dataset.tab);
function showTab(id) {
  if (!TABS.includes(id)) id = TABS[0];
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === id));
  document.querySelectorAll('#tabs button').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === id)));
  try { history.replaceState(null, '', '#' + id); } catch (e) { /* file:// or sandbox */ }
  drawAll();  // charts measure their container, so draw after the panel is visible
}
document.querySelectorAll('#tabs button').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
showTab(location.hash.slice(1));
let resizeTimer; window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(drawAll, 150); });
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
