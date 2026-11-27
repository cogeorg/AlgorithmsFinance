# Phase 2 audit: LaviBen

Audit of Ben Lavi's Phase 1 submission by Yannick Welscher.

## Target

| | |
|---|---|
| Repository | `github.com/cogeorg/AlgorithmsFinance` |
| Folder | `Submissions/LaviBen/` |
| Audited commit | `4777c48ce08afb1dd500cce97ab577d03621ae47` (last commit touching the folder) |
| Measured commit in his results | `b122ea5`; between `b122ea5` and `4777c48` only documentation and results changed, no code |
| Audit environment | Apple M4 Pro, macOS 26.5.1, Python 3.13.15 (his README requires 3.10 or newer; he measured with 3.14.7) |

The audited code was never edited. It was checked out at the commit above in a
separate worktree and run from there.

## How to reproduce this audit

```bash
# from the repository root
git fetch https://github.com/cogeorg/AlgorithmsFinance.git
git worktree add ../audit-LaviBen 4777c48
cd Submissions/WelscherYannick
python3 audit/reproducers/repro_b1_preparation_includes_freeing.py ../../../audit-LaviBen/Submissions/LaviBen   # exits 1: bug present
python3 audit/reproducers/repro_b2_duplicate_sizes_mix_inputs.py ../../../audit-LaviBen/Submissions/LaviBen    # exits 1: bug present
python3 audit/reproducers/run_contract_checks.py ../../../audit-LaviBen/Submissions/LaviBen .
```

No third-party packages are needed. Saved outputs of every run are in
`audit/evidence/` (local paths replaced by placeholders).

## What was run, unchanged

| Step | Command (in his folder) | Result | Evidence |
|---|---|---|---|
| His tests | `python3 -m unittest discover -s tests -v` | 11 of 11 pass | `01_his_tests.txt` |
| His benchmark | `python3 benchmark.py --output <tmp>` | runs, about 1.5 s | `02_his_benchmark_and_dashboard.txt` |
| His dashboard | `python3 dashboard.py --input … --output …` | runs | same file |
| Input reproducibility | compare input digests of my run with his committed manifest | identical for all 18 cases (Python 3.13 vs 3.14) | `03_rerun_comparison.txt` |
| My contract checks | 18 checks from `tests/contract.py` against his 4 methods | 71 of 72 pass; the failure is not a bug (see below) | `04_contract_checks.txt` |
| Edge case: zero queries | `--sizes 10 --query-counts 0 --repeats 1` | benchmark and dashboard run | `07_edge_zero_queries.txt` |

The `--output` option of his own scripts was used so that his committed
results stayed untouched; `git status` in the audited checkout was empty
afterwards.

## Reproduced bugs

### B1: preparation time includes freeing the previous algorithm's state

**Target.** `benchmark.py`, `_measure_fixed_inputs`, lines 319–325.

```python
combined_started = perf_counter_ns()
preparation_started = perf_counter_ns()
prepared = algorithm.prepare(fixed_input.ids)      # line 321
preparation_finished = perf_counter_ns()
query_started = perf_counter_ns()
result = algorithm.query_batch(prepared, fixed_input.queries)   # line 324
```

**Smallest useful example.**
`audit/reproducers/repro_b1_preparation_includes_freeing.py`. Part 1 calls his
unchanged `_measure_fixed_inputs` with two test-double algorithms: A builds a
state that takes 5 ms to free, B's `prepare` returns its input and does no
work. Part 2 times his real `prepare_linear` the same way on his own data.

**Evidence** (`05_repro_b1.txt`).

| | Expected | Actual |
|---|---|---|
| Part 1: B's preparation when it follows A | far below 1 ms | 6.3 ms |
| Part 2: `prepare_linear` (returns `ids`), n = 100,000, after a sorted copy | about 0.1 µs | 79 µs (0.25 µs if the previous state is released first) |

His own committed raw data show the same pattern. `prepare_linear` does no
work, yet its median preparation time grows with n and depends on which
algorithm ran before (`results/raw_timings.csv`, grouped by predecessor):

| n | after binary v2 | after hash set |
|---|---|---|
| 1,000 | 854 ns | 729 ns |
| 10,000 | 9,126 ns | 4,250 ns |
| 100,000 | 109,500 ns | 65,812 ns |

**Explanation.** When the timer starts, the local variable `prepared` still
refers to the previous algorithm's sorted copy or hash set. Assigning the new
state on line 321 drops the last reference, and Python frees the old
structure inside the timed region. The same happens to the previous `result`
list on line 324, which matters little because it is short. Slide 61 asks for
fresh preparation state per repeat and for timing only the operation itself.

**Impact.**
* Every preparation time contains the cost of freeing whatever ran before;
  the README's "Linear search preparation 0.065 ms" (n = 100,000) is entirely
  this artefact.
* Because of the fixed rotation, binary v2 runs directly after binary v1 in
  4 of 5 repeats and pays for freeing v1's sorted copy, while v1 mostly
  follows linear search, whose state is the input itself and is not freed.
  This biases the v1/v2 preparation comparison against v2; it matches his
  reported medians (v2 10.557 ms vs v1 10.468 ms at n = 100,000, q = 100,
  mixed, although both call the same `sorted`).
* Combined times include the same artefact.

