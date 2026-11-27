# LAB_SPEC — Coding lab: Implement and audit

Source: lecture slides 54–68, *Algorithms in Finance* (FIN71055, Prof. Co-Pierre Georg,
Frankfurt School). This file restates the specification so that the code, the tests and
the agent rules (`AGENTS.md`) can refer to it. Requirement IDs (e.g. `T3`) are used in
docstrings, tests and docs.

## 0. Organisation

- Two phases, two submissions, both in the public repository
  `github.com/cogeorg/AlgorithmsFinance` under `Submissions/LastnameFirstname/`
  (here: `Submissions/BuehlerLaurin/`).
- Do not edit course folders such as `Class1-2/`.
- Phase 1: everyone implements. Phase 2: everyone audits another student's code.

## 1. Phase 1 — Implement and measure

### 1.1 Task: three methods, one specification

- **F1** Implement `LinearSearch`, `BinarySearch` on a sorted copy, and membership
  using a standard-library hash set.
- **F2** Input: an integer ID array and ordered queries.
- **F3** Output: one Boolean per query, in the same order as the queries.
- **F4** The given array must stay unchanged.
- **F5** All three methods must satisfy the same tests.
- **F6** Library sorting and sets are allowed. Both search procedures (linear, binary)
  must be implemented by hand in Python.

### 1.2 Tests and synthetic data first

- **T1** Write tests (pytest or plain assertions) before implementing.
- **T2** Cover: empty arrays, empty queries, one entry, duplicates, unsorted input,
  queries that are present or absent.
- **T3** Check output order and that the input is unchanged.
- **T4** Example: array `[7, 11, 7]`, queries `[11, 9, 7]` → `[True, False, True]`.
- **T5** Write a synthetic-data generator for larger inputs. Keep data generation
  separate from the algorithms and from the measurement code.

### 1.3 Implement, test, revise

- **R1** Run the tests before implementing; confirm they detect missing or wrong behaviour.
- **R2** Implement all three methods. Trace a small example by hand, then run every test.
- **R3** Make at least one revision, e.g. replace recursive binary search with an
  iterative version, or remove an unnecessary copy.
- **R4** Run the same tests again. Add tests for newly discovered cases. Never weaken
  expected results to accommodate a bug.
- **R5** Preserve both versions for comparison.
- **R6** Record what changed and why. If AI was used, record which suggestions were
  accepted, corrected or rejected.
- **R7** Passing tests are evidence, not a proof of correctness.

### 1.4 Fix the inputs before comparing performance

- **I1** Array sizes n ∈ {1,000, 10,000, 100,000}; query counts q ∈ {1, 100}.
- **I2** Query sets: all-present, all-absent and mixed.
- **I3** Every method and version gets identical inputs.
- **I4** Save the seed, generator settings, query count, hit rate and duplicate policy.
- **I5** Measure preparation, the complete query batch, and their combined elapsed time.
  Sorting or hash-set construction counts as preparation.
- **I6** Save raw results, units, Python version, machine details and code version.

### 1.5 Runtime measurement code

- **M1** Use `time.perf_counter()` before and after the operation; elapsed seconds are
  the difference (`timeit` is another option).
- **M2** Warm up, then repeat five times and report the median.
- **M3** For very short calls, time several calls together and divide by the number of calls.
- **M4** Create fresh preparation state for each repeat. Do not time a previously built
  sorted copy or hash set as if preparation were free.
- **M5** Exclude data generation, tests, printing, AI calls and dashboard rendering.
- **M6** Run timing separately from memory tracing and profiling.
- **M7** State whether each result is per query or per complete batch; keep the raw
  repeat values.

### 1.6 Memory measurement

- **MEM1** `tracemalloc`: build the input first, start tracing, run the method, read
  `get_traced_memory()` (current and peak bytes), stop tracing.
- **MEM2** Start a fresh tracing run for each method.
- **MEM3** Include preparation if the sorted copy or hash set should be counted.
- **MEM4** Keep the returned output alive while reading memory.
- **MEM5** Optional: `psutil.Process().memory_info().rss` (process memory), sampled in a
  separate run; brief peaks may be missed.
- **MEM6** `tracemalloc` misses some native allocations; RSS includes interpreter and
  other overhead. Neither equals auxiliary space. Report whether input, prepared
  structures and output are included.

