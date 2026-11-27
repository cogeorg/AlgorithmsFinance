# Assignment requirements checklist

The table below records the original requirements and planned evidence; the
latest completion state is tracked in **Benchmark execution status** below.
The supplied package manifest was checked during setup: all 15 present entries
then matched their listed byte counts and SHA-256 values; `.DS_Store` is listed
in the manifest but absent from the package. The later authorized README
quick-start changes the README hash; its original specification text remains
below the addition.

| Requirement | Planned tests | Planned implementation | Planned experiments | Evidence | Status |
|---|---|---|---|---|---|
| Integer units, event schema, and model boundaries | Validate prices/quantities as positive integers, explicitly rejecting booleans; check required fields, types, and sequence behavior. | Both versions implement validation; modeling boundaries are recorded in the baseline design. | None. | Parameterized specification tests and `docs/baseline_design.md`. | Verified for Versions A and B |
| Required interfaces and event results | Check `AddLimitOrder`, `CancelOrder`, `FillMarketSell`, event dispatch, and book inspection; assert result field names, statuses, and ordered fills. | Both versions implement the same event interface and observation properties. | Replay the worked example using both versions. | `docs/interface.md`, full test suite, and supplied worked-example test. | Verified for Versions A and B |
| Matching, price-time priority, and quantities | Independently calculate tests for empty/one-order books; smaller, equal, and oversized market sells; multiple makers at one price; multiple price levels; partial fill followed by another sale; crossing and noncrossing limits; identifier order different from arrival; and a long same-price queue. Check maker/taker IDs, execution order, maker prices, and conservation. | Both versions preserve FIFO within a price, best-price selection across levels, original arrival sequence on residuals, and maker-price execution. | Compare both versions after every event, including ordered fills and canonical books. | Independent expected values and passing full suite. | Verified for Versions A and B |
| Validation, cancellation, and invariants | Cover zero, negative, noninteger, boolean, unknown type/side, duplicate live IDs, and nonincreasing sequence. Assert invalid events do not mutate book or accepted sequence. Test cancellation before/after partial fill, after full fill, repeat cancellation, and unknown targets. Check no crossed resting book, positive remaining quantities, and unique active storage. | Both versions validate before mutation; unknown cancel is accepted as `not_found`; remove only remaining quantity; limit residuals rest and market residuals do not. | Include invalid and cancel-heavy streams in parity checks. | Parameterized mutation snapshots and passing specification tests. | Verified for Versions A and B |
| Results, inspection, and accounting | Assert submission/cancel/rejection schemas, statuses, residual quantities, ordered fill records, and canonical inspection sorted by best price then arrival. Check incoming, maker, cancellation, and proceeds conservation. | Both versions return only current-event fills and retain no optional history. | None beyond replay and correctness tests. | Full test suite and design documentation. | Verified for Versions A and B |
| Two implementation versions and generated correctness checks | Run the same tests against both; use small generated event streams and compare after every event to independent expected answers. Confirm specification tests fail for missing behavior before implementation. | Version A remains unchanged; Version B is implemented with indexed queues and bounded lazy heaps. | Compare all three deterministic streams event by event; benchmark parity separately from timing. | Preimplementation failure evidence, parameterized tests, and per-event results/book/sequence comparison. | Verified for correctness and generated parity |
| Supplied benchmark workload families and sizes | Validate each workload's event count, sequence ordering, and metadata before replay. | Replay `buildup`, `crowded`, `mixed`, `sweep`, and `cancel_churn` streams from an empty book. | Use M = 1,000, 10,000, and 100,000; use seeds 42, 43, and 44 across all five families. Try M = 1,000,000 if feasible and record limits or stopped runs. | Generator commands/settings, checksums, raw result rows, and `results/coverage.csv`. | Partial; full matrix incomplete and M=1,000,000 has no complete five-repeat replay set |
| Submission flood and scaling | Check active-order and occupied-level peaks independently of the timed run. | Measure book construction and full-stream replay; derive logical state peaks from event-result shadow bookkeeping, not full-book inspection. | Compare versions on identical streams; vary event count, seed, and workload family. | Raw timings, medians, event throughput, logical active-order and price-level peaks. | Partial; see coverage statuses |
| Fixed-book liquidation | Independently verify expected maker touches, levels visited, fills, and unfilled quantity. | Build a fresh, identical bid book for each sale size; round 10% quantity up to at least one unit. | Test 10%, 100%, and 200% of available bid quantity; report book construction/reset separately and include matching, state updates, and fill-list creation in sale timing. | Raw sale results, requested quantities, fill counts, depth metrics, and reset timings. | Partial; smoke and full-matrix phases are distinguished in coverage |
| Queue concentration | Assert FIFO and price-time correctness under concentrated and spread-out prices. | Record occupied price levels and queue sizes without changing matching semantics. | Hold initial order count fixed and compare 4 versus 1,000 prices for correctness and speed; keep snapshot-based heavy counters to a small representative case and label inferred counts as estimates. | Workload settings, estimate labels, and raw timings. | Partial; saved scenarios and price-level peaks are exposed in the dashboard |
| Cancellation churn | Check that cancelled orders are absent and active book size stays small. | Track active orders separately from any stale entries or history. | Measure time and memory after many cancellations with few active orders; detect unbounded stale-entry/history accumulation. | Active counts, memory measurements, and churn results. | Partial; anchored churn checkpoints saved; large matrix has gaps |
| Timing protocol and latency | Check the timing harness uses identical pre-generated inputs and fresh empty books for each replay; test phase-specific continuation and incomplete-repeat handling. | Use `time.perf_counter`; keep generation, parsing, engine replay, and full-application timing boundaries explicit. | Warm up; retain all five repeats and their median. Report throughput. In a separate instrumentation run, report per-event median, p95, and p99 with a documented percentile convention. Give primary, latency, memory, state-peak, counter, and profile phases independent equal-for-both-version budgets. | Every raw repeat, median, phase status, compatibility decision, percentile method, throughput, and timing-boundary notes. | Partial; phase coverage, policies, and incomplete sets are in `results/coverage.csv` |
| Memory and profiling | Check instrumentation does not contaminate primary timing runs and that diagnostics have separate enforced budgets. | Use separate `tracemalloc` captures; state whether preloaded input, book, returned fills, and saved history are included. | Measure insertion growth and post-cancellation state; profile only the small representative workload. Distinguish traced allocations from auxiliary space and total/native memory. | Peak traced bytes, capture boundaries, profile output, and phase-level completion/stopped/error status. | Partial; see saved phase evidence and final report |
| Results, environment, dashboard, and report | Validate result records include required fields and distinguish timing from memory runs; verify incomplete sets are excluded from medians/speedups. | Save CSV or JSON with version, scenario, seed, event count, active-order/level peaks, sale quantity where relevant, fill count, phase, repeat, elapsed seconds, and traced peak bytes. Record Python, dependencies, machine, OS, code version, and generator settings. Build a dashboard that loads saved results, not reruns. | Show construction, replay, individual-sale scaling, version comparison, throughput, latency distributions, post-cancellation memory, and correctness outcomes; label units and missing/stopped runs. | `results/coverage.csv`, `dashboard/app.py`, `docs/report.md`, and `results/dashboard_verification.txt`. | Dashboard checks passed; latest coverage includes 19 supplemental short-policy replay attempts; full matrix remains incomplete |
| Reproducibility and AI disclosure | Verify clean-environment instructions and supplied worked output. | Keep exact run commands and dependency pins; do not include generated million-event datasets. Record AI assistance accurately. | Re-run documented checks in a fresh temporary copy; do not launch the full matrix. | `RUNNING.md`, pinned `requirements.txt`, and `results/final_submission_verification.txt`; commit identifier remains pending. | Fresh-copy verification passed; broader benchmark matrix remains partial |

