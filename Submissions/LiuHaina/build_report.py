"""Write the English lab report from saved measurements without rerunning them."""

import hashlib
import json
from pathlib import Path
import statistics

from dashboard import build_payload

BASE = Path(__file__).resolve().parent
METHODS = ("linear_search", "binary_search", "hash_set_search")
NAMES = dict(linear_search="Linear search", binary_search="Binary search", hash_set_search="Hash set")


def table(headers, rows):
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *("| " + " | ".join(map(str, row)) + " |" for row in rows),
    ])


def main():
    payload = build_payload(BASE / "results")
    if payload["source_mismatches_at_build"]:
        raise ValueError("Measured source changed: " + str(payload["source_mismatches_at_build"]))
    meta = payload["metadata"]
    data = json.loads((BASE / "data/inputs.json").read_text())
    if hashlib.sha256((BASE / "data/inputs.json").read_bytes()).hexdigest() != meta["input_sha256"]:
        raise ValueError("Saved inputs differ from the measured inputs")
    timing = {(r["case_id"], r["version"], r["method"], r["metric"]): r for r in payload["summary"]}
    memory = {(r["case_id"], r["version"], r["method"]): r for r in payload["memory"]}
    def row(n, q, scenario, method, version="revised", metric="total"):
        return timing[(f"n{n}_q{q}_{scenario}", version, method, metric)]
    def seconds(n, q, scenario, method, version="revised", metric="total"):
        return row(n, q, scenario, method, version, metric)["median_seconds"]
    def ms(*args, **kwargs):
        return f"{seconds(*args, **kwargs) * 1000:.6f}"

    arrays = table(["Array length n", "Distinct IDs", "Duplicate entries beyond first occurrences"], [
        [f"{a['n']:,}", f"{a['distinct_count']:,}", f"{a['n'] - a['distinct_count']:,}"]
        for a in data["arrays"].values()])
    mixed = table(["n", *[NAMES[m] + " (ms)" for m in METHODS]], [
        [f"{n:,}", *[ms(n, 100, "mixed", m) for m in METHODS]] for n in (1000, 10000, 100000)])
    single = table(["n", "Scenario", *[NAMES[m] + " (ms)" for m in METHODS]], [
        [f"{n:,}", scenario.replace("_", " "), *[ms(n, 1, scenario, m) for m in METHODS]]
        for n in (1000, 10000, 100000) for scenario in ("all_present", "all_absent")])
    phases = table(["Method", "Preparation (ms)", "Query batch (ms)", "Total (ms)"], [
        [NAMES[m], *[ms(100000, 100, "mixed", m, metric=metric)
                     for metric in ("preparation", "query_batch", "total")]] for m in METHODS])
    hits = table(["Scenario", *[NAMES[m] + " (ms)" for m in METHODS]], [
        [scenario.replace("_", " "), *[ms(100000, 100, scenario, m) for m in METHODS]]
        for scenario in ("all_present", "mixed", "all_absent")])
    versions = table(["Method", "Original total (ms)", "Revised total (ms)", "Original / Revised"], [
        [NAMES[m], ms(100000, 100, "mixed", m, "original"), ms(100000, 100, "mixed", m),
         f"{seconds(100000, 100, 'mixed', m, 'original') / seconds(100000, 100, 'mixed', m):.3f}x"] for m in METHODS])
    empty_rows = []
    for n in (1000, 10000, 100000):
        for method in ("binary_search", "hash_set_search"):
            original_mem = memory[(f"n{n}_q0_empty", "original", method)]
            revised_mem = memory[(f"n{n}_q0_empty", "revised", method)]
            empty_rows.append([f"{n:,}", NAMES[method], ms(n, 0, "empty", method, "original"),
                               f"{seconds(n, 0, 'empty', method) * 1000:.7f}",
                               f"{original_mem['peak_traced_bytes']/1024:.3f}",
                               f"{revised_mem['peak_traced_bytes']/1024:.3f}"])
    empty = table(["n", "Method", "Original total (ms)", "Revised total (ms)",
                   "Original peak (KiB)", "Revised peak (KiB)"], empty_rows)
    mem = table(["Method", "Version", "Current traced (KiB)", "Peak traced (KiB)"], [
        [NAMES[m], version.title(),
         f"{memory[('n100000_q100_mixed', version, m)]['current_traced_bytes']/1024:.3f}",
         f"{memory[('n100000_q100_mixed', version, m)]['peak_traced_bytes']/1024:.3f}"]
        for m in METHODS for version in ("original", "revised")])
    ratios = [seconds(c["n"], c["q"], c["scenario"], m, "original") /
              seconds(c["n"], c["q"], c["scenario"], m)
              for c in data["cases"] if not c["supplementary"] for m in METHODS]
    single_cases = [c for c in data["cases"] if c["q"] == 1]
    batch_cases = [c for c in data["cases"] if c["q"] == 100]
    def winner(case):
        return min(METHODS, key=lambda m: seconds(case["n"], case["q"], case["scenario"], m))
    linear_wins = sum(winner(c) == "linear_search" for c in single_cases)
    hash_wins = sum(winner(c) == "hash_set_search" for c in batch_cases)
    single_findings = f"Linear search had the lowest revised total in {linear_wins} of {len(single_cases)} single-query cases."
    exceptions = [f"n = {c['n']:,}, {c['scenario'].replace('_', ' ')}: {NAMES[winner(c)]}"
                  for c in single_cases if winner(c) != "linear_search"]
    if exceptions:
        single_findings += " Other winners were " + "; ".join(exceptions) + "."
    batch_findings = f"Hash sets had the lowest revised total time in {hash_wins} of {len(batch_cases)} tested q = 100 cases across sizes and hit scenarios."
    distinct_large = data["arrays"]["n100000"]["distinct_count"]
    report = f'''# Membership Search Implementation and Performance Report

**Student:** Liu Haina  
**Course:** Algorithms in Finance  
**Experiment date:** 20 November 2026  
**Scope:** Phase 1 implementation, correctness checks, revision, and performance evaluation

The three methods solve the same integer membership problem while preserving the input array and query order. In this experiment, the revised hash-set method had the lowest total time in {hash_wins} of {len(batch_cases)} tested configurations with 100 queries. For one query, linear search had the lowest total in {linear_wins} of {len(single_cases)} configurations and avoided preparation. The revision removed unnecessary sorting and set construction for empty query batches; nonempty-workload comparisons are evaluated below.

## Task and implementations

Each public function accepts an integer ID list and an ordered query list, returning one Python Boolean per query. For example, IDs `[7, 11, 7]` and queries `[11, 9, 7]` must produce `[True, False, True]` without changing the ID list.

Linear search explicitly scans the array until it finds the current query or exhausts the array. Binary search creates a sorted copy with `sorted(array)` and uses a handwritten iterative search. Hash-set membership constructs a standard-library `set` and evaluates membership for each query. Both search procedures are implemented directly in Python.

For nonempty inputs, the expected resource tradeoffs are:

| Method | Preparation | Complete query batch | Additional prepared storage |
| --- | --- | --- | --- |
| Linear search | O(1) | O(nq) worst case | O(1) |
| Binary search | O(n log n) worst case | O(q log n) | O(n) |
| Hash set | Expected O(n) | Expected O(q) | O(u), for u distinct IDs |

All methods also allocate the required O(q) output. Hash-set bounds assume well-distributed hashes and are not worst-case guarantees. The storage column excludes required output and given input; the traced-memory measurements below have a different, explicitly stated scope.

## Correctness evidence

The tests were written before implementation using Python's `unittest`. The initial run recorded 39 failing subtests because all three functions were missing. After implementation, the same 13 test methods passed for each version, with each test applied to all three methods. The expected results were not weakened.

The suite checks empty arrays and queries, a single entry, duplicates, unsorted inputs, first and last matches, gaps and absent values, negative and large integers, Boolean output types, query order, unchanged input, and repeated calls without stale state. The staged versions and both pre-refactoring snapshots pass the same suite. Separately, all 18 saved input cases were checked against independently computed set-membership answers for both versions and three methods, giving 108 successful end-to-end validations. The benchmark also checks stage results before timing. These checks provide evidence rather than a proof of correctness.

Evidence files are `test_baseline.txt`, `test_implementation.txt`, `test_revision.txt`, `test_stages.txt`, and `data_validation.txt`.

## Synthetic inputs and experiment design

The generator uses base seed {meta['generator']['base_seed']} and Python's `random.Random`. The same saved array and ordered query values are supplied to every method and version. Array entries are drawn uniformly with replacement from `range(n//2)`, producing the following saved arrays:

{arrays}

The required feasible workload consists of n in {{1,000, 10,000, 100,000}}, q in {{1, 100}}, and all-present, all-absent, or mixed queries. Mixed batches contain exactly 50 hits and 50 misses. A single query cannot contain both a hit and a miss, so the three q = 1 mixed combinations are explicitly recorded as infeasible rather than reported as mixed observations. This leaves 15 main cases. Three supplementary q = 0 cases assess the revision, giving 18 cases and 108 method/version configurations.

Hit queries sample existing array positions with replacement, making frequent IDs more likely to be queried. Misses are sampled from negative integers while arrays contain only nonnegative IDs; query order is shuffled. This guarantees the intended hit rates, but the misses are outside the array's value range and do not represent every possible search difficulty. `data/inputs.json` records the values, seeds, generation policy, actual hit counts, distinct counts, expected answers, and array hashes. Empty batches have an undefined hit rate recorded as null.

## Measurement protocol

The measurement environment was CPython {meta['generator']['python_version']} on `{meta['platform']}`, with {meta['logical_cpu_count']} logical CPU cores. No container was used. The benchmark measured the staged `search_original.py` and `search.py` sources identified by SHA-256 hashes in `results/metadata.json`. The recorded repository HEAD is `{meta['git_head']}`; local measured files may be uncommitted, so that HEAD alone does not identify the full measured implementation.

Timing uses `time.perf_counter()`. Each metric receives an untimed warm-up and calibration, followed by five recorded repeats. Short operations are grouped toward 3 ms, capped at 8,192 calls, and divided by the call count. The reported statistic is the median elapsed seconds per complete query batch, not per individual query. Tables below convert these medians to milliseconds.

Preparation calls the actual `prepare_*` function, including sorting, set construction, or revised early checks. Query-batch timing calls the actual `query_*` function after preparation; each recorded repeat receives fresh state, reused read-only within its group. Total timing independently invokes the public function with fresh preparation on every call. The metrics are separate experiments, so their medians need not add exactly. Configuration order is shuffled with seed 2026, while the five repeats for each metric run consecutively.

Input loading, generation, copying, validation, printing, memory tracing, profiling, and dashboard rendering are excluded from timed regions. Loop and function-call overhead and release of previous grouped results remain included. The final result remains alive until the timer stops. For phase separation, both versions expose preparation/query helpers; pre-refactoring sources remain under `snapshots/`. The extra helper calls can affect very short operations, and the tables describe the staged implementations.

Memory is measured after all timing using a fresh `tracemalloc` run per configuration. Inputs exist before tracing and are excluded. Preparation and query execution are included, with prepared state and output kept alive at reading. Current and peak values represent traced Python allocations, not total process RSS, all native allocations, or auxiliary space alone. Each configuration has one memory observation. KiB means 1,024 bytes.

## Runtime results

### Preparation cost changes the comparison

For the revised implementation with n = 100,000, q = 100, and 50% hits:

{phases}

Hash-set membership has a low query-batch cost, but constructing the set still costs time. Binary search also answers the batch much faster than linear scanning once prepared, but sorting dominates its total for this workload. Excluding preparation would therefore give an incomplete comparison of independent calls.

### Workload size and hit rate

Revised total times for q = 100 and 50% hits are:

{mixed}

{batch_findings} For example, at n = 100,000 with mixed queries, its total was {ms(100000,100,'mixed','hash_set_search')} ms, compared with {ms(100000,100,'mixed','binary_search')} ms for binary search and {ms(100000,100,'mixed','linear_search')} ms for linear search. These observations apply to the saved workloads and this machine; they do not establish a universal crossover point.

For q = 1, preparation can outweigh a faster membership operation:

{single}

{single_findings} Comparisons depend on preparation cost, query position, and measurement overhead. One sampled query per hit scenario is insufficient to characterize all single-query behavior.

At n = 100,000 and q = 100, revised totals vary with the hit scenario:

{hits}

Linear search can stop early for present IDs, whereas every absent query scans the entire array. Its total therefore rises from the all-present to mixed to all-absent workload. Binary-search and hash-set totals change much less because their preparation costs dominate at this batch size.

## Revision results

The revision adds an empty-input check before preparation. With zero queries, the revised version skips sorting and set construction. With an empty array, it constructs the required all-false output directly. In the measured staged implementation, preparation returns a `None` state for these cases and the query phase constructs the output; the public interface remains unchanged.

For the main example n = 100,000, q = 100, and mixed queries:

{versions}

Across the 45 main method/workload comparisons, Original / Revised ranges from {min(ratios):.3f}x to {max(ratios):.3f}x, with a descriptive median of {statistics.median(ratios):.3f}x. Values occur on both sides of 1. The search logic for nonempty inputs is unchanged apart from extra checks, so this run does not support a consistent improvement for the required nonempty workloads. The pooled ratio is descriptive, not a statistical significance test.

The targeted supplementary empty-query cases show a different result:

{empty}

Here the original binary-search and hash-set versions still prepare unused structures. The revision removes this work and its large allocation peaks. Revised timings are sub-microsecond and strongly affected by wrapper/loop overhead, so the important conclusion is that the O(n log n) sorting or expected O(n) set-building work is avoided, rather than a precise large speedup factor. Original linear search already performs almost no work for zero queries; adding checks does not provide the same benefit. Empty-array behavior is covered by correctness tests but was not separately benchmarked.

## Memory results

For n = 100,000, q = 100, and mixed queries:

{mem}

Linear search retains only small new working objects and the required output. Binary search allocates a sorted list of references plus sorting workspace; existing integer objects belong to the pre-existing input and are not newly traced. The set representation has a larger peak for this saved input, containing {distinct_large:,} distinct IDs. The original and revised versions retain the same kinds of preparation structures for this nonempty example. The revision's substantial memory benefit occurs when those structures can be skipped, as shown in the empty-query table.

## Reproduction and dashboard

From the repository root, run:

```bash
cd Submissions/LiuHaina
python3 -B run_tests.py
python3 -B validate_data.py
python3 -B dashboard.py
```

Open `dashboard.html` in a browser. It displays the saved measurements with filters, three timing charts, original/revised comparisons, memory tables, raw repeats, downloads, and environment details. It does not rerun algorithms when filters change. `dashboard_validation.txt` records successful checks of 54 filter/unit combinations, CSV downloading, offline behavior, and desktop/mobile layouts.

To regenerate inputs and measurements, then refresh the dashboard and report:

```bash
python3 -B generate_data.py --seed 42 --include-empty-queries
python3 -B validate_data.py
python3 -B benchmark.py
python3 -B dashboard.py
python3 -B build_report.py
```

These commands use Python's standard library; the dashboard uses browser-native HTML, CSS, SVG, and JavaScript. Regeneration overwrites default input/result files. Fixed seeds reproduce saved input values in the recorded environment, while timings naturally vary. `build_report.py` reads saved results, checks consistency and source hashes, and writes this report without benchmarking. Its checked tables are also exported in `results/report_tables.json`.

## Limitations and conclusions

This is one machine, one interpreter, one base seed, and one array per size. Five repeats assess local timing variation, not variation across machines, seeds, or data distributions. Array generation deliberately includes duplicates, hit sampling favors frequent IDs, and negative misses are all below the stored domain. Broader generalization would require additional seeds, duplicate policies, in-range absent values, and query patterns.

Consecutive repeats, background load, garbage collection, and grouped state reuse can affect timings. In particular, the reused preparation in query-only groups does not represent independently preparing each query batch; the independently measured total captures fresh preparation per call. Very short operations are sensitive to harness overhead. Memory has one traced observation per configuration and excludes pre-existing inputs and untracked native allocations. The empty-query cases are supplementary and do not replace the required q = 1 and q = 100 cases.

For these experiments, hash-set membership has the lowest revised total time in {hash_wins} of {len(batch_cases)} configurations with 100 queries, with a higher traced memory cost in the detailed mixed-query example. Linear search wins {linear_wins} of {len(single_cases)} single-query cases and avoids preparation. Binary search provides fast queries after sorting, but sorting a fresh copy on every public call adds substantial cost for the tested batches. The revision preserves tested behavior and removes unnecessary empty-query preparation. Performance conclusions should be read with the version ratios and workload scope above.

## AI assistance and scope

OpenAI Codex drafted the tests, implementations, revision, data generator, measurement scripts, dashboard, documentation, and this report under the user's step-by-step requests. The implementation uses the proposed iterative binary search and empty-input optimization. Validation includes unchanged expected results, independent membership checks, saved raw repeats, source hashes, and browser checks. AI-generated claims were checked against the saved data; no personal accept/correct/reject judgments are attributed to the student. Student review of the code, reasoning, and assistance record remains necessary before submission.

This report covers Phase 1. The independent peer audit and its reproducible bug evidence belong to Phase 2. A final submission commit and audit target have not been created by this report-writing step.

## Evidence files

- `results/timing_raw.csv`, `results/timing_summary.csv`, and `results/memory.csv`: numeric observations behind the tables.
- `results/metadata.json`: environment, timing/memory definitions, seeds, input hash, and measured source hashes.
- `data/inputs.json`: authoritative shared experimental inputs and expected answers.
- `test_search.py` and the saved validation logs: correctness and execution evidence.
- `REVISION.md` and `snapshots/`: revision explanation and preserved earlier sources.
- `dashboard.html`: interactive English presentation of the saved measurements.
'''
    (BASE / "REPORT.md").write_text(report, encoding="utf-8")
    tables = {"mixed_batch_totals": mixed, "single_query_totals": single,
              "phase_comparison": phases, "hit_scenarios": hits,
              "version_comparison": versions, "empty_query_revision": empty,
              "memory_comparison": mem, "array_composition": arrays}
    export = {"measurement_run_id": meta["run_id"], "tables": tables,
              "source_files_sha256": {name: hashlib.sha256((BASE / "results" / name).read_bytes()).hexdigest()
                  for name in ("timing_raw.csv", "timing_summary.csv", "memory.csv", "metadata.json")},
              "nonempty_original_over_revised": dict(min=min(ratios), max=max(ratios), median=statistics.median(ratios))}
    (BASE / "results/report_tables.json").write_text(json.dumps(export, indent=2) + "\n")
    print(f"Saved English REPORT.md ({len(report.split()):,} words) and results/report_tables.json")


if __name__ == "__main__":
    main()
