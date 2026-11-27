"""Queue concentration: the same order count on 4 vs 1,000 prices per side.

Called by run_benchmark.py (phase "concentration"). Streams: buildup with
--levels 4 and with --levels 1000, same M and seed (every event a resting
LIMIT; buys and sells never cross). With 4 levels the queues are long
(about M/8 orders per price); with 1,000 they are short.

1. Speed (timing rows, experiment "concentration"): build the whole book,
   then sell 100% of its bid quantity in one MARKET_SELL; fresh book for
   every repeat; same timing protocol as the liquidation test.
2. Price-time correctness (concentration_check.csv): every version replays
   the stream event by event; results are compared after every event, the
   canonical books (inspect_book) and assert_invariants() at 10 checkpoints
   and at the end. Then the same full sale runs on every book and is checked
   with invariants.check_event, whose oracle derives the expected fills from
   the canonical book before the sale (price first, then arrival). Version A
   takes part up to M = 10,000; at 100,000 B-sorted and B-heap are compared
   (A's replay alone exceeds the time limit there, see the timing rows).
"""

from bench_common import (CONCENTRATION_SALE_PCT, ROOT, VERSIONS, append_rows,
                          book_class, drop_rows, read_manifest, rel, requested_qty, rotated,
                          write_rows)
from bench_timing import RESULT_FIELDS, sale_cell
from invariants import check_event
from replay import load_events

FIELDS = ["dataset", "scenario", "levels", "seed", "events", "versions", "events_compared",
          "book_checkpoints", "mismatches", "invariant_failures", "sale_qty_units",
          "sale_fills", "sale_price_levels", "max_fills_at_one_price", "sale_check", "result",
          "first_problem"]
A_MAX_EVENTS = 10_000


def check_stream(ds):
    versions = VERSIONS if ds["events"] <= A_MAX_EVENTS else ["b_sorted", "b_heap"]
    events = load_events(ROOT / ds["file"])
    books = {v: book_class(v)() for v in versions}
    ref = versions[0]
    every = max(1, len(events) // 10)
    mismatches = invariant_failures = checkpoints = 0
    problems = []

    def note(text):
        if not problems:
            problems.append(text)

    for i, event in enumerate(events, 1):
        results = {v: b.process_event(event) for v, b in books.items()}
        if any(results[v] != results[ref] for v in versions):
            mismatches += 1
            note(f"event {i}: results differ")
        if i % every == 0 or i == len(events):
            checkpoints += 1
            snaps = {v: b.inspect_book() for v, b in books.items()}
            if any(snaps[v] != snaps[ref] for v in versions):
                mismatches += 1
                note(f"event {i}: books differ")
            for v, b in books.items():
                try:
                    b.assert_invariants()
                except AssertionError as exc:
                    invariant_failures += 1
                    note(f"event {i}: {v} invariant: {exc}")

    # Full sale through the (long) queues, checked against the priority oracle.
    total = sum(o["qty_units"] for o in books[ref].inspect_book() if o["side"] == "BUY")
    qty = requested_qty(CONCENTRATION_SALE_PCT, total)
    sale = {"seq": events[-1]["seq"] + 1, "event_id": "concentration_sale",
            "type": "MARKET_SELL", "order_id": "concentration_sale", "qty_units": qty}
    sale_check = "pass"
    sale_results = {}
    for v, b in books.items():
        before = b.inspect_book()
        sale_results[v] = b.process_event(sale)
        try:
            check_event(before, sale, sale_results[v], b.inspect_book())
        except AssertionError as exc:
            sale_check = "fail"
            note(f"sale: {v}: {exc}")
    if any(sale_results[v] != sale_results[ref] for v in versions):
        mismatches += 1
        note("sale: results differ")
    fills = sale_results[ref]["fills"]
    per_price = {}
    for f in fills:
        per_price[f["price_ticks"]] = per_price.get(f["price_ticks"], 0) + 1
    ok = mismatches == 0 and invariant_failures == 0 and sale_check == "pass"
    return {"dataset": ds["dataset"], "scenario": ds["scenario"], "levels": ds["levels"],
            "seed": ds["seed"], "events": ds["events"], "versions": ";".join(versions),
            "events_compared": len(events), "book_checkpoints": checkpoints,
            "mismatches": mismatches, "invariant_failures": invariant_failures,
            "sale_qty_units": qty, "sale_fills": len(fills),
            "sale_price_levels": len(per_price),
            "max_fills_at_one_price": max(per_price.values(), default=0),
            "sale_check": sale_check, "result": "pass" if ok else "fail",
            "first_problem": problems[0] if problems else ""}


def run(cfg):
    drop_rows(cfg.results_csv, RESULT_FIELDS,
              lambda r: r["run_kind"] == "timing" and r["experiment"] == "concentration")
    cells = [d for d in read_manifest(cfg)
             if d["scenario"] == "buildup" and d["kind"] in ("grid", "concentrated")]
    cells.sort(key=lambda d: (d["events"], d["seed"], d["levels"]))
    for i, ds in enumerate(cells):
        for version in rotated(VERSIONS, i):
            sale_cell(cfg, ds, version, "concentration", [CONCENTRATION_SALE_PCT])

    out = cfg.out / "concentration_check.csv"
    write_rows(out, FIELDS, [])
    for ds in cells:
        row = check_stream(ds)
        append_rows(out, FIELDS, [row])
        print(f"  check {ds['dataset']:34s} {row['versions']:18s} {row['result']}", flush=True)
    print(f"  wrote {rel(out)}")
