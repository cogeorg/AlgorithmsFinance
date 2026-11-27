"""Benchmark data phase: generate every dataset outside timing and describe it.

Called by run_benchmark.py (phase "data"). For each dataset it
  1. runs the professor's generator (00_instructions/generate_orders.py) into
     <out>/data/bench/<scenario>_M<events>_seed<seed>_L<levels>.jsonl.gz
     (gitignored) plus the generator's .metadata.json (kept),
  2. checks the file's sha256 against that metadata,
  3. replays it once on B-sorted (not timed) to record the dataset's
     properties: event mix, fills, peak active orders, peak occupied price
     levels, final book size, and the build prefix used by the sale tests.
Writes <out>/benchmark_datasets.csv (the manifest every later phase reads).

Datasets: the grid (5 scenarios x sizes x seeds, --levels 1000), buildup
with --levels 4 for queue concentration (same event count, 4 prices per
side), and the one-million-event mixed file (seed 43, README command).
"""

import json
import subprocess
import sys

from bench_common import (CONCENTRATED_LEVELS, GENERATOR, LEVELS, ROOT, SCENARIOS,
                          book_class, dataset_name, load_events, rel, sha256_file,
                          write_rows)

FIELDS = ["dataset", "kind", "file", "scenario", "events", "seed", "levels", "sha256",
          "compressed_bytes", "identical_events_to", "generator_command", "limits",
          "market_sells", "cancels", "rejected", "not_found_cancels", "fills",
          "peak_active_orders", "peak_price_levels", "final_book_size", "build_events",
          "build_active_orders", "build_price_levels", "build_bid_orders",
          "build_bid_price_levels", "build_bid_qty_units"]


def planned(cfg):
    out = []
    for m in cfg.sizes:
        for seed in cfg.seeds:
            for scenario in SCENARIOS:
                out.append(("grid", scenario, m, seed, LEVELS))
            out.append(("concentrated", "buildup", m, seed, CONCENTRATED_LEVELS))
    if cfg.million:
        mil = cfg.million
        out.append(("million", mil["scenario"], mil["events"], mil["seed"], mil["levels"]))
    return out


def build_prefix(scenario, events):
    """Events that build the book for a sale test (None: no sale test)."""
    if scenario == "sweep":
        return max(1, events * 4 // 5)      # the generator's sweep_start: LIMITs only
    if scenario == "buildup":
        return events
    return None


def describe(path, scenario, m):
    events = load_events(path)
    assert len(events) == m, (rel(path), len(events))
    book = book_class("b_sorted")()
    n_build = build_prefix(scenario, m)
    s = dict.fromkeys(["limits", "market_sells", "cancels", "rejected", "not_found_cancels",
                       "fills", "peak_active_orders", "peak_price_levels"], 0)
    build = dict.fromkeys(["build_events", "build_active_orders", "build_price_levels",
                           "build_bid_orders", "build_bid_price_levels",
                           "build_bid_qty_units"], "")
    for i, event in enumerate(events, 1):
        result = book.process_event(event)
        kind = event["type"]
        s["limits"] += kind == "LIMIT"
        s["market_sells"] += kind == "MARKET_SELL"
        s["cancels"] += kind == "CANCEL"
        s["rejected"] += result["status"] == "rejected"
        s["not_found_cancels"] += result["status"] == "not_found"
        s["fills"] += len(result.get("fills", ()))
        levels = len(book.levels["BUY"]) + len(book.levels["SELL"])
        s["peak_active_orders"] = max(s["peak_active_orders"], len(book.orders))
        s["peak_price_levels"] = max(s["peak_price_levels"], levels)
        if n_build and i <= n_build:
            assert kind == "LIMIT" and not result["fills"], "build prefix must not trade"
        if i == n_build:
            bids = book.levels["BUY"]
            build.update(build_events=n_build, build_active_orders=len(book.orders),
                         build_price_levels=levels,
                         build_bid_orders=sum(lv.live_count for lv in bids.values()),
                         build_bid_price_levels=len(bids),
                         build_bid_qty_units=sum(lv.live_qty for lv in bids.values()))
    s["final_book_size"] = len(book.orders)
    s.update(build)
    return s


def generate(cfg, scenario, m, seed, levels):
    path = cfg.data / f"{dataset_name(scenario, m, seed, levels)}.jsonl.gz"
    cmd = [sys.executable, str(GENERATOR), "--scenario", scenario, "--events", str(m),
           "--levels", str(levels), "--seed", str(seed), "--out", str(path)]
    subprocess.run(cmd, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    meta_path = path.with_name(path.name + ".metadata.json")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    sha = sha256_file(path)
    if sha != meta["sha256"]:
        raise RuntimeError(f"checksum mismatch for {rel(path)}")
    command = (f"python {rel(GENERATOR)} --scenario {scenario} --events {m} "
               f"--levels {levels} --seed {seed} --out {rel(path)}")
    return path, sha, meta["compressed_bytes"], command


def run(cfg):
    cfg.data.mkdir(parents=True, exist_ok=True)
    rows = []
    for kind, scenario, m, seed, levels in planned(cfg):
        path, sha, size, command = generate(cfg, scenario, m, seed, levels)
        row = {"dataset": dataset_name(scenario, m, seed, levels), "kind": kind,
               "file": rel(path), "scenario": scenario, "events": m, "seed": seed,
               "levels": levels, "sha256": sha, "compressed_bytes": size,
               "identical_events_to": "", "generator_command": command}
        row.update(describe(path, scenario, m))
        rows.append(row)
        print(f"  data {row['dataset']}: peak {row['peak_active_orders']} orders, "
              f"{row['peak_price_levels']} levels, {row['fills']} fills", flush=True)

    # The generator draws buildup prices with randrange(levels) and crowded with
    # randrange(4); with --levels 4 both streams can coincide. Record it.
    by_sha = {}
    for row in rows:
        by_sha.setdefault(row["sha256"], []).append(row["dataset"])
    for row in rows:
        twins = [d for d in by_sha[row["sha256"]] if d != row["dataset"]]
        row["identical_events_to"] = ";".join(twins)
    write_rows(cfg.out / "benchmark_datasets.csv", FIELDS, rows)
    print(f"  wrote {rel(cfg.out / 'benchmark_datasets.csv')} ({len(rows)} datasets)")
    return rows
