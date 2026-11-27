"""Audit saved Revised-only measurements; never launch an engine or benchmark."""
import base64
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time
import zlib

RUN=Path(__file__).resolve().parent
ROOT=RUN.parent.parent
sys.path.insert(0,str(ROOT))
import benchmark as bm


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close(left,right):
    return math.isclose(left,right,rel_tol=1e-12,abs_tol=1e-12)


def known_diagnostics(events,scenario):
    """Source-only oracles for passive books, a passive-then-sell sweep and churn."""
    limits=[e for e in events if e["type"]=="LIMIT"]
    submitted=sum(e["qty_units"] for e in limits)
    prices={(e["side"],e["price_ticks"]) for e in limits}
    expected={}
    if scenario in ("buildup","crowded"):
        expected=dict(fill_count=0,unfilled_qty_units=submitted,cancelled_qty_units=0,
            active_orders_peak=len(limits),active_orders_final=len(limits),
            occupied_prices_peak=len(prices),occupied_prices_final=len(prices))
        active=limits
    elif scenario=="cancel_churn":
        expected=dict(fill_count=0,unfilled_qty_units=submitted,cancelled_qty_units=submitted,
            active_orders_peak=1,active_orders_final=0,occupied_prices_peak=1,occupied_prices_final=0)
        active=[]
    elif scenario=="sweep":
        first_sale=next(i for i,e in enumerate(events) if e["type"]=="MARKET_SELL")
        assert all(e["type"]=="LIMIT" for e in events[:first_sale])
        assert all(e["type"]=="MARKET_SELL" for e in events[first_sale:])
        bids=sorted((e for e in limits if e["side"]=="BUY"),key=lambda e:(-e["price_ticks"],e["seq"]))
        asks=[e for e in limits if e["side"]=="SELL"]
        maker=0
        remaining=bids[0]["qty_units"] if bids else 0
        fills=unsold=0
        # Count intersections between sale quantities and sorted resting bid quantities.
        for sale in events[first_sale:]:
            needed=sale["qty_units"]
            while needed and maker<len(bids):
                executed=min(needed,remaining)
                needed-=executed
                remaining-=executed
                fills+=1
                if remaining==0:
                    maker+=1
                    remaining=bids[maker]["qty_units"] if maker<len(bids) else 0
            unsold+=needed
        assert maker==len(bids)
        expected=dict(fill_count=fills,unfilled_qty_units=submitted+unsold,cancelled_qty_units=0,
            active_orders_peak=len(limits),active_orders_final=len(asks),
            occupied_prices_peak=len(prices),
            occupied_prices_final=len({e["price_ticks"] for e in asks}))
        active=asks
    else:
        # Mixed matching is covered by the unchanged correctness suite. Here check
        # input-based bounds and internal diagnostic consistency without another engine.
        return expected,None
    orders=[dict(order_id=e["order_id"],side=e["side"],price_ticks=e["price_ticks"],
                 qty_units=e["qty_units"],arrival_seq=e["seq"]) for e in active]
    snapshot=dict(bids=sorted((o for o in orders if o["side"]=="BUY"),
                             key=lambda o:(-o["price_ticks"],o["arrival_seq"])),
                  asks=sorted((o for o in orders if o["side"]=="SELL"),
                             key=lambda o:(o["price_ticks"],o["arrival_seq"])))
    return expected,hashlib.sha256(json.dumps(snapshot,sort_keys=True).encode()).hexdigest()


