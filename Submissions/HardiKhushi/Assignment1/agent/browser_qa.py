"""Exercise the offline dashboard in an existing Chrome, without network/downloads."""
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
CHROME=Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

PROBE=r"""
<script>
(async()=>{
 const checks=[]; let captured=null;
 function check(value,label){if(!value)throw Error(label);checks.push(label);}
 try{
  let states=0;
  for(const scenario of DATA.metadata.settings.scenarios)
  for(const seed of DATA.metadata.settings.seeds)
  for(const size of DATA.metadata.settings.sizes)
  for(const scale of ['linear','log']){
   for(const [id,value] of Object.entries({scenario,seed,size,scale}))$(id).value=value;
   APP.render(); states++;
   const samples=DATA.measurements.filter(r=>r.scenario===scenario&&r.seed===seed&&r.event_count===size&&r.version==='revised'&&r.phase==='replay'&&r.repeat>0&&r.status==='ok').map(r=>r.elapsed_seconds).sort((a,b)=>a-b);
   if(samples.length===5)check($('replay-value').textContent===`${fmt(samples[2],4)} s`,'raw median card '+states);
   check(!Array.from(document.querySelectorAll('svg path')).some(p=>/NaN|Infinity/.test(p.getAttribute('d'))),'finite chart coordinates '+states);
   check(Array.from(document.querySelectorAll('svg')).every(svg=>{const boxes=Array.from(svg.querySelectorAll('.x-tick')).map(t=>t.getBBox());return boxes.every((b,i)=>!i||boxes[i-1].x+boxes[i-1].width+1<=b.x);}), 'x-axis labels do not overlap '+states);
   check($('raw-table').rows.length>1,'raw measurement rows '+states);
   check(document.documentElement.scrollWidth<=window.innerWidth+1,'no page overflow '+states);
  }
  for(const levels of [4,1000])for(const sale of [10,100,200]){
   $('levels').value=levels;$('sale').value=sale;APP.render();
   check($('sell-table').rows.length>1,'liquidation outcomes '+levels+'/'+sale);
  }
  for(const phase of ['construction','application','parse']){
   $('phase').value=phase;APP.render();check($('construction-chart').textContent.length>0,'phase '+phase);
  }
  $('scenario').value=DATA.metadata.settings.scenarios[0];$('seed').value=DATA.metadata.settings.seeds[0];APP.render();
  const create=URL.createObjectURL,click=HTMLAnchorElement.prototype.click;
  URL.createObjectURL=blob=>{captured=blob;return create(blob);};
  HTMLAnchorElement.prototype.click=function(){};
  $('download').click();
  URL.createObjectURL=create;HTMLAnchorElement.prototype.click=click;
  check(captured instanceof Blob,'download produces Blob');
  const bytes=new Uint8Array(await captured.arrayBuffer()),parsed=JSON.parse(await captured.text());
  check(bytes[0]===91,'download JSON has no BOM');
  check(parsed.length===DATA.measurements.filter(r=>r.scenario===$('scenario').value&&r.seed===+$('seed').value).length,'download row count');
  check(window.__errors.length===0,'no JavaScript errors');
  const p=document.createElement('pre');p.id='qa-result';p.textContent=JSON.stringify({ok:true,states,checks:checks.length,width:window.innerWidth,download_rows:parsed.length});document.body.appendChild(p);
 }catch(error){const p=document.createElement('pre');p.id='qa-result';p.textContent=JSON.stringify({ok:false,error:String(error),checks:checks.length});document.body.appendChild(p);}
})();
</script>
"""


class Capture(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside=False
        self.text=""

    def handle_starttag(self,tag,attrs):
        if tag=="pre" and dict(attrs).get("id")=="qa-result": self.inside=True

    def handle_endtag(self,tag):
        if tag=="pre": self.inside=False

    def handle_data(self,data):
        if self.inside: self.text+=data


def main():
    if not CHROME.exists(): raise SystemExit("Existing macOS Google Chrome not found; no installation attempted")
    scratch=ROOT/".preview/browser"
    scratch.mkdir(parents=True,exist_ok=True)
    html=(ROOT/"dashboard.html").read_text()
    probe=scratch/"probe.html"
    probe.write_text(html.replace("</body>",PROBE+"</body>"))
    results=[]
    for width,height,label in ((1440,1100,"desktop"),(500,1100,"mobile")):
        base=[str(CHROME),"--headless","--disable-gpu","--no-first-run","--no-default-browser-check",
              "--disable-background-networking","--disable-extensions","--disable-sync","--disable-crash-reporter",
              "--no-sandbox","--allow-file-access-from-files",f"--user-data-dir={scratch/('profile-'+label)}",
              f"--crash-dumps-dir={scratch/'crashes'}",f"--window-size={width},{height}"]
        run=subprocess.run(base+["--virtual-time-budget=3000","--dump-dom",probe.as_uri()],
                           capture_output=True,text=True,timeout=45)
        (scratch/f"{label}.stderr").write_text(run.stderr)
        assert run.returncode==0,f"Chrome failed ({run.returncode}); see ignored stderr"
        capture=Capture();capture.feed(run.stdout)
        assert capture.text,"No browser probe result"
        result=json.loads(capture.text)
        assert result["ok"],result
        assert result["width"]==width,"Chrome viewport differs from requested screenshot width"
        result["viewport"]=label
        shot=scratch/f"{label}.png"
        screenshot=subprocess.run(base+["--hide-scrollbars",f"--screenshot={shot}",(ROOT/"dashboard.html").as_uri()],
                                  capture_output=True,text=True,timeout=30)
        assert screenshot.returncode==0 and shot.exists(),"Screenshot failed"
        result["screenshot_sha256"]=hashlib.sha256(shot.read_bytes()).hexdigest()
        lower=scratch/f"lower-{label}.html"
        offset=1250 if label=="desktop" else 3000
        lower.write_text(html.replace("</head>",f"<style>main{{position:relative;top:-{offset}px}}</style></head>"))
        lower_shot=scratch/f"lower-{label}.png"
        capture_lower=subprocess.run(base+["--hide-scrollbars","--virtual-time-budget=500",
            f"--screenshot={lower_shot}",lower.as_uri()],capture_output=True,text=True,timeout=30)
        assert capture_lower.returncode==0 and lower_shot.exists()
        result["lower_screenshot_sha256"]=hashlib.sha256(lower_shot.read_bytes()).hexdigest()
        results.append(result)
    evidence=dict(browser="existing macOS Google Chrome, headless",html_sha256=hashlib.sha256(
        (ROOT/"dashboard.html").read_bytes()).hexdigest(),no_external_download=True,results=results,
        screenshots=".preview/browser/ (ignored, visually inspected separately)")
    (ROOT/"results/evidence/browser_qa.json").write_text(json.dumps(evidence,indent=2)+"\n")
    print(json.dumps(evidence,indent=2))


if __name__=="__main__":
    main()
