#!/usr/bin/env python3
"""Write results/summary.md: the key tables quoted in REPORT.md, computed from saved results."""
import json
from statistics import median

from _util import RESULTS, read_csv


def med(vals):
    return median(vals) if vals else None


def f(x, nd=4):
    if x is None:
        return "–"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    return f"{x:.{nd}g}"


def main():
    out = []
    t = read_csv(RESULTS / "timing.csv")
    cfg = {}
    for r in t:
        k = (r["version"], r["scenario"], int(r["events"]), int(r["seed"]))
        c = cfg.setdefault(k, {"replay": [], "parse": [], "status": "ok", "B": r["active_orders_peak"],
                               "P": r["price_levels_peak"], "F": r["fills"]})
        if r["phase"] == "replay" and r["status"] == "ok":
            c["replay"].append(float(r["elapsed_s"]))
        if r["phase"] == "parse":
            c["parse"].append(float(r["elapsed_s"]))
        if r["status"] in ("stopped_time_limit", "not_attempted", "failed"):
            c["status"] = r["status"]

    parse = {}
    if (RESULTS / "parse.csv").exists():
        for r in read_csv(RESULTS / "parse.csv"):
            if r["status"] == "ok":
                parse.setdefault((r["scenario"], int(r["events"]), int(r["seed"])), []).append(float(r["elapsed_s"]))
    out.append("## Replay (median seconds of 5 repeats, seed 42; throughput in events/s)\n")
    out.append("| scenario | M | peak B | peak P | fills F | A replay s | B replay s | A events/s | B events/s | B parse s | A/B |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for scen in ("buildup", "crowded", "mixed", "sweep", "cancel_churn"):
        for n in (1000, 10000, 100000, 1000000):
            a, b = cfg.get(("A", scen, n, 42)), cfg.get(("B", scen, n, 42))
            if not b:
                continue
            am = med(a["replay"]) if a and a["status"] == "ok" else None
            bm = med(b["replay"]) if b["status"] == "ok" else None
            astat = f(am) if am else (a["status"] if a else "–")
            out.append(f"| {scen} | {n:,} | {int(b['B']):,} | {int(b['P']):,} | {int(b['F']):,} | {astat} | {f(bm)} | "
                       f"{f(n / am) if am else '–'} | {f(n / bm) if bm else '–'} | {f(med(parse.get((scen, n, 42), b['parse'])))} | "
                       f"{f(am / bm, 3) if am and bm else '–'} |")
    # seed spread
    out.append("\nSeed spread (B replay median over seeds 42/43/44, M = 100,000): " + ", ".join(
        f"{s} {f(min(med(cfg[('B', s, 100000, sd)]['replay']) for sd in (42, 43, 44)))}–"
        f"{f(max(med(cfg[('B', s, 100000, sd)]['replay']) for sd in (42, 43, 44)))} s"
        for s in ("buildup", "crowded", "mixed", "sweep", "cancel_churn")
        if all(('B', s, 100000, sd) in cfg for sd in (42, 43, 44))))
    stopped = sorted({(k[0], k[1], k[2]) for k, c in cfg.items() if c["status"] != "ok"})
    out.append("\nStopped / not attempted (version, scenario, M): " + "; ".join(f"{v} {s} {n:,}" for v, s, n in stopped))

    lq = read_csv(RESULTS / "liquidation.csv")
    out.append("\n## Large market sell (median seconds of 5 trials; reset reported separately)\n")
    out.append("| book | sale | requested units | fills F | levels L | unfilled | A sell s | B sell s | A reset s | B reset s | A work | B work |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    groups = {}
    for r in lq:
        label = r["note"].split()[1]
        g = groups.setdefault((r["scenario"], int(r["events"]), label), {})
        v = g.setdefault(r["version"], {"sell": [], "reset": [], "status": "ok"})
        if r["status"] == "ok" and r["phase"] == "sell":
            v["sell"].append(float(r["elapsed_s"]))
        if r["status"] == "ok" and r["phase"] == "reset":
            v["reset"].append(float(r["elapsed_s"]))
        if r["status"] in ("stopped_time_limit", "failed"):
            v["status"] = r["status"]
        if r["work_steps"]:
            bids = r["note"].split("bid orders ")[1].split(";")[0] if "bid orders " in r["note"] else "?"
            g.update(req=int(r["requested_qty_units"]), F=r["fills"], L=r["levels_visited"], U=r["unfilled_qty_units"],
                     orders=r["active_orders_peak"], bids=bids)
            v["work"] = int(r["work_steps"])
    for (scen, n, label), g in groups.items():
        A, B = g.get("A", {}), g.get("B", {})
        a_sell = (f(med(A.get("sell"))) if A.get("status") == "ok"
                  else f"stopped ({len(A.get('sell', []))} of 5 finished)")
        out.append(f"| {scen} after {n:,} ({g.get('bids')} bid orders) | {label} | {g.get('req', 0):,} | {g.get('F')} | {g.get('L')} | "
                   f"{g.get('U')} | {a_sell} | {f(med(B.get('sell')))} | {f(med(A.get('reset')))} | {f(med(B.get('reset')))} | "
                   f"{A.get('work', 0):,} | {B.get('work', 0):,} |")

    lat = json.loads((RESULTS / "latency.json").read_text())
    out.append("\n## Per-event processing latency (ns, nearest-rank percentiles, seed 42)\n")
    out.append("| version | scenario | M | p50 | p95 | p99 | max | early p50 | late p50 | early p99 | late p99 |")
    out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in [x for x in lat["runs"] if x.get("seed", 42) == 42]:
        if r["status"] != "ok":
            out.append(f"| {r['version']} | {r['scenario']} | {r['events']:,} | not attempted | | | | | | | |")
            continue
        a, e, l = r["all"], r["early_first_10pct"], r["late_last_10pct"]
        out.append(f"| {r['version']} | {r['scenario']} | {r['events']:,} | {a['p50_ns']:,} | {a['p95_ns']:,} | {a['p99_ns']:,} | "
                   f"{a['max_ns']:,} | {e['p50_ns']:,} | {l['p50_ns']:,} | {e['p99_ns']:,} | {l['p99_ns']:,} |")

    mem = read_csv(RESULTS / "memory.csv")
    out.append("\n## Memory (tracemalloc, seed 42; input excluded from replay peak)\n")
    out.append("| version | scenario | M | input bytes | replay peak bytes | book after (structures) | book after (incl. parsed ids/ints) | stored orders | bytes/order (incl.) |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    idx = {(r["version"], r["scenario"], r["events"], r["phase"]): r for r in mem if r["seed"] == "42"}
    for n in ("10000", "100000"):
        for scen in ("buildup", "crowded", "mixed", "sweep", "cancel_churn"):
            for v in ("A", "B"):
                pk = idx.get((v, scen, n, "replay_peak"))
                if not pk:
                    continue
                if pk["status"] != "ok" or (v, scen, n, "book_after") not in idx:
                    out.append(f"| {v} | {scen} | {int(n):,} | {pk['status']} | | | | |")
                    continue
                af, inp = idx[(v, scen, n, "book_after")], idx[(v, scen, n, "input")]
                full = idx.get((v, scen, n, "book_after_incl_input_objects"))
                whole = int(full["traced_current_bytes"]) if full else None
                so = int(af["active_orders_peak"])
                out.append(f"| {v} | {scen} | {int(n):,} | {int(inp['traced_current_bytes']):,} | {int(pk['traced_peak_bytes']):,} | "
                           f"{int(af['traced_current_bytes']):,} | {f'{whole:,}' if whole is not None else '–'} | {so:,} | "
                           f"{whole // so if so and whole is not None else '–'} |")

    spread = {}
    for r in lat["runs"]:
        if r["status"] == "ok" and r["version"] == "B" and r["events"] == 100000:
            spread.setdefault(r["scenario"], []).append((r["seed"], r["all"]["p50_ns"], r["all"]["p99_ns"]))
    if spread:
        out.append("\nLatency seed spread (Version B, 100,000 events; p50 / p99 ns per seed): " + "; ".join(
            f"{sc} " + ", ".join(f"s{sd} {p50}/{p99}" for sd, p50, p99 in sorted(v)) for sc, v in spread.items()))
    mspread = {}
    for r in mem:
        if r["phase"] == "book_after_incl_input_objects" and r["version"] == "B" and r["events"] == "100000" and r["status"] == "ok":
            mspread.setdefault(r["scenario"], []).append((r["seed"], int(r["traced_current_bytes"])))
    if mspread:
        out.append("\nMemory seed spread (Version B, 100,000 events, book incl. parsed objects, bytes): " + "; ".join(
            f"{sc} " + ", ".join(f"s{sd} {b:,}" for sd, b in sorted(v)) for sc, v in mspread.items()))
    oc = read_csv(RESULTS / "op_counts.csv") if (RESULTS / "op_counts.csv").exists() else []
    if oc:
        out.append("\n## Operation counts per replay (seed 42)\n")
        out.append("| scenario | M | A list entries visited | A per event | B steps | B per event |")
        out.append("|---|---|---|---|---|---|")
        d = {(r["version"], r["scenario"], r["events"]): r for r in oc}
        for n in ("1000", "10000", "100000"):
            for scen in ("buildup", "crowded", "mixed", "sweep", "cancel_churn"):
                a, b = d.get(("A", scen, n)), d.get(("B", scen, n))
                if not b:
                    continue
                aw = int(a["work_steps"]) if a and a["work_steps"] else None
                bw = int(b["work_steps"])
                out.append(f"| {scen} | {int(n):,} | {f'{aw:,}' if aw else 'not attempted'} | "
                           f"{f(aw / int(n), 4) if aw else '–'} | {bw:,} | {f(bw / int(n), 3)} |")
    st = read_csv(RESULTS / "revision_steps.csv") if (RESULTS / "revision_steps.csv").exists() else []
    if st:
        out.append("\n## Version B revision steps (100,000 events, seed 42, median ms of 5 replays)\n")
        out.append("| scenario | step 1 levels | step 2 + fast path | step 3 + list orders | step 3 vs 1 | identical |")
        out.append("|---|---|---|---|---|---|")
        for scen in ("buildup", "crowded", "mixed", "sweep", "cancel_churn"):
            m = [med([float(r["elapsed_s"]) for r in st if r["scenario"] == scen and r["version"] == v and r["status"] == "ok"])
                 for v in ("B_step1_levels", "B_step2_fastpath", "B_step3_lists")]
            same = all(r["note"].startswith("results identical") for r in st if r["scenario"] == scen)
            if all(m):
                out.append(f"| {scen} | {m[0]*1000:.1f} | {m[1]*1000:.1f} | {m[2]*1000:.1f} | {100*(m[2]/m[0]-1):+.0f}% | {same} |")
    (RESULTS / "summary.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))


if __name__ == "__main__":
    main()
