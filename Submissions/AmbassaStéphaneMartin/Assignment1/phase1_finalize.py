"""Regenerate the final coverage/report from saved evidence without rewriting history."""
import argparse
from collections import Counter
import json,subprocess,sys,platform
from importlib.metadata import version as dependency_version
from pathlib import Path
import benchmark as bm
import benchmark_report as br
from phase1_results import identity,read

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"/"phase1_final"

def run():
    index=read(OUT/"index.json")
    records=index["records"]
    args=argparse.Namespace(counts=[1000,10000,100000],seeds=[42,43,44],
        scenarios=list(bm.SCENARIOS),experiments=["replay","market-sell","queue-concentration","cancel-churn"],levels=1000)
    expected=bm.case_matrix(args);selected={identity(r):r for r in records}
    required=[];missing=[]
    for c in expected:
        for phase in bm.PHASES:
            for version in ([None] if phase=="io" else ["baseline","revised"]):
                key=identity(dict(c,version=version,phase=phase))
                r=selected.get(key)
                if r is None:missing.append(dict(c,version=version,phase=phase,state="missing"))
                else:required.append(r)
    for path,hashes in index["source_fingerprints"].items():
        names=("order_book.py","generate_orders.py","dispatcher.py")
        if Path(path).parent.name.startswith("final_"):
            names+=("benchmark.py","test_order_book.py","test_price_heaps.py","test_lazy_cancellation.py","test_benchmark.py")
        for name in names:
            assert hashes[name]==br.sha(ROOT/name),name
    protected=("order_book.py","generate_orders.py","benchmark.py","dispatcher.py","test_order_book.py",
        "test_price_heaps.py","test_lazy_cancellation.py","test_benchmark.py","test_benchmark_report.py","ASSIGNMENT.md","data","results")
    changed=subprocess.run(["git","diff","--name-only","--",*protected],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
    assert not changed,changed
    states=Counter(r["state"] for r in required)
    for state in ("completed","stopped","unattempted","failed"):states.setdefault(state,0)
    errors=[r for r in required if r["state"] in ("failed","unattempted")]
    mismatches=[c for c in index["diagnostic_pairs"] if c["status"]=="mismatch"]
    required_ids={c["case_id"] for c in expected}
    diagnostic_states=dict(Counter(c["status"] for c in index["diagnostic_pairs"] if c["case_id"] in required_ids))
    tested=read(OUT/"test_results.json") if (OUT/"test_results.json").exists() else dict(status="not_yet_verified")
    ui=read(OUT/"dashboard_tests.json") if (OUT/"dashboard_tests.json").exists() else dict(status="not_yet_verified")
    browser=read(OUT/"browser_check.json") if (OUT/"browser_check.json").exists() else dict(status="not_yet_verified")
    setup=read(OUT/"clean_environment.json") if (OUT/"clean_environment.json").exists() else dict(status="not_yet_verified")
    io=[r for r in required if r["phase"]=="io" and r["experiment"]=="replay" and r["requested_count"]==100000]
    projected={r["scenario"]:r["decoded_bytes"]*10 for r in io if r["seed"]==42}
    optional=dict(attempted=False,decision="Optional feasibility assessment not yet finalized.",
        explanation="The 10x payload projections alone do not establish feasibility: identifier widths and processing/allocation work also grow. Retain the existing limits.",
        projected_bytes_from_100000=projected,projection_is_not_a_measurement=True,
        worker_seconds=60,payload_bytes=128*1024**2,traced_bytes=512*1024**2)
    if (OUT/"optional_audit.json").exists():optional=read(OUT/"optional_audit.json")
    (OUT/"million_decision.json").write_text(json.dumps(optional,indent=2)+"\n",encoding="utf-8")
    execution=[]
    for name in ("replay_execution.json","controlled_execution.json","corrected_execution.json","optional_execution.json"):
        if (OUT/name).exists():execution.extend(read(OUT/name))
    outcome=dict(commands=len(execution),actual_command_wall_seconds=sum(x["total_command_wall_seconds"] for x in execution),
        completed_commands=sum(x["exit_code"]==0 for x in execution),
        commands_with_documented_stops=sum(x["exit_code"]==2 for x in execution),
        failed_commands=sum(x["exit_code"] not in (0,2) for x in execution),
        note="Includes the preserved interference-affected run and its replacement; phases and engine times remain separate.")
    validation_ok=not missing and not errors and not mismatches and all(r.get("status")=="passed" for r in (tested,ui,browser,setup))
    historical_gap="No contemporaneous initial failing TDD record was available; this historical requirement cannot be verified retroactively."
    verification=dict(status="verified_current_work_with_documented_stops_and_historical_evidence_gap" if validation_ok else "incomplete",
        required_workload_cases=len(expected),required_phase_groups=len(required)+len(missing),
        states=dict(states),missing=missing,failed_or_unattempted=errors,diagnostic_mismatches=mismatches,
        compatible_complete_pairs=sum(c["status"]=="comparable" and c["case_id"] in required_ids for c in index["comparisons"]),
        all_index_comparable_pairs=sum(c["status"]=="comparable" for c in index["comparisons"]),
        diagnostic_pair_states=diagnostic_states,queue_concentration_input_pairs_checked=len({(r["requested_count"],r["seed"]) for r in required if r["experiment"]=="queue-concentration"}),
        tests=tested,dashboard=ui,existing_measured_sources_unchanged=True,historical_measurements_unchanged=True,
        browser=dict(status=browser.get("status"),address=browser.get("address"),screenshots=browser.get("screenshots")),
        clean_environment_status=setup.get("status"),
        new_execution_totals=outcome,
        optional_million=optional,
        unmet_requirements=[historical_gap]+([] if validation_ok else ["See missing cases, validation or execution states above."]))
    (OUT/"verification.json").write_text(json.dumps(verification,indent=2)+"\n",encoding="utf-8")
    lines=["# Final measured coverage","",
        "All values below are regenerated from audited saved data. Documented stops are attempted coverage, not completed estimates.",
        f"Required workload cases: {len(expected)}; phase groups: {len(required)+len(missing)}.",
        "States: "+str(dict(states))+f". Missing: {len(missing)}.",
        f"Available complete comparable timing pairs: {verification['compatible_complete_pairs']}; mismatches: {len(mismatches)}.",
        "Diagnostic pairs (checked independently of timing completion): "+str(diagnostic_states)+".",
        f"Required concentration input pairs with identical quantities, IDs and arrival order: {verification['queue_concentration_input_pairs_checked']} (all-index pairs, including count-120 validation: {index['queue_input_pairs_checked']}).",
        "New execution totals (command wall time, including preparation): "+str(outcome)+".",
        "", "## Actual outcomes by experiment/count/implementation",
        "", "| Experiment | Requested count | Version | Completed | Stopped | Failed | Unattempted |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: |"]
    groups={}
    for r in required:groups.setdefault((r["experiment"],r["requested_count"],r["version"] or "shared I/O"),Counter())[r["state"]]+=1
    for (exp,n,v),counts in sorted(groups.items()):
        lines.append(f"| {exp} | {n} | {v} | {counts['completed']} | {counts['stopped']} | {counts['failed']} | {counts['unattempted']} |")
    lines += ["","## Complete measured timings","","Seconds; construction and sale/replay are distinct. All displayed groups have five repetitions. Speedups are only in the audited comparison table and dashboard.",
        "","| Case | Version | Construction, s | Operation, s | Total compute, s | Processed events |",
        "| --- | --- | ---: | ---: | ---: | ---: |"]
    for r in required:
        if r["phase"]=="timing" and r["state"]=="completed":
            construct="n/a" if r["construction_seconds"] is None else f"{r['construction_seconds']:.6f}"
            lines.append(f"| {r['case_id']} | {r['version']} | {construct} | {r['replay_seconds']:.6f} | {r['total_compute_seconds']:.6f} | {r['processed_events']} |")
    lines += ["","## Incomplete groups","","| Case | Version | Phase | Repetitions | Reason |","| --- | --- | --- | ---: | --- |"]
    for r in required:
        if r["state"]!="completed":
            lines.append(f"| {r['case_id']} | {r['version']} | {r['phase']} | {r['completed_repetitions']}/{r['expected_repetitions']} | {r['error']} |")
    optional_text=optional.get("explanation",optional["decision"]+" Actual states: "+str(optional.get("states"))+". See optional_audit.json for saved per-phase outcomes and elapsed time.")
    lines += ["","## Optional million-event decision","",optional_text,
        "The optional probe is separate from required coverage. Its generated input is excluded from submission; settings, checksums, raw results and actual stops are retained.",
        "", "## Findings and limits","",
        "Passive growth and full book construction expose the Baseline list scans. Revised replay is complete across all required seeds, while large Baseline stops prevent most large-book cross-version speedups.",
        "Small-live-book cancellation streams are a different workload; the supplied alternating stream peaks at one active order. The controlled old-head churn stream captures retained inactive objects and final cleanup separately.",
        "Controlled full-depth and oversized sales may touch every maker, but fewer price levels when orders concentrate at four prices. Sale residual and level counts were independently checked from ordered source bids.",
        "Where Baseline memory stopped, no memory comparison is made even if timing is complete.",
        "Exact actual elapsed command times and settings remain in each run's command_wall_time.json. No estimate replaces a missing measurement.",
        "", "## Historical evidence gap", "",historical_gap,
        "","See REPORT.md at the submission root for algorithms, complexity, profiling, modeling assumptions and AI assistance."]
    (OUT/"coverage.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    replay,candidates,invalid,runs=br.load_catalog((ROOT/"results").resolve())
    assert not invalid
    replay_index=br.make_index(replay,invalid,runs)
    br.dashboard(replay_index,ROOT/"dashboard.html")
    authored=("README.md","REPORT.md","requirements.txt","dashboard.py","dashboard.html","benchmark_report.py",
        "phase1_campaign.py","phase1_queue.py","phase1_results.py","phase1_finalize.py","profile_diagnostic.py",
        "test_phase1_results.py","verify_dashboard.py","verify_browser.py","audit_optional.py")
    reporting=dict(git_head=subprocess.run(["git","rev-parse","HEAD"],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),
        python=sys.version,executable=sys.executable,platform=platform.platform(),
        dependencies={name:dependency_version(name) for name in ("streamlit","matplotlib","pandas","numpy")},
        authored_source_sha256={name:br.sha(ROOT/name) for name in authored},
        note="Reporting/UI provenance only. This does not replace historical benchmark manifests or imply changed measured engine code.")
    (OUT/"reporting_environment.json").write_text(json.dumps(reporting,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(status=verification["status"],required=len(expected),states=dict(states),missing=len(missing))))
    return verification

if __name__=="__main__":run()