## Setup verification

| Item | Evidence | Status |
|---|---|---|
| Assignment-local environment | `.venv` uses Python 3.14.7; pytest 9.2.0 is installed and importable from that environment. | Verified |
| Supplied package checksums | 15 present manifest entries matched at setup; the authorized README quick-start now causes an expected README SHA-256 mismatch; `.DS_Store` is absent as noted above. | Verified with documented README delta |

## Preimplementation specification-test coverage

The existing FIFO and best-price tests in `tests/test_price_time.py` are
preserved. `tests/test_specification.py` adds independent, literal expected
fills/books for empty books, the three one-bid market-sell depth cases,
partial-then-subsequent fills with maker priority, a five-order same-price
queue whose IDs are not in arrival order, cancellation lifecycle cases,
crossing limit buys and sells across multiple makers, resting-maker execution
prices, equality and worse-price boundaries, residual limit orders, and the
supplied worked example. Accepted submission assertions include quantity
conservation and positive fills; representative books are checked for no
cross, positive resting sizes, and unique active IDs. Integer tick-times-unit
proceeds are asserted against a hand-calculated constant.

The validation tests cover unknown event type and side, missing common and
type-specific fields, zero/negative/noninteger/boolean prices, quantities, and
sequences, duplicate live submission IDs, and equal/lower sequences. They
assert rejection reason, unchanged canonical book, unchanged last accepted
sequence, valid `not_found` cancellation sequence advancement, and reuse of a
rejected sequence. The additional read-only `last_accepted_seq` observation is
documented in `docs/interface.md`; its initial value is chosen as `None`.

