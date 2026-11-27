"""Audit the separate optional limit probe without adding it to the required matrix."""
from collections import Counter,defaultdict
import gzip,json,math,re,statistics,shutil,hashlib
from pathlib import Path
import benchmark as bm
import benchmark_report as br
from phase1_results import ROOT,FINAL,read,rows,sha

def run():
    directory=FINAL/"optional_million_mixed"
    manifest=read(directory/"manifest.json");wall=read(directory/"command_wall_time.json")
    case,=manifest["workloads"]
    source=Path(case["source"]["path"])
    assert sha(source)==case["source"]["sha256"]==case["source"]["metadata"]["sha256"]
    previous=0;event_ids=set();decoded_bytes=0;count=0
    with gzip.open(source,"rb") as stream:
        for line in stream:
            decoded_bytes+=len(line);event=json.loads(line);count+=1
            assert type(event["seq"]) is int and event["seq"]>previous
            previous=event["seq"]
            assert isinstance(event["event_id"],str) and event["event_id"].strip() and event["event_id"] not in event_ids
            event_ids.add(event["event_id"])
            for field in ("price_ticks","qty_units"):
                if field in event:assert type(event[field]) is int and event[field]>0
    assert count==case["event_count"]==1000000
    for name,fingerprint in manifest["environment"]["source_sha256"].items():assert br.sha(ROOT/name)==fingerprint
    intervals={}
    for point in wall["progress"]:
        match=re.match(r"^\[\d+/\d+\]\s+(\S+)\s+(shared|baseline|revised)\s+(\w+):",point["line"])
        if match:
            cid,version,phase=match.groups()
            intervals[(cid,None if version=="shared" else version,phase)]=point["interval_seconds"]
    groups=defaultdict(list)
    for row in rows(directory/"raw.jsonl"):groups[(row["case_id"],row["version"],row["phase"])].append(row)
    audited=[];transport=[]
    for summary in rows(directory/"summaries.jsonl"):
        key=(summary["case_id"],summary["version"],summary["phase"])
        state=br.classify(summary,groups[key],intervals.get(key))
        for raw in groups[key]:
            if raw["status"]!="complete":continue
            assert raw.get("price_levels_visited") is None
            if raw["phase"]=="timing":
                assert raw["processed_events"]==count
                assert math.isclose(raw["throughput_events_per_second"],count/raw["replay_seconds"],rel_tol=1e-12)
                assert math.isclose(raw["total_compute_seconds"],raw["initialization_seconds"]+raw["replay_seconds"],rel_tol=1e-12)
            if raw["phase"]=="io":
                assert raw["decoded_bytes"]==decoded_bytes and raw["compressed_bytes"]==source.stat().st_size
                assert math.isclose(raw["io_total_seconds"],sum(raw[k] or 0 for k in ("read_seconds","decompress_seconds","parse_seconds")),rel_tol=1e-12)
            if raw["phase"]=="memory":assert raw["memory_peak_bytes"]>=raw["memory_current_bytes"]>=0
            if raw["phase"]=="diagnostics":assert raw["rejected_event_count"]==0
        if summary["phase"]=="latency" and state=="completed":
            path=Path(summary["latency_samples_path"])
            samples=read(path)["samples"]
            assert len(samples)==summary["latency_sample_count"]==count
            values=sorted(s["seconds"] for s in samples)
            assert summary["latency_median_seconds"]==statistics.median(values)
            assert summary["latency_p95_seconds"]==values[math.ceil(.95*count)-1]
            assert summary["latency_p99_seconds"]==values[math.ceil(.99*count)-1]
            archive=path.with_suffix(path.suffix+".gz")
            with path.open("rb") as original,archive.open("wb") as target:
                with gzip.GzipFile(fileobj=target,mode="wb",mtime=0) as compressed:
                    shutil.copyfileobj(original,compressed)
            restored=hashlib.sha256()
            with gzip.open(archive,"rb") as stream:
                for chunk in iter(lambda:stream.read(1024**2),b""):restored.update(chunk)
            assert restored.hexdigest()==sha(path)
            transport.append(dict(original=str(path.relative_to(ROOT)),archive=str(archive.relative_to(ROOT)),
                original_bytes=path.stat().st_size,original_sha256=sha(path),archive_sha256=sha(archive),
                note="Lossless post-measurement transport compression. Original local bytes retained and ignored by Git; manifests/raw provenance are unchanged."))
        audited.append(dict(summary,state=state,controller_progress_interval_seconds=intervals.get(key)))
    assert not any(r["state"] in ("failed","unattempted") for r in audited)
    comparisons=manifest["diagnostic_comparisons"]
    assert all(c["status"]=="passed" for c in comparisons)
    payload=dict(attempted=True,decision="One bounded mixed-workload million-event probe was feasible after mandatory coverage; no other million-event cases attempted.",
        scenario="mixed",seed=42,event_count=count,versions=manifest["versions"],worker_seconds=60,campaign_seconds=900,
        payload_bytes=128*1024**2,traced_bytes=512*1024**2,states=dict(Counter(r["state"] for r in audited)),
        actual_command_wall_seconds=wall["total_command_wall_seconds"],decoded_bytes=decoded_bytes,
        workload_sha256=case["source"]["sha256"],input_audit_status="Checksum, exact integers, sequence and unique event IDs verified from the local generated input.",
        input_in_submission=False,input_location="Ignored .cache/optional_million; generator settings and checksum preserved in the manifest.",
        summaries=audited,diagnostic_comparisons=comparisons,latency_transport=transport,
        comparison_status="performed" if comparisons else "not performed: no completed Baseline/Revised diagnostic pair",
        manifest=str((directory/"manifest.json").relative_to(ROOT)),
        note="Optional outcomes are separate from the required 99 workload cases. Historical provenance is retained; clean report regeneration consumes this audit and does not pretend to recheck an absent million-event input.")
    (FINAL/"optional_audit.json").write_text(json.dumps(payload,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in payload.items() if k not in ("summaries",)}))
    return payload
if __name__=="__main__":run()