def audit():
    start=time.perf_counter()
    before=read(RUN/"before_checks.json")
    assert before["tests"]["exit_code"]==0
    protected=before["preservation"]
    paths=json.loads(zlib.decompress(base64.b64decode(protected["protected_paths_zlib_base64"])))
    assert len(paths)==protected["protected_files"]
    current={name:sha(ROOT/name) for name in paths}
    canonical=json.dumps(current,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest()==protected["protected_tree_sha256"]
    for name,value in protected["source_sha256"].items():
        assert sha(ROOT/name)==value,name
    manifest=read(RUN/"manifest.json")
    wall=read(RUN/"command_wall_time.json")
    raw=rows(RUN/"raw.jsonl")
    summaries=rows(RUN/"summaries.jsonl")
    assert manifest["versions"]==["revised"] and manifest["repetitions"]==5
    assert tuple(manifest["phases"])==("io","timing","latency","memory","diagnostics")
    assert manifest["run_kind"]=="first-100000-revised"
    assert manifest["environment"]["git_head"]==before["git_head"]
    assert manifest["diagnostic_comparisons"]==[]
    for name,value in manifest["environment"]["source_sha256"].items():
        assert sha(ROOT/name)==value
        assert protected["source_sha256"][name]==value
    assert manifest["limits"]==dict(worker_wall_seconds=60.0,
        measurement_campaign_wall_seconds=900.0,payload_bytes=128*1024**2,
        traced_allocation_bytes=512*1024**2,os_rss_hard_limit=None,
        preparation="Generation precedes measurement deadline; no preparation timeout")
    assert len(wall["progress"])==25 and len(manifest["workloads"])==5
    assert [p["job_index"] for p in wall["progress"]]==list(range(1,26))
    assert close(sum(p["interval_since_previous_progress_seconds"] for p in wall["progress"]),
                 wall["progress"][-1]["elapsed_command_seconds"])
    assert wall["total_command_wall_seconds"]>=wall["progress"][-1]["elapsed_command_seconds"]
    workloads={}
    for case in manifest["workloads"]:
        assert case["experiment"]=="replay" and case["sale_percent"] is None
        assert case["event_count"]==case["source_event_count"]==case["requested_count"]==100000
        assert case["seed"]==42 and case["levels"]==1000
        path=Path(case["source"]["path"])
        assert path.parent==ROOT/"data"/"benchmark"
        assert sha(path)==case["source"]["sha256"]
        meta=read(path.with_suffix(path.suffix+".metadata.json"))
        assert meta==case["source"]["metadata"] and meta["sha256"]==sha(path)
        assert meta["events"]==100000 and meta["seed"]==42 and meta["levels"]==1000
        assert meta["price_tick_usd"]=="0.01" and meta["quantity_unit_btc"]=="0.00000001"
        assert meta["generator_source_sha256"]==sha(ROOT/"generate_orders.py")
        assert meta["benchmark_source_sha256"]==sha(ROOT/"benchmark.py")
        assert path.stat().st_mtime<=datetime.fromisoformat(manifest["started_utc"]).timestamp()+1
        events,io=bm.load_events(path,128*1024**2,100000)
        # Regenerate in memory only: no additional dataset, book or benchmark is run.
        assert events==list(bm.generate_orders.events(case["scenario"],100000,42,1000))
        expected,snapshot=known_diagnostics(events,case["scenario"])
        workloads[case["case_id"]]=dict(case=case,events=events,io=io,
            expected_diagnostics=expected,expected_snapshot_digest=snapshot)
    assert {w["case"]["scenario"] for w in workloads.values()}==set(bm.SCENARIOS)
    groups={}
    for row in raw:
        key=(row["case_id"],row["version"],row["phase"])
        groups.setdefault(key,[]).append(row)
        assert row["version"]==(None if row["phase"]=="io" else "revised")
        assert row["price_levels_visited"] is None
        assert row["workload_sha256"]==workloads[row["case_id"]]["case"]["source"]["sha256"]
        assert row["event_count"]==100000 and row["seed"]==42
        assert all(field in row for field in bm.METRICS)
        if row["status"]!="complete":
            assert row["status"] in ("stopped","not_run","error")
            assert all(row[field] is None for field in bm.METRICS)
            continue
        phase=row["phase"]
        if phase=="io":
            for field in ("compressed_bytes","decoded_bytes"):
                assert row[field]==workloads[row["case_id"]]["io"][field]
            components=[row[field] for field in ("read_seconds","decompress_seconds","parse_seconds")]
            assert all(math.isfinite(v) and v>=0 for v in components)
            assert close(row["io_total_seconds"],sum(components))
        elif phase=="timing":
            assert row["processed_events"]==100000 and row["construction_seconds"] is None
            assert row["initialization_seconds"]>=0 and row["replay_seconds"]>0
            assert close(row["total_compute_seconds"],row["initialization_seconds"]+row["replay_seconds"])
            assert close(row["throughput_events_per_second"],100000/row["replay_seconds"])
            assert row["memory_peak_bytes"] is None and row["latency_p99_seconds"] is None
        elif phase=="latency":
            saved=read(row["latency_samples_path"])
            samples=saved["samples"]
            assert len(samples)==row["latency_sample_count"]==100000
            for sample,event in zip(samples,workloads[row["case_id"]]["events"]):
                assert sample["event_id"]==event["event_id"] and sample["seq"]==event["seq"]
                assert sample["repetition"]==1 and math.isfinite(sample["seconds"]) and sample["seconds"]>=0
            values=sorted(s["seconds"] for s in samples)
            assert row["latency_median_seconds"]==statistics.median(values)
            assert row["latency_p95_seconds"]==values[math.ceil(.95*len(values))-1]
            assert row["latency_p99_seconds"]==values[math.ceil(.99*len(values))-1]
        elif phase=="memory":
            assert row["processed_events"]==100000
            assert row["memory_peak_bytes"]>=row["memory_current_bytes"]>=0
            assert row["memory_peak_bytes"]>=row["memory_after_construction_bytes"]>=0
            assert row["replay_seconds"] is None
        else:
            workload=workloads[row["case_id"]]
            limits=[e for e in workload["events"] if e["type"]=="LIMIT"]
            markets=[e for e in workload["events"] if e["type"]=="MARKET_SELL"]
            possible_prices={(e["side"],e["price_ticks"]) for e in limits}
            for field in ("active_orders_peak","active_orders_final","occupied_prices_peak",
                          "occupied_prices_final","retained_queue_entries_peak",
                          "retained_queue_entries_final","inactive_queue_entries_final",
                          "heap_entries_final","fill_count","unfilled_qty_units",
                          "cancelled_qty_units","rejected_event_count"):
                assert type(row[field]) is int and row[field]>=0
            assert row["active_orders_final"]<=row["active_orders_peak"]<=len(limits)
            assert row["occupied_prices_final"]<=row["occupied_prices_peak"]<=len(possible_prices)
            assert row["fill_count"]<=2*len(limits)+len(markets)
            assert row["cancelled_qty_units"]<=sum(e["qty_units"] for e in limits)
            assert row["unfilled_qty_units"]<=sum(e.get("qty_units",0) for e in workload["events"])
            assert row["retained_queue_entries_final"]-row["active_orders_final"]==row["inactive_queue_entries_final"]
            assert row["retained_queue_entries_final"]<=2*row["active_orders_final"]+32*row["occupied_prices_final"]
            assert row["retained_queue_entries_peak"]<=2*row["active_orders_peak"]+32*row["occupied_prices_peak"]
            assert row["heap_entries_final"]<=2*row["occupied_prices_final"]+64
            for field,value in workload["expected_diagnostics"].items():
                assert row[field]==value,(row["scenario"],field,row[field],value)
            if workload["expected_snapshot_digest"] is not None:
                assert row["snapshot_digest"]==workload["expected_snapshot_digest"]
    assert len(groups)==len(summaries)==25 and len(raw)==85
    jobs=[]
    scenario_results=[]
    for index,summary in enumerate(summaries,1):
        key=(summary["case_id"],summary["version"],summary["phase"])
        group=groups[key]
        expected=5 if summary["phase"] in ("io","timing","memory") else 1
        complete_count=sum(r["status"]=="complete" for r in group)
        complete=complete_count==expected
        assert len(group)==expected and [r["repetition"] for r in group]==list(range(1,expected+1))
        assert summary["completed_repetitions"]==complete_count and summary["expected_repetitions"]==expected
        assert summary["status"]==("complete" if complete else "incomplete")
        for field in bm.METRICS:
            values=[r[field] for r in group if r[field] is not None]
            expected_value=statistics.median(values) if complete and len(values)==expected else None
            assert summary[field]==expected_value,(key,field)
        states={r["status"] for r in group}
        state="complete" if complete else "stopped" if "stopped" in states else "unattempted" if states=={"not_run"} else "failed"
        progress=wall["progress"][index-1]
        assert (progress["case_id"],progress["version"],progress["phase"])==key
        jobs.append(dict(index=index,scenario=summary["scenario"],phase=summary["phase"],
            state=state,completed_repetitions=complete_count,expected_repetitions=expected,error=summary["error"]))
    checkpoints=0
    for path in sorted((RUN/"workers").glob("*.job.json")):
        job=read(path)
        checkpoint=Path(job["checkpoint"])
        saved=read(checkpoint) if checkpoint.exists() else {"rows":[]}
        key=(job["case"]["case_id"],job["version"],job["phase"])
        completed=[r for r in groups[key] if r["status"]=="complete"]
        assert saved["rows"]==completed
        checkpoints+=1
    assert checkpoints==25
    for case_id,workload in workloads.items():
        phases={s["phase"]:s for s in summaries if s["case_id"]==case_id}
        scenario_results.append(dict(scenario=workload["case"]["scenario"],phases=phases,
            diagnostic_validation="source oracle" if workload["expected_diagnostics"] else "input bounds and storage invariants",
            cross_version_comparison="not_performed",reason="Baseline intentionally excluded"))
    counts=Counter(j["state"] for j in jobs)
    for field in ("complete","stopped","unattempted","failed"):
        counts.setdefault(field,0)
    assert manifest["completed_jobs"]==counts["complete"]
    assert manifest["raw_rows"]==85 and manifest["summary_rows"]==25
    assert manifest["status"]==("complete" if counts["complete"]==25 else "incomplete")
    assert wall["exit_code"]==(0 if counts["complete"]==25 else 2)
    unexpected=[dict(scenario=s["scenario"],count=s["phases"]["diagnostics"]["rejected_event_count"])
                for s in scenario_results if s["phases"]["diagnostics"]["status"]=="complete"
                and s["phases"]["diagnostics"]["rejected_event_count"]!=0]
    return dict(audit_status="passed",campaign_status=manifest["status"],
        code_version=manifest["environment"]["git_head"],source_files_unchanged=True,
        source_sha256=manifest["environment"]["source_sha256"],
        protected_files_verified=len(paths),protected_tree_sha256=protected["protected_tree_sha256"],
        tests=before["tests"],total_command_wall_seconds=wall["total_command_wall_seconds"],
        job_counts=dict(counts),raw_record_states=dict(Counter(r["status"] for r in raw)),
        jobs=jobs,scenario_results=scenario_results,unexpected_rejections=unexpected,
        diagnostic_jobs_missing=[s["scenario"] for s in scenario_results if s["phases"]["diagnostics"]["status"]!="complete"],
        cross_version_comparisons=dict(status="not_performed",reason="Baseline intentionally excluded",speedups=None),
        audit_elapsed_seconds=time.perf_counter()-start)


if __name__=="__main__":
    result=audit()
    path=RUN/"audit.json"
    if path.exists():
        old=read(path)
        a,b=dict(old),dict(result)
        a.pop("audit_elapsed_seconds")
        b.pop("audit_elapsed_seconds")
        assert a==b
    else:
        path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:result[key] for key in ("audit_status","campaign_status",
        "total_command_wall_seconds","job_counts","raw_record_states",
        "unexpected_rejections","diagnostic_jobs_missing","cross_version_comparisons")},indent=2))