`tests/fixtures/generated_seed_{13,37,91}.jsonl` are deterministic 18-event
valid streams generated separately from engine and measurement code. Their
cycle, random choices, ranges, and regeneration command are recorded in
`tests/fixtures/README.md`. Fixture reproducibility/shape checks pass. The
event-by-event comparison now checks ordered results, accepted sequence, and
canonical inspection for both versions after each event in all three streams.

### Pre-code suite result (historical evidence)

The complete suite was collected with no import or collection errors:

```text
Command: python -m pytest -q --tb=short
Result: 66 collected; 3 passed; 63 failed
Failure reason: all 63 failures raise NotImplementedError from the baseline
scaffold; the engine and inspection behavior are intentionally unimplemented.
Evidence: results/specification_tests_before_code.txt
```

### Version A verification

After implementation, `python -m pytest -q` completed with **66 passed**.
The three fixture reproducibility/shape checks remain included; the 63
preimplementation `NotImplementedError` failures now pass against Version A.
Final output is saved in `results/tests_baseline.txt`. Earlier pre-code
evidence above remains unchanged.

### Version B preimplementation regression result

Before Version B behavior was added, the focused regression/parity command
collected successfully and reported **10 failed, 3 passed**. All 10 failures
were `NotImplementedError` from the Version B scaffold; the three passing
cases were fixture reproducibility checks. Evidence is preserved in
`results/revised_tests_before_code.txt`.

### Both-version verification

The full suite now parameterizes specification tests over both versions and
compares generated streams after every event. Final output is saved in
`results/tests_revised.txt`: **131 passed**. Version B's seven focused
storage regressions also pass, including the bounded-heap assertion under
repeated churn.

### Remaining gaps

- The full matrix is incomplete; see `results/coverage.csv` for each phase.
- One million-event feasibility was attempted under `phase-primary-30s`; baseline completed 0/5 repeats and revised 1/5 before timeout.
- The final report is limited by missing measurements; no full-completion claim is made.
- Commit identifier remains pending; fresh-copy verification passed.

### Benchmark execution status

The benchmark helper tests cover integer-ceiling liquidation quantities,
nearest-rank percentiles and median/throughput calculations, fresh book
isolation for both engines, queue-concentration quantity/price counts, closed
worker-pipe errors, and stopped rows with null elapsed time.

