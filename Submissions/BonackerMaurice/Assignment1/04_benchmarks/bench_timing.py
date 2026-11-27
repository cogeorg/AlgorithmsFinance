"""Primary timing: replay grid, million-event attempt, large liquidation, and
the timing half of queue concentration. Also writes the timing summary.

Called by run_benchmark.py (phases "timing", "liquidation", "concentration",
"summary"). One child process per (dataset, version); the version order is
rotated from cell to cell. Definitions: bench_common.DEFINITIONS.

Child modes (internal):
    bench_timing.py --child replay <file> <version>
    bench_timing.py --child sale <file> <version> <build_events> <pct> [<pct> ...]
"""

import argparse
import gc
import statistics
import sys
import time

from bench_common import (REPEATS, SALE_PCTS, VERSIONS, WARMUPS, append_rows, book_class,
                          drop_rows, emit, load_timed, read_manifest, read_rows,
                          requested_qty, rotated, run_child, stop_note, write_rows)

RESULT_FIELDS = ["run_kind", "experiment", "version", "scenario", "seed", "levels",
                 "dataset_events", "events", "peak_active_orders", "peak_price_levels",
                 "sale_pct", "requested_qty_units", "fills", "makers_touched",
                 "price_levels_visited", "unfilled_qty_units", "phase", "repeat", "warmup",
                 "elapsed_seconds", "traced_peak_bytes", "traced_current_bytes", "status",
                 "note"]
SUMMARY_FIELDS = ["experiment", "version", "scenario", "seed", "levels", "dataset_events",
                  "events", "peak_active_orders", "peak_price_levels", "sale_pct",
                  "requested_qty_units", "fills", "makers_touched", "price_levels_visited",
                  "unfilled_qty_units", "phase", "repeats_ok", "repeats_planned",
                  "median_seconds", "min_seconds", "max_seconds", "spread_pct",
                  "throughput_events_per_s", "status", "note"]
STEPS = range(WARMUPS + REPEATS)        # 0 = warm-up, 1..5 timed


# ----- child side --------------------------------------------------------------

def child_replay(path, version):
    events, parse_s = load_timed(path)
    emit(row={"phase": "parse", "sale_pct": "", "repeat": 1, "elapsed_seconds": parse_s})
    cls = book_class(version)
    for r in STEPS:
        key = ["replay", "", r]
        emit(start=key)
        book = cls()
        process = book.process_event
        fills = 0
        gc.collect()
        gc.disable()
        start = time.perf_counter()
        for event in events:
            fills += len(process(event).get("fills", ()))
        elapsed = time.perf_counter() - start
        gc.enable()
        emit(stop=key)
        final = len(book.inspect_book())              # check, outside the timer
        emit(row={"phase": "replay", "sale_pct": "", "repeat": r,
                  "elapsed_seconds": elapsed, "fills": fills, "final_book_size": final})
        del process, book


def child_sale(path, version, n_build, pcts):
    events, parse_s = load_timed(path)
    emit(row={"phase": "parse", "sale_pct": "", "repeat": 1, "elapsed_seconds": parse_s})
    build = events[:n_build]
    del events
    assert all(e["type"] == "LIMIT" for e in build)
    total = sum(e["qty_units"] for e in build if e["side"] == "BUY")
    next_seq = build[-1]["seq"] + 1
    cls = book_class(version)
    for pct in pcts:
        qty = requested_qty(pct, total)
        sale = {"seq": next_seq, "event_id": f"liquidation_{pct}pct", "type": "MARKET_SELL",
                "order_id": f"liq_{pct}pct", "qty_units": qty}
        for r in STEPS:
            key = ["build", pct, r]
            emit(start=key)
            book = cls()
            process = book.process_event
            gc.collect()
            gc.disable()
            start = time.perf_counter()
            for event in build:
                process(event)
            build_s = time.perf_counter() - start
            gc.enable()
            emit(stop=key)
            emit(row={"phase": "build", "sale_pct": pct, "repeat": r,
                      "elapsed_seconds": build_s})

            key = ["sell", pct, r]
            emit(start=key)
            gc.collect()
            gc.disable()
            start = time.perf_counter()
            result = process(sale)
            sell_s = time.perf_counter() - start
            gc.enable()
            emit(stop=key)
            # Checks and counts, outside the timer.
            fills = result["fills"]
            sold = sum(f["qty_units"] for f in fills)
            bids_after = sum(o["qty_units"] for o in book.inspect_book() if o["side"] == "BUY")
            problems = []
            if sold + result["unfilled_qty_units"] != qty:
                problems.append("sold + unfilled != requested")
            if bids_after != total - sold:
                problems.append("bid quantity not conserved")
            if pct >= 100 and bids_after != 0:
                problems.append("bids left after a full sale")
            emit(row={"phase": "sell", "sale_pct": pct, "repeat": r, "elapsed_seconds": sell_s,
                      "requested_qty_units": qty, "fills": len(fills),
                      "makers_touched": len({f["maker_id"] for f in fills}),
                      "price_levels_visited": len({f["price_ticks"] for f in fills}),
                      "unfilled_qty_units": result["unfilled_qty_units"],
                      "check": "; ".join(problems)})
            del process, book, result, fills


