"""Build an offline Plotly dashboard from saved assignment measurements."""
import csv
import hashlib
import html
import json
import statistics
from pathlib import Path

from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / '40_Results'
TARGET = RESULTS / 'targeted_comparison_20261123_175037'
HIST = RESULTS / 'full_comparison_20261123_171219'
DIAG = RESULTS / 'diagnostic_v1_20261123_152031'
SCALING = RESULTS / 'scaling_100000_20261124_114134'
CURRENT_1000 = RESULTS / 'current_1000_20261124_151858'
CONSTRUCTION = RESULTS / 'construction_scaling_20261124_162635'
OUTPUT = RESULTS / 'bitcoin_order_book_dashboard.html'


def read(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def environment(path):
    return json.loads((path / 'environment.json').read_text(encoding='utf-8'))


def main():
    runs, latency, memory = (read(TARGET / name) for name in ('runs.csv', 'latency.csv', 'memory.csv'))
    historical = read(HIST / 'controlled.csv')
    diagnostic = read(DIAG / 'diagnostics.csv')
    scaling = read(SCALING / 'attempts.csv')
    snapshots = read(SCALING / 'progress.csv')
    construction_runs = read(CONSTRUCTION / 'timings.csv')
    construction_ops = read(CONSTRUCTION / 'operation_counts.csv')
    construction_env = environment(CONSTRUCTION)
    small_runs = read(CURRENT_1000 / 'runs.csv')
    small_env = environment(CURRENT_1000)
    scaling_env = environment(SCALING)
    assert len(scaling) == 15
    env, hist_env, diag_env = environment(TARGET), environment(HIST), environment(DIAG)
    for name in ('order_book_v1.py', 'order_book_v2.py'):
        assert small_env['code_sha256'][name] == env['code_sha256'][name]
    scenarios = ['buildup', 'crowded', 'mixed', 'sweep', 'cancel_churn']
    seeds = [42, 43, 44]
    comparisons = []
    for scenario in scenarios:
        for seed in seeds:
            common = [r for r in runs if r['scenario'] == scenario and int(r['seed']) == seed]
            check = [r for r in common if r['phase'] == 'correctness' and r['status'] == 'completed']
            assert len(check) == 1 and check[0]['processed'] == '10000'
            medians = {}
            inputs = set()
            for version in ('A', 'B'):
                rows = [r for r in common if r['version'] == version and r['phase'] == 'replay']
                assert len(rows) == 5 and all(r['status'] == 'completed' for r in rows)
                assert {int(r['repeat']) for r in rows} == set(range(1, 6))
                median = statistics.median(float(r['elapsed_seconds']) for r in rows)
                assert all(abs(float(r['median_seconds']) - median) < 1e-10 for r in rows)
                inputs.update(r['input_sha256'] for r in rows)
                medians[version] = median
            assert len(inputs) == 1 and check[0]['input_sha256'] in inputs
            comparisons.append(dict(scenario=scenario, seed=seed, a=medians['A'], b=medians['B'],
                                    speedup=medians['A']/medians['B'], fingerprint=inputs.pop()))
    assert len([r for r in memory if r['status'] == 'stopped']) == 4
    application = []
    for source, size in ((small_runs, 1000), (runs, 10000)):
        for scenario in scenarios:
            for seed in seeds:
                for version in ('A', 'B'):
                    subset = [r for r in source if r['scenario'] == scenario and int(r['seed']) == seed
                              and r['version'] == version and r['phase'] == 'replay' and r['status'] == 'completed']
                    assert len(subset) == 5
                    application.append(dict(scenario=scenario, seed=seed, version=version, events=size,
                                            replay=statistics.median(float(r['elapsed_seconds']) for r in subset),
                                            parse=statistics.median(float(r['read_parse_seconds']) for r in subset),
                                            total=statistics.median(float(r['elapsed_seconds']) + float(r['read_parse_seconds']) for r in subset)))
    assert sum(r['phase']=='correctness' and r['status']=='completed' for r in small_runs)==15
    lat = [dict(scenario=r['scenario'], seed=int(r['seed']), version=r['version'], group=r['group'],
                median=float(r['median_us']), p95=float(r['p95_us']), p99=float(r['p99_us']),
                samples=int(r['samples'])) for r in latency if r['group'] in ('LIMIT','MARKET_SELL','CANCEL')]
    mem = [dict(scenario=r['scenario'], seed=int(r['seed']), version=r['version'], status=r['status'],
                peak=int(r['peak_bytes']) if r['peak_bytes'] else None,
                final_bytes=int(r['current_bytes']) if r['current_bytes'] else None,
                final_orders=int(r['end_orders']) if r['end_orders'] else 0,
                processed=int(r['processed']), reason=r['reason'],
                heap=int(r['heap_entries']) if r['heap_entries'] else 0,
                stale=int(r['stale_entries']) if r['stale_entries'] else 0,
                rebuilds=int(r['rebuilds']) if r['rebuilds'] else 0)
           for r in memory]
    controlled = []
    for level in (4, 1000):
        for kind in ('sell10', 'sell100', 'sell200', 'cancel'):
            for version in ('A','B'):
                rows = [r for r in historical if r['price_levels'] == str(level) and r['test'] == kind
                        and r['version'] == version and r['status'] == 'completed']
                if rows:
                    assert len(rows) == 5
                    controlled.append(dict(level=level, kind=kind, version=version,
                                           seconds=statistics.median(float(r['elapsed_seconds']) for r in rows),
                                           fills=int(rows[0]['fills']), unfilled=int(rows[0]['unfilled_units']),
                                           orders=int(rows[0]['initial_orders'])))
    cancels = []
    for size in (10,1000):
        rows = [r for r in diagnostic if r['test'] == 'cancel_last' and r['initial_orders'] == str(size)]
        if rows:
            cancels.append(dict(orders=size, version='A', seconds=statistics.median(float(r['elapsed_seconds']) for r in rows)))
    construction = []
    for level in (4, 1000):
        for version in ('A','B'):
            trial = [r for r in historical if r['test']=='sell100' and r['version']==version
                     and int(r['price_levels'])==level and r['status']=='completed']
            assert len(trial)==5
            construction.append(dict(level=level,version=version,orders=1000,
                                     seconds=statistics.median(float(r['construction_seconds']) for r in trial)))
    construction_series = []
    for count in (100,1000,5000,10000):
        for config in ('concentrated','dispersed'):
            matches = [r for r in construction_ops if r['orders']==str(count) and r['configuration']==config]
            assert len(matches)==1 and matches[0]['verification']=='passed'
            info=matches[0]
            for version in ('A','B'):
                raw=[r for r in construction_runs if r['orders']==str(count) and r['configuration']==config
                     and r['version']==version and r['phase']=='construction' and r['status']=='completed']
                warm=[r for r in construction_runs if r['orders']==str(count) and r['configuration']==config
                      and r['version']==version and r['phase']=='warmup']
                complete=len(raw)==5 and len(warm)==1 and warm[0]['status']=='completed'
                if complete:
                    assert all(r['input_sha256']==info['input_sha256'] for r in raw)
                    duration=statistics.median(float(r['elapsed_seconds']) for r in raw)
                    assert all(abs(float(r['median_seconds'])-duration)<1e-10 for r in raw)
                else:
                    duration=None
                construction_series.append(dict(version=version,configuration=config,orders=count,
                    levels=int(info['price_levels']),seed=int(info['seed']),fingerprint=info['input_sha256'],
                    median=duration,throughput=count/duration if duration else None,
                    status='completed' if complete else 'incomplete'))
    data = dict(comparisons=comparisons, latency=lat, memory=mem, controlled=controlled,
                cancellation=cancels, target_env=env, historical_env=hist_env, diagnostic_env=diag_env,
                scaling=scaling, snapshots=snapshots, scaling_env=scaling_env,
                application=application, construction=construction, small_env=small_env,
                construction_series=construction_series, construction_ops=construction_ops,
                construction_env=construction_env)
    largest = max(comparisons, key=lambda x: x['speedup'])
    payload = json.dumps(data, separators=(',', ':'), ensure_ascii=True).replace('</', r'<\/')
    script = r'''
const D = DATA_PLACEHOLDER;
const scenarios = ['buildup','crowded','mixed','sweep','cancel_churn'];
const colors = {A:'#215cc5',B:'#0d8a75'};
const fmt = n => n.toLocaleString(undefined,{maximumFractionDigits:2});
const median = a => {const v=[...a].sort((x,y)=>x-y); return v[Math.floor(v.length/2)];};
const pretty = s => s.replaceAll('_',' ');
const layout = extra => Object.assign({font:{family:'Inter,Segoe UI,Arial',color:'#26354a',size:12},
  paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',margin:{l:70,r:25,t:30,b:95},
  legend:{orientation:'h',y:1.16},hovermode:'closest'},extra);
const config = {responsive:true,displaylogo:false};
function plot(id,traces,options){Plotly.newPlot(id,traces,layout(options),config);}
function paired(id,measure,title){
 const selected=document.getElementById('replay-scenario').value;
 const shown=scenarios.filter(s=>selected==='all'||selected===s);
 const traces=['A','B'].map(v=>({type:'bar',name:'Version '+v,marker:{color:colors[v]},
   x:shown.map(pretty),y:shown.map(s=>{let rows=D.comparisons.filter(r=>r.scenario===s);
     let sec=median(rows.map(r=>r[v.toLowerCase()])); return measure==='time'?sec:10000/sec;}),
   hovertemplate:'%{x}<br>'+title+': %{y:,.5g}<extra>Version '+v+'</extra>'}));
 plot(id,traces,{barmode:'group',yaxis:{title:title,type:'log'},xaxis:{tickangle:-15}});
}
function replay(){paired('runtime','time','Replay seconds (log scale)');
 paired('throughput','throughput','Events per second (log scale)');}
document.getElementById('replay-scenario').onchange=replay; replay();
function speed(){let s=document.getElementById('scenario').value;
 let rows=D.comparisons.filter(r=>s==='all'||r.scenario===s);
 plot('speedup',[{type:'scatter',mode:'markers',name:'Per-seed A / B',
  x:rows.map(r=>pretty(r.scenario)),y:rows.map(r=>r.speedup),
  customdata:rows.map(r=>[r.seed,r.a,r.b]),marker:{size:12,color:rows.map(r=>r.seed),colorscale:'Viridis',showscale:true,colorbar:{title:'Seed'}},
  hovertemplate:'%{x}<br>Seed %{customdata[0]}<br>A %{customdata[1]:.5f} s<br>B %{customdata[2]:.5f} s<br>Speedup %{y:.2f}×<extra></extra>'}],
  {yaxis:{title:'A / B per seed (log scale)',type:'log'},shapes:[{type:'line',xref:'paper',x0:0,x1:1,y0:1,y1:1,line:{dash:'dash',color:'#7a8798'}}]});}
document.getElementById('scenario').onchange=speed; speed();
function latency(){const s=document.getElementById('lat-scenario').value, typ=document.getElementById('lat-type').value;
 let rows=D.latency.filter(r=>r.scenario===s&&r.group===typ);
 document.getElementById('lat-note').textContent=rows.length?'Each point is a separately measured seed.':'No events of this type were measured for this scenario.';
 let traces=[]; for(const v of ['A','B']) for(const stat of ['median','p95','p99']){
 let x=rows.filter(r=>r.version===v); if(x.length) traces.push({type:'scatter',mode:'lines+markers',name:v+' '+stat,
 x:x.map(r=>'Seed '+r.seed),y:x.map(r=>r[stat]),line:{color:colors[v],dash:stat==='median'?'solid':stat==='p95'?'dot':'dash'},
 hovertemplate:'%{x}<br>%{y:.2f} µs<extra>'+v+' '+stat+'</extra>'});}
 plot('latency',traces,{margin:{l:70,r:25,t:75,b:70},legend:{orientation:'h',x:0,y:1.03,yanchor:'bottom',font:{size:10}},yaxis:{title:'Event processing latency (µs, log scale)',type:'log'}});}
document.getElementById('lat-scenario').onchange=latency; document.getElementById('lat-type').onchange=latency; latency();
function memory(){let s=document.getElementById('mem-scenario').value; let rows=D.memory.filter(r=>r.scenario===s);
 let traces=['A','B'].map(v=>{let r=rows.filter(x=>x.version===v);return {type:'bar',name:'Version '+v,
 x:r.map(x=>'Seed '+x.seed),y:r.map(x=>x.peak===null?null:x.peak/1048576),marker:{color:colors[v]},
 hovertemplate:'%{x}<br>%{y:.4f} MiB<extra>Version '+v+'</extra>'};});
 let stops=rows.filter(r=>r.status==='stopped'); document.getElementById('stops').textContent=stops.length?
 'Stopped, no peak available: '+stops.map(r=>'Version '+r.version+', seed '+r.seed+' (at least '+r.processed+' events)').join('; '):'All memory runs for this scenario completed.';
 plot('memory',traces,{barmode:'group',yaxis:{title:'Peak traced Python allocations (MiB, log scale)',type:'log'}});
 let b=rows.filter(r=>r.version==='B');document.getElementById('cleanup').innerHTML=b.map(r=>'<tr><td>'+r.seed+'</td><td>'+r.heap+'</td><td>'+r.stale+'</td><td>'+r.rebuilds+'</td></tr>').join('');}
document.getElementById('mem-scenario').onchange=memory; memory();
let churn=D.memory.filter(r=>r.scenario==='cancel_churn');
document.getElementById('churn-memory').innerHTML=churn.map(r=>'<tr><td>'+r.seed+'</td><td>'+r.version+'</td><td>'+(r.final_bytes===null?'not measured':r.final_bytes.toLocaleString())+'</td><td>'+r.final_orders+'</td></tr>').join('');
function costTable(){let size=Number(document.getElementById('cost-size').value);
 document.getElementById('cost-rows').innerHTML=scenarios.map(s=>{
  let parts=['A','B'].map(v=>{let r=D.application.filter(x=>x.scenario===s&&x.version===v&&x.events===size);
   return median(r.map(x=>x.total)).toFixed(5)});
  return '<tr><td>'+pretty(s)+'</td><td>'+parts[0]+'</td><td>'+parts[1]+'</td></tr>';
 }).join('');}
document.getElementById('cost-size').onchange=costTable;costTable();
document.getElementById('construction-rows').innerHTML=D.construction.map(r=>'<tr><td>'+r.level+'</td><td>'+r.version+'</td><td>'+r.seconds.toFixed(5)+'</td></tr>').join('');
function scaling(){
 let s=document.getElementById('scaling-scenario').value;
 let rows=D.scaling.filter(r=>r.scenario===s);
 let series=rows.map(r=>'Seed '+r.seed);
 let measured=rows.map(r=>r.a_status==='completed'?Number(r.a_seconds):null);
 let linear=rows.map(r=>Number(r.linear_estimate_seconds));
 let quadratic=rows.map(r=>Number(r.quadratic_estimate_seconds));
 let b=rows.map(r=>r.b_status==='completed'?Number(r.b_seconds):null);
 let old=rows.map(r=>Number(r.historical_b_median_seconds));
 let b10=rows.map(r=>{let v=D.comparisons.find(c=>c.scenario===s&&c.seed===Number(r.seed));return v?v.b:null});
 let aHash=D.scaling_env.code_sha256['order_book_v1.py'];
 let bHash=D.scaling_env.code_sha256['order_book_v2.py'];
 let oldHash=D.scaling_env.historical_b_sha256;
 function tip(description,hash){return series.map(seed=>[seed,description,hash]);}
 const hover='%{customdata[0]}<br>%{customdata[1]}<br>%{y:.4g} seconds<br>Code SHA-256: %{customdata[2]}<extra></extra>';
 plot('scaling-runtime',[
  {type:'scatter',mode:'markers',name:'A · 100k',x:series,y:measured,customdata:tip('A: 100,000 events, single measured attempt',aHash),hovertemplate:hover,marker:{color:colors.A,size:12}},
  {type:'scatter',mode:'markers',name:'B · 100k',x:series,y:b,customdata:tip('B: 100,000 events, single measured attempt',bHash),hovertemplate:hover,marker:{color:colors.B,size:12}},
  {type:'scatter',mode:'markers',name:'B · 10k',x:series,y:b10,customdata:tip('B: 10,000 events, median of five runs',bHash),hovertemplate:hover,marker:{color:colors.B,symbol:'square-open',size:10}},
  {type:'scatter',mode:'markers',name:'B · earlier',x:series,y:old,customdata:tip('B: 100,000 events, earlier code, median of five runs',oldHash),hovertemplate:hover,marker:{color:'#8a6aaa',symbol:'diamond-open',size:11}},
  {type:'scatter',mode:'markers',name:'A · linear estimate',x:series,y:linear,customdata:tip('A: hypothetical linear estimate, not measured',aHash),hovertemplate:hover,marker:{color:'#db9b39',symbol:'triangle-up-open',size:12}},
  {type:'scatter',mode:'markers',name:'A · quadratic estimate',x:series,y:quadratic,customdata:tip('A: hypothetical quadratic estimate, not measured',aHash),hovertemplate:hover,marker:{color:'#b45832',symbol:'x-open',size:12}}],
  {margin:{l:70,r:20,t:100,b:60},yaxis:{title:'Seconds (log scale)',type:'log'},legend:{orientation:'h',x:0,y:1.03,yanchor:'bottom',font:{size:10}}});
 let progress=[];
 for(let row of rows){let points=D.snapshots.filter(p=>p.version==='A'&&p.scenario===s&&p.seed===row.seed);
  progress.push({type:'scatter',mode:'lines+markers',name:'Seed '+row.seed,
   x:points.map(p=>Number(p.elapsed_seconds)),y:points.map(p=>Number(p.completed_events)),
   customdata:points.map(()=>[row.seed,row.a_status,aHash]),
   marker:{size:4},hovertemplate:'Seed %{customdata[0]} · %{customdata[1]}<br>%{x:.2f} s<br>%{y:,} completed events<br>Code SHA-256: %{customdata[2]}<extra></extra>'});}
 plot('scaling-progress',progress,{margin:{l:70,r:20,t:65,b:60},legend:{orientation:'h',x:0,y:1.03,yanchor:'bottom',font:{size:10}},xaxis:{title:'Observed elapsed processing seconds'},yaxis:{title:'Completed events'},
  shapes:[{type:'line',x0:120,x1:120,yref:'paper',y0:0,y1:1,line:{color:'#b34e36',dash:'dash'}}],
  annotations:[{x:120,y:1,yref:'paper',text:'120 s limit',showarrow:false,xanchor:'right'}]});
 document.getElementById('scaling-table').innerHTML=rows.map(r=>{
 let observed=r.a_status==='completed'?Number(r.a_seconds).toFixed(2)+' s':r.a_status+' — '+Number(r.a_processed).toLocaleString()+' confirmed';
 let comp=r.speedup_measured?Number(r.speedup_measured).toFixed(1)+'× (single attempts)':r.a_status==='stopped'&&r.b_status==='completed'&&r.a_last_snapshot_seconds?'&gt; '+(Number(r.a_last_snapshot_seconds)/Number(r.b_seconds)).toFixed(1)+'× (observed snapshot / B single)':'not available';
 return '<tr><td>'+r.seed+'</td><td>'+observed+'</td><td>'+(r.b_status==='completed'?Number(r.b_seconds).toFixed(3)+' s':'not available')+'</td><td>'+comp+'</td></tr>';
 }).join('');
}
document.getElementById('scaling-scenario').onchange=scaling; scaling();
function constructionScaling(){
 const selected=document.getElementById('construction-config').value;
 const rows=D.construction_series.filter(r=>r.configuration===selected);
 const traces=['A','B'].map(v=>{let a=rows.filter(r=>r.version===v).sort((x,y)=>x.orders-y.orders);
  return {type:'scatter',mode:'lines+markers',name:'Version '+v,x:a.map(r=>r.orders),y:a.map(r=>r.median),
    connectgaps:false,line:{color:colors[v]},marker:{size:9},
    customdata:a.map(r=>[r.levels,r.throughput,r.seed,r.fingerprint,r.status]),
    hovertemplate:'%{x:,} orders<br>%{y:.6f} seconds<br>%{customdata[1]:,.0f} orders/s<br>%{customdata[0]:,} occupied prices<br>Seed %{customdata[2]}<br>Input SHA-256 %{customdata[3]}<br>Status %{customdata[4]}<extra>Version '+v+'</extra>'};});
 plot('construction-scaling',traces,{margin:{l:80,r:25,t:65,b:65},legend:{orientation:'h',x:0,y:1.03,yanchor:'bottom'},
  xaxis:{title:'Submitted orders (log scale)',type:'log',tickvals:[100,1000,5000,10000],ticktext:['100','1,000','5,000','10,000']},
  yaxis:{title:'Median construction time (seconds, log scale)',type:'log'}});
 const missing=rows.filter(r=>r.status!=='completed');
 document.getElementById('construction-status').textContent=missing.length?
   'Incomplete runs: '+missing.map(r=>r.version+' '+r.orders).join(', '):'All eight version / order-count combinations completed for this selection.';
 const ops=D.construction_ops.filter(r=>r.configuration===selected);
 document.getElementById('construction-ops').innerHTML=ops.map(r=>'<tr><td>'+Number(r.orders).toLocaleString()+'</td><td>'+r.new_levels+'</td><td>'+Number(r.existing_level_submissions).toLocaleString()+'</td><td>'+Number(r.duplicate_id_lookup_calls).toLocaleString()+'</td><td>'+Number(r.a_theoretical_prior_order_comparisons).toLocaleString()+'</td></tr>').join('');
}
document.getElementById('construction-config').onchange=constructionScaling; constructionScaling();
function historical(){let level=Number(document.getElementById('level').value);
 let rows=D.controlled.filter(r=>r.level===level&&r.kind.startsWith('sell'));
 plot('sell',['A','B'].map(v=>{let x=rows.filter(r=>r.version===v); return {type:'scatter',mode:'lines+markers',name:'Version '+v,
 x:x.map(r=>Number(r.kind.slice(4))),y:x.map(r=>r.seconds),customdata:x.map(r=>[r.fills,r.unfilled]),line:{color:colors[v]},
 hovertemplate:'%{x}% of depth<br>%{y:.6f} s<br>%{customdata[0]} fills<br>%{customdata[1]} units unfilled<extra>Version '+v+'</extra>'};}),
 {xaxis:{title:'Sale size (% of available quantity)',tickvals:[10,100,200]},yaxis:{title:'Sell seconds (log scale)',type:'log'}});}
document.getElementById('level').onchange=historical; historical();
let histCancel=D.controlled.filter(r=>r.kind==='cancel');
let cancelTraces=[{type:'scatter',mode:'lines+markers',name:'A · earlier',x:D.cancellation.map(r=>r.orders),y:D.cancellation.map(r=>r.seconds*1e6),line:{color:colors.A},hovertemplate:'%{x} orders<br>%{y:.2f} µs<br>Earlier A-only diagnostic<extra></extra>'}];
for(const v of ['A','B']) {let r=histCancel.filter(x=>x.version===v);cancelTraces.push({type:'scatter',mode:'markers',name:v+' · trial',
 x:r.map(x=>x.orders),y:r.map(x=>x.seconds*1e6),customdata:r.map(x=>x.level),marker:{color:colors[v],symbol:v==='A'?'diamond':'square',size:10},
 hovertemplate:'%{x} orders<br>%{y:.2f} µs<br>%{customdata} price levels<extra></extra>'});}
plot('cancel',cancelTraces,{margin:{l:70,r:25,t:65,b:70},legend:{orientation:'h',x:0,y:1.03,yanchor:'bottom',font:{size:10}},xaxis:{title:'Initial active orders (log scale)',type:'log'},yaxis:{title:'Cancellation µs (log scale)',type:'log'}});
'''.replace('DATA_PLACEHOLDER', payload)
    source = html.escape(json.dumps(env['code_sha256'], indent=2))
    hist_source = html.escape(json.dumps(hist_env['code_sha256'], indent=2))
    document = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bitcoin Limit Order Book — Algorithm Performance</title><style>
:root{font-family:Inter,Segoe UI,Arial,sans-serif;color:#26354a;background:#f3f6fa}*{box-sizing:border-box}body{margin:0}header{background:#102b49;color:#fff;padding:42px max(5vw,24px)}header h1{font-size:clamp(26px,4vw,42px);margin:0 0 7px}header p{color:#bed3e9;margin:0;font-size:18px}main{max-width:1420px;margin:auto;padding:24px}h2{font-size:23px;margin:0 0 10px}h3{margin:0 0 8px}p{line-height:1.55}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.metric,.card{background:white;border:1px solid #dfe6ef;border-radius:12px;box-shadow:0 2px 10px #1d355009}.metric{padding:18px}.metric strong{display:block;font-size:27px;color:#1553a7}.metric span,.muted{font-size:13px;color:#5b6c80}.card{padding:22px;margin-top:20px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.plot{height:355px;min-width:0}.wide{height:390px}select{padding:7px;border:1px solid #bdcbda;border-radius:6px;background:white;color:#26354a}label{margin-right:12px;font-size:14px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;text-align:left;border-bottom:1px solid #e6edf5}pre{font-size:11px;white-space:pre-wrap;overflow-wrap:anywhere}details{margin-top:14px}a{color:#1756b0}.pill{color:#9b5a00;background:#fff1d7;padding:10px;border-radius:6px}@media(max-width:850px){.metrics,.grid{grid-template-columns:1fr 1fr}}@media(max-width:600px){.metrics,.grid{grid-template-columns:1fr}main{padding:14px}.plot{height:320px}}
</style><script>PLOTLY_JS</script></head><body><header><h1>Bitcoin Limit Order Book — Algorithm Performance</h1><p>Version A vs. Version B</p></header><main>
<section class="metrics"><div class="metric"><strong>LARGEST</strong><span>Largest per-seed speedup · LARGEST_LABEL</span></div><div class="metric"><strong>15 / 15</strong><span>Comparative correctness checks</span></div><div class="metric"><strong>5</strong><span>Workload scenarios</span></div><div class="metric"><strong>10,000</strong><span>Events per workload</span></div></section>
<section class="card"><h2>What changed</h2><p>Version B substantially improved the measured growing-book and large-sell workloads. Version A remained faster for cancellation churn, where the book stayed almost empty. Measurements reflect this machine and synthetic inputs.</p></section>
<section class="card"><h2>Replay and throughput</h2><p class="muted">Bars show the median of three seed-specific medians. Throughput is 10,000 events divided by the replay median; it does not assume constant event time or measure live-exchange capacity. Axes are logarithmic.</p><label>Scenario <select id="replay-scenario"><option value="all">All scenarios</option>SCENARIOS</select></label><div class="grid"><div><div id="runtime" class="plot"></div></div><div><div id="throughput" class="plot"></div></div></div><h3>Per-seed speedup variation</h3><p class="muted">Each point is A’s five-repeat median divided by B’s five-repeat median for the same seed and input. Values above 1 favor B. Hover for the individual medians.</p><label>Scenario <select id="scenario"><option value="all">All scenarios</option>SCENARIOS</select></label><div id="speedup" class="plot wide"></div></section>
<section class="card"><h2>Processing latency</h2><p class="muted">Latency measures each event; throughput describes the average processing rate across a stream. Percentiles use nearest rank, and each line shows the separately measured seeds.</p><label>Scenario <select id="lat-scenario">SCENARIOS</select></label><label>Event <select id="lat-type"><option>LIMIT</option><option>MARKET_SELL</option><option>CANCEL</option></select></label><p id="lat-note" class="muted"></p><div id="latency" class="plot"></div></section>
<section class="card"><h2>Memory and cleanup</h2><p>Version B maintains additional indexes and heaps, which can increase allocations in exchange for faster lookup. Traced Python allocations are not total process memory; instrumentation differs between versions, so the bars are not pure book-memory comparisons.</p><label>Scenario <select id="mem-scenario">SCENARIOS</select></label><p class="pill" id="stops"></p><div id="memory" class="plot"></div><details><summary>Version B cleanup details (end-of-run heap entries)</summary><table><thead><tr><th>Seed</th><th>Heap entries</th><th>Stale entries</th><th>Rebuilds</th></tr></thead><tbody id="cleanup"></tbody></table></details></section>
<section class="card"><h2>100,000 Events — Scaling and Computational Limits</h2><p>Current Version A and B each use one attempt on identical inputs with progress recorded every 1,000 completed events; full 100,000-event equivalence was not reverified. The hollow B points are historical five-repeat medians using an earlier code hash and different progress overhead. They are not measurements of the current B code.</p><p class="pill"><strong>ESTIMATED — NOT MEASURED.</strong> Linear and quadratic estimates multiply the matching 10,000-event A median by 10 and 100 respectively. They are hypothetical models, not guaranteed bounds or confidence intervals. Sweep work also depends on liquidity and fills.</p><label>Scenario <select id="scaling-scenario">SCENARIOS</select></label><div class="grid"><div><h3>Runtime: actual and estimated</h3><div id="scaling-runtime" class="plot wide"></div></div><div><h3>Version A observed progress</h3><div id="scaling-progress" class="plot wide"></div></div></div><p class="muted">Stopped attempts show the last confirmed snapshot; conservative speedup lower bounds divide the last observed processing time by the current B single attempt. The supervisor's 120-second clock begins just before the child timer, so the observed snapshot avoids overstating the bound. These are not extrapolated speedups or statistical guarantees. Timings include progress-reporting overhead.</p><table><thead><tr><th>Seed</th><th>A outcome</th><th>B current time</th><th>Comparison</th></tr></thead><tbody id="scaling-table"></tbody></table><p class="muted">Detailed input hashes, code hashes, snapshot times and raw attempts: <a href="scaling_100000_20261124_114134/attempts.csv">attempts.csv</a> · <a href="scaling_100000_20261124_114134/progress.csv">progress.csv</a> · <a href="scaling_100000_20261124_114134/environment.json">environment.json</a>.</p></section>
<section class="card"><h2>Historical controlled experiments</h2><p class="pill">Earlier code versions, before identifier-validation harmonization. These trials are historical diagnostic evidence, not results from the targeted benchmark. Source hashes are in the methodology below.</p><div class="grid"><div><h3>Large market sells</h3><label>Price levels <select id="level"><option value="4">4</option><option value="1000">1,000</option></select></label><p class="muted">Hover for fills and unfilled units. Each point is the median of five fresh-book trials.</p><div id="sell" class="plot"></div></div><div><h3>Cancellation by book size</h3><p class="muted">A’s earlier diagnostic measured 10 and 1,000 orders; the controlled A/B trial measured 1,000 orders at two price concentrations. No B result for 10 orders was recorded.</p><div id="cancel" class="plot"></div></div></div></section>
<section class="card"><h2>Why Version B is faster on growing books</h2><table><thead><tr><th>Version A</th><th>Version B</th></tr></thead><tbody><tr><td>One list of individual orders; scans for makers and cancellations.</td><td>ID index for lookup; insertion-ordered dictionaries preserve FIFO at exact prices.</td></tr><tr><td>Finds the best price by scanning the active book.</td><td>Heaps select the best price. Filled and cancelled orders are removed immediately; stale price entries are removed lazily and heaps are rebuilt periodically.</td></tr></tbody></table><p class="muted">Indexes add memory and cleanup work. A simple list can be faster when very few orders are active.</p></section>
<section class="card"><h2>Methodology and raw data</h2><p>Five scenarios · 10,000 events · seeds 42, 43, 44 · one warm-up and five timed replays per seed · identical inputs for both versions · 120-second phase limit · 15 completed correctness checks. Latency and memory were measured separately. Progress updates occurred once per 100 events; timing includes that small overhead.</p><p>Python PYTHON · PLATFORM · MACHINE · PROCESSOR. Results depend on the machine and workload; they are not hardware-independent.</p><p>Raw targeted measurements: <a href="targeted_comparison_20261123_175037/runs.csv">runs.csv</a> · <a href="targeted_comparison_20261123_175037/latency.csv">latency.csv</a> · <a href="targeted_comparison_20261123_175037/memory.csv">memory.csv</a> · <a href="targeted_comparison_20261123_175037/environment.json">environment.json</a>. Historical: <a href="full_comparison_20261123_171219/controlled.csv">controlled.csv</a> · <a href="diagnostic_v1_20261123_152031/diagnostics.csv">diagnostic trials</a>.</p><details><summary>Source hashes and measurement boundaries</summary><p>Targeted benchmark source SHA-256:</p><pre>SOURCE_HASHES</pre><p>Historical controlled source SHA-256:</p><pre>HIST_HASHES</pre><p>Earlier cancellation diagnostic Version A SHA-256: DIAG_HASH</p><p>The targeted run preloaded inputs before tracing. Temporary price-level sets and the Version B rebuild counter add instrumentation allocations. Stopped memory runs are shown as missing, never zero.</p></details></section>
</main><script>APP_JS</script></body></html>'''
    construction_section = '''<section class="card"><h2>Order Book Construction — Scaling</h2>
<p>Fresh, initially empty books receive non-crossing BUY limits. Each point is the median of five measured constructions after one warm-up, including book creation. Both versions use the same seeded events. The 100-order dispersed case has 100 prices; larger dispersed books have 1,000. Concentrated books have four.</p>
<label>Price levels <select id="construction-config"><option value="concentrated">Concentrated · 4 levels</option><option value="dispersed">Dispersed · up to 1,000 levels</option></select></label><div id="construction-scaling" class="plot wide"></div><p class="muted" id="construction-status"></p>
<p>Version A's construction time grew sharply as the active book grew, consistent with repeated scans. At 10,000 orders, B was about 0.021 s with four prices and 0.023 s with 1,000 prices; A was about 3.98 s and 3.37 s. These are observations from one seed, not proof that either concentration is always faster. B indexes order IDs and uses heaps when a price is first created.</p>
<details><summary>Operation counts and measurement boundaries</summary><p>Submitted orders, new levels, existing-level submissions, and duplicate-ID lookup calls are inferred from the verified event stream and the code. The final column is N × (N−1) / 2 for A's unique-ID scans: a theoretical count, not directly instrumented comparisons. Each version was verified against the same input and independently sorted final book; the final order and price-level counts in the CSV come from that separate, untimed verification. Input generation and loading are outside timing; book creation, event processing and a progress update every 100 completed events are included. All runs use seed 42 and a 30-second attempt limit.</p>
<table><thead><tr><th>Orders</th><th>New levels</th><th>Existing-level submissions</th><th>ID lookup calls</th><th>A theoretical ID comparisons</th></tr></thead><tbody id="construction-ops"></tbody></table></details>
<p class="muted">Raw data and configuration: <a href="construction_scaling_20261124_162635/timings.csv">timings.csv</a> · <a href="construction_scaling_20261124_162635/operation_counts.csv">operation_counts.csv</a> · <a href="construction_scaling_20261124_162635/environment.json">environment.json</a>. Exact generated inputs and SHA-256 fingerprints are preserved in the same folder.</p></section>'''
    document = document.replace('<section class="card"><h2>100,000 Events', construction_section + '<section class="card"><h2>100,000 Events')
    evidence = '''<section class="card"><h2>Correctness and measurement evidence</h2>
<table><thead><tr><th>Check</th><th>Result</th><th>Scope</th></tr></thead><tbody>
<tr><td>Correctness suite</td><td>27 passed</td><td>Both versions, including the worked example and instructor-file checksums.</td></tr>
<tr><td>1,000-event comparison</td><td>15 / 15 matched</td><td>Current versions; results and book state compared after every event.</td></tr>
<tr><td>10,000-event comparison</td><td>15 / 15 matched</td><td>Current versions; event results and final books compared.</td></tr>
<tr><td>100,000-event comparison</td><td>Incomplete</td><td>Current-code full comparison not rerun; 12 prior checks stopped and three churn checks passed on earlier code.</td></tr>
</tbody></table><p class="muted">Tests provide evidence, not a proof. A million-event experiment was not performed: Version A's observed scaling made it infeasible within the available time and resources, not mathematically impossible.</p>
<details><summary>Estimated application cost (saved parsing + replay)</summary><p class="muted">For each seed and version, we add the separately saved parsing time and replay time for each repeat, then take the median of five; the table is the median across seeds. This is a derived estimate, not a separately timed end-to-end run; process startup and printing are excluded. Times are seconds.</p><label>Events <select id="cost-size"><option value="1000">1,000</option><option value="10000">10,000</option></select></label><table><thead><tr><th>Scenario</th><th>Version A</th><th>Version B</th></tr></thead><tbody id="cost-rows"></tbody></table></details>
<details><summary>Historical construction and post-cancellation memory</summary><p class="muted">Construction is the median of five fresh 1,000-bid books used for the 100% sell trial. These are historical, earlier-code measurements; they are not current-code construction scaling results.</p><table><thead><tr><th>Price levels</th><th>Version</th><th>Construction seconds</th></tr></thead><tbody id="construction-rows"></tbody></table><p class="muted">The following are final traced allocations after the current 10,000-event cancellation-churn stream. Input was preloaded before tracing; instrumentation and the last returned result are included. These are not total process memory or pure book size.</p><table><thead><tr><th>Seed</th><th>Version</th><th>Final traced bytes</th><th>Active orders</th></tr></thead><tbody id="churn-memory"></tbody></table></details>
<p class="muted">Current 1,000-event raw results: <a href="current_1000_20261124_151858/runs.csv">runs.csv</a> · <a href="current_1000_20261124_151858/environment.json">environment.json</a>. Historical controlled source hashes remain listed below.</p></section>'''
    document = document.replace('<section class="card"><h2>100,000 Events', evidence + '<section class="card"><h2>100,000 Events')
    options = ''.join(f'<option value="{s}">{s.replace("_", " ")}</option>' for s in scenarios)
    replacements = {'SCENARIOS': options,
                    'LARGEST_LABEL': f"{largest['scenario'].replace('_',' ')} · seed {largest['seed']}",
                    'LARGEST': f"{largest['speedup']:.1f}×", 'PYTHON': html.escape(env['python']),
                    'PLATFORM': html.escape(env['platform']), 'MACHINE': html.escape(env['machine']),
                    'PROCESSOR': html.escape(env['processor']), 'SOURCE_HASHES': source,
                    'HIST_HASHES': hist_source, 'DIAG_HASH': html.escape(diag_env['v1_sha256']),
                    'APP_JS': script, 'PLOTLY_JS': get_plotlyjs()}
    for key, value in replacements.items():
        document = document.replace(key, value)
    OUTPUT.write_text(document, encoding='utf-8')
    print('Dashboard:', OUTPUT)
    print('Largest per-seed speedup:', largest)
    print('Plotly embedded; stopped memory runs:', len([r for r in mem if r['status'] == 'stopped']))


if __name__ == '__main__':
    main()