After adding these checks, the complete assignment suite passed **142 tests**
with `.\.venv\Scripts\python.exe -m pytest -q`. Exact output is saved in
`results/tests_benchmark_infrastructure.txt`; the earlier 131-test Version B
evidence remains unchanged.

The final all-mode smoke command was:

```text
.\.venv\Scripts\python.exe benchmarks\run_benchmarks.py --smoke --run-id smoke_final_04
```

It completed **18/18** version/configuration runs: all five supplied workload
families, 10%/100%/200% fresh-book sells, 4-versus-1,000-price queue
concentration, and anchored cancellation churn. It recorded five primary
timing repeats per measured phase, 18 latency summaries and raw event streams,
94 memory checkpoints, and two bounded profiles. Parity checks passed all
smoke workload events and fixed-sale cases. This validates infrastructure
only; the small workloads do not establish comparative performance.

Timeout recording was exercised separately with a 0.001-second limit. All 18
configurations were recorded as `stopped_timeout`, with null elapsed time
rather than zero. That run returns the documented nonzero status because the
workers were intentionally stopped.

A first Windows smoke attempt exposed a pipe-EOF error on normal worker
shutdown. Its partial progress was preserved; pipe closure handling was fixed,
and the final smoke run completed cleanly. Measurement boundaries, limits,
resume behavior, and exact full-run commands are in
`docs/benchmark_protocol.md`.

### Revised diagnostic and continuation protocol

The original aggregate configuration timeout included snapshot counters that
called `inspect_book()` before every event. The revised runner confines
snapshot-based counters and profiling to the small representative workload,
labels inferred counts as estimates, and computes large-run logical state
peaks with an event-result ledger rather than per-event book inspection.
Primary timing, latency, memory, state peaks, counters, and profiling now have
separate equal-for-both-version budgets and independent phase statuses.
Continuation planning verifies workload checksums, engine/generator hashes,
phase definition IDs/hashes, phase settings, and completeness. It reuses only
complete compatible phases and preserves all historical records.

The post-correction full assignment suite passed **149 tests**, including
continuation compatibility, five-repeat completeness, independent phase
status, and representative-only diagnostics checks. Exact command and output
are saved in `results/tests_benchmark_protocol_correction.txt`.

The all-mode smoke run was:

```text
.\.venv\Scripts\python.exe benchmarks\run_benchmarks.py --smoke --run-id smoke_phase_protocol_v2
```

It completed **18/18** version/configurations and **140/140** measurement
phases. All **82/82** primary timing phase sets had five completed repeats.
Counters and profiles ran only for the two version runs of the selected small
mixed case; all smoke outputs and phase records are under
`results/benchmarks/smoke_phase_protocol_v2/`. Saved metadata code hashes
match the measured files. Smoke data validates the instrumentation only and
is not performance evidence.

The no-worker continuation plan for `full_20261125` covers **98**
version/configurations and **700** configured phases: **158 reusable**, **73
incompatible** (saved candidates lacked matching phase rows), and **469
pending** (no candidate phase record). Reusable phases comprise 33 input
parsing, 33 empty construction, 28 engine replay, 28 total application, 18
latency, and 18 memory phases. State peaks are not reused from the old
snapshot-counter implementation. The plan reports `workers_started: 0` and is
saved in `results/benchmarks/full_20261125/continuation_plans/`. The full matrix
remains paused; no full benchmark worker was started after correction.

### Dashboard and report verification

Streamlit 1.67.0 was installed in the assignment-local Python 3.14.7
environment and pinned with the resolved dependencies. The saved-results
dashboard and `results/coverage.csv` were checked without running benchmarks.
The earlier dashboard-verification command was
`.\.venv\Scripts\python.exe -m pytest -q`; **155 passed** at that historical
checkpoint, including Streamlit AppTest rendering, version-filter interaction, explicit
missing-data handling, 4-versus-1,000 price-concentration display, and a
displayed five-repeat median checked against the raw result rows. Compatible
paired speedups also check hashes, policy,
measurement definitions or the saved continuation reuse decision, and all
five distinct repeat numbers. The command output is saved in
`results/dashboard_verification.txt`. The dashboard uses seconds, seconds per
event, events per second, bytes, and integer quantity units as labeled; it
does not convert absent timings to zero. `RUNNING.md` contains setup, test,
replay, benchmark, and dashboard commands. The final report explicitly calls
out the incomplete million-event repeats and matrix.

