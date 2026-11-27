"""Build a standalone dashboard from saved CSV/JSON measurements only."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path


def load_csv(path: Path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def load_json(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=Path("results/raw_results.csv"))
    parser.add_argument(
        "--liquidations", type=Path, default=Path("results/liquidation_results.csv")
    )
    parser.add_argument(
        "--correctness", type=Path, default=Path("results/correctness.json")
    )
    parser.add_argument(
        "--latency-detail", type=Path, default=Path("results/latency_detail.csv")
    )
    parser.add_argument(
        "--environment", type=Path, default=Path("results/environment.json")
    )
    parser.add_argument("--output", type=Path, default=Path("dashboard.html"))
    args = parser.parse_args()

    payload = {
        "results": load_csv(args.results),
        "liquidations": load_csv(args.liquidations),
        "latency_detail": load_csv(args.latency_detail),
        "correctness": load_json(args.correctness),
        "environment": load_json(args.environment),
    }
    embedded = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    document = DASHBOARD.replace("__DATA__", embedded)
    args.output.write_text(document, encoding="utf-8")
    print(args.output)


DASHBOARD = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Limit Order Book Benchmark</title>
  <style>
    :root{--ink:#162b37;--muted:#5e7180;--paper:#f4f7f8;--panel:#fff;--line:#d9e2e7;--a:#c98419;--b:#0e7182;--ok:#247548;--bad:#a33a2b}
    *{box-sizing:border-box} body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.45 system-ui,-apple-system,sans-serif}
    header,main{max-width:1180px;margin:auto;padding:24px} header{padding-bottom:8px} h1{margin:0;font-size:clamp(26px,4vw,42px)} h2{margin:0 0 12px;font-size:20px} p{margin:4px 0;color:var(--muted)}
    .controls,.cards,.grid{display:grid;gap:14px}.controls{grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin:18px 0}.cards{grid-template-columns:repeat(auto-fit,minmax(180px,1fr));margin:12px 0 20px}.grid{grid-template-columns:repeat(auto-fit,minmax(360px,1fr))}
    .card,.panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}.metric{font-size:28px;font-weight:700}.label{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
    label{display:grid;gap:5px;font-weight:600} select{width:100%;padding:9px;border:1px solid var(--line);border-radius:8px;background:white;color:var(--ink)}
    .chart{display:grid;gap:10px}.bar-row{display:grid;grid-template-columns:110px 1fr 90px;gap:8px;align-items:center}.track{height:14px;background:#e9eef1;border-radius:999px;overflow:hidden}.bar{height:100%;border-radius:999px}.bar.a{background:var(--a)}.bar.b{background:var(--b)}.value{text-align:right;font-variant-numeric:tabular-nums}.legend{display:flex;gap:16px;color:var(--muted);font-size:13px}.swatch{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px}.swatch.a{background:var(--a)}.swatch.b{background:var(--b)}
    .table-wrap{overflow:auto}.table-wrap.wide{max-height:420px} table{border-collapse:collapse;width:100%;font-size:13px} th,td{border-bottom:1px solid var(--line);padding:8px;text-align:left;white-space:nowrap}th{position:sticky;top:0;background:var(--panel)} td.num{text-align:right;font-variant-numeric:tabular-nums}.ok{color:var(--ok);font-weight:700}.bad{color:var(--bad);font-weight:700}.empty{color:var(--muted);padding:16px 0}
    footer{max-width:1180px;margin:auto;padding:0 24px 30px;color:var(--muted);font-size:13px}@media(max-width:500px){header,main{padding:16px}.grid{grid-template-columns:1fr}.bar-row{grid-template-columns:85px 1fr 76px}}
  </style>
</head>
<body>
<header><div class="label">Algorithms in Finance · Assignment 1</div><h1>Limit order book benchmark</h1><p>Saved measurements only. Changing a filter does not rerun an experiment.</p></header>
<main>
  <section class="controls" aria-label="Dashboard filters">
    <label>Scenario<select id="scenario"></select></label>
    <label>Event count<select id="eventCount"></select></label>
    <label>Seed<select id="seed"></select></label>
  </section>
  <section class="cards">
    <div class="card"><div class="label">Correctness</div><div id="correctness" class="metric">—</div><p id="correctnessNote"></p></div>
    <div class="card"><div class="label">Version B speedup</div><div id="speedup" class="metric">—</div><p>Median replay, A ÷ B</p></div>
    <div class="card"><div class="label">Selected workload</div><div id="workload" class="metric">—</div><p id="workloadNote"></p></div>
  </section>
  <section class="grid">
    <article class="panel"><h2>Throughput</h2><div class="legend"><span><i class="swatch a"></i>Version A</span><span><i class="swatch b"></i>Version B</span></div><div id="throughput" class="chart"></div></article>
    <article class="panel"><h2>Processing latency</h2><p>Instrumented run; nearest-rank p95 in microseconds.</p><div id="latency" class="chart"></div></article>
    <article class="panel"><h2>Peak traced allocation</h2><p>Input events excluded; live book and current result included.</p><div id="memory" class="chart"></div></article>
    <article class="panel"><h2>Operation explanation</h2><div id="operations" class="table-wrap"></div></article>
  </section>
  <section class="panel" style="margin-top:14px"><h2>Latency by event type and stream position</h2><p>Separate run; nearest-rank percentiles. Early and late are the first and last 10% of the stream.</p><div id="latencyDetail" class="table-wrap"></div></section>
  <section class="panel" style="margin-top:14px"><h2>Large liquidation experiments</h2><p>Fresh bid book for every sale; construction and matching measured separately.</p><div id="liquidations" class="table-wrap"></div></section>
  <section class="panel" style="margin-top:14px"><h2>Raw repeats, missing and stopped runs</h2><div id="raw" class="table-wrap wide"></div></section>
</main>
<footer id="environment"></footer>
<script>
const DATA=__DATA__;
const $=id=>document.getElementById(id);
const unique=(rows,key)=>[...new Set(rows.map(r=>r[key]).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b),undefined,{numeric:true}));
function fillSelect(id,values){const el=$(id);el.innerHTML=values.map(v=>`<option>${v}</option>`).join('')}
function number(value){const n=Number(value);return Number.isFinite(n)?n:null}
function fmt(value,digits=2){return value==null?'missing':Number(value).toLocaleString(undefined,{maximumFractionDigits:digits})}
function selected(){return {scenario:$('scenario').value,event_count:$('eventCount').value,seed:$('seed').value}}
function filtered(phase){const s=selected();return DATA.results.filter(r=>r.scenario===s.scenario&&r.event_count===s.event_count&&r.seed===s.seed&&(!phase||r.phase===phase))}
function bars(target,items,unit){if(!items.length){$(target).innerHTML='<div class="empty">No completed measurement.</div>';return}const max=Math.max(...items.map(x=>x.value),1);$(target).innerHTML=items.map(x=>`<div class="bar-row"><span>${x.label}</span><div class="track"><div class="bar ${x.kind}" style="width:${100*x.value/max}%"></div></div><span class="value">${fmt(x.value)} ${unit}</span></div>`).join('')}
function table(target,headers,rows){if(!rows.length){$(target).innerHTML='<div class="empty">No saved rows.</div>';return}$(target).innerHTML=`<table><thead><tr>${headers.map(h=>`<th>${h.label}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${headers.map(h=>`<td class="${h.num?'num':''}">${r[h.key]??''}</td>`).join('')}</tr>`).join('')}</tbody></table>`}
function update(){const s=selected();$('workload').textContent=Number(s.event_count).toLocaleString();$('workloadNote').textContent=`${s.scenario}, seed ${s.seed}`;
 const med=filtered('replay_median').filter(r=>r.status==='completed');const a=med.find(r=>r.version.startsWith('A'));const b=med.find(r=>r.version.startsWith('B'));$('speedup').textContent=a&&b?`${fmt(number(a.elapsed_seconds)/number(b.elapsed_seconds))}×`:'—';
 bars('throughput',med.map(r=>({label:r.version,kind:r.version.startsWith('A')?'a':'b',value:number(r.throughput_events_per_second)})).filter(x=>x.value!=null),'evt/s');
 const lat=filtered('latency_instrumented');bars('latency',lat.map(r=>({label:r.version,kind:r.version.startsWith('A')?'a':'b',value:number(r.latency_p95_us)})).filter(x=>x.value!=null),'µs');
 const mem=filtered('memory');bars('memory',mem.map(r=>({label:r.version,kind:r.version.startsWith('A')?'a':'b',value:number(r.traced_peak_bytes)/1048576})).filter(x=>x.value!=null),'MiB');
 table('operations',[{key:'version',label:'Version'},{key:'maker_scans',label:'Maker scans',num:true},{key:'fill_count',label:'Fills',num:true},{key:'price_levels_visited',label:'Price levels',num:true},{key:'active_order_peak',label:'Peak active',num:true}],lat);
 const detail=(DATA.latency_detail||[]).filter(r=>r.scenario===s.scenario&&r.event_count===s.event_count&&r.seed===s.seed);table('latencyDetail',[{key:'version',label:'Version'},{key:'group',label:'Group'},{key:'category',label:'Category'},{key:'sample_count',label:'Samples',num:true},{key:'median_us',label:'Median µs',num:true},{key:'p95_us',label:'p95 µs',num:true},{key:'p99_us',label:'p99 µs',num:true}],detail);
 const raw=filtered().filter(r=>r.phase==='replay');table('raw',[{key:'version',label:'Version'},{key:'repeat',label:'Repeat',num:true},{key:'status',label:'Status'},{key:'completed_events',label:'Completed',num:true},{key:'elapsed_seconds',label:'Seconds',num:true},{key:'throughput_events_per_second',label:'Events/s',num:true},{key:'notes',label:'Notes'}],raw);
}
const rows=DATA.results;fillSelect('scenario',unique(rows,'scenario'));fillSelect('eventCount',unique(rows,'event_count'));fillSelect('seed',unique(rows,'seed'));['scenario','eventCount','seed'].forEach(id=>$(id).addEventListener('change',update));
const c=DATA.correctness||{};$('correctness').textContent=c.passed?`${c.tests_run}/${c.tests_run}`:`${c.tests_run-(c.failures||0)-(c.errors||0)}/${c.tests_run||0}`;$('correctness').classList.add(c.passed?'ok':'bad');$('correctnessNote').textContent=c.passed?'All saved checks passed':'Failures or errors recorded';
table('liquidations',[{key:'version',label:'Version'},{key:'available_prices',label:'Prices',num:true},{key:'sale_percent',label:'Sale',num:true},{key:'sell_seconds',label:'Sell seconds',num:true},{key:'fill_count',label:'Fills',num:true},{key:'price_levels_visited',label:'Visited prices',num:true},{key:'unfilled_qty_units',label:'Unfilled units',num:true}],DATA.liquidations.slice(0,120));
const env=DATA.environment||{};$('environment').textContent=`Python ${env.python||'unknown'} · ${env.platform||'environment not recorded'} · generated from saved CSV/JSON`;
update();
</script>
</body></html>'''


if __name__ == "__main__":
    main()