# ----- parent side ---------------------------------------------------------------

def base_row(ds, version, experiment):
    return {"run_kind": "timing", "experiment": experiment, "version": version,
            "scenario": ds["scenario"], "seed": ds["seed"], "levels": ds["levels"],
            "dataset_events": ds["events"], "events": "", "peak_active_orders": "",
            "peak_price_levels": "", "sale_pct": "", "requested_qty_units": "", "fills": "",
            "makers_touched": "", "price_levels_visited": "", "unfilled_qty_units": "",
            "phase": "", "repeat": "", "warmup": "", "elapsed_seconds": "",
            "traced_peak_bytes": "", "traced_current_bytes": "", "status": "", "note": ""}


def fill_phase(row, ds, phase, pct):
    """Event count and book peaks that belong to this phase."""
    row["phase"] = phase
    row["sale_pct"] = pct
    if phase in ("parse", "replay"):
        row["events"] = ds["events"]
    if phase == "replay":
        row["peak_active_orders"] = ds["peak_active_orders"]
        row["peak_price_levels"] = ds["peak_price_levels"]
    if phase in ("build", "sell"):
        row["events"] = ds["build_events"] if phase == "build" else 1
        row["peak_active_orders"] = ds["build_active_orders"]
        row["peak_price_levels"] = ds["build_price_levels"]


def measured_row(cfg, ds, base, m):
    row = dict(base)
    fill_phase(row, ds, m["phase"], m["sale_pct"])
    row["repeat"] = m["repeat"]
    row["warmup"] = m["phase"] != "parse" and m["repeat"] < WARMUPS
    for k in ("requested_qty_units", "fills", "makers_touched", "price_levels_visited",
              "unfilled_qty_units"):
        if k in m:
            row[k] = m[k]
    row["elapsed_seconds"] = f"{m['elapsed_seconds']:.9f}"
    row["status"] = "ok"
    problems = []
    if m["phase"] == "replay":
        if m["fills"] != ds["fills"]:
            problems.append(f"fills {m['fills']} != manifest {ds['fills']}")
        if m["final_book_size"] != ds["final_book_size"]:
            problems.append(f"final book {m['final_book_size']} != "
                            f"manifest {ds['final_book_size']}")
    if m.get("check"):
        problems.append(m["check"])
    if problems:
        row["status"] = "mismatch"
        row["note"] = "; ".join(problems)
    if m["phase"] != "parse" and m["elapsed_seconds"] > cfg.time_limit:
        row["status"] = "stopped"
        row["note"] = (f"stopped: finished in {m['elapsed_seconds']:.3g} s, above the "
                       f"{cfg.time_limit:g} s limit; value not used")
        row["elapsed_seconds"] = ""
    return row


def run_cell(cfg, ds, version, experiment, mode, extra, planned):
    """One child for one (dataset, version); returns True if it was stopped."""
    base = base_row(ds, version, experiment)
    recorded = set()

    def on_message(message):
        if "row" not in message:
            return False
        row = measured_row(cfg, ds, base, message["row"])
        append_rows(cfg.results_csv, RESULT_FIELDS, [row])
        m = message["row"]
        key = (m["phase"], m["sale_pct"], m["repeat"])
        recorded.add(key)
        return key if row["status"] == "stopped" else False

    stopped = run_child("bench_timing.py", [mode, ds["file"], version, *extra],
                        cfg.time_limit, on_message)
    if stopped:
        rows = []
        for key in planned:
            if key in recorded:
                continue
            phase, pct, r = key
            row = dict(base)
            fill_phase(row, ds, phase, pct)
            row.update(repeat=r, warmup=phase != "parse" and r < WARMUPS, status="stopped",
                       note=stop_note(stopped, key, cfg.time_limit))
            rows.append(row)
        append_rows(cfg.results_csv, RESULT_FIELDS, rows)
    print(f"  {experiment:13s} {ds['dataset']:34s} {version:8s} "
          f"{'STOPPED' if stopped else 'ok'}", flush=True)
    return bool(stopped)


