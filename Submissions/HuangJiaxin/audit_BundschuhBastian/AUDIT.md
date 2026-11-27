# Phase 2 audit: Bastian Bundschuh's implementation

* **Reviewer:** Huang Jiaxin
* **Reviewed folder:** `Submissions/BundschuhBastian/`
* **Reviewed commit:** `63002bc` (latest commit touching his folder, merged in pull request #18).
  His saved timing results were produced at `dfc2968`, which is also the last commit that
  changed `membership.py` and `bench_time.py` (`logs/code_version.txt`), so the results match
  the reviewed code.
* **Reviewer environment:** MacBook Air (Apple Silicon), Docker image `python:3.11-slim`
  (Python 3.11.18, Linux aarch64), his pinned `requirements.txt`.

## Summary

**The algorithms are correct.** All four methods returned the correct answer on every input
I tried, never changed their input, and his 363 tests pass in a clean environment. His saved
numbers are internally consistent, and every number quoted in his README matches his raw data.

I found **two small reproduced bugs** outside the algorithms (dashboard number formatting and
the code-version metadata), **four shortcomings** (claims that do not fully match the code or
the data) and **one environment-dependent observation**. None of them changes a membership
answer.

| # | Type | Where | Severity |
|---|---|---|---|
| B1 | Bug: 4 instead of 3 significant digits | `dashboard/report.py`, `sig3` | low (display) |
| B2 | Bug: unknown code version reported as "no uncommitted changes" | `bench_time.py`, `environment` | low to medium (reproducibility) |
| S1 | Claim does not match code | `membership.py` docstring, `REVISIONS.md` refactor note | low |
| S2 | Number does not match data | `REVISIONS.md`, "Measured effect" | low |
| S3 | Duplicate workload presented as a separate setting | `datagen.py`, README, dashboard | low to medium |
| S4 | Benefit claimed but not measured (verified here) | `REVISIONS.md`, change 2 | informational |
| O1 | Scaling statement differs on another machine | README, "Complexity claims" | observation |

## How to reproduce everything

From this folder, with git and Docker installed:

```bash
bash run_audit.sh
```

It records the code history (`logs/code_version.txt`), then starts `python:3.11-slim`,
installs his `requirements.txt`, runs his tests and my scripts, and reruns his timing
pipeline **in a temporary copy** of his folder. Nothing is written into his folder.
All outputs are in `logs/`.

| Script | What it checks | Log |
|---|---|---|
| `fuzz_methods.py` | correctness against Python's `in`; inputs and prepared state unchanged; data generator | `logs/fuzz_methods.txt` |
| `finding_1_public_method.py` | reproducer for S1 and S4 | `logs/finding_1_public_method.txt` |
| `finding_2_bugs.py` | reproducer for B1, B2 and the dashboard sentence in S2 | `logs/finding_2_bugs.txt` |
| `check_claims.py` | summaries recomputed from raw repeats; every README / REVISIONS number; S2, S3 | `logs/check_claims.txt` |
| `compare_rerun.py` | his conclusions after a fresh rerun on my machine; O1 | `logs/compare_rerun.txt` |

In the logs, `FAIL` marks a claim that did not hold, not a crash of the script.

## Checks that passed

* His tests: **363 passed** (`logs/his_tests.txt`), as stated in his README.
* Hand-picked edge cases from the specification for all four methods: slide example,
  empty array, empty queries, both empty, one entry, all entries equal, unsorted input,
  first and last position, negative IDs, integers of size 10^30, repeated queries and
  output order. All correct, inputs unchanged, every answer a `bool`.
* Random differential test: 3,000 random inputs × 4 methods, compared with `x in ids`:
  0 mismatches. Calling each answer phase twice on one prepared state gives the same
  answer and leaves the state unchanged.
* `binary_v1` on 2,000,000 sorted IDs: no recursion error.
* Data generator, 2,000 random settings: correct sizes, exact hit counts, no duplicates
  for `duplicates="none"`, identical output for the same seed.
* `timing_summary.csv` recomputed from `timing_raw.csv`: medians, minima and maxima match
  exactly for all 216 rows; every configuration has 5 repeats; per-query = per-batch / q.
* `total_consistency.csv` recomputed; the README figures (ratio 0.73 to 1.25; 42 / 22 / 8;
  12 non-overlapping ranges) match.
* Revision figures (query v2/v1 0.64 to 0.75; total v2/v1 0.82 to 1.06), the evidence
  table, the hit-rate statements and the memory figures (800,056 B, 4,194,520 B, peak 1.5×)
  match his data.
* **Rerun on my machine** (`logs/compare_rerun.txt`): linear search is fastest for q = 1,
  the hash set is fastest for q = 100, hash query time is flat in n, and `binary_v2` is
  faster than `binary_v1` in the query phase in **all 18 configurations** (v2/v1 0.66 to
  0.93). His qualitative conclusions reproduce.

## Reproduced bugs

### B1. `sig3` shows four significant digits when rounding crosses a power of ten

* **Target:** `dashboard/report.py`, function `sig3` (used for all numbers in the
  dashboard's text and tables).
* **Smallest example:** `python finding_2_bugs.py`
* **Evidence:** the docstring promises "3 significant digits". Actual output:
  `sig3(0.9996)` gives `'1.000'`, `sig3(9.996)` gives `'10.00'`, `sig3(99.96)` gives
  `'100.0'`; expected `'1.00'`, `'10.0'`, `'100'`. Values that do not round up, such as
  `0.1769` and `133.39`, are correct.
* **Explanation:** the number of decimals is computed from the value **before** rounding.
  When rounding moves the value to the next power of ten, one decimal too many is kept.
  His tests only use values that do not round up.
* **Impact:** low; only the display of some numbers, never the stored results.
* **Suggestion:** after rounding, recompute the number of decimals from the rounded value,
  and add a test for 0.9996 and 99.96.

### B2. An unknown code version is recorded as "no uncommitted changes"

* **Target:** `bench_time.py`, function `environment` (`_run` returns `""` on any error).
* **Smallest example:** `python finding_2_bugs.py` inside the audit container (no git), or
  `logs/rerun_results/timing_metadata.json` from my rerun.
* **Evidence:** without git, `environment()` returns `git_commit = ''` and
  `git_uncommitted_changes_outside_results = False`. The second field therefore claims a
  clean checkout even though the code version could not be determined.
* **Explanation:** an empty `git status` output is treated as "clean", but an empty output
  also results from git being missing or the folder not being a repository. Slide 59 asks
  to save the code version with the results; a reviewer running his project in Docker, from
  a copy or from a ZIP download gets misleading metadata.
* **Impact:** low to medium for reproducibility; his own saved run is not affected (it shows
  commit `dfc2968`, which matches the code).
* **Suggestion:** record `None` or `"unknown"` for both fields when `git rev-parse HEAD`
  fails, and allow the commit to be passed in (for example through an environment variable).

## Shortcomings

### S1. "Every public method is exactly answer(prepare(ids), queries)" is false for binary_v2 with no queries

* **Target:** `membership.py`, module docstring and `binary_search_iterative`;
  `REVISIONS.md`, "Refactor note".
* **Smallest example:** `python finding_1_public_method.py`
* **Evidence:** with `ids = [5, 3, 9]` and `queries = []`, the public method `binary_v2`
  calls the preparation (sorting) **0 times**, while `answer(prepare(ids), [])` from
  `PHASES` calls it once. Both return `[]`.
* **Explanation:** the documents state that the tested public method and the timed phases
  are the same code ("so the tested code is the timed code"). The early return added in
  v2 makes them different paths when q = 0. Outputs are equal, so this is not a
  correctness bug, but the claim is too strong. Outside the specification the two
  versions even behave differently: `binary_v1([1, "a"], [])` raises `TypeError`,
  `binary_v2([1, "a"], [])` returns `[]`.
* **Impact:** low. q = 0 is not in his benchmark grid, so no saved number is affected.
* **Suggestion:** state the exception in the docstring and in `REVISIONS.md`, or move the
  empty-query check into the answer phase so that both paths are identical again.

### S2. "Sorting takes about 20 ms of the 21 to 25 ms total" does not match the saved data

* **Target:** `REVISIONS.md`, "Measured effect".
* **Smallest example:** `python check_claims.py` (check "sort 'about 20 ms'").
* **Evidence:** at n = 100,000 the saved sorting medians range from **19.7 to 26.0 ms**,
  and the totals for q = 100 from **21.0 to 24.9 ms**. One preparation median (26.0 ms,
  `binary_v2`, all-absent) is larger than every total.
* **Explanation:** the sentence presents the sort as a fixed 20 ms share of the total.
  His own README section on `total` vs `prepare + query` explains that the blocks run at
  different moments and vary by up to 1.33×; this sentence does not reflect that.
* **Same issue on the dashboard:** the first "Findings" sentence reads "binary search in
  21.8 ms (99 % of it is sorting)". The 21.8 ms is the measured `total`, but the 99 % is
  computed from `prepare / (prepare + query)` of different runs; the sorting median in the
  same setting is 22.49 ms, more than the quoted total (`logs/finding_2_bugs.txt`).
* **Impact:** low; the conclusion "sorting dominates the total" still holds.
* **Suggestion:** quote the range (about 20 to 26 ms) or refer to the variation section.

### S3. For q = 1, "mixed" is the same workload as "all-present"

* **Target:** `datagen.py` (`(q + 1) // 2` present queries), README "Data", dashboard
  hit-rate control.
* **Smallest example:** `python check_claims.py` (check "'mixed' differs").
* **Evidence:** in `timing_metadata.json`, all three q = 1 "mixed" datasets have
  `hits = 1`, exactly like "all-present". The generator docstring mentions this, but the
  README and the dashboard present three hit rates for every q.
* **Explanation:** 3 of the 18 configurations repeat another configuration under a
  different label. A reader comparing "mixed" with "all-present" at q = 1 sees only
  measurement noise, not a hit-rate effect.
* **Impact:** low to medium for interpreting the dashboard; no wrong answers.
* **Suggestion:** label q = 1 "mixed" as identical to "all-present", or leave it out.

### S4. The benefit of the second v2 change is claimed but never measured

* **Target:** `REVISIONS.md`, change 2 ("Early return for an empty query list").
* **Smallest example:** `python finding_1_public_method.py` (timing lines).
* **Evidence:** his grid only uses q ∈ {1, 100}, so the early return is never timed.
  I measured it at n = 100,000, q = 0: `binary_v1` median **16.1 ms**, `binary_v2`
  median **0.0001 ms** (5 repeats each).
* **Explanation:** his claim is correct; it is only unsupported by his own results.
  Because v2 bundles two changes (loop instead of recursion, early return), the measured
  v2/v1 difference for q ≥ 1 comes from the first change only, which his README already
  says correctly.
* **Suggestion:** add q = 0 to the grid or quote a measurement like the one above.

## Observation (environment-dependent, not counted as a shortcoming)

### O1. Linear scaling from n = 10,000 to n = 100,000 was much steeper on my machine

* **Target:** README, "Complexity claims": "Linear grows about 10x when n grows 10x".
* **Evidence:** on his machine the statement holds. In my rerun (q = 100, all-absent,
  query phase) the median grew **10.4×** from n = 1,000 to 10,000 but **51.1×** from
  10,000 to 100,000 (9.2 ms to 470 ms); the five repeats at n = 100,000 were 470, 466,
  985, 379 and 476 ms (`logs/rerun_results/timing_raw.csv`).
* **Explanation:** the most likely cause is my environment (a fanless laptop running a
  Docker virtual machine under sustained load, and memory effects at large n), not his
  code. His README already says absolute numbers depend on the machine; the "about 10x"
  statement is the asymptotic expectation and is not wrong.
* **Suggestion:** none required; optionally note that the 10× growth was observed on
  his machine.

## Outside the specification (for information only)

* With a one-shot iterator instead of an array (`iter([3, 1, 2])`, queries `[2, 3]`),
  `linear_v1` returns `[True, False]` because the first query consumes the iterator; the
  other methods return `[True, True]`. The specification asks for an array, so this is
  not a bug.

## Limits of this audit

* Correctness was tested with random and hand-picked inputs, not proved.
* Timings were rerun once, on one machine, inside Docker; I did not repeat the rerun to
  separate noise from systematic effects.
* I did not rerun `bench_memory.py`; I only checked his saved memory results.
* I opened his dashboard and looked through the page myself; his 23 dashboard tests pass
  and the data it loads is consistent. I did not compare every plotted value with the raw
  data point by point.

## Use of AI

The audit scripts and this report were drafted with Claude (Anthropic) as an AI assistant;
commits are marked with a Co-Authored-By line. I ran the full audit on my own machine,
and the numbers in this report come from my run (`logs/`). Where my machine and the
assistant's earlier trial run disagreed (the assistant's run had shown `binary_v2` slower
than `binary_v1` in one configuration; mine showed it faster in all 18), the report
follows my run and does not list that point as a shortcoming.
