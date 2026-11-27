"""Inspect the local running dashboard with headless Chrome; no publication."""
import base64,json,os,subprocess,time,urllib.request
from pathlib import Path
from websockets.sync.client import connect
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"/"phase1_final"

def read_url(url):
    with urllib.request.urlopen(url,timeout=10) as r:return r.read()

def run():
    address="http://127.0.0.1:8501"
    assert read_url(address+"/_stcore/health")==b"ok"
    profile=ROOT/".cache"/("browser_"+str(time.time_ns()))
    if profile.exists():raise RuntimeError("Use a new browser profile directory")
    chrome=Path(os.environ["ProgramFiles"])/"Google"/"Chrome"/"Application"/"chrome.exe"
    process=subprocess.Popen([str(chrome),"--headless=new","--remote-debugging-port=0",
        "--user-data-dir="+str(profile),"--no-first-run","--no-default-browser-check",
        "--window-size=1600,1200",address],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline=time.perf_counter()+60
        while not (profile/"DevToolsActivePort").exists():
            if time.perf_counter()>deadline:raise TimeoutError("Chrome did not expose its local debug endpoint")
            time.sleep(.25)
        port=(profile/"DevToolsActivePort").read_text().splitlines()[0]
        tabs=json.loads(read_url("http://127.0.0.1:"+port+"/json/list"))
        target=next(t for t in tabs if t["type"]=="page")
        with connect(target["webSocketDebuggerUrl"],max_size=32*1024**2) as socket:
            counter=0
            def call(method,params=None):
                nonlocal counter
                counter+=1;socket.send(json.dumps(dict(id=counter,method=method,params=params or {})))
                while True:
                    value=json.loads(socket.recv(timeout=30))
                    if value.get("id")==counter:
                        assert "error" not in value,value
                        return value.get("result",{})
            def evaluate(expression):
                value=call("Runtime.evaluate",dict(expression=expression,returnByValue=True,awaitPromise=True))
                assert "exceptionDetails" not in value,value
                return value["result"].get("value")
            while True:
                body=evaluate("document.body.innerText")
                ready=evaluate("document.querySelectorAll('[role=tab]').length >= 5 && document.querySelectorAll('img').length > 0")
                if "BTC order book" in body and "Completed groups" in body and ready:break
                if time.perf_counter()>deadline:raise TimeoutError(body)
                time.sleep(.5)
            assert "Traceback" not in body
            screenshots=[];panels=[]
            for label in ("Scaling","Memory and cleanup","Sales and correctness","Coverage and provenance"):
                expression="Array.from(document.querySelectorAll('[role=tab]')).find(x=>x.textContent.trim()==="+json.dumps(label)+").click()"
                evaluate(expression)
                visible="Array.from(document.querySelectorAll('img')).filter(x=>{const r=x.getBoundingClientRect();return r.width>0&&r.bottom>0&&r.top<innerHeight})"
                marker={"Scaling":"Construction, replay / individual sale", "Memory and cleanup":"Separate-process tracemalloc",
                    "Sales and correctness":"Independent expected tests supplement", "Coverage and provenance":"Complete identity includes"}[label]
                readiness="(()=>{const selected=document.querySelector('[role=tab][aria-selected=true]');const images="+visible+";return selected&&selected.textContent.trim()==="+json.dumps(label)+"&&document.body.innerText.includes("+json.dumps(marker)+")&&images.every(x=>x.complete&&x.naturalWidth>0)"
                if label in ("Scaling","Memory and cleanup"):readiness+="&&images.length>0"
                readiness+="})()"
                ready_deadline=time.perf_counter()+30
                while not evaluate(readiness):
                    if time.perf_counter()>ready_deadline:raise TimeoutError("Visible tab images did not load: "+label)
                    time.sleep(.25)
                evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
                panels.append(dict(tab=label,visible_images=evaluate(visible+".map(x=>({width:x.naturalWidth,height:x.naturalHeight}))"),
                    visible_text=evaluate("document.body.innerText")))
                screenshot=call("Page.captureScreenshot",dict(format="png",captureBeyondViewport=False))
                name="dashboard_"+label.lower().replace(" ","_")+".png"
                (OUT/name).write_bytes(base64.b64decode(screenshot["data"]))
                screenshots.append(name)
            result=dict(status="passed",address=address,health="ok",browser=call("Browser.getVersion"),title=evaluate("document.title"),
                screenshots=screenshots,panels=panels,initial_visible_text=body,
                note="Local headless Chromium inspection; benchmarks were not running.")
            (OUT/"browser_check.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
            print(json.dumps({k:v for k,v in result.items() if k not in ("initial_visible_text","panels")}))
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
if __name__=="__main__":run()
