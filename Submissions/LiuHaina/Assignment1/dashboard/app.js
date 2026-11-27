/* Offline presentation only: no network requests, engine imports or experiments. */
(() => {
  "use strict";
  const D = JSON.parse(document.getElementById("saved-data").textContent);
  const $ = id => document.getElementById(id);
  const sizes = [1000, 10000, 100000];
  const versions = ["A", "B"];
  const colors = {A: "#b96721", B: "#087d91"};
  const esc = x => String(x ?? "—").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const comma = x => x == null ? "—" : Number(x).toLocaleString("en-US", {maximumFractionDigits:0});
  const decimal = (x, digits=3) => x == null || !Number.isFinite(x) ? "—" : Number(x).toLocaleString("en-US", {maximumFractionDigits:digits, minimumFractionDigits:Math.abs(x)<1 ? Math.min(digits,3) : 0});
  const compact = x => x >= 1e6 ? `${decimal(x/1e6,1)}M` : x >= 1000 ? `${decimal(x/1000,1)}k` : decimal(x,3);
  const numeric = text => ({html:esc(text), cls:"numeric"});
  const markup = text => ({html:text});
  const status = (value, extra="") => markup(`<span class="status ${value === "completed" || value === "passed" ? "ok" : "partial"}">${esc(value)}${extra ? " · "+esc(extra) : ""}</span>`);
  const ver = value => markup(`<span class="version-${value.toLowerCase()}">${value === "A" ? "●" : "■"} ${value}</span>`);
  let rawPage = 0;
  let filteredRaw = [];
  const state = () => ({scenario:$("scenario").value,seed:+$("seed").value,event_count:+$("size").value,levels:1000});
  function match(row, criteria) {return Object.entries(criteria).every(([k,v]) => row[k] === v);}
  function find(phase, version, extra={}) {return D.summary.find(r => r.phase===phase && r.version===version && match(r,{...state(),...extra}));}
  function raw(phase, version, extra={}) {return D.raw.find(r => r.phase===phase && r.version===version && match(r,{...state(),...extra}));}
  function ms(row) {return row?.median_elapsed_seconds == null ? "—" : decimal(row.median_elapsed_seconds*1000);}
  function outcome(row, wanted=5) {
    if (!row) return markup('<span class="na">not measured</span>');
    if (!row.completed_repeats) return status(row.statuses?.join(" / ") || "not completed");
    return status(row.completed_repeats===wanted ? "completed" : "partial repeats",`${row.completed_repeats}/${wanted}`);
  }
  function table(id, headings, rows) {
    $(id).innerHTML = `<table><thead><tr>${headings.map(h=>`<th scope="col">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.length ? rows.map(cells=>`<tr>${cells.map(c=>`<td class="${c?.cls || ""}">${c && typeof c === "object" && "html" in c ? c.html : esc(c)}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${headings.length}">No saved observations for this selection.</td></tr>`}</tbody></table>`;
  }
  function lineChart(id, series, options={}) {
    const all = series.flatMap(s=>s.points.filter(p=>p.y!=null && Number.isFinite(p.y)));
    if (!all.length) {$(id).innerHTML='<div class="empty">No completed measurement for this selection.</div>'; return;}
    const w=Math.max(280,Math.round($(id).clientWidth || 640)),h=282,l=76,r=30,t=25,b=51;
    const logX=!!options.logX, logY=!!options.logY;
    const transX=x=>logX?Math.log10(Math.max(x,1e-12)):x;
    const transY=y=>logY?Math.log10(Math.max(y,1e-12)):y;
    const xDomain=options.xDomain || [Math.min(...all.map(p=>p.x)),Math.max(...all.map(p=>p.x))];
    let xmin=transX(xDomain[0]),xmax=transX(xDomain[1]); if(xmin===xmax)xmax=xmin+1;
    const ys=all.map(p=>transY(p.y));
    let ymin=logY?Math.floor(Math.min(...ys)):0;
    let ymax=logY?Math.ceil(Math.max(...ys)):Math.max(...ys)*1.12;
    if(ymax<=ymin)ymax=ymin+1;
    const X=x=>l+(transX(x)-xmin)/(xmax-xmin)*(w-l-r);
    const Y=y=>h-b-(transY(y)-ymin)/(ymax-ymin)*(h-t-b);
    let svg=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(options.label || options.unit || 'Saved measurements')}"><title>${esc(options.label || 'Saved measurements')}</title><text x="${l}" y="13">${esc(options.unit || '')}${logY?' · log scale':''}</text>`;
    const yTicks=logY ? Array.from({length:Math.min(7,ymax-ymin+1)},(_,i)=>ymin+i*(ymax-ymin)/Math.max(1,Math.min(6,ymax-ymin))) : Array.from({length:5},(_,i)=>ymin+i*(ymax-ymin)/4);
    for(const value of yTicks) {
      const actual=logY?10**value:value, y=Y(actual);
      svg+=`<line class="gridline" x1="${l}" x2="${w-r}" y1="${y}" y2="${y}"/><text x="${l-10}" y="${y+4}" text-anchor="end">${esc(options.tickY?options.tickY(actual):compact(actual))}</text>`;
    }
    const xTicks=options.xTicks || [...new Set(all.map(p=>p.x))].sort((a,b)=>a-b);
    for(const x of xTicks)svg+=`<text x="${X(x)}" y="${h-b+23}" text-anchor="middle">${esc(options.tickX?options.tickX(x):comma(x))}</text>`;
    svg+=`<text x="${(l+w-r)/2}" y="${h-4}" text-anchor="middle">${esc(options.xLabel || 'Incoming events · M')}${logX?' · log scale':''}</text>`;
    for(const s of series) {
      let path="",connected=false;
      for(const p of s.points) {
        if(p.y==null || !Number.isFinite(p.y)){connected=false;continue;}
        path+=`${connected?'L':'M'}${X(p.x).toFixed(2)},${Y(p.y).toFixed(2)} `;connected=true;
      }
      svg+=`<path d="${path}" fill="none" stroke="${colors[s.version]}" stroke-width="2.4" ${s.partial?'stroke-dasharray="5 4"':''}/>`;
      for(const p of s.points.filter(p=>p.y!=null && Number.isFinite(p.y))) {
        const x=X(p.x),y=Y(p.y),tip=`${s.version} · ${options.tickX?options.tickX(p.x):comma(p.x)}: ${decimal(p.y,5)} ${options.unit || ''}${s.partial?' · partial prefix':''}`;
        svg+=s.version==='A'?`<circle cx="${x}" cy="${y}" r="4.1" fill="${colors.A}"><title>${esc(tip)}</title></circle>`:`<rect x="${x-3.8}" y="${y-3.8}" width="7.6" height="7.6" fill="${colors.B}"><title>${esc(tip)}</title></rect>`;
      }
    }
    // Grouped tooltips make nearly coincident A/B points inspectable.
    const groups=[...new Set(all.map(p=>p.x))].sort((a,b)=>a-b);
    groups.forEach((x,i)=>{
      const left=i? (X(groups[i-1])+X(x))/2:l, right=i<groups.length-1?(X(x)+X(groups[i+1]))/2:w-r;
      const values=series.flatMap(s=>s.points.filter(p=>p.x===x && p.y!=null).map(p=>`${s.version}: ${decimal(p.y,6)} ${options.unit || ''}${s.partial?' (prefix)':''}`));
      svg+=`<rect x="${left}" y="${t}" width="${Math.max(1,right-left)}" height="${h-t-b}" fill="transparent"><title>${esc((options.tickX?options.tickX(x):comma(x))+" · "+values.join(" · "))}</title></rect>`;
    });
    $(id).innerHTML=svg+"</svg>";
  }
  function scaling() {
    const phase=$("phase").value;
    const labels={replay:"Engine replay",construction:"Book construction",input_parse:"Read + gzip + JSON",parse_plus_replay:"Parse + replay sum"};
    $("time-title").textContent=labels[phase];
    const points=(version,ph,field,factor=1)=>sizes.map(n=>{
      const row=find(ph,version,{event_count:n});
      return {x:n,y:row?.completed_repeats && row[field]!=null ? row[field]*factor:null};
    });
    lineChart("time-chart",versions.map(version=>({version,points:points(version,phase,"median_elapsed_seconds",1000)})),{logX:true,logY:true,xDomain:[1000,100000],xTicks:sizes,unit:"milliseconds",label:`${labels[phase]} scaling, completed repeat medians`});
    lineChart("throughput-chart",versions.map(version=>({version,points:points(version,"replay","throughput_events_per_second")})),{logX:true,logY:true,xDomain:[1000,100000],xTicks:sizes,unit:"events / second",label:"Engine throughput scaling"});
    $("time-note").textContent=phase==="construction" && !["buildup","crowded","sweep"].includes(state().scenario)?"Construction is not separately defined for this mixed/cancellation stream; no value is invented.":phase==="parse_plus_replay"?"Sum of the two clocks from each repeat. Excludes final inspection, reporting and process startup.":"Incomplete attempts have no median here. Select raw records to inspect time limits and prefixes.";
    const rows=[];
    for(const n of sizes)for(const version of versions){const r=find(phase,version,{event_count:n});rows.push([numeric(comma(n)),ver(version),numeric(ms(r)),outcome(r)]);}
    table("scaling-table",["Events · M","Version","Median · ms","Saved repeats / outcome"],rows);
  }
  function liquidation() {
    const levels=+$("sell-levels").value,ratio=+$("sell-ratio").value;
    const sale=(v,n,p=levels)=>find("individual_sale",v,{scenario:"liquidation",seed:42,event_count:n,levels:p,sale_percent:ratio});
    lineChart("sell-chart",versions.map(version=>({version,points:sizes.map(n=>({x:n,y:sale(version,n)?.median_elapsed_seconds!=null?sale(version,n).median_elapsed_seconds*1000:null}))})),{logX:true,logY:true,xDomain:[1000,100000],xTicks:sizes,xLabel:"Initial bid orders · N",unit:"sell milliseconds",label:"Individual sell scaling on fresh bid books"});
    lineChart("concentration-chart",versions.map(version=>({version,points:[4,1000].map(p=>({x:p,y:sale(version,state().event_count,p)?.median_elapsed_seconds!=null?sale(version,state().event_count,p).median_elapsed_seconds*1000:null}))})),{logX:true,logY:true,xDomain:[4,1000],xTicks:[4,1000],xLabel:`Available prices · N=${comma(state().event_count)}`,unit:"sell milliseconds",label:"Price concentration comparison at fixed initial order count"});
    table("sell-table",["Version","Requested units","Fills / makers","Prices visited","Unfilled units","Build · ms (once)","Reset · ms","Sell · ms","Outcome"],versions.map(v=>{
      const n=state().event_count,r=sale(v,n),build=find("sell_template_construction",v,{scenario:"liquidation",seed:42,event_count:n,levels}),reset=find("sell_reset",v,{scenario:"liquidation",seed:42,event_count:n,levels,sale_percent:ratio});
      const attempt=D.raw.find(x=>x.phase==="individual_sale" && x.version===v && x.event_count===n && x.levels===levels && x.sale_percent===ratio);
      return [ver(v),numeric(comma(r?.requested_qty_units ?? attempt?.requested_qty_units)),numeric(comma(r?.fill_count)),numeric(comma(r?.price_levels_visited)),numeric(comma(r?.unfilled_qty_units)),numeric(ms(build)),numeric(ms(reset)),numeric(ms(r)),outcome(r)];
    }));
  }
  function latency() {
    const notes=[];
    const distributions=[];
    const allEdges=D.histogram_edges_us;
    for(const version of versions){
      const r=raw("latency",version);
      if(!r?.raw_file)continue;
      const hist=D.histograms[r.job_id];
      notes.push(`${version}: ${comma(hist.samples)} / ${comma(state().event_count)} events${r.status!=="completed"?' · partial prefix':''}`);
      const nonzero=hist.counts.map((n,i)=>n?i:-1).filter(i=>i>=0);
      if(nonzero.length){
        const first=Math.max(0,nonzero[0]-1),last=Math.min(hist.counts.length-1,nonzero[nonzero.length-1]+1);
        distributions.push({version,partial:r.status!=="completed",points:hist.counts.slice(first,last+1).map((n,j)=>{
          const i=j+first,lower=allEdges[i],upper=allEdges[i+1];
          return {x:lower?Math.sqrt(lower*upper):upper*.7,y:n/hist.samples*100};
        })});
      }
    }
    const xs=distributions.flatMap(s=>s.points.map(p=>p.x));
    const lo=xs.length?10**Math.floor(Math.log10(Math.min(...xs))):.1,hi=xs.length?10**Math.ceil(Math.log10(Math.max(...xs))):100;
    const ticks=[];for(let n=Math.log10(lo);n<=Math.log10(hi);n++)ticks.push(10**n);
    lineChart("latency-chart",distributions,{logX:true,xDomain:[lo,hi],xTicks:ticks,tickX:compact,xLabel:"Event processing latency · µs",unit:"% of observed events",label:"Log-binned distribution of individual event processing latency"});
    $("latency-note").textContent=notes.join(". ")+". Dashed series are incomplete prefixes. Frequency is normalized within each observed series.";
    lineChart("position-chart",versions.map(version=>({version,points:["early","late"].map((position,i)=>{
      const r=raw("latency_by_position",version,{position});
      return {x:i,y:r?.p99_seconds!=null?r.p99_seconds*1e6:null};
    }),partial:raw("latency",version)?.status!=="completed"})),{xDomain:[0,1],xTicks:[0,1],tickX:x=>x?"Last 10%":"First 10%",xLabel:"Position in original stream",unit:"P99 · microseconds",label:"Early versus late algorithm processing P99"});
    const rows=[];
    for(const version of versions)for(const kind of ["all","LIMIT","MARKET_SELL","CANCEL"]){
      const r=kind==="all"?raw("latency",version):raw("latency_by_type",version,{event_type:kind});if(!r)continue;
      rows.push([ver(version),kind,numeric(comma(r.samples)),numeric(decimal(r.median_seconds*1e6)),numeric(decimal(r.p95_seconds*1e6)),numeric(decimal(r.p99_seconds*1e6)),status(r.status)]);
    }
    table("latency-table",["Version","Event type","Observed events","Median · µs","P95 · µs","P99 · µs","Run status"],rows);
  }
  function memory() {
    const metric=$("memory-metric").value,notes=[];
    const series=versions.map(version=>{
      const r=raw("memory",version);
      if(r)notes.push(`${version}: ${comma(r.events_processed)} / ${comma(state().event_count)} events · ${r.status}`);
      return {version,partial:r?.status!=="completed",points:(r?.snapshots||[]).map(p=>({x:p.event_index,y:p[metric]/1048576}))};
    });
    const n=state().event_count;
    lineChart("memory-chart",series,{xDomain:[0,n],xTicks:[0,n/2,n],xLabel:"Completed event index",unit:"traced MiB",label:"Allocation checkpoints through selected stream"});
    $("memory-note").textContent=notes.join(". ")+". Dashed lines stop at observed prefixes; no extrapolation to M.";
    lineChart("churn-chart",versions.map(version=>({version,points:sizes.map(event_count=>{
      const r=find("memory",version,{scenario:"cancel_churn",event_count});
      return {x:event_count,y:r?.completed_repeats?r.traced_current_bytes/1024:null};
    })})),{logX:true,xDomain:[1000,100000],xTicks:sizes,unit:"final traced KiB",label:"Current traced memory after cancellation churn"});
    table("memory-table",["Version","Completed events","Current · bytes","Peak · bytes","Run status"],versions.map(v=>{
      const r=raw("memory",v);return [ver(v),numeric(comma(r?.events_processed)),numeric(comma(r?.traced_current_bytes)),numeric(comma(r?.traced_peak_bytes)),r?status(r.status):"not measured"];
    }));
  }
  function evidence() {
    table("correctness-table",["Check","Scope","Outcome"],[
      ["Independent expected-outcome and boundary tests",`${D.tests.count} tests`,status(D.tests.passed?"passed":"needs review")],
      ["A/B equivalence after every event","5 supplied files · 50,000 events",status(D.parity.files.every(x=>x.every_event_equal)?"passed":"needs review")],
      ["Completed benchmark final-book digests","Primary matrix + latency / memory runs",status(D.validation.status)],
      ["Independent liquidation fill oracle","All completed sales · exact fill sequence",status("passed")],
      ["Raw repeats, quantiles, source and input hashes",`${D.validation.primary_repeat_rows} primary attempts · ${comma(D.validation.latency_samples)} latency samples`,status(D.validation.status)]
    ]);
    $("bottleneck").innerHTML='<p>On the first 200 buildup events, A\'s live-ID scan line produces 20,300 trace events and its maker-scan loop 20,100; B\'s ID dictionary check line produces 200. This is separate line tracing, not timing or a CPU-instruction count. A repeatedly scans a growing active book even when no fills occur.</p><p>B need not win every operation: at seed 42, cancellation churn with 100,000 events takes about 106 ms for A and 110 ms for B. A single full-depth sale can also favor A\'s one sort and sequential pass over B\'s per-maker queue/index updates. Use N, occupied prices and fill count together.</p>';
    const million=D.raw.filter(r=>r.event_count===1000000 && ["replay","worker"].includes(r.phase));
    table("million-table",["Version","Phase","Repeat","Completed prefix","Observed elapsed · s","Status"],million.map(r=>[ver(r.version),r.phase,r.repeat,numeric(comma(r.events_processed)),numeric(decimal(r.elapsed_seconds,3)),status(r.status)]));
    const s=D.settings;
    $("environment").innerHTML=`<dl class="env"><dt>Runtime</dt><dd>${esc(s.python)}</dd><dt>Machine</dt><dd>${esc(s.operating_system)} · ${esc(s.logical_cpus)} logical CPUs. Exact model / physical RAM were unavailable in this run.</dd><dt>Dependencies</dt><dd>Python standard library only; dashboard has no external assets.</dd><dt>Limits</dt><dd>${s.phase_limit_seconds} seconds per measured phase; ${s.rss_limit_bytes/1048576} MiB whole-process RSS budget, checked approximately every 100ms.</dd><dt>Timing boundary</dt><dd>${esc(s.primary_scope)}</dd><dt>Memory boundary</dt><dd>${esc(s.memory_scope)}</dd><dt>Source data SHA-256</dt><dd class="code-list">${esc(D.raw_source_sha256)}</dd><dt>Git base commit</dt><dd class="code-list">${esc(s.git_base_commit)}<br>Work is uncommitted. This base commit does not contain the measured source files; their SHA-256 map is below.</dd><dt>Measured source files</dt><dd class="code-list">${Object.entries(s.code_sha256).map(([n,h])=>`${esc(n)}<br>${esc(h)}`).join("<br><br>")}</dd></dl>`;
    const stopped=D.raw.filter(r=>r.scenario===state().scenario && r.seed===state().seed && r.status!=="completed");
    table("stopped-table",["Version","M / N","Phase","Repeat","Completed events","Status"],stopped.map(r=>[r.version,numeric(comma(r.event_count)),r.phase,r.repeat,numeric(comma(r.events_processed)),status(r.status)]));
  }
  function rawRows() {
    const all=$("raw-all").checked,phase=$("raw-phase").value,desired=$("raw-status").value;
    return D.raw.filter(r=>(all || (r.scenario===state().scenario && r.seed===state().seed)) && (phase==="all"||r.phase===phase) && (desired==="all" || (desired==="completed"?r.status==="completed":r.status!=="completed")));
  }
  function renderRaw() {
    filteredRaw=rawRows();
    const pages=Math.max(1,Math.ceil(filteredRaw.length/30));rawPage=Math.min(rawPage,pages-1);
    const selected=filteredRaw.slice(rawPage*30,(rawPage+1)*30);
    table("raw-table",["Version","Scenario","Seed","M / N","Phase","Repeat","Sale %","Seconds","Peak trace · B","Status","Record"],selected.map(r=>[
      r.version,r.scenario,r.seed,numeric(comma(r.event_count)),r.phase,r.repeat,r.sale_percent??"—",numeric(decimal(r.elapsed_seconds,8)),numeric(comma(r.traced_peak_bytes)),status(r.status),markup(`<button class="details-button" type="button" data-index="${D.raw.indexOf(r)}">Details ↗</button>`)
    ]));
    $("raw-count").textContent=`${comma(filteredRaw.length)} saved records`;
    $("raw-page").textContent=`Page ${rawPage+1} / ${pages}`;
    $("previous").disabled=rawPage===0;$("next").disabled=rawPage>=pages-1;
  }
  function render() {
    const s=state(),meta=D.raw.find(r=>r.phase==="workload_metadata" && match(r,{scenario:s.scenario,seed:s.seed,event_count:s.event_count}));
    $("workload-context").textContent=meta?`M=${comma(s.event_count)} submitted events · peak active orders B=${comma(meta.active_order_peak)} · peak occupied price levels P=${comma(meta.price_level_peak)} · maker fills F=${comma(meta.fill_count)}. Synthetic single-venue teaching data.`:"No workload metadata for this selection.";
    scaling();liquidation();latency();memory();evidence();renderRaw();
  }
  const validation=D.validation;
  $("stats").innerHTML=[
    [`${validation.primary_statuses.completed} / ${validation.primary_repeat_rows}`,"completed replay attempts",`${validation.primary_statuses.stopped_time_limit || 0} reached the 5 s limit`],
    [String(D.tests.count),"correctness & boundary tests",D.tests.passed?"all passed":"needs review"],
    [`${(validation.latency_samples/1e6).toFixed(2)}M`,"saved event latencies","separate instrumentation runs"],
    [String(validation.primary_cases),"version / workload cases","5 scenarios · 3 sizes · 3 seeds · 2 versions"]
  ].map(([value,label,sub])=>`<div class="stat"><span class="number">${esc(value)}</span><span class="label">${esc(label)}</span><span class="sub">${esc(sub)}</span></div>`).join("");
  for(const value of [...new Set(D.raw.map(r=>r.phase))].sort()){
    const option=document.createElement("option");option.value=value;option.textContent=value;$("raw-phase").appendChild(option);
  }
  $("raw-phase").value="replay";
  for(const id of ["scenario","seed","size","phase","sell-levels","sell-ratio","memory-metric","raw-phase","raw-status","raw-all"]){$(id).addEventListener("change",()=>{rawPage=0;render();});}
  $("previous").addEventListener("click",()=>{rawPage--;renderRaw();});
  $("next").addEventListener("click",()=>{rawPage++;renderRaw();});
  $("raw-table").addEventListener("click",event=>{
    const target=event.target.closest("button[data-index]");if(!target)return;
    $("record-json").textContent=JSON.stringify(D.raw[+target.dataset.index],null,2);$("record-dialog").showModal();
  });
  $("close-dialog").addEventListener("click",()=>$("record-dialog").close());
  $("download").addEventListener("click",()=>{
    const fields=[...new Set(filteredRaw.flatMap(r=>Object.keys(r)))].filter(k=>!filteredRaw.some(r=>typeof r[k]==="object" && r[k]!==null)).sort();
    const quote=x=>'"'+String(x??"").replace(/"/g,'""')+'"';
    const csv=[fields.map(quote).join(","),...filteredRaw.map(r=>fields.map(k=>quote(r[k])).join(","))].join("\r\n");
    const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
    const link=document.createElement("a");link.href=url;link.download="lob-filtered-records.csv";link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  });
  // Read-only QA hook: exposes selection/counts, never an experiment entry point.
  window.LOB_DASHBOARD={state:()=>({...state()}),rawCount:()=>filteredRaw.length,sourceSha256:D.raw_source_sha256};
  let resizeTimer;
  window.addEventListener("resize",()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(render,100);});
  render();
})();
