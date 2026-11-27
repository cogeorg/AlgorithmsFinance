#!/usr/bin/env python3
"""Build a dependency-free interactive dashboard from saved measurements."""

from __future__ import annotations

import argparse
from html import escape
import json
from pathlib import Path
import re

from measurement.metrics import load_report, validate_report


PROJECT_ROOT = Path(__file__).resolve().parent


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Limit order book - saved-results dashboard</title>
<style>
:root{--ink:#10243e;--muted:#617188;--paper:#f4f7fb;--card:#fff;--line:#d9e2ec;--blue:#1769aa;--teal:#0b8f87;--orange:#d97706;--red:#b42318;--green:#15803d;--shadow:0 8px 30px rgba(15,35,60,.08)}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:14px/1.45 ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{padding:36px clamp(20px,5vw,70px);background:linear-gradient(120deg,#10243e,#174f78);color:white}header h1{font-size:clamp(27px,4vw,46px);margin:0 0 8px;letter-spacing:-.025em}header p{max-width:900px;margin:0;color:#d9e9f4;font-size:16px}.shell{max-width:1500px;margin:auto;padding:24px}.warning{padding:13px 16px;border-left:4px solid var(--orange);background:#fff7e6;border-radius:8px;margin-bottom:20px}.ok{border-color:var(--green);background:#ecfdf3}.filters,.cards,.grid{display:grid;gap:14px}.filters{grid-template-columns:repeat(auto-fit,minmax(170px,1fr));background:var(--card);padding:16px;border-radius:12px;box-shadow:var(--shadow);position:sticky;top:8px;z-index:4}.filters label{font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}.filters select,.filters button{width:100%;margin-top:5px;border:1px solid var(--line);border-radius:8px;background:white;padding:9px 10px;color:var(--ink)}.filters button{background:var(--ink);color:white;cursor:pointer}.cards{grid-template-columns:repeat(auto-fit,minmax(170px,1fr));margin:18px 0}.metric{background:var(--card);padding:16px;border-radius:12px;box-shadow:var(--shadow);min-width:0}.metric b{font-size:25px;display:block;overflow-wrap:anywhere}.metric span{color:var(--muted)}section{margin:22px 0;background:var(--card);padding:20px;border-radius:14px;box-shadow:var(--shadow)}section h2{margin:0 0 5px;font-size:22px}section>p{margin:0 0 16px;color:var(--muted)}.grid{grid-template-columns:repeat(auto-fit,minmax(420px,1fr))}.panel{border:1px solid var(--line);border-radius:10px;padding:13px;min-height:300px}.panel h3{margin:0 0 8px}.chart svg{width:100%;height:260px;overflow:visible}.empty{display:grid;place-items:center;height:230px;color:var(--muted)}.legend{display:flex;gap:14px;flex-wrap:wrap;color:var(--muted);font-size:12px}.legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:8px 9px;border-bottom:1px solid var(--line);vertical-align:top}th{position:sticky;top:0;background:#edf3f8;color:#40536a}.table-wrap{overflow:auto;max-height:430px;border:1px solid var(--line);border-radius:9px}.tag{display:inline-block;padding:3px 8px;border-radius:999px;background:#e7f0f8;color:#174f78;font-weight:700;font-size:12px}.tag.bad{background:#fee4e2;color:var(--red)}pre{white-space:pre-wrap;word-break:break-word;background:#0d2138;color:#d9e9f4;padding:16px;border-radius:9px;max-height:440px;overflow:auto}.note{padding:13px;background:#eef8f7;border-left:4px solid var(--teal);border-radius:7px}.small{font-size:12px;color:var(--muted)}@media(max-width:600px){.shell{padding:12px}.grid{grid-template-columns:1fr}.panel{min-width:0}.filters{position:static}}
</style>
</head>
<body>
<header><h1>Saved-results dashboard</h1><p>Limit order book baseline versus revision. Every view below is computed from the embedded saved report; filters never rerun a benchmark.</p></header>
<main class="shell">
  <div id="status" class="warning__STATUS_CLASS__">__STATUS_HTML__</div>
  <div class="filters">
    <div><label for="experiment">Experiment</label><select id="experiment"></select></div>
    <div><label for="scenario">Scenario</label><select id="scenario"></select></div>
    <div><label for="seed">Seed</label><select id="seed"></select></div>
    <div><label for="phase">Timing phase</label><select id="phase"></select></div>
    <div><label>Raw evidence</label><button id="download">Download filtered timing CSV</button></div>
  </div>
  <div id="cards" class="cards"></div>

  <section><h2>Timing and throughput</h2><p>Preparation, engine replay, total application, construction, and sale phases are selectable above. Curves plot only complete repeat sets; partial, stopped, and missing evidence remains visible in the tables.</p><div class="grid"><div class="panel"><h3>Median elapsed time (seconds)</h3><div id="timing" class="chart"></div></div><div class="panel"><h3>Median throughput (events/second)</h3><div id="throughput" class="chart"></div></div></div></section>

  <section><h2>Processing latency</h2><p>Separate instrumented runs in nanoseconds. The ECDF is computed only from saved per-event samples. Percentiles use the recorded nearest-rank convention; these are engine processing times, not network latency.</p><div class="grid"><div class="panel"><h3>Empirical cumulative distribution (ECDF)</h3><div id="latencyEcdf" class="chart"></div></div><div class="panel"><h3>p50 / p95 / p99 scaling</h3><div id="latency" class="chart"></div></div><div class="panel"><h3>Early, late, and event-type summaries</h3><div id="latencyTable" class="table-wrap"></div></div></div></section>

  <section><h2>Traced memory</h2><p>Python allocations measured separately with input excluded and book plus final output alive. This is not auxiliary space or total process RSS.</p><div class="grid"><div class="panel"><h3>Peak traced MiB</h3><div id="memory" class="chart"></div></div><div class="panel"><h3>Memory measurements and growth checkpoints</h3><div id="memoryTable" class="table-wrap"></div></div></div></section>

  <section><h2>Liquidation</h2><p>Each 10%, 100%, and 200% sale uses its own freshly rebuilt bid book. Construction and individual-sale costs are saved separately.</p><div class="grid"><div class="panel"><h3>Sale-size scaling</h3><div id="liquidation" class="chart"></div></div><div class="panel"><h3>Makers, price levels, and residual</h3><div id="liquidationTable" class="table-wrap"></div></div></div></section>

  <section><h2>Correctness and work</h2><p>Agreement supplements independent expected results. Operation counts explain work separately from timing.</p><div class="grid"><div class="panel"><h3>Correctness</h3><div id="correctness" class="table-wrap"></div></div><div class="panel"><h3>Operation counts</h3><div id="operations" class="table-wrap"></div></div></div><p class="note"><b>Bottleneck interpretation.</b> The baseline validates and finds makers by scanning active orders, so growing active depth raises work even for noncrossing submissions. The revision indexes live identifiers and FIFO price levels, trading list scans for sorted-price maintenance. Queue concentration, exhausted levels, cancellation cleanup, and fill count therefore determine when the revision wins; the saved operation counts and complexity notes should be read with the plots rather than assuming one version always dominates.</p></section>

  <section><h2>Raw repeats</h2><p id="rawCaption"></p><div id="raw" class="table-wrap"></div></section>
  <section><h2>Stopped, partial, or missing evidence</h2><p>Declared limits and incomplete repeat sets are evidence, not data to hide or extrapolate.</p><div id="stopped" class="table-wrap"></div></section>
  <section><h2>Environment and settings</h2><p>Recorded code version, machine, Python, clock, units, generator settings, and exact command.</p><div class="grid"><div><h3>Environment</h3><pre id="environment"></pre></div><div><h3>Settings</h3><pre id="settings"></pre></div></div><h3>Datasets</h3><div id="datasets" class="table-wrap"></div></section>
</main>
<script>
const REPORT=__REPORT_JSON__;
const records=REPORT.records||[];
const colors={baseline:'#1769aa',revised:'#0b8f87',shared:'#d97706',p50:'#1769aa',p95:'#d97706',p99:'#b42318'};
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
const uniq=a=>[...new Set(a.filter(v=>v!==undefined&&v!==null))].sort((a,b)=>String(a).localeCompare(String(b),undefined,{numeric:true}));
function fillSelect(id,values,all=true){const s=document.getElementById(id);s.innerHTML=(all?'<option value="all">All</option>':'')+values.map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join('')}
fillSelect('experiment',uniq((REPORT.datasets||[]).map(d=>d.experiment)));fillSelect('scenario',uniq((REPORT.datasets||[]).map(d=>d.scenario)));fillSelect('seed',uniq((REPORT.datasets||[]).map(d=>d.seed)));fillSelect('phase',uniq(records.filter(r=>r.measurement_kind==='timing_summary').map(r=>r.phase)),false);
function setDefault(id,value){const s=document.getElementById(id);if([...s.options].some(o=>o.value===String(value)))s.value=String(value)}
setDefault('experiment','stream');setDefault('scenario','mixed');setDefault('seed','43');
if([...document.getElementById('phase').options].some(o=>o.value==='engine_replay'))document.getElementById('phase').value='engine_replay';
function selected(id){return document.getElementById(id).value}
function baseFilter(r){return (selected('experiment')==='all'||String(r.experiment)===selected('experiment'))&&(selected('scenario')==='all'||String(r.scenario)===selected('scenario'))&&(selected('seed')==='all'||String(r.seed)===selected('seed'))}
function seriesKey(r,suffix=''){const parts=[r.version];if(selected('experiment')==='all')parts.push(r.experiment);if(selected('scenario')==='all')parts.push(r.scenario);if(selected('seed')==='all')parts.push(`seed ${r.seed}`);if(suffix)parts.push(suffix);return parts.join(' · ')}
function fmt(v,d=3){if(v===null||v===undefined||v==='')return '—';return Number.isFinite(Number(v))?Number(v).toLocaleString(undefined,{maximumFractionDigits:d}):'—'}
function mib(v){return Number(v)/1048576}
function completionStatus(r){if(r.completion_status)return r.completion_status;if(r.measurement_kind!=='timing_summary')return '—';const done=Number(r.completed_repeat_count||0),stopped=Number(r.stopped_repeat_count||0);if(done&&stopped)return 'partial';if(done)return 'complete';return 'stopped'}
function table(target,rows,columns){const el=document.getElementById(target);if(!rows.length){el.innerHTML='<div class="empty">No saved rows for this filter.</div>';return}el.innerHTML=`<table><thead><tr>${columns.map(c=>`<th>${esc(c[0])}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${columns.map(c=>`<td>${esc(typeof c[1]==='function'?c[1](r):r[c[1]])}</td>`).join('')}</tr>`).join('')}</tbody></table>`}
function lineChart(target,rows,xKey,yKey,seriesFn,yFormat=fmt){const el=document.getElementById(target);rows=rows.filter(r=>Number(r[xKey])>0&&Number(r[yKey])>=0);if(!rows.length){el.innerHTML='<div class="empty">No saved points for this filter and phase.</div>';return}const W=620,H=250,m={l:62,r:18,t:18,b:42};const xs=uniq(rows.map(r=>Number(r[xKey]))).map(Number),ys=rows.map(r=>Number(r[yKey]));const lx=xs.map(Math.log10),minX=Math.min(...lx),maxX=Math.max(...lx),maxY=Math.max(...ys,1e-12);const x=v=>m.l+(Math.log10(Number(v))-minX)/(maxX-minX||1)*(W-m.l-m.r),y=v=>H-m.b-Number(v)/maxY*(H-m.t-m.b);const groups={};rows.forEach(r=>(groups[seriesFn(r)]??=[]).push(r));let svg=`<svg viewBox="0 0 ${W} ${H}" role="img"><line x1="${m.l}" y1="${H-m.b}" x2="${W-m.r}" y2="${H-m.b}" stroke="#9cadbf"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${H-m.b}" stroke="#9cadbf"/>`;[0,.25,.5,.75,1].forEach(p=>{const yy=H-m.b-p*(H-m.t-m.b);svg+=`<line x1="${m.l}" y1="${yy}" x2="${W-m.r}" y2="${yy}" stroke="#e5ebf1"/><text x="${m.l-8}" y="${yy+4}" text-anchor="end" font-size="10" fill="#617188">${esc(yFormat(maxY*p))}</text>`});xs.forEach(v=>svg+=`<text x="${x(v)}" y="${H-18}" text-anchor="middle" font-size="10" fill="#617188">${esc(fmt(v,0))}</text>`);Object.entries(groups).forEach(([name,pts],i)=>{pts.sort((a,b)=>Number(a[xKey])-Number(b[xKey]));const color=colors[name]||['#6d28d9','#be123c','#0891b2','#4d7c0f'][i%4];svg+=`<polyline fill="none" stroke="${color}" stroke-width="2.5" points="${pts.map(r=>`${x(r[xKey])},${y(r[yKey])}`).join(' ')}"/>`;pts.forEach(r=>svg+=`<circle cx="${x(r[xKey])}" cy="${y(r[yKey])}" r="3.5" fill="${color}"><title>${esc(name)}: x=${r[xKey]}, y=${r[yKey]}</title></circle>`)});svg+='</svg><div class="legend">'+Object.keys(groups).map((name,i)=>`<span><i style="background:${colors[name]||['#6d28d9','#be123c','#0891b2','#4d7c0f'][i%4]}"></i>${esc(name)}</span>`).join('')+'</div>';el.innerHTML=svg}
function ecdfChart(target,rows){const el=document.getElementById(target),series=[];rows.forEach(r=>{const samples=(r.samples_ns||[]).map(Number).filter(Number.isFinite).sort((a,b)=>a-b);if(!samples.length)return;const stride=Math.max(1,Math.ceil(samples.length/800)),points=[];for(let i=0;i<samples.length;i+=stride)points.push([samples[i],(i+1)/samples.length]);if(points.at(-1)[0]!==samples.at(-1))points.push([samples.at(-1),1]);series.push({name:`${seriesKey(r)} · M ${r.event_count}`,points})});if(!series.length){el.innerHTML='<div class="empty">No saved latency samples for this filter.</div>';return}const W=620,H=250,m={l:62,r:18,t:18,b:42},values=series.flatMap(s=>s.points.map(p=>p[0])),minX=Math.min(...values),maxX=Math.max(...values),x=v=>m.l+(v-minX)/(maxX-minX||1)*(W-m.l-m.r),y=v=>H-m.b-v*(H-m.t-m.b);let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Latency empirical cumulative distribution"><line x1="${m.l}" y1="${H-m.b}" x2="${W-m.r}" y2="${H-m.b}" stroke="#9cadbf"/><line x1="${m.l}" y1="${m.t}" x2="${m.l}" y2="${H-m.b}" stroke="#9cadbf"/>`;[0,.25,.5,.75,1].forEach(p=>{const yy=y(p);svg+=`<line x1="${m.l}" y1="${yy}" x2="${W-m.r}" y2="${yy}" stroke="#e5ebf1"/><text x="${m.l-8}" y="${yy+4}" text-anchor="end" font-size="10" fill="#617188">${fmt(p,2)}</text>`});[0,.25,.5,.75,1].forEach(p=>{const value=minX+p*(maxX-minX),xx=x(value);svg+=`<text x="${xx}" y="${H-18}" text-anchor="middle" font-size="10" fill="#617188">${fmt(value,0)}</text>`});series.forEach((item,i)=>{const color=['#1769aa','#0b8f87','#d97706','#b42318','#6d28d9','#0891b2'][i%6];svg+=`<polyline fill="none" stroke="${color}" stroke-width="2" points="${item.points.map(p=>`${x(p[0])},${y(p[1])}`).join(' ')}"><title>${esc(item.name)}</title></polyline>`});svg+='</svg><div class="small">x: saved processing latency (ns) · y: cumulative fraction</div><div class="legend">'+series.map((item,i)=>`<span><i style="background:${['#1769aa','#0b8f87','#d97706','#b42318','#6d28d9','#0891b2'][i%6]}"></i>${esc(item.name)}</span>`).join('')+'</div>';el.innerHTML=svg}
function redraw(){const filtered=records.filter(baseFilter),phase=selected('phase');const timing=filtered.filter(r=>r.measurement_kind==='timing_summary'&&r.phase===phase&&completionStatus(r)==='complete');lineChart('timing',timing,'event_count','elapsed_seconds_median',r=>seriesKey(r),v=>fmt(v,4));lineChart('throughput',timing.filter(r=>r.throughput_events_per_second_median!==undefined),'event_count','throughput_events_per_second_median',r=>seriesKey(r),v=>fmt(v,0));const latency=filtered.filter(r=>r.measurement_kind==='latency'&&!r.stopped),latencyPoints=[];ecdfChart('latencyEcdf',latency);latency.forEach(r=>['p50','p95','p99'].forEach(p=>latencyPoints.push({...r,percentile_ns:r[p+'_ns'],series:seriesKey(r,p)})));lineChart('latency',latencyPoints,'event_count','percentile_ns',r=>r.series,v=>fmt(v,0));const latencyRows=[];latency.forEach(r=>{['early_window','late_window'].forEach(k=>r[k]&&latencyRows.push({...r,group:k.replace('_',' '),...r[k]}));Object.entries(r.by_event_type||{}).forEach(([k,v])=>latencyRows.push({...r,group:k,...v}))});table('latencyTable',latencyRows,[['Scenario','scenario'],['M','event_count'],['Version','version'],['Group','group'],['n','count'],['p50 ns','p50_ns'],['p95 ns','p95_ns'],['p99 ns','p99_ns']]);const memory=filtered.filter(r=>r.measurement_kind==='memory'&&!r.stopped);lineChart('memory',memory.map(r=>({...r,peak_mib:mib(r.peak_traced_bytes)})),'event_count','peak_mib',r=>seriesKey(r),v=>fmt(v,2));table('memoryTable',memory,[['Scenario','scenario'],['M','event_count'],['Version','version'],['Phase','phase'],['Current MiB',r=>fmt(mib(r.current_traced_bytes),3)],['Peak MiB',r=>fmt(mib(r.peak_traced_bytes),3)],['Checkpoints',r=>(r.allocation_checkpoints||[]).map(c=>`${c.events_processed}:${fmt(mib(c.current_traced_bytes),2)}MiB`).join(' | ')],['Boundary',r=>`input ${r.input_included?'in':'out'}, book ${r.book_included?'in':'out'}, final output ${r.final_output_included?'in':'out'}`]]);const liq=filtered.filter(r=>r.measurement_kind==='timing_summary'&&r.phase==='individual_sale'&&completionStatus(r)==='complete');lineChart('liquidation',liq,'liquidation_percent','elapsed_seconds_median',r=>seriesKey(r),v=>fmt(v,5));table('liquidationTable',filtered.filter(r=>r.measurement_kind==='correctness'&&r.phase==='individual_sale'),[['M','event_count'],['Seed','seed'],['Sale %','liquidation_percent'],['Requested units','requested_qty_units'],['Fills','fill_count'],['Price levels','maker_price_levels_visited'],['Unfilled units','unfilled_qty_units']]);table('correctness',filtered.filter(r=>r.measurement_kind==='correctness'),[['Dataset','dataset_id'],['Phase','phase'],['Events',r=>r.events_compared??'—'],['Ordered results',r=>r.ordered_results_equal?'pass':'—'],['Final books',r=>r.final_books_equal?'pass':'—'],['Stopped',r=>r.stopped?'yes':'no']]);table('operations',filtered.filter(r=>r.measurement_kind==='operation_counts'),[['Dataset','dataset_id'],['Requested','events_requested'],['Processed','events_processed'],['Active peak','active_order_peak'],['Price-level peak','occupied_price_level_peak'],['Fills','fill_count'],['Visited levels','maker_price_levels_visited'],['Final active','final_active_order_count']]);const raw=filtered.filter(r=>r.measurement_kind==='timing'&&r.phase===phase);document.getElementById('rawCaption').textContent=`Showing ${Math.min(raw.length,500)} of ${raw.length} saved raw repeats for ${phase}.`;table('raw',raw.slice(0,500),[['Dataset','dataset_id'],['Version','version'],['Repeat','repeat'],['Attempted',r=>r.attempted===false?'no':'yes'],['Seconds',r=>fmt(r.elapsed_seconds,6)],['Events','events_processed'],['Throughput/s',r=>fmt(r.throughput_events_per_second,0)],['Stopped',r=>r.stopped?`yes: ${r.stop_reason}`:'no']]);const exceptional=filtered.filter(r=>r.stopped||completionStatus(r)==='partial'||completionStatus(r)==='missing');table('stopped',exceptional,[['Dataset','dataset_id'],['Kind','measurement_kind'],['Phase','phase'],['Version','version'],['Repeat','repeat'],['Attempted',r=>r.attempted===false?'no':r.measurement_kind==='timing'?'yes':'—'],['Completion status',completionStatus],['Expected repeats',r=>r.expected_repeat_count??'—'],['Completed repeats',r=>r.completed_repeat_count??'—'],['Stopped repeats',r=>r.stopped_repeat_count??'—'],['Missing repeats',r=>r.missing_repeat_count??'—'],['Reason',r=>r.stop_reason??(completionStatus(r)==='missing'?'repeat data missing':'partial repeat set')]]);document.getElementById('cards').innerHTML=[['Run label',REPORT.run_label],['Datasets',(REPORT.datasets||[]).length],['Saved records',records.length],['Stopped records',records.filter(r=>r.stopped).length],['Partial summaries',records.filter(r=>completionStatus(r)==='partial').length],['Missing summaries',records.filter(r=>completionStatus(r)==='missing').length],['Git commit',(REPORT.environment||{}).git_commit||'—']].map(([k,v])=>`<div class="metric"><b>${esc(v)}</b><span>${esc(k)}</span></div>`).join('')}
['experiment','scenario','seed','phase'].forEach(id=>document.getElementById(id).addEventListener('change',redraw));
document.getElementById('download').addEventListener('click',()=>{const phase=selected('phase'),rows=records.filter(r=>baseFilter(r)&&r.measurement_kind==='timing'&&r.phase===phase),cols=['dataset_id','experiment','scenario','seed','event_count','levels','version','phase','repeat','attempted','elapsed_seconds','events_processed','throughput_events_per_second','stopped','stop_reason'],csv=[cols.join(','),...rows.map(r=>cols.map(c=>`"${String(r[c]??'').replaceAll('"','""')}"`).join(','))].join('\n'),blob=new Blob([csv],{type:'text/csv'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`timing-${phase}.csv`;a.click();URL.revokeObjectURL(a.href)});
document.getElementById('environment').textContent=JSON.stringify(REPORT.environment||{},null,2);document.getElementById('settings').textContent=JSON.stringify(REPORT.settings||{},null,2);table('datasets',REPORT.datasets||[],[['Dataset','dataset_id'],['Experiment','experiment'],['Scenario','scenario'],['M','event_count'],['Seed','seed'],['Levels','levels'],['Event SHA-256','event_sha256']]);redraw();
</script>
</body></html>
"""


def evidence_status(report: dict[str, object]) -> tuple[str, str, bool]:
    """Return the saved report's label, explanation, and canonical status."""

    try:
        validate_report(report)
    except ValueError as error:
        return ("Invalid measurement evidence.", str(error), False)

    environment = report.get("environment", {})
    settings = report.get("settings", {})
    dirty = bool(environment.get("git_dirty"))  # type: ignore[union-attr]
    revision = int(  # type: ignore[union-attr]
        settings.get("measurement_integrity_revision", 0)
    )
    if report.get("run_label") == "canonical" and not dirty:
        if revision >= 4:
            return (
                "Canonical clean-tree evidence.",
                "Views are backed by the recorded corrected measurement commit.",
                True,
            )
        return (
            "Superseded legacy measurement evidence.",
            "This clean-tree report predates measurement-integrity revision 4.",
            False,
        )
    return (
        str(report.get("run_label", "unknown run")),
        (
            "The tree was dirty; do not present this report as canonical submission evidence."
            if dirty
            else "Do not present this noncanonical report as canonical submission evidence."
        ),
        False,
    )


def render_dashboard(report: dict[str, object]) -> str:
    """Return deterministic HTML containing only the supplied saved report."""

    validate_report(report)
    serialized = json.dumps(report, sort_keys=True, separators=(",", ":"))
    serialized = serialized.replace("</", "<\\/")
    label, explanation, canonical = evidence_status(report)
    status_html = f"<b>{escape(label)}</b> {escape(explanation)}"
    replacements = {
        "__REPORT_JSON__": serialized,
        "__STATUS_CLASS__": " ok" if canonical else "",
        "__STATUS_HTML__": status_html,
    }
    return re.sub(
        "|".join(re.escape(token) for token in replacements),
        lambda match: replacements[match.group(0)],
        HTML_TEMPLATE,
    )


def write_dashboard(report: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard(report), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        type=Path,
        default=PROJECT_ROOT / "results" / "raw_measurements.json.gz",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "results" / "dashboard.html",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = load_report(args.results)
    write_dashboard(report, args.output)
    print(f"loaded_results={args.results}")
    print(f"run_label={report['run_label']}")
    print(f"records={len(report['records'])}")
    print(f"dashboard={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
