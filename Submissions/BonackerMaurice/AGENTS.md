# AGENTS.md: Algorithms in Finance lab (BonackerMaurice)

Instructions for AI coding agents and collaborators working on this submission.
Read this file fully before changing anything. The source is the lab slides
54–64 of *Algorithms in Finance*. Where this file and the slides disagree, the
slides win; fix this file.

## 1. Ground rules

- Course repository: `github.com/cogeorg/AlgorithmsFinance` (public).
- **Only edit files inside `Submissions/BonackerMaurice/`.** Never edit course
  folders (`Class1-2/`, the root `README.md`, `Submissions/README.md`) or other
  students' folders.
- **Git workflow:**
  - Remote `origin` is the course repository (read-only for us). Remote `fork`
    is Maurice's fork `Oxilop365/AlgorithmsFinance`.
  - Work happens on the branch `bonacker/phase1`. It is pushed to `fork`, and a
    pull request goes from there to `cogeorg:main`. The skeleton PR (#8) is
    already merged.
  - Before committing new work, bring the branch up to date with `origin/main`.
  - **Commit or push only when Maurice asks.**
- **Folder numbering** follows the course convention:
  - `00_docs/` holds the docs.
  - `01_code/` holds all Python. The packages inside it keep plain names,
    because Python module names cannot start with a digit.
  - `02_results/` holds the saved runs.
- **Keep it simple.** This is a time-boxed lab. Prefer small, readable,
  standard-library code over frameworks and abstractions. Do not add features
  the slides do not ask for.
- **Never weaken an expected test result to make a bug pass.** Add a test for
  every newly discovered case.
- Record every change to algorithm code in `00_docs/REVISIONS.md` (what changed,
  why, and the evidence). Record AI involvement in `00_docs/AI_USAGE.md`, saying
  which suggestions were accepted, corrected or rejected.
- Run `python -m pytest` (from `01_code/`) after every code change.

## 2. The assignment

### Phase 1: implement (current)

Three methods, one specification:

| Method | Preparation | Query |
|---|---|---|
| `LinearSearch` | none | hand-written scan of the given array |
| `BinarySearch` | `sorted()` copy of the array (library sort is allowed) | hand-written binary search on the sorted copy |
| Hash membership | `set()` of the array (standard library) | `q in id_set` |

**Contract:**

- The input is an integer ID array plus ordered queries.
- The output is a `list` with one `bool` per query, in query order.
- The given array (and the queries) stay unchanged.
- All three methods must pass the **same** tests.
- Both search procedures are implemented by hand in Python. Do not use `in` on
  a list, `bisect`, `list.index` or `list.count` inside linear or binary
  search. An AST test enforces this.

**Process the slides require:**

1. Write tests (pytest) and a synthetic-data generator first. The tests cover:
   - empty arrays and empty queries
   - one entry
   - duplicates
   - unsorted input
   - present and absent queries
   - output order
   - unchanged input
   - the slide example: array `[7, 11, 7]` with queries `[11, 9, 7]` returns
     `[True, False, True]`.

   Keep data generation separate from the algorithms and the measurement code.
2. Run the tests before implementing and confirm that they detect missing or
   wrong behaviour. This is logged in `00_docs/DEVLOG.md`, and
   `python -m tests.mutation_check` provides the evidence.
3. Implement all three methods. Trace a small example by hand, then run every
   test.
4. Make at least one revision. Keep **both** versions and rerun the same tests.
5. Record what changed and why, plus AI usage. Passing tests are evidence, not
   proof.
6. Measure (section 6), build the dashboard (section 8), and write the README
   (section 9).

Docker is optional and not planned. Add it only if Maurice asks.

### Phase 2: audit (later)

Run another student's project, challenge its correctness and performance
claims, and submit reproducible evidence of bugs and shortcomings to the same
repository. Someone will do the same to us, so every claim we make must be
easy to verify from saved data and exact commands. An AI pre-audit has already
been done, and its findings and fixes are in `00_docs/AI_USAGE.md`.

## 3. Project layout

```
Submissions/BonackerMaurice/
  AGENTS.md              this file (CLAUDE.md imports it)
  README.md              run commands, expected test results, definitions, revision summary
  00_docs/               DEVLOG.md, REVISIONS.md, AI_USAGE.md
  01_code/               run every command from here
    requirements.txt     pinned dependency versions
    pytest.ini           pytest config (testpaths, pythonpath)
    search_algos/        the algorithms (stdlib only)
      linear.py          LinearSearch v1 (original) and v2 (revised)
      binary.py          BinarySearch v1 (recursive, original) and v2 (iterative, revised)
      hashset.py         hash-set membership (single version)
      validation.py      shared input validation
      registry.py        Method objects: METHODS, CURRENT, get_method()
    datagen/generator.py synthetic data (seeded; separate from algorithms and measurement)
    benchmarks/          measurement code (stdlib only)
      config.py          grid, measurement DEFINITIONS, paths
      environment.py     machine, Python, packages, git, source fingerprint
      timing.py          timing phase (perf_counter)
      memory.py          memory phase (tracemalloc), run as a separate process
      run.py             orchestrator: tests, then timing, then memory, into ../02_results/<run_id>/
    dashboard/           app.py (Streamlit page), data.py (loading and derived tables)
    explore/large_n.py   large-n exploration (n up to 10M): timing pipeline, custom grid
    tests/               pytest suite, plus mutation_check.py
  02_results/<run_id>/   saved raw results (committed; *_quick runs are gitignored, except
                         the large-n run reported in the README)
```

## 4. Commands

Run these from `Submissions/BonackerMaurice/01_code/`:

```bash
python -m pip install -r requirements.txt
python -m pytest                          # all tests
python -m tests.mutation_check            # the tests catch deliberately buggy variants
python -m benchmarks.run                  # full run: tests, timing, memory -> ../02_results/<run_id>/
python -m benchmarks.run --quick          # small grid for development (gitignored)
python -m datagen.generator --n 1000 --q 100 --scenario mixed   # inspect one dataset
python -m explore.large_n [sizes]         # exploration up to n = 10M (about 9 min; gitignored)
python -m streamlit run dashboard/app.py  # dashboard on http://localhost:8501
```

Use `python -m streamlit`, not `streamlit`: on Windows, application-control
policies can block the `streamlit.exe` launcher.

## 5. Code conventions

- Each method is a `Method` in `search_algos/registry.py` with
  `prepare(ids) -> state` and `query(state, queries) -> list[bool]`.
- Calling `method(ids, queries)` validates the input first and then runs
  `query(prepare(ids), queries)`.
- Versions: `v1` is the original and `v2` is the revised version. **Never edit a
  version after it has been measured in a committed run.** Add `v3` instead,
  register it, and update `CURRENT`.
- Validation (`validation.py`) runs only in `Method.__call__`, not inside
  `prepare` or `query`, so it is excluded from timings.
- Invalid input raises `TypeError`, identically for every method. Invalid input
  means any of the following:
  - not a sequence, or a `str` or `bytes` value
  - elements that are not Python `int`, including `bool` and NumPy integers
    (pass `array.tolist()` instead)
- Algorithms, the generator and the benchmarks use the standard library only.
  pandas, Streamlit and Altair are for the dashboard only.

## 6. Measurement protocol (`01_code/benchmarks/`)

**Grid:**

- array length n ∈ {1,000; 10,000; 100,000}
- query count q ∈ {1; 100}
- scenarios: `all_present` (1.0), `all_absent` (0.0), `mixed` (0.5). q=1
  `mixed` is skipped because one query cannot be half present.
- duplicate policy `allow` (IDs drawn with replacement from `[0, 2n)`)
- seed 2026

For the same n and seed, every q and scenario uses the identical array. Every
method and version gets identical inputs. Checksums are saved, and the memory
phase re-checks them.

**Hit placement:** present queries are placed at stratified *first-occurrence*
positions (where a linear scan stops), spread evenly over the array.
`mean_first_hit_frac` (≈ 0.5) is saved per dataset. Without this, a q=1 hit
position is a single random draw and linear-search scaling is distorted.

**Timing** (`time.perf_counter`):

1. A preflight check runs first: exact `bool` results, correct against a
   reference, and the input unchanged.
2. Calibration doubles as the warm-up. It picks `calls_per_measurement`, plus a
   25% margin, so that one measurement lasts at least `min_measure_seconds`.
   Short calls are batched, and the elapsed time is divided by the number of
   calls.
3. Three segments are measured separately and **directly**:
   - `prepare`: one `prepare(ids)`, including freeing the result
   - `query`: one complete batch of q queries on a state built fresh for that
     repeat. This is a warm-cache, steady-state figure.
   - `total`: a fresh `prepare` plus the complete batch. Total ≠ prepare + query.
4. There are 5 repeats per (dataset, method, version, segment). The method order
   is rotated per repeat. Report the **median** and keep every raw repeat.
5. Garbage collection is disabled inside the timed loops (as in `timeit`) and
   `gc.collect()` runs between measurements.
6. Excluded from timing: data generation, validation, tests, printing,
   correctness checks and dashboard rendering.
7. Every timing is **seconds per call**. Per-query values are derived as
   batch / q and labelled as derived.
8. Harness overhead is saved as `noop_call_s` (the partial wrapper used by the
   prepare and query segments) and `noop_lambda_call_s` (the total segment).
   Medians within about 10× of these are overhead-dominated.

**Memory** (`tracemalloc`, in its own process after timing):

- The input is built before tracing starts.
- Each method gets a fresh tracing run. Peak and current bytes are read after
  `prepare` and again after `query`, keeping the state and output alive.
- Included: the prepared structure, the output list, transient buffers in the
  peaks, and about 50–110 bytes of harness objects (`memory_baseline` in
  `run.json`).
- Excluded: the input array and queries, and native allocations that
  tracemalloc does not see.

**Rules:**

- Never benchmark while anything else heavy runs: other agents, pytest,
  Streamlit, browsers or video. Plug the laptop in.
- The final committed run must come from a **committed, clean** `01_code/`
  (`git.dirty: false`, no `_dirty` in the run_id).
- `environment.json` records a `source.sha256` fingerprint of `search_algos/`,
  `datagen/` and `benchmarks/`. `run.json` records `source_unchanged`
  (re-checked at the end of the run).

## 7. Results format (`02_results/<run_id>/`)

`run_id` = `YYYYMMDD-HHMMSS_<shortsha|nogit>[_dirty][_quick]`, with the
timestamp in UTC.

| File | Content |
|---|---|
| `run.json` | run_id, status (`running` / `complete` / `aborted: …`), command, grid, method list (key, method, version, role, label, description), `current`, definitions, test summary, `noop_call_s`, `noop_lambda_call_s`, `memory_baseline`, `source_unchanged`, phases |
| `environment.json` | Python version, platform, CPU, RAM, perf_counter clock info, package versions, git (commit, branch, dirty: true / false / null), source fingerprint, timestamp |
| `tests.xml`, `tests.txt` | pytest JUnit XML and console output from this run (hostname and home paths redacted) |
| `datasets.csv` | dataset_id, n, q, scenario, target_hit_rate, present_queries, realized_hit_rate, mean_first_hit_frac, duplicate_policy, id_space, distinct_values, seed, array_sha256, queries_sha256 |
| `timings_raw.csv` | dataset_id, n, q, scenario, realized_hit_rate, method, version, segment, repeat, calls_per_measurement, elapsed_s |
| `timings_summary.csv` | dataset_id, n, q, scenario, realized_hit_rate, method, version, segment, repeats, median_s, min_s, max_s |
| `memory.csv` | dataset_id, n, q, scenario, method, version, prepare_current_bytes, prepare_peak_bytes, total_current_bytes, total_peak_bytes |

`segment` ∈ {`prepare`, `query`, `total`}. `method` ∈ {`linear`, `binary`,
`hash`}. `version` ∈ {`v1`, `v2`}.

## 8. Dashboard (`01_code/dashboard/`)

The audience is the **Phase 2 reviewer**. The dashboard loads saved results only
and never reruns benchmarks. Keep it readable: four tabs, with the main page
showing only what a reviewer needs first.

- **Overview:** measured commit, tree state, run status and test result; the key
  results table (current versions, largest n and q, mixed); the v1 → v2
  speed-ups with the same-code noise band; the reproduce commands. Warnings
  appear above the tabs only when something is wrong.
- **Runtime:** item 4 below, with a "compare v1 and v2" toggle (item 5's
  curves), a values table (median prepare, batch, derived per query and total
  for every n) and a compact slope table (item 6).
- **Spot check:** item 9.
- **Details for auditors:** items 1–3, 5 (tables), 6 (full), 7 and 8, one
  section at a time.

The content these tabs must cover:

1. **Provenance:**
   - commit and branch, the dirty and unknown-git warnings, and the run status
   - the source fingerprint, with a check against the checked-out code
   - environment details
   - the exact reproduce commands
2. **Correctness:** test counts and a per-test table from `tests.xml`, and the
   mutation-check command.
3. **Definitions and inputs:** all definitions, the overhead values, and the
   dataset table with checksums and `mean_first_hit_frac`.
4. **Runtime against n:** current versions on log–log axes, with prepare, query
   batch and total separately. Filters for q and scenario. Overhead-dominated
   medians are drawn hollow.
5. **Original vs revised:** v1 vs v2 curves and a speed-up table. The binary
   `prepare` ratio is a **same-code control** that shows the noise band.
6. **Scaling check:** fitted log–log slopes next to expected bands:
   - linear query and total ≈ 1
   - linear v1 prepare ≈ 1
   - linear v2 prepare ≈ 0 (overhead only)
   - binary prepare ≈ 1.0–1.2
   - binary query ≈ 0.1–0.3 (log n plus cache effects)
   - hash prepare ≈ 1
   - hash query ≈ 0–0.3

   q=1 slopes are flagged as unreliable.
7. **Memory:** the tracemalloc table, what it includes, and `memory_baseline`.
8. **Raw data:** filterable raw repeats, the spread of each median, the
   environment and run JSON, and downloads.
9. **Spot check:** reviewer-typed IDs and queries run through every method,
   with disagreements highlighted. Inputs are capped at 10,000 elements.

## 9. README requirements (upload checklist)

`README.md` must contain:

- the exact run commands
- the expected test results (the number of tests and that all pass)
- the measurement definitions
- an explanation of the revision
- the dependency versions
- the run_id of the committed results
- **the commit hash to be audited**

The upload must include:

- the algorithm versions
- the tests
- the generator
- the measurement scripts
- the raw results
- the dashboard code
- `requirements.txt`
- the README

Reviewers must be able to run the audited commit without editing it.

## 10. Definition of done (Phase 1)

- [ ] All tests pass. The README states the expected count.
- [ ] `00_docs/DEVLOG.md` shows that the tests failed before the implementation.
- [ ] v1 and v2 are both registered and both measured. `00_docs/REVISIONS.md`
      explains the revision with numbers from a committed run.
- [ ] A full run is in `02_results/`, made from a clean, committed `01_code/`
      on a quiet machine.
- [ ] The dashboard runs from a fresh checkout and covers section 8.
- [ ] `00_docs/AI_USAGE.md` is filled in by Maurice (accepted, corrected or
      rejected).
- [ ] The README has the commit hash to be audited.
- [ ] Pushed only with Maurice's go-ahead, and a PR is opened to `cogeorg:main`.

## 11. Working style for follow-up sessions

- The base was built with high reasoning effort. Refinements can use a faster
  model. Keep diffs small and focused, and do not restructure working code.
- Read the relevant module and its tests before editing. Run the tests after
  editing.
- Benchmarks: use `--quick` while developing. Run the full benchmark once at the
  end, from a clean commit, on a quiet machine.