### Short-budget experimental follow-up

The original stop manifest's 13 never-attempted configurations each received
an `engine_replay` attempt under the new, separate `phase-primary-30s` policy,
with identical 30-second per-version deadlines and a sampled 4,096 MiB memory
limit. Ten attempts completed all five repeats; the three M=100,000 sweep
baseline attempts timed out before a timed repeat. The six cancellation-churn
configurations, three revised sweep configurations, and revised mixed seed44
completed. No incomplete set is summarized or paired across policies.

The 4-versus-1,000-price queue replay was attempted under the same new policy
for both versions. Both revised attempts completed five repeats; baseline
stopped at 2/5 and 1/5 respectively. Existing fixed-book sell phases were
already complete under the older 60-second primary policy and were not
repeated. The queue baseline total-application and latency gaps remain.

The bounded one-million-event `buildup`, seed-42 input took 18.06 seconds to
generate and hash (13,153,228 compressed bytes; SHA-256
`7419d40f1a55a7a5d475e6e1e4d134996fdaff31cd49c555d9880a91e588a3aa`).
Baseline replay timed out at 0/5 repeats; revised timed out at 1/5. Sampled
working sets were below the 4,096 MiB limit, so this is a time-limited
incomplete feasibility check, not a completed benchmark. The dataset remains
ignored in the run input directory.

Exact execution command:
`.\.venv\Scripts\python.exe results\coverage_recovery_execution.py`
The run finished in 278.79 seconds; the full raw records, statuses, script
hash, command, and generation metadata are under
`results/benchmarks/coverage_recovery_short_20261126_1232/`.

### Final submission-copy verification

A temporary copy excluding only `.venv` and `.pytest_cache` installed the
pinned requirements; `pip check` found no broken requirements. The earlier
pre-correctness-review suite passed **155 tests**. Both worked-example commands returned the expected fills,
accepted sequence 6, unchanged ask, 4 BTC remaining on `b4`, and gross
proceeds `$359,400`; specification tests compare the results with
`worked_expected.json`. The smoke run completed **18/18** configurations and
**140/140** phases. Dashboard AppTests passed within the suite, and the
Streamlit health endpoint returned HTTP 200. Exact commands and output are
saved in `results/final_submission_verification.txt`; no full benchmark was
launched.

The current hashes of both engines and the benchmark-measured source files
match the supplemental run metadata. The README manifest hash differs because
of the authorized student quick-start; the original specification text below
it remains preserved. Environment metadata retains absolute interpreter and
generator commands as provenance, while input paths and runtime dashboard
paths are project-relative and worked in the temporary copy. The deferred
document-instruction keyword check remains pending.

### Latest correctness and packaging status

The latest full assignment suite passed **185 tests**. In the separate
10,000-event supplied-stream parity check, mixed and cancel-churn completed;
buildup stopped at 4,600 events, crowded at 4,700, and sweep at 4,300 under
their individual enforced 60-second limits. Their completed prefixes showed
no mismatch, but the remaining suffixes are unchecked. These three checks
remain partial; see `docs/test_coverage.md` and
`results/correctness_review_log.txt`.

The final candidate was exported from the Git index, not copied from the
working tree. Its fresh temporary Python 3.14.7 environment installed the
pinned dependencies and passed `pip check`. The full suite passed **185 tests**
in 62.04 seconds; all 5 dashboard AppTests passed in 73.81 seconds; both worked-example replay
outputs matched `worked_expected.json`; the Streamlit health endpoint returned
HTTP 200. No evidence references were missing, and no benchmark was run. Exact
verification commands and results are in
`results/final_packaging_verification.txt`.