### 1.7 Dashboard from saved measurements

- **D1** Plot elapsed time against input length n, one curve per method, plus a
  comparison of the original and revised versions.
- **D2** Show preparation, query-batch and total time separately.
- **D3** Display query count, hit rate, units, and a table of the memory measurements.
- **D4** Load saved results; do not rerun benchmarks when the view changes.
- **D5** Give access to the raw repeats and the environment details.
- **D6** Suggested tool: Streamlit (`st.line_chart`).

### 1.8 Optional: Docker

- **DK1** If used: a `Dockerfile` specifying the Python and dependency versions.
- **DK2** Document the build, test, measurement and dashboard commands, the dashboard
  port, and how results are saved outside the container.
- **DK3** Test the commands from a fresh checkout; tests and benchmarks must run without
  editing files inside the container. Timings still depend on the host and limits.

### 1.9 Upload a reproducible project

- **U1** Algorithm versions, tests, synthetic-data generator, measurement scripts.
- **U2** Raw results, dashboard code, dependency versions.
- **U3** A README with exact run commands, expected test results, measurement
  definitions, and an explanation of the revision.
- **U4** A `Dockerfile` only if Docker packaging was chosen.
- **U5** Record the commit to be audited. Reviewers must be able to run that version
  without editing it.

## 2. Phase 2 — Audit another implementation

### 2.1 Look for failures, not just passing tests

- **A1** Record the commit; build and run the supplied tests and dashboard without
  editing the code.
- **A2** Try empty input, duplicates, first/last matches, absent queries, repeated calls
  and input mutation. Determine expected answers independently.
- **A3** Check preparation costs, input consistency, units, memory labels, and whether
  the dashboard agrees with the raw results.
- **A4** Document reproduced bugs and suspected weaknesses separately.

### 2.2 Evidence per demonstrated bug

- **E1 Target:** reviewed commit and affected procedure or file.
- **E2 Smallest useful example:** input or fixed seed, a runnable failing test or
  script, and the command that runs it (container command only if Docker is used).
- **E3 Evidence:** expected behaviour from the specification, actual output or error,
  saved execution output. For a measurement bug, include the raw data and calculation.
- **E4 Explanation:** why the behaviour is wrong, its impact, a suggested correction.
  Keep the original failure reproducible before proposing a fix.
- **E5** Submit report, reproducer, inputs and logs. List shortcomings and cases
  checked. If no bug is found, state the limits of the investigation.

## 3. Discussion questions (class)

- Which revision preserved correctness and improved measured performance?
- Which peer test exposed a bug or an unsupported performance claim?
- Could another student reproduce the result from the submitted repository files?

## 4. Decisions on ambiguous points

Decided by Laurin after Step 3. These fill gaps in the slides; they are our
interpretation, not part of the official specification.

| # | Question | Decision |
|---|---|---|
| Q1 | Duplicate policy (I4) | Generator supports `"unique"` (n distinct IDs) and `"allow"` (IDs drawn with replacement, duplicates occur naturally). Benchmarks use `"allow"`; tests cover both. The policy is saved with every result. |
| Q2 | Meaning of "mixed" (I2) | Hit rate 0.5: half the queries present, half absent, shuffled. Hit rates used: 1.0 (all-present), 0.0 (all-absent), 0.5 (mixed). The realized hit rate is saved as well. |
| Q3 | Shape of v1 binary search / the revision (R3) | v1: recursive binary search that slices the list (`arr[mid+1:]`), a common naive version that copies O(n) elements per query. v2: the fastest correct hand-written binary search we can find: iterative, index-based, no copies. Candidate v2 variants are checked against the same tests and the fastest is chosen by measurement; the choice is documented in `docs/REVISION.md`. Goal: fastest correct algorithm. |
| Q4 | v2 of linear search and hash set | Same code as v1, exposed under the `revised` version and marked "unchanged" in `docs/REVISION.md`. |
| Q5 | Input type (F2) | `ids` and `queries` are Python `list[int]` (any sequence of ints is accepted for reading). No type validation; documented in docstrings. |
| Q6 | Docker (DK1–DK3) | Skipped for now; may be added after Step 10. |
