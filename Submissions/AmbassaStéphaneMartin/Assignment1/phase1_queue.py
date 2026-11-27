"""Sequential remaining mandatory cases, with external command wall clocks."""
from datetime import datetime,timezone
import json,queue,subprocess,sys,threading,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
GROUP=ROOT/"results"/"phase1_final"
GROUP.mkdir(parents=True,exist_ok=True)
stage=sys.argv[1]
jobs=[]
if stage=="replay":
    for seed in (43,44):
        jobs.append((f"final_revised_100000_s{seed}",["benchmark.py","run","--counts","100000","--seeds",str(seed),
            "--scenarios","buildup","crowded","mixed","sweep","cancel_churn","--experiments","replay",
            "--versions","revised","--levels","1000","--worker-seconds","60","--campaign-seconds","900",
            "--label","final-revised-replay"]))
elif stage=="controlled":
    for count in (1000,10000,100000):
        for seed in (42,43,44):
            for experiment,levels,percent in ([("market-sell",1000,p) for p in (10,100,200)]
                    +[("queue-concentration",p,100) for p in (4,1000)]+[("cancel-churn",1,None)]):
                name=f"final_{experiment}_n{count}_s{seed}_l{levels}_p{percent}"
                command=["phase1_campaign.py","--count",str(count),"--seed",str(seed),"--experiment",experiment,"--levels",str(levels)]
                if experiment=="market-sell":command+=["--sale-percent",str(percent)]
                jobs.append((name,command))
elif stage=="corrected":
    jobs.append(("final_corrected_market_sell_n1000_s42_p10",["phase1_campaign.py","--count","1000","--seed","42",
        "--experiment","market-sell","--levels","1000","--sale-percent","10"]))
elif stage=="optional":
    jobs.append(("phase1_final/optional_million_mixed",["benchmark.py","run","--counts","1000000","--seeds","42",
        "--scenarios","mixed","--experiments","replay","--versions","baseline","revised","--levels","1000",
        "--worker-seconds","60","--campaign-seconds","900","--data-dir",str(ROOT/".cache"/"optional_million"),
        "--label","optional-million-limit-probe"]))
else:raise SystemExit("Unknown stage")
outcomes=[]
for name,command in jobs:
    out=ROOT/"results"/name
    if out.exists():
        if (out/"command_wall_time.json").exists():
            old=json.loads((out/"command_wall_time.json").read_text())
            outcomes.append(dict(name=name,**old));continue
        raise SystemExit(f"Incomplete existing output requires review: {out}")
    command=[sys.executable,"-B",*command,"--out",str(out)]
    start=time.perf_counter();started=datetime.now(timezone.utc).isoformat()
    process=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                             encoding="utf-8",errors="replace",bufsize=1)
    q=queue.Queue()
    def reader():
        for line in process.stdout:q.put(line)
        q.put(None)
    threading.Thread(target=reader,daemon=True).start()
    lines=[];progress=[];previous=start
    print("START "+name,flush=True)
    while True:
        try:line=q.get(timeout=20)
        except queue.Empty:
            print(f"WAIT {name} {time.perf_counter()-start:.1f}s",flush=True);continue
        if line is None:break
        now=time.perf_counter();lines.append(line)
        if line.startswith("["):
            progress.append(dict(line=line.strip(),elapsed_seconds=now-start,interval_seconds=now-previous));previous=now
        print(name+" "+line,end="",flush=True)
    code=process.wait();elapsed=time.perf_counter()-start
    record=dict(command=command,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),
        exit_code=code,total_command_wall_seconds=elapsed,progress=progress,
        boundary="Process creation through exit, including preparation/all phases; excludes tests and audit.")
    if not out.is_dir():raise SystemExit("Command failed before producing results")
    (out/"command_wall_time.json").write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    (out/"command_output.txt").write_text("".join(lines),encoding="utf-8")
    raw=[json.loads(l) for l in (out/"raw.jsonl").read_text().splitlines()]
    errors=[r for r in raw if r["status"]=="error"]
    m=json.loads((out/"manifest.json").read_text())
    mismatches=[r for r in m["diagnostic_comparisons"] if r["status"]!="passed"]
    outcomes.append(dict(name=name,**record))
    (GROUP/(stage+"_execution.json")).write_text(json.dumps(outcomes,indent=2)+"\n",encoding="utf-8")
    print("OUTCOME "+json.dumps(dict(name=name,exit_code=code,wall_seconds=elapsed,errors=len(errors),mismatches=mismatches)),flush=True)
    if code not in (0,2) or errors or mismatches:raise SystemExit("Execution error/mismatch requires review")
print("STAGE_FINISHED "+stage,flush=True)

