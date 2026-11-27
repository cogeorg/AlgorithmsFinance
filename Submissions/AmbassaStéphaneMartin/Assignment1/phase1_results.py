"""Audit all saved experiments and export immutable-provenance dashboard data."""
from collections import defaultdict,Counter
import hashlib,json,math,re,statistics
from pathlib import Path
import benchmark as bm
import benchmark_report as legacy

ROOT=Path(__file__).resolve().parent
FINAL=ROOT/"results"/"phase1_final"

def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def rows(p):return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines()]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def identity(r):
    return tuple(r.get(k) for k in ("experiment","scenario","requested_count","event_count","seed","levels","sale_percent","version","phase"))
def digest(value,compact=False):
    return hashlib.sha256(json.dumps(value,sort_keys=True,**({"separators":(",",":")} if compact else {})).encode()).hexdigest()

def sale_oracle(events,percent):
    depth=sum(e["qty_units"] for e in events)
    quantity=(depth*percent+99)//100
    remaining=quantity;fills=[];active=[]
    h=hashlib.sha256()
    for e in events:
        result=dict(event_id=e["event_id"],order_id=e["order_id"],status="resting",
                    unfilled_qty_units=e["qty_units"],fills=[])
        h.update((json.dumps(result,sort_keys=True,separators=(",",":"))+"\n").encode())
    previous=None;levels=0
    for e in sorted(events,key=lambda e:(-e["price_ticks"],e["seq"])):
        q=min(remaining,e["qty_units"])
        if q:
            fills.append(dict(maker_id=e["order_id"],taker_id="measured-sale",price_ticks=e["price_ticks"],qty_units=q))
            if previous!=e["price_ticks"]:levels+=1;previous=e["price_ticks"]
            remaining-=q
        if e["qty_units"]>q:
            active.append(dict(order_id=e["order_id"],side="BUY",price_ticks=e["price_ticks"],
                               qty_units=e["qty_units"]-q,arrival_seq=e["seq"]))
    result=dict(event_id="measured-sale",order_id="measured-sale",
                status="filled" if remaining==0 else "partial" if fills else "unfilled",
                unfilled_qty_units=remaining,fills=fills)
    h.update((json.dumps(result,sort_keys=True,separators=(",",":"))+"\n").encode())
    assert quantity==sum(f["qty_units"] for f in fills)+remaining
    return dict(requested_sale_qty_units=quantity,fill_count=len(fills),price_levels_visited=levels,
                unfilled_qty_units=remaining,result_digest=h.hexdigest(),
                snapshot_digest=digest(dict(bids=active,asks=[])),ordered_fills_sha256=digest(fills,True))

def samples(record):
    path=record.get("latency_samples_path")
    return read(legacy.saved_path(path))["samples"] if path else []

def diagnostic_pair(left,right):
    """Check available diagnostics even when primary timing did not complete."""
    if not left or not right or any(r["state"]!="completed" for r in (left,right)):
        return dict(status="unavailable",reason="Both completed diagnostic groups are required")
    if identity(left)[:-2]!=identity(right)[:-2] or left["workload_sha256"]!=right["workload_sha256"]:
        return dict(status="incomparable",reason="Case identity or input differs")
    if left["protocol"]!=right["protocol"]:
        return dict(status="incomparable",reason="Recorded measured code or execution protocol differs")
    fields=("result_digest","snapshot_digest","fill_count","price_levels_visited","unfilled_qty_units",
        "cancelled_qty_units","rejected_event_count","active_orders_peak","occupied_prices_peak",
        "active_orders_final","occupied_prices_final")
    if not left.get("result_digest") or not left.get("snapshot_digest"):
        return dict(status="unavailable",reason="Diagnostic digests are missing")
    different=[f for f in fields if left.get(f)!=right.get(f)]
    return dict(status="mismatch" if different else "matching",different_fields=different)

