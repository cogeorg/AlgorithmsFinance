// Local Chrome DevTools pipe: no server, network access or package dependency.
import {spawn} from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath,pathToFileURL} from "node:url";
import {createHash} from "node:crypto";
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const work=path.join(root,"work/dashboard-qa");fs.mkdirSync(work,{recursive:true});
const browser=spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",[
  "--headless","--no-sandbox","--disable-gpu","--no-first-run","--disable-background-networking",
  "--disable-component-update","--disable-default-apps","--disable-sync","--disable-breakpad",
  "--disable-crash-reporter","--remote-debugging-pipe",`--user-data-dir=${work}/profile`,"about:blank"
],{stdio:["ignore","pipe","pipe","pipe","pipe"]});
let next=1,buffer="",stderr="";
const pending=new Map(),errors=[];
browser.stderr.on("data",chunk=>{stderr+=chunk.toString();});
browser.stdio[4].on("data",chunk=>{
  buffer+=chunk.toString();
  let end;
  while((end=buffer.indexOf("\0"))>=0){
    const text=buffer.slice(0,end);buffer=buffer.slice(end+1);if(!text)continue;
    const message=JSON.parse(text);
    if(message.id && pending.has(message.id)){
      const p=pending.get(message.id);pending.delete(message.id);clearTimeout(p.timer);
      message.error?p.reject(new Error(JSON.stringify(message.error))):p.resolve(message.result);
    }else if(message.method==="Runtime.exceptionThrown")errors.push(message.params.exceptionDetails);
  }
});
browser.on("exit",(code,signal)=>{
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(new Error(`Chrome exit ${code}/${signal}: ${stderr.slice(-2500)}`));}
  pending.clear();
});
function command(method,params={},sessionId){
  return new Promise((resolve,reject)=>{
    const id=next++,timer=setTimeout(()=>{pending.delete(id);reject(new Error(`CDP timeout: ${method}; ${stderr.slice(-2000)}`));},60000);
    pending.set(id,{resolve,reject,timer});
    browser.stdio[3].write(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})})+"\0");
  });
}
function check(condition,message){if(!condition)throw new Error(message);}
let session;
const evaluate=async expression=>{
  const result=await command("Runtime.evaluate",{expression,returnByValue:true,awaitPromise:true},session);
  if(result.exceptionDetails)throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
};
try{
  const {targetId}=await command("Target.createTarget",{url:"about:blank"});
  ({sessionId:session}=await command("Target.attachToTarget",{targetId,flatten:true}));
  await command("Page.enable",{},session);await command("Runtime.enable",{},session);
  await command("Emulation.setDeviceMetricsOverride",{width:1440,height:1050,deviceScaleFactor:1,mobile:false},session);
  await command("Page.navigate",{url:pathToFileURL(path.join(root,"dashboard.html")).href},session);
  let ready=false;
  for(let i=0;i<80;i++){
    ready=await evaluate("!!window.LOB_DASHBOARD");if(ready)break;
    await new Promise(resolve=>setTimeout(resolve,100));
  }
  check(ready,"Dashboard did not initialize");
  const initial=await evaluate(`({charts:document.querySelectorAll('.chart svg').length,state:LOB_DASHBOARD.state(),raw:LOB_DASHBOARD.rawCount(),overflow:document.documentElement.scrollWidth>innerWidth+1,bad:/NaN|undefined|Infinity/.test(document.body.innerText)})`);
  check(initial.charts===8,"Expected eight populated initial charts");check(!initial.bad,"Invalid numeric labels");check(!initial.overflow,"Desktop root overflow");
  const unitLabels=await evaluate(`(()=>{const h=[...document.querySelectorAll('#latency-table th')].find(e=>e.textContent.includes('µs'));return !!h&&getComputedStyle(h).textTransform==='none'})()`);
  check(unitLabels,"Case-sensitive unit labels must not be transformed to uppercase");
  const sweep=await evaluate(`(()=>{let cases=0;for(const scenario of ['buildup','crowded','mixed','sweep','cancel_churn'])for(const seed of [42,43,44])for(const size of [1000,10000,100000])for(const phase of ['replay','construction','input_parse','parse_plus_replay']){document.getElementById('scenario').value=scenario;document.getElementById('seed').value=seed;document.getElementById('size').value=size;document.getElementById('phase').value=phase;document.getElementById('phase').dispatchEvent(new Event('change'));if(/NaN|undefined|Infinity/.test(document.body.innerText))throw Error('Invalid label '+[scenario,seed,size,phase]);cases++;}return cases})()`);
  check(sweep===180,"Filter sweep incomplete");
  const sellCases=await evaluate(`(()=>{let cases=0;const data=JSON.parse(document.getElementById('saved-data').textContent);for(const n of [1000,10000,100000])for(const levels of [4,1000])for(const ratio of [10,100,200]){document.getElementById('size').value=n;document.getElementById('sell-levels').value=levels;document.getElementById('sell-ratio').value=ratio;document.getElementById('sell-ratio').dispatchEvent(new Event('change'));const expected=data.summary.find(r=>r.phase==='individual_sale'&&r.version==='B'&&r.event_count===n&&r.levels===levels&&r.sale_percent===ratio);const cells=document.querySelectorAll('#sell-table tbody tr')[1].querySelectorAll('td');if(cells[1].textContent!==expected.requested_qty_units.toLocaleString('en-US'))throw Error('Sale quantity filter mismatch');if(Math.abs(Number(cells[7].textContent.replaceAll(',',''))-expected.median_elapsed_seconds*1000)>.00051)throw Error('Sale time unit/filter mismatch');cases++;}return cases})()`);
  check(sellCases===18,"Sale filter sweep incomplete");
  await evaluate(`(()=>{document.getElementById('raw-all').checked=true;document.getElementById('raw-phase').value='all';document.getElementById('raw-status').value='stopped';document.getElementById('raw-status').dispatchEvent(new Event('change'));const d=JSON.parse(document.getElementById('saved-data').textContent);if(LOB_DASHBOARD.rawCount()!==d.raw.filter(r=>r.status!=='completed').length)throw Error('Stopped/all-scope filter mismatch');})()`);
  await evaluate(`(()=>{const values={scenario:'mixed',seed:'42',size:'10000',phase:'replay','sell-levels':'1000','sell-ratio':'100','memory-metric':'traced_current_bytes','raw-phase':'replay','raw-status':'all'};for(const [id,value] of Object.entries(values))document.getElementById(id).value=value;document.getElementById('raw-all').checked=false;document.getElementById('scenario').dispatchEvent(new Event('change'));})()`);
  const selected=await evaluate(`({count:LOB_DASHBOARD.rawCount(),first:document.getElementById('raw-table').innerText})`);
  check(selected.count===40,"Expected 30 main replay records plus 10 optional-million placeholders/attempts");
  await evaluate("document.getElementById('next').click()");
  check(await evaluate("document.getElementById('raw-table').querySelectorAll('tbody tr').length===10"),"Second page should contain remaining 10 records");
  await evaluate("document.getElementById('previous').click()");
  const memorySwitch=await evaluate(`(()=>{const before=document.getElementById('memory-chart').innerHTML;document.getElementById('memory-metric').value='traced_peak_bytes';document.getElementById('memory-metric').dispatchEvent(new Event('change'));const changed=before!==document.getElementById('memory-chart').innerHTML;document.getElementById('memory-metric').value='traced_current_bytes';document.getElementById('memory-metric').dispatchEvent(new Event('change'));return changed})()`);
  check(memorySwitch,"Memory current/peak control did not update chart");
  await evaluate("document.querySelector('#raw-table button[data-index]').click()");
  check(await evaluate("document.getElementById('record-dialog').open"),"Details dialog failed");
  check(await evaluate("JSON.parse(document.getElementById('record-json').textContent).phase==='replay'"),"Wrong raw detail record");
  await evaluate("document.getElementById('close-dialog').click()");
  const downloads=path.join(work,"downloads");fs.mkdirSync(downloads,{recursive:true});
  const download=path.join(downloads,"lob-filtered-records.csv");
  fs.rmSync(download,{force:true});
  await command("Browser.setDownloadBehavior",{behavior:"allow",downloadPath:downloads});
  await evaluate("document.getElementById('download').click()");
  for(let i=0;i<60 && !fs.existsSync(download);i++)await new Promise(resolve=>setTimeout(resolve,100));
  check(fs.existsSync(download),"CSV download missing");
  check(fs.readFileSync(download,"utf8").split(/\r?\n/).length===41,"CSV download row count differs from filter");
  async function screenshot(name,y,height,width=1440){
    const result=await command("Page.captureScreenshot",{format:"png",captureBeyondViewport:true,clip:{x:0,y,width,height,scale:1}},session);
    const file=path.join(work,name+".png");fs.writeFileSync(file,Buffer.from(result.data,"base64"));return file;
  }
  const screenshots=[];
  screenshots.push(await screenshot("desktop-overview",0,1150));
  const memoryY=await evaluate("document.getElementById('memory').getBoundingClientRect().top+scrollY");
  screenshots.push(await screenshot("desktop-memory",memoryY,1050));
  for(const section of ["liquidation","latency"]){
    const y=await evaluate(`document.getElementById('${section}').getBoundingClientRect().top+scrollY`);
    screenshots.push(await screenshot("desktop-"+section,y,1000));
  }
  await command("Emulation.setDeviceMetricsOverride",{width:390,height:844,deviceScaleFactor:1,mobile:true},session);
  await new Promise(resolve=>setTimeout(resolve,250));
  const mobile=await evaluate("({overflow:document.documentElement.scrollWidth>innerWidth+1,width:innerWidth,charts:document.querySelectorAll('.chart svg').length})");
  check(!mobile.overflow,"Mobile root overflow");check(mobile.charts===8,"Mobile charts missing");
  screenshots.push(await screenshot("mobile-overview",0,1550,390));
  check(errors.length===0,"Browser JavaScript exceptions: "+JSON.stringify(errors));
  const sha=createHash("sha256").update(fs.readFileSync(path.join(root,"dashboard.html"))).digest("hex");
  const result={status:"passed",browser:"local Chrome headless via DevTools pipe",dashboard_sha256:sha,unit_labels_preserve_case:unitLabels,filter_combinations:sweep,sale_filter_combinations:sellCases,memory_metric_switch:memorySwitch,pagination:true,stopped_and_all_scope_filters:true,initial_state:initial,mobile,raw_filter_count:40,csv_download_records:40,details_dialog:true,javascript_exceptions:errors,screenshots};
  fs.writeFileSync(path.join(root,"evidence/dashboard_browser_qa.json"),JSON.stringify(result,null,2)+"\n");
  console.log(JSON.stringify(result,null,2));
}finally{
  fs.writeFileSync(path.join(work,"chrome.stderr.log"),stderr);
  browser.kill();
}
