"""Run only the planned missing Baseline cases, sequentially, with unchanged CLI."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time

GROUP=Path(__file__).resolve().parent
ROOT=GROUP.parent.parent
plan=json.loads((GROUP/"plan.json").read_text(encoding="utf-8"))
assert plan["tests"]["exit_code"]==0
state=dict(status="running",started_utc=datetime.now(timezone.utc).isoformat(),outcomes=[])
pattern=re.compile(r"^\[(\d+)/(\d+)\]\s+(\S+)\s+(shared|baseline)\s+(\w+):\s+(\w+)$")

def save(path,value):
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
    tmp.replace(path)

for job in plan["jobs"]:
    for name,expected in plan["preservation"]["source_sha256"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==expected,name
    out=ROOT/"results"/job["name"]
    if out.exists():
        raise SystemExit(f"Refusing to overwrite existing run: {out}")
    command=[sys.executable,"-B","benchmark.py","run","--counts","100000","--seeds",str(job["seed"]),
        "--scenarios",job["scenario"],"--experiments","replay","--versions","baseline","--levels","1000",
        "--out",str(out),"--worker-seconds","60","--campaign-seconds","900","--label","missing-baseline-100000"]
    print("START "+json.dumps(job),flush=True)
    started=datetime.now(timezone.utc).isoformat()
    begin=previous=time.perf_counter()
    child=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
        text=True,encoding="utf-8",errors="replace",bufsize=1)
    messages=queue.Queue()
    def reader():
        for line in child.stdout:
            messages.put(line)
        messages.put(None)
    threading.Thread(target=reader,daemon=True).start()
    lines=[]
    progress=[]
    while True:
        try:
            line=messages.get(timeout=20)
        except queue.Empty:
            print(f"WAIT seed={job['seed']} scenario={job['scenario']} command_elapsed={time.perf_counter()-begin:.1f}s",flush=True)
            continue
        if line is None:break
        now=time.perf_counter()
        lines.append(line)
        matched=pattern.match(line.strip())
        if matched:
            index,total,case,version,phase,status=matched.groups()
            progress.append(dict(job_index=int(index),total_jobs=int(total),case_id=case,
                version=None if version=="shared" else version,phase=phase,status=status,
                elapsed_command_seconds=now-begin,interval_since_previous_progress_seconds=now-previous))
            previous=now
        print(f"{job['seed']}/{job['scenario']} "+line,end="",flush=True)
    code=child.wait()
    elapsed=time.perf_counter()-begin
    wall=dict(command=command,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),
        exit_code=code,total_command_wall_seconds=elapsed,progress=progress,
        boundary="External perf_counter: process creation through exit; includes preparation, loading, warm-up, repetitions and all phases; excludes tests/audit/report.",
        interval_boundary="Observed intervals between stdout job completions include parent/checkpoint overhead; first also includes preparation. These are not single-replay times.",
        limits=plan["limits"])
    if not out.is_dir():
        state.update(status="failed",error="Runner failed before creating output")
        save(GROUP/"execution.json",state)
        raise SystemExit(3)
    save(out/"command_wall_time.json",wall)
    (out/"command_output.txt").write_text("".join(lines),encoding="utf-8")
    raw_path=out/"raw.jsonl"
    if not raw_path.exists():
        state.update(status="failed",error="Runner did not export measurements")
        save(GROUP/"execution.json",state)
        raise SystemExit(3)
    raw=[json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    errors=[r for r in raw if r["status"]=="error"]
    manifest=json.loads((out/"manifest.json").read_text(encoding="utf-8"))
    mismatches=[r for r in manifest["diagnostic_comparisons"] if r["status"]!="passed"]
    outcome=dict(**job,exit_code=code,total_command_wall_seconds=elapsed,
        status="failed" if errors or mismatches or code not in (0,2) else "completed" if code==0 else "stopped",
        errors=errors,diagnostic_mismatches=mismatches)
    state["outcomes"].append(outcome)
    save(GROUP/"execution.json",state)
    print("OUTCOME "+json.dumps(outcome),flush=True)
    if outcome["status"]=="failed":
        state["status"]="failed"
        save(GROUP/"execution.json",state)
        raise SystemExit(3)
state.update(status="finished",finished_utc=datetime.now(timezone.utc).isoformat(),
    total_command_wall_seconds=sum(o["total_command_wall_seconds"] for o in state["outcomes"]))
save(GROUP/"execution.json",state)
print("ALL_BASELINE_ATTEMPTS_FINISHED "+json.dumps(state),flush=True)