def nonprice_signature(events):
    """Hold quantities, identifiers and arrival order fixed across concentration cases."""
    h=hashlib.sha256()
    for e in events:
        h.update((json.dumps({k:v for k,v in e.items() if k!="price_ticks"},sort_keys=True)+"\n").encode())
    return h.hexdigest()

def build():
    selected={};invalid=[];oracles={};datasets={};all_records=[];source_fingerprints={};concentration={};source_checks={}
    corrections=read(FINAL/"provenance_corrections.json") if (FINAL/"provenance_corrections.json").exists() else {}
    excluded={r["directory"] for r in corrections.get("excluded_runs",[])}
    for mpath in sorted((ROOT/"results").glob("*/manifest.json")):
        m=read(mpath);rawpath=mpath.parent/"raw.jsonl";sp=mpath.parent/"summaries.jsonl"
        if not rawpath.exists() or not sp.exists():
            invalid.append(dict(path=str(mpath),error="Missing exports"));continue
        raw=rows(rawpath);summaries=rows(sp);groups=defaultdict(list)
        for r in raw:groups[(r["case_id"],r["version"],r["phase"])].append(r)
        wall=read(mpath.parent/"command_wall_time.json") if (mpath.parent/"command_wall_time.json").exists() else {}
        times={}
        for p in wall.get("progress",[]):
            if "case_id" in p:
                times[(p["case_id"],p["version"],p["phase"])]=p["interval_since_previous_progress_seconds"]
            else:
                match=re.match(r"^\[\d+/\d+\]\s+(\S+)\s+(shared|baseline|revised)\s+(\w+):",p["line"])
                if match:
                    c,v,phase=match.groups();times[(c,None if v=="shared" else v,phase)]=p["interval_seconds"]
        cases={c["case_id"]:c for c in m["workloads"]}
        for r in summaries:
            try:
                c=cases[r["case_id"]];source=legacy.saved_path(c["source"]["path"])
                if source not in datasets:
                    if len(datasets)>1:datasets.pop(next(iter(datasets)))
                    events,io=bm.load_events(source,128*1024**2,c["source_event_count"])
                    datasets[source]=(events,sha(source),io)
                events,fingerprint,io=datasets[source]
                assert fingerprint==r["workload_sha256"]==c["source"]["sha256"]
                assert c["source"]["metadata"]["sha256"]==fingerprint
                assert bm.metadata_matches(c["source"]["metadata"],c)
                if c["sale_percent"] is not None:
                    assert c["construction_event_count"]==len(events)==c["requested_count"]
                    assert c["event_count"]==len(events)+1
                else:
                    assert c["event_count"]==len(events)
                    assert len(events)==(2*c["requested_count"]+2 if c["experiment"]=="cancel-churn" else c["requested_count"])
                if c["sale_percent"] is not None and fingerprint not in source_checks:
                    assert all(e["type"]=="LIMIT" and e["side"]=="BUY" for e in events)
                    assert len({e["price_ticks"] for e in events})==c["actual_controlled_price_levels"]
                    source_checks[fingerprint]=nonprice_signature(events)
                if c["experiment"]=="queue-concentration":
                    concentration.setdefault((c["requested_count"],c["seed"]),{})[c["levels"]]=source_checks[fingerprint]
                group=groups[(r["case_id"],r["version"],r["phase"])]
                state=legacy.classify(r,group,times.get((r["case_id"],r["version"],r["phase"])))
                processed=1 if c["sale_percent"] is not None else len(events)
                for v in group:
                    if v["status"]!="complete":continue
                    if v["phase"]=="timing":
                        assert v["processed_events"]==processed
                        assert math.isclose(v["throughput_events_per_second"],processed/v["replay_seconds"],rel_tol=1e-12)
                        assert math.isclose(v["total_compute_seconds"],sum(v[k] or 0 for k in
                            ("initialization_seconds","construction_seconds","replay_seconds")),rel_tol=1e-12)
                    if v["phase"]=="io":
                        assert math.isclose(v["io_total_seconds"],sum(v[k] or 0 for k in
                            ("read_seconds","decompress_seconds","parse_seconds")),rel_tol=1e-12)
                        assert v["compressed_bytes"]==io["compressed_bytes"] and v["decoded_bytes"]==io["decoded_bytes"]
                    if v["phase"]=="memory":assert v["memory_peak_bytes"]>=v["memory_current_bytes"]>=0
                    if v["phase"]=="diagnostics":assert v["rejected_event_count"]==0
                    for field in bm.METRICS:
                        value=v.get(field)
                        assert value is None or (type(value) in (int,float) and math.isfinite(value)),field
                    if v["phase"] in ("timing","memory","diagnostics"):
                        assert v["processed_events"]==processed
                    if c["experiment"]=="cancel-churn" and v["phase"]=="memory":
                        assert v["memory_after_cancellation_bytes"]==v["memory_current_bytes"]
                        assert v["memory_before_final_cancel_bytes"]>=0
                    if c["experiment"]=="cancel-churn" and v["phase"]=="diagnostics":
                        assert v["active_orders_before_final_cancel"]==1
                        assert v["active_orders_final"]==v["retained_queue_entries_final"]==0
                        if v["version"]=="revised":
                            assert v["retained_queue_entries_before_final_cancel"]<=34
                            assert v["inactive_entries_before_final_cancel"]==v["retained_queue_entries_before_final_cancel"]-1
                            assert v["heap_entries_final"]==0
                record=dict(r,state=state,source=str(sp.relative_to(ROOT)),protocol=legacy.protocol(m),
                    finished_utc=m.get("finished_utc",""),command_wall_seconds=wall.get("total_command_wall_seconds"),
                    controller_progress_interval_seconds=times.get((r["case_id"],r["version"],r["phase"])))
                if r["phase"]=="latency" and state=="completed":
                    ss=samples(r);values=sorted(x["seconds"] for x in ss)
                    assert all(type(x["seconds"]) in (int,float) and math.isfinite(x["seconds"]) and x["seconds"]>=0 for x in ss)
                    record["historical_latency_samples_path"]=r["latency_samples_path"]
                    record["latency_samples_path"]=str(legacy.saved_path(r["latency_samples_path"]))
                    assert len(ss)==(5 if c["sale_percent"] is not None else len(events))
                    assert r["latency_sample_count"]==r["processed_events"]==len(ss)
                    if c["sale_percent"] is not None:
                        assert [(x["seq"],x["event_id"],x["repetition"]) for x in ss]==[(len(events)+1,"measured-sale",i) for i in range(1,6)]
                    else:
                        assert [(x["seq"],x["event_id"],x["repetition"]) for x in ss]==[(e["seq"],e["event_id"],1) for e in events]
                    assert r["latency_median_seconds"]==statistics.median(values)
                    assert r["latency_p95_seconds"]==values[math.ceil(.95*len(values))-1]
                    assert r["latency_p99_seconds"]==values[math.ceil(.99*len(values))-1]
                    n=max(1,len(ss)//10)
                    record.update(early_latency_median_seconds=statistics.median(x["seconds"] for x in ss[:n]),
                        late_latency_median_seconds=statistics.median(x["seconds"] for x in ss[-n:]))
                    if c["experiment"]=="cancel-churn":
                        record.update(instrumented_before_final_seconds=sum(x["seconds"] for x in ss[:-1]),
                                      instrumented_final_cancel_seconds=ss[-1]["seconds"])
                if c["sale_percent"] is not None and r["phase"] in ("timing","diagnostics") and state=="completed":
                    key=(fingerprint,c["sale_percent"])
                    if key not in oracles:oracles[key]=sale_oracle(events,c["sale_percent"])
                    expected=oracles[key]
                    for field in ("requested_sale_qty_units","fill_count","price_levels_visited","unfilled_qty_units"):
                        if field=="price_levels_visited" and field not in r:continue
                        assert r[field]==expected[field],(r["case_id"],field)
                    if r["phase"]=="diagnostics":
                        for field in ("result_digest","snapshot_digest"):assert r[field]==expected[field],(r["case_id"],field)
                    record["ordered_fills_sha256"]=expected["ordered_fills_sha256"]
                elif c["sale_percent"] is None:assert r.get("price_levels_visited") is None
                all_records.append(record)
                k=identity(record);old=selected.get(k)
                rank={"completed":3,"stopped":2,"unattempted":1,"failed":0}
                if mpath.parent.name not in excluded and (old is None or (rank[state],record["finished_utc"])>(rank[old["state"]],old["finished_utc"])):
                    selected[k]=record
                source_fingerprints[str(mpath.relative_to(ROOT))]=m["environment"]["source_sha256"]
            except (AssertionError,KeyError,ValueError,OSError) as e:
                invalid.append(dict(path=str(sp),case=r["case_id"],phase=r["phase"],error=str(e)))
        for jp in (mpath.parent/"workers").glob("*.job.json"):
            job=read(jp);checkpoint=legacy.saved_path(job["checkpoint"])
            completed=[r for r in groups[(job["case"]["case_id"],job["version"],job["phase"])] if r["status"]=="complete"]
            assert (read(checkpoint)["rows"] if checkpoint.exists() else [])==completed
    for key,settings in concentration.items():
        if 4 in settings and 1000 in settings:assert settings[4]==settings[1000],key
    records=list(selected.values());comparisons=[];diagnostic_pairs=[]
    for r in records:
        if r["version"]!="baseline" or r["phase"]!="timing":continue
        def find(version,phase):
            return next((s for s in records if identity(s)[:-2]==identity(r)[:-2] and s["version"]==version and s["phase"]==phase),None)
        def wrap(s):return dict(state=s["state"],summary=s,protocol=s["protocol"],workload_sha256=s["workload_sha256"]) if s else None
        pair=legacy.compare_pair(wrap(r),wrap(find("revised","timing")),wrap(find("baseline","diagnostics")),wrap(find("revised","diagnostics")))
        comparisons.append(dict(case_id=r["case_id"],experiment=r["experiment"],requested_count=r["requested_count"],seed=r["seed"],
                                levels=r["levels"],sale_percent=r["sale_percent"],**pair))
    for r in records:
        if r["version"]!="baseline" or r["phase"]!="diagnostics":continue
        right=next((s for s in records if identity(s)[:-2]==identity(r)[:-2]
            and s["version"]=="revised" and s["phase"]=="diagnostics"),None)
        diagnostic_pairs.append(dict(case_id=r["case_id"],experiment=r["experiment"],requested_count=r["requested_count"],
            seed=r["seed"],levels=r["levels"],sale_percent=r["sale_percent"],**diagnostic_pair(r,right)))
    assert not invalid,invalid
    assert not [c for c in comparisons if c["status"]=="mismatch"]
    assert not [c for c in diagnostic_pairs if c["status"]=="mismatch"]
    payload=dict(records=records,comparisons=comparisons,invalid=invalid,source_fingerprints=source_fingerprints,provenance_corrections=corrections,
        diagnostic_pairs=diagnostic_pairs,queue_input_pairs_checked=sum(4 in s and 1000 in s for s in concentration.values()),
        status_counts=dict(Counter(r["state"] for r in records)),selection="Complete before documented stop; newest within state; full case identity")
    FINAL.mkdir(parents=True,exist_ok=True)
    (FINAL/"index.json").write_text(json.dumps(payload,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(dict(records=len(records),states=payload["status_counts"],comparable=sum(c["status"]=="comparable" for c in comparisons))))
    return payload

if __name__=="__main__":build()