def replay_cell(cfg, ds, version, experiment):
    planned = [("parse", "", 1)] + [("replay", "", r) for r in STEPS]
    return run_cell(cfg, ds, version, experiment, "replay", [], planned)


def sale_cell(cfg, ds, version, experiment, pcts):
    planned = [("parse", "", 1)] + [(phase, pct, r) for pct in pcts for r in STEPS
                                    for phase in ("build", "sell")]
    return run_cell(cfg, ds, version, experiment, "sale", [ds["build_events"], *pcts],
                    planned)


def _clear(cfg, experiments):
    drop_rows(cfg.results_csv, RESULT_FIELDS,
              lambda r: r["run_kind"] == "timing" and r["experiment"] in experiments)


def run_replays(cfg):
    """Phase timing: the grid (5 scenarios x sizes x seeds) and the million file."""
    _clear(cfg, {"replay", "million"})
    manifest = read_manifest(cfg)
    grid = [d for d in manifest if d["kind"] == "grid"]
    for i, ds in enumerate(grid):
        for version in rotated(VERSIONS, i):
            replay_cell(cfg, ds, version, "replay")
    for ds in (d for d in manifest if d["kind"] == "million"):
        for version in VERSIONS:      # A too: the same limit decides
            replay_cell(cfg, ds, version, "million")


def run_liquidation(cfg):
    """Phase liquidation: first 80% of every sweep file, then 10/100/200% sales."""
    _clear(cfg, {"liquidation"})
    sweeps = [d for d in read_manifest(cfg) if d["kind"] == "grid" and d["scenario"] == "sweep"]
    for i, ds in enumerate(sweeps):
        for version in rotated(VERSIONS, i):
            sale_cell(cfg, ds, version, "liquidation", SALE_PCTS)


# ----- summary -------------------------------------------------------------------

GROUP = ["experiment", "version", "scenario", "seed", "levels", "dataset_events", "sale_pct",
         "phase"]
CARRY = ["events", "peak_active_orders", "peak_price_levels", "requested_qty_units", "fills",
         "makers_touched", "price_levels_visited", "unfilled_qty_units"]


def write_summary(cfg):
    groups = {}
    for r in read_rows(cfg.results_csv):
        if r["run_kind"] == "timing" and r["warmup"] != "True":
            groups.setdefault(tuple(r[k] for k in GROUP), []).append(r)
    out = []
    for key, rows in groups.items():
        planned = 1 if key[-1] == "parse" else REPEATS
        ok = [float(r["elapsed_seconds"]) for r in rows if r["status"] == "ok"]
        statuses = {r["status"] for r in rows}
        row = dict(zip(GROUP, key))
        first = next((r for r in rows if r["status"] == "ok"), rows[0])
        row.update({k: first[k] for k in CARRY})
        row.update(repeats_ok=len(ok), repeats_planned=planned, median_seconds="",
                   min_seconds="", max_seconds="", spread_pct="", throughput_events_per_s="",
                   note="")
        if statuses == {"ok"} and len(ok) == planned:
            med = statistics.median(ok)
            row.update(status="ok", median_seconds=f"{med:.9f}", min_seconds=f"{min(ok):.9f}",
                       max_seconds=f"{max(ok):.9f}")
            if med > 0:
                row["spread_pct"] = f"{100 * (max(ok) - min(ok)) / med:.1f}"
                if key[-1] in ("replay", "build"):
                    row["throughput_events_per_s"] = f"{int(row['events']) / med:.1f}"
        else:
            row["status"] = "mismatch" if "mismatch" in statuses else "stopped"
            row["note"] = next((r["note"] for r in rows if r["status"] != "ok"), "")
        out.append(row)
    write_rows(cfg.out / "benchmark_summary.csv", SUMMARY_FIELDS, out)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", nargs="+", required=True)
    args = parser.parse_args()
    mode, path, version, *rest = args.child
    if mode == "replay":
        child_replay(path, version)
    elif mode == "sale":
        child_sale(path, version, int(rest[0]), [int(p) for p in rest[1:]])
    else:
        sys.exit(f"unknown child mode {mode}")


if __name__ == "__main__":
    main()