**Suggested correction.** Release the previous objects before starting the
timers, for example `prepared = None` and `result = None` (followed by
`gc.collect()` outside the timed region if desired) at the top of the
loop body. The reproducer stays valid for the original commit.

### B2: a repeated array size merges two different inputs into one summary row

**Target.** `benchmark.py`, case id on line 272 and matching in
`_summarize` on lines 359–363.

**Smallest useful example.**
`audit/reproducers/repro_b2_duplicate_sizes_mix_inputs.py`, equivalent to
`python3 benchmark.py --sizes 10,10 --query-counts 1 --scenarios all_present --repeats 2`.

**Evidence** (`06_repro_b2.txt`). Two cases get the same id
`n10_q1_all_present` but different seeds (2026, 2027) and different input
digests. The summary row for linear search reports `repeats=2` but is the
median of 4 raw rows from both inputs, and the summary contains the same id
twice.

**Explanation.** The case id is built from n, q and scenario only, while each
generated case gets its own seed. `_summarize` selects raw rows by case id,
so repeated values on the command line silently mix different inputs.

**Impact.** Low: the default run and his committed results are not affected.
It can mislead anyone who passes repeated values to the command-line options.

**Suggested correction.** Reject or de-duplicate repeated values in
`_parse_integers` and `_parse_scenarios`, or include the seed in the case id
and match raw rows by `input_sha256`.

## Missing requirements

| | Requirement | Finding |
|---|---|---|
| A1 | Slide 62: measure memory with `tracemalloc` and state what it includes; slide 63: a table of the chosen memory measurements | No memory measurement anywhere in `benchmark.py` or `dashboard.py` (no `tracemalloc`, no `psutil`), no memory table. |
| A2 | Slide 63: show preparation, query-batch and total time separately; display query count, hit rate and units; access to raw repeats | The charts show combined time only; preparation and query batch appear only in the table. The hit rate (requested or realized) is not shown anywhere. The page reports the number of raw rows (360) but gives no access to them. Query count and units are shown. |

## Suspected weaknesses

| | Finding | Why it matters |
|---|---|---|
| S1 | Each repeat times a single call (`benchmark.py` lines 319–325). A hash query with q = 1 takes about 50 ns, close to the clock resolution of about 42 ns on this machine. | Slide 61: "For very short calls, time several calls together and divide by the number of calls." His q = 1 hash query medians range from 0.17 µs (n = 1,000) to 1.67 µs (n = 100,000), whereas my submission, timing many calls together, measures about 45 ns independent of n. A single cold call mostly measures timer and cache effects, not the lookup. |
| S2 | "mixed" with q = 1 is realized as all present (hit rate 1.0 in all three `q1_mixed` cases). | Documented in his README and manifest, but the dashboard labels these charts "mixed" without any hit rate (see A2). |
| S3 | Absent queries are always larger than every id (`synthetic_data.py`: `value_pool_size + …`); ids are never negative in the benchmark data. | Binary search always walks to the right end for misses; misses in gaps or below the minimum are not measured. Correctness is still covered by his tests. |
| S4 | v2 changes two things at once: a loop instead of recursion and no helper call per query (v1 calls `_recursive_contains` per query; v2 inlines the loop into the batch function). | The measured query-batch gain cannot be attributed to the loop alone. |
| S5 | In the charts the v1 and v2 lines lie on top of each other; v1 (purple) is barely visible. | The original-versus-revised comparison required by slide 63 is hard to read in the charts. |
| S6 | The chart x-axis spaces sizes evenly by position. | Correct for 1k / 10k / 100k (a log scale), misleading for other size lists. |

## Checked and not a bug

* **Linear search keeps a reference to the input.** `prepare_linear` returns
  `ids` itself, so the prepared state would follow later changes to `ids`. My
  contract check `check_state_independent_of_later_changes` fails for it. This
  rule belongs to my own specification, not to his or to the slides, which
  only require that the input is not modified; his code satisfies that. Not
  reported as a bug.

## Strengths

* All four methods are correct on 71 of 72 of my checks (the remaining one
  above), including empty inputs, duplicates, unsorted and tuple inputs, ints
  beyond 64 bits, first and last matches, output order and repeated calls.
* No third-party dependencies; everything runs with the standard library.
* Inputs are fixed per case, stored as tuples and fingerprinted with SHA-256;
  my rerun with a different Python version produced identical inputs.
* Raw timings are kept in nanoseconds; seeds, policies, environment and
  source digest are recorded. Measured and audited code are identical.

## Cases checked

Empty array, empty queries, both empty, one entry, duplicates, unsorted input
(shuffled, descending, rise-then-fall), first and last element, below minimum,
above maximum, gaps, negative ids and zero, output order with repeated
queries, return type, unchanged list and tuple inputs, repeated calls on one
prepared state, ints beyond 64 bits, binary-search boundaries for every
length 0–8, comparison with an independent reference on generated data, zero
queries in the benchmark, repeated command-line values, input reproducibility
across Python versions, dashboard against the saved JSON.

## Limits of this audit

* Timings were rerun on one machine (Apple M4 Pro) only; absolute numbers are
  not comparable with his machine.
* The dashboard was inspected visually and by reading `dashboard.py`; there is
  no automated check of every rendered value.
* B1 was demonstrated for preparation; the smaller effect on the query batch
  (freeing the previous result list) was not quantified.
* Memory behaviour could not be audited because it is not measured (A1).
