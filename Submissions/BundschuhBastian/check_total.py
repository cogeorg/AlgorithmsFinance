"""Consistency check of the saved timing results: is `total` close to prepare + query?

    .venv/bin/python check_total.py            # reads results/timing_summary.csv
                                               # writes results/total_consistency.csv
                                               # adds a note to results/timing_metadata.json

Per configuration (n, q, hit rate, method):
    ratio        = median(total) / (median(prepare) + median(query))
    spread_*     = max / min of the repeats of that phase (1.0 = identical repeats)
    ranges_overlap = [min total, max total] overlaps
                     [min prepare + min query, max prepare + max query]
Nothing is measured here. The measurement protocol of bench_time.py is not changed.
"""
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
KEY = ("n", "q", "hit_rate", "method")

EXPLANATION = (
    "'total' is measured on its own (method(ids, queries) called k times per repeat), "
    "not as the sum of 'prepare' and 'query'. The three phases run as separate blocks of "
    "repeats at different moments, so total and prepare + query can differ. "
    "Measured causes: (1) timing noise inside a block: repeats of one phase differ "
    "(spread = max/min of the repeats); (2) variation BETWEEN blocks: prepare(ids) does "
    "exactly the same work for every q and hit rate (same seed, same ids), yet its median "
    "differs between these blocks (see prepare_variation_between_blocks); this is slower "
    "or faster machine state at that moment, and it is larger than the spread of the "
    "repeats inside one block. (3) Calibration picks its own number of calls k per phase. "
    "Possible but NOT tested: cache state of the sorted list or set differs between "
    "'query' (state built before the repeat) and 'total' (queries run right after "
    "preparation). Tested and not supported: that building a set while the previous one "
    "is still alive (as in the 'prepare' phase) is slower than discarding it at once "
    "(6.8 vs 6.8 ms at n = 100000). "
    "Check: if the [min, max] range of 'total' overlaps the range of the summed phases, "
    "the difference is inside the repeat-to-repeat variation; in some configurations it "
    "does not (counted in ranges_do_not_overlap), so within-block spread alone does not "
    "explain every difference. A ratio far from 1 is a measure of how large the noise of "
    "this measurement is, not an error in the algorithms."
)


def load(path):
    with path.open() as handle:
        return list(csv.DictReader(handle))


def compute(summary_rows):
    """Return one dict per configuration from rows of timing_summary.csv."""
    cells = {}
    for row in summary_rows:
        key = tuple(row[k] for k in KEY)
        cells.setdefault(key, {})[row["phase"]] = row
    result = []
    for key, phases in cells.items():
        if not {"prepare", "query", "total"} <= set(phases):
            raise ValueError(f"missing phase for {key}")
        value = lambda phase, field: float(phases[phase][field + "_seconds_per_batch"])  # noqa: E731
        prepare, query, total = (value(p, "median") for p in ("prepare", "query", "total"))
        sum_min = value("prepare", "min") + value("query", "min")
        sum_max = value("prepare", "max") + value("query", "max")
        entry = dict(zip(KEY, key))
        entry.update({
            "median_prepare": prepare, "median_query": query,
            "median_sum": prepare + query, "median_total": total,
            "ratio_total_over_sum": total / (prepare + query),
            "spread_prepare": value("prepare", "max") / value("prepare", "min"),
            "spread_query": value("query", "max") / value("query", "min"),
            "spread_total": value("total", "max") / value("total", "min"),
            "ranges_overlap": value("total", "min") <= sum_max and sum_min <= value("total", "max"),
        })
        result.append(entry)
    return result


def summarize(entries):
    ratios = [e["ratio_total_over_sum"] for e in entries]
    return {
        "configurations": len(entries),
        "ratio_min": min(ratios), "ratio_max": max(ratios),
        "below_0.97": sum(r < 0.97 for r in ratios),
        "above_1.03": sum(r > 1.03 for r in ratios),
        "within_3_percent": sum(0.97 <= r <= 1.03 for r in ratios),
        "ranges_overlap": sum(e["ranges_overlap"] for e in entries),
        "ranges_do_not_overlap": sum(not e["ranges_overlap"] for e in entries),
    }


def prepare_variation(summary_rows):
    """Same operation, different blocks: max/min of the prepare medians over all (q, hit
    rate) blocks, per (method, n). Linear search has no preparation and is skipped."""
    groups = {}
    for row in summary_rows:
        if row["phase"] == "prepare" and row["algorithm"] != "linear":
            groups.setdefault((row["method"], row["n"]), []).append(
                float(row["median_seconds_per_batch"]))
    return {f"{method} n={n}": {"blocks": len(v), "max_over_min": max(v) / min(v)}
            for (method, n), v in sorted(groups.items())}


def main():
    results = HERE / "results"
    summary_rows = load(results / "timing_summary.csv")
    entries = compute(summary_rows)
    variation = prepare_variation(summary_rows)
    entries.sort(key=lambda e: (e["method"], int(e["n"]), int(e["q"]), e["hit_rate"]))
    with (results / "total_consistency.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(entries[0].keys()))
        writer.writeheader()
        writer.writerows(entries)
    stats = summarize(entries)
    metadata_path = results / "timing_metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["total_vs_prepare_plus_query"] = {
        "added_by": "check_total.py after the measurement run; the protocol was not changed",
        "explanation": EXPLANATION, "check_file": "total_consistency.csv", **stats,
        "prepare_variation_between_blocks": variation}
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(stats, indent=2))
    print("same prepare work, different blocks (max/min of medians):")
    for name, v in variation.items():
        print(f"  {name}: {v['max_over_min']:.2f} over {v['blocks']} blocks")
    worst = sorted(entries, key=lambda e: abs(e["ratio_total_over_sum"] - 1), reverse=True)[:5]
    for e in worst:
        print(f"ratio {e['ratio_total_over_sum']:.3f}  {e['method']} n={e['n']} q={e['q']} "
              f"{e['hit_rate']}  spreads prepare/query/total = "
              f"{e['spread_prepare']:.2f}/{e['spread_query']:.2f}/{e['spread_total']:.2f}  "
              f"overlap={e['ranges_overlap']}")


if __name__ == "__main__":
    main()
