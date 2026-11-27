"""Streamlit/Matplotlib viewer of audited saved results. Never executes benchmarks."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from benchmark_report import saved_path

ROOT=Path(__file__).resolve().parent
INDEX=ROOT/"results"/"phase1_final"/"index.json"

@st.cache_data
def load_index(stamp):
    return json.loads(INDEX.read_text(encoding="utf-8"))

@st.cache_data
def latencies(path,stamp):
    return json.loads(Path(path).read_text(encoding="utf-8"))["samples"]

def case_key(r):
    return tuple(r.get(k) for k in ("experiment","scenario","requested_count","event_count","seed","levels","sale_percent"))

def comparable_phase(records,comparisons,phase):
    allowed={(c["case_id"],c["seed"],c["levels"],c["sale_percent"]) for c in comparisons if c["status"]=="comparable"}
    grouped={}
    for r in records:
        if r["phase"]==phase:grouped.setdefault(case_key(r),[]).append(r)
    valid=set()
    for key,group in grouped.items():
        if len(group)==2 and {r["version"] for r in group}=={"baseline","revised"} and all(r["state"]=="completed" for r in group):
            a,b=group
            if a["protocol"]==b["protocol"] and (a["case_id"],a["seed"],a["levels"],a["sale_percent"]) in allowed:
                valid.add(key)
    return [r for r in records if r["phase"]==phase and r["state"]=="completed" and case_key(r) in valid]

def plot_lines(data,fields,ylabel):
    fig,axes=plt.subplots(len(fields),1,figsize=(9,4*len(fields)),squeeze=False)
    for (field,label),axes_row in zip(fields,axes):
        ax=axes_row[0]
        groups={}
        for r in data:
            if r.get(field) is not None:
                groups.setdefault((r["version"],r["seed"],r["levels"],r["sale_percent"]),[]).append(r)
        for key,group in groups.items():
            group.sort(key=lambda r:r["requested_count"])
            ax.plot([r["requested_count"] for r in group],[r[field] for r in group],marker="o",
                label=f"{key[0]} s{key[1]} L{key[2]} p{key[3]} {label}")
        ax.set_xscale("log");ax.set_xlabel("Requested count (stream events / setup orders / churn pairs)");ax.set_ylabel(ylabel)
        ax.set_title(label);ax.grid(alpha=.25)
        if ax.lines:ax.legend(fontsize=7,bbox_to_anchor=(1.02,1),loc="upper left")
        else:ax.text(.5,.5,"No applicable complete comparable measurements",ha="center",transform=ax.transAxes)
    fig.tight_layout();st.pyplot(fig);plt.close(fig)

def main():
    st.set_page_config(page_title="Phase 1 order book benchmarks",layout="wide")
    st.title("BTC order book — Phase 1")
    st.caption("Saved data only · integer cents/BTC and 10^-8 BTC quantities · complete groups and documented limits")
    if not INDEX.exists():
        st.error("Generate the audited index with: python -B phase1_results.py");return
    index=load_index(INDEX.stat().st_mtime_ns)
    records=index["records"]
    exp=st.sidebar.selectbox("Experiment",["replay","market-sell","queue-concentration","cancel-churn"])
    subset=[r for r in records if r["experiment"]==exp]
    scenario=st.sidebar.selectbox("Scenario",sorted({r["scenario"] for r in subset}))
    counts=st.sidebar.multiselect("Requested counts",sorted({r["requested_count"] for r in subset}),default=[1000,10000,100000])
    seeds=st.sidebar.multiselect("Seeds",[42,43,44],default=[42,43,44])
    versions=st.sidebar.multiselect("Implementations",["baseline","revised"],default=["baseline","revised"])
    levels=st.sidebar.multiselect("Price-level setting",sorted({r["levels"] for r in subset}),default=sorted({r["levels"] for r in subset}))
    percents=sorted({r["sale_percent"] for r in subset if r["sale_percent"] is not None})
    pct=st.sidebar.multiselect("Sale percentage",percents,default=percents) if percents else []
    only=st.sidebar.checkbox("Comparable pairs only in plots",value=True,help="With both implementations selected, exclude incomplete or incompatible phase pairs. Select one implementation to inspect its unpaired completed observations.")
    chosen=[r for r in subset if r["scenario"]==scenario and r["requested_count"] in counts and r["seed"] in seeds
        and (r["version"] in versions or r["phase"]=="io") and r["levels"] in levels and (not percents or r["sale_percent"] in pct)]
    def phase(name):
        if name=="io":return [r for r in chosen if r["phase"]==name and r["state"]=="completed"]
        if only and set(versions)=={"baseline","revised"}:
            return comparable_phase(chosen,index["comparisons"],name)
        return [r for r in chosen if r["phase"]==name and r["state"]=="completed"]
    cols=st.columns(4)
    for col,state in zip(cols,("completed","stopped","unattempted","failed")):
        col.metric(state.title()+" groups",sum(r["state"]==state for r in chosen))
    st.info("Stopped groups retain partial raw repetitions but no complete median. A 60-second worker budget includes loading and warm-up. Unpaired curves are independent observations; speedups require matching complete groups and diagnostics.")
    tabs=st.tabs(["Scaling","Latency","Memory and cleanup","Sales and correctness","Coverage and provenance"])
    with tabs[0]:
        timing=phase("timing")
        st.subheader("Construction, replay / individual sale, and total compute")
        plot_lines(timing,[("initialization_seconds","book initialization"),("construction_seconds","construction"),("replay_seconds","sale" if exp in ("market-sell","queue-concentration") else "replay"),
                           ("total_compute_seconds","total compute")],"Seconds (five-repeat medians)")
        plot_lines(timing,[("throughput_events_per_second","throughput")],"Sales/s" if exp in ("market-sell","queue-concentration") else "Events/s")
        plot_lines(phase("diagnostics"),[("active_orders_peak","active orders peak"),("occupied_prices_peak","occupied side/price levels peak")],"Count (separate diagnostic run)")
        st.subheader("Separate input reading, decompression and parsing")
        st.dataframe(pd.DataFrame([{k:r.get(k) for k in ("requested_count","seed","levels","sale_percent","read_seconds","decompress_seconds","parse_seconds","io_total_seconds")} for r in phase("io")]),hide_index=True)
        eligible={r["case_id"] for r in chosen}
        st.dataframe(pd.DataFrame([c for c in index["comparisons"] if c["case_id"] in eligible]),hide_index=True)
    with tabs[1]:
        data=phase("latency")
        plot_lines(data,[("latency_median_seconds","median"),("latency_p95_seconds","P95"),("latency_p99_seconds","P99")],"Instrumented seconds/event")
        st.caption("Median averages the central pair; P95/P99 use nearest rank. Single-sale distributions contain five fresh-book observations.")
        if data:
            n=st.selectbox("Distribution count",sorted({r["requested_count"] for r in data}))
            fig,ax=plt.subplots(figsize=(9,4))
            for r in data:
                if r["requested_count"]!=n:continue
                path=str(saved_path(r["latency_samples_path"]))
                ss=latencies(path,Path(path).stat().st_mtime_ns)
                ax.hist([x["seconds"]*1e6 for x in ss],bins=50,histtype="step",density=True,
                    label=f"{r['version']} s{r['seed']} L{r['levels']} p{r['sale_percent']} n={len(ss)}")
            ax.set_xlabel("Processing latency, microseconds");ax.set_ylabel("Density");ax.legend(fontsize=7)
            fig.tight_layout();st.pyplot(fig);plt.close(fig)
        plot_lines(data,[("early_latency_median_seconds","early window"),("late_latency_median_seconds","late window")],"Median instrumented seconds/event")
        st.caption("Windows contain the first/last max(1, sample_count // 10) samples of the same uninterrupted replay pass. Five-sample controlled sales use fresh books; those windows do not describe within-book growth. Setup is excluded from sale samples.")
    with tabs[2]:
        mem=phase("memory")
        plot_lines(mem,[("memory_peak_bytes","peak"),("memory_current_bytes","retained"),
            ("memory_before_final_cancel_bytes","before final cancellation"),("memory_after_cancellation_bytes","after final cancellation")],"Incremental traced bytes")
        st.caption("Separate-process tracemalloc: preloaded input/imports excluded; book construction, transient results and cleanup included; no result history. Python allocation bytes, not RSS.")
        diag=phase("diagnostics")
        plot_lines(diag,[("retained_queue_entries_peak","queue peak"),("retained_queue_entries_before_final_cancel","before final cancellation"),
            ("retained_queue_entries_final","queue final"),("heap_entries_before_final_cancel","heap before"),("heap_entries_final","heap final")],"Retained objects / heap entries")
        st.dataframe(pd.DataFrame([{k:r.get(k) for k in ("version","requested_count","seed","active_orders_before_final_cancel",
            "retained_queue_entries_before_final_cancel","inactive_entries_before_final_cancel","heap_entries_before_final_cancel",
            "active_orders_final","retained_queue_entries_final","inactive_queue_entries_final","heap_entries_final")} for r in diag]),hide_index=True)
        st.dataframe(pd.DataFrame([{k:r.get(k) for k in ("version","requested_count","seed","instrumented_before_final_seconds",
             "instrumented_final_cancel_seconds")} for r in phase("latency")]),hide_index=True)
        st.caption("Churn times above come from the separate per-event instrumentation pass: sum before the final event and one final-cancellation sample; they are not primary five-repeat timing medians.")
    with tabs[3]:
        fields=("experiment","requested_count","construction_event_count","event_count","processed_events","seed","version","levels","actual_controlled_price_levels","occupied_prices_peak","sale_percent",
                "fill_count","price_levels_visited","requested_sale_qty_units","unfilled_qty_units","rejected_event_count")
        table=[]
        for r in chosen:
            if r["phase"]!="diagnostics":continue
            d={k:r.get(k) for k in fields}
            for k in ("requested_sale_qty_units","unfilled_qty_units"):
                d[k]="unavailable" if d[k] is None else str(d[k])
            d.update(state=r["state"],ordered_fills_sha256=r.get("ordered_fills_sha256"))
            table.append(d)
        st.dataframe(pd.DataFrame(table),hide_index=True)
        st.caption("Single-sale fields describe only the measured sale. Replay/churn fill and residual fields aggregate their task; returned limit residuals are included in replay residual totals.")
        plot_lines(phase("diagnostics"),[("fill_count","maker fills"),("price_levels_visited","executed price levels")],"Counts")
        if exp in ("market-sell","queue-concentration"):
            plot_lines(phase("diagnostics"),[("unfilled_qty_units","unfilled residual")],"Quantity units (10^-8 BTC)")
        st.success("The original 99-test gate passed before the campaigns. Final verification is recorded in results/phase1_final/verification.json.")
        verification=ROOT/"results"/"phase1_final"/"verification.json"
        if verification.exists():
            result=json.loads(verification.read_text(encoding="utf-8"))
            st.json({k:result.get(k) for k in ("status","tests","dashboard","unmet_requirements")})
        st.write("Independent expected tests supplement shared-logic differential tests. Source-only sale oracles verify ordered result digests, maker fills, executed prices, requested units and residuals.")
        eligible={r["case_id"] for r in chosen}
        st.dataframe(pd.DataFrame([r for r in index.get("diagnostic_pairs",[]) if r["case_id"] in eligible]),hide_index=True)
    with tabs[4]:
        st.dataframe(pd.DataFrame([{k:r.get(k) for k in ("experiment","scenario","requested_count","event_count","seed","levels","sale_percent","version","phase",
             "state","completed_repetitions","expected_repetitions","controller_progress_interval_seconds","error","source")} for r in chosen]),hide_index=True)
        st.write("Complete identity includes experiment, both count meanings, seed, level setting, percentage, implementation and phase. No partial group is displayed as a five-repeat median.")
        st.caption("Controller progress intervals are wall-clock observations between job completion messages; the first includes preparation. They are not individual replay durations.")
        if st.checkbox("Show saved raw repetitions (including partial groups)"):
            raw=[]
            for source in sorted({r["source"] for r in chosen}):
                wanted={(r["case_id"],r["version"],r["phase"]) for r in chosen if r["source"]==source}
                for line in saved_path(source).with_name("raw.jsonl").read_text(encoding="utf-8").splitlines():
                    r=json.loads(line)
                    if (r["case_id"],r["version"],r["phase"]) in wanted:
                        raw.append(dict(source=source,**{k:r.get(k) for k in ("case_id","version","phase","repetition","status","error",
                            "initialization_seconds","construction_seconds","replay_seconds","total_compute_seconds",
                            "memory_peak_bytes","fill_count","price_levels_visited","unfilled_qty_units")}))
            st.dataframe(pd.DataFrame(raw),hide_index=True)
            st.caption("These are individual raw observations, including retained repetitions from stopped groups; no partial-group median is computed.")
        st.json(index["status_counts"])
        st.json(index.get("provenance_corrections",{}))
        optional=ROOT/"results"/"phase1_final"/"optional_audit.json"
        if optional.exists():
            st.subheader("Separate optional million-event limit probe")
            probe=json.loads(optional.read_text(encoding="utf-8"))
            st.write(probe["decision"])
            st.json({k:probe[k] for k in ("states","actual_command_wall_seconds","workload_sha256","comparison_status")})
            st.dataframe(pd.DataFrame([{k:r.get(k) for k in ("version","phase","state","completed_repetitions",
                "expected_repetitions","replay_seconds","memory_peak_bytes","error")} for r in probe["summaries"]]),hide_index=True)
        st.write("Source/environment fingerprints and raw values are preserved in the audited index; historical manifests and audit files are never rewritten by this application.")
        st.download_button("Download audited index",INDEX.read_bytes(),file_name="phase1_index.json",mime="application/json")

if __name__=="__main__":main()

