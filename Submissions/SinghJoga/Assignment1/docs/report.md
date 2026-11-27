# Assignment 1 report

## Specification and model

The implementation is a sequential, single-venue limit order book using
positive integer cents per BTC and integer `1e-8 BTC` quantity units. Orders
execute at the resting maker's price, by best price and FIFO arrival sequence.
There are no fees, account balances, hidden orders, self-trade rules, network
delays, or simultaneous events. The generated inputs are synthetic teaching
streams, not historical exchange data or calibrated market behavior.

## Correctness

Versions A and B implement the same documented event interface. The
specification suite uses independent expected books and fills, validation
rejection snapshots, conservation assertions, cancellation lifecycle cases,
and per-event generated-stream comparison. The latest complete suite, including
dashboard verification and the correctness review, passed **185 tests**. The
worked example expects maker orders `b1,b2,b3,b4` to execute in order and gross
proceeds of `$359,400`. Of the five supplied 10,000-event parity streams, mixed
and cancel-churn completed; buildup, crowded, and sweep stopped at 4,600,
4,700, and 4,300 events respectively under their separate 60-second limits.
Their saved prefixes showed no mismatch; the remaining suffixes are unchecked.

The engines retain active orders only. Version A scans a list and sorts
eligible opposite-side orders for matching; Version B indexes active IDs,
FIFO price queues and best-price heaps with bounded lazy cleanup. See
[`baseline_design.md`](baseline_design.md) and
[`revision_design.md`](revision_design.md) for pseudocode, invariants, costs,
and the applied heap cleanup policy.

The shared invariants are positive remaining quantities, one storage location
per active order, no crossed resting book, maker-price execution, FIFO by
arrival sequence within a price, and conservation of incoming quantity across
fills and residual. Rejected events preserve the book and accepted sequence.
For Version A, active-list duplicate/cancel scans and selection/sorting make
matching scale with active orders (up to `O(B log B)` plus `O(F)` output);
list removals are linear. Version B uses an active-ID dictionary, per-price
FIFO queues and best-price heaps: dictionary operations are expected `O(1)`,
heap selection is `O(log H)`, and consuming `F` makers costs at least
`O(F)` plus heap work for exhausted levels. Heap cleanup can rebuild in
`O(P + H)` occasionally; the stated amortized bounds and physical heap size
`H` are documented in the revision design. Both versions use `O(B + P)`
logical book space plus returned fills `O(F)`; Version B additionally tracks
bounded heap entries. See the cited design documents for full event-by-event
pseudocode and storage-specific terms.

## Measurement protocol and evidence

The dashboard is a read-only consumer of saved JSON records. The reconciled
[`coverage.csv`](../results/coverage.csv) records configuration, phase,
status, policy, source, code/input hashes and raw repeat count. Reused phase
results are references to their original source, not a second measurement.
The historical aggregate-timeout policy remains separate from the later
phase-budget policy. Coverage does not combine incompatible or incomplete
repeat sets.

The paused matrix plan contains 49 scenarios and 98 version/configuration
combinations. The continuation evidence includes 69 completed configurations,
15 partial configurations, one progress-only interrupted configuration, and
13 configurations never attempted. The run lasted about **54m46s**. Its
authoritative incomplete-coverage and stop details are in
[`CONTINUATION_STOP_20261126.json`](../results/benchmarks/full_20261125/CONTINUATION_STOP_20261126.json).
The 13 never-attempted IDs are listed in that manifest and in the
`configuration_status` column of the coverage export.

The never-attempted configurations are:

- `workload_cancel_churn_M100000_seed42__baseline`
- `workload_cancel_churn_M100000_seed42__revised`
- `workload_cancel_churn_M100000_seed43__baseline`
- `workload_cancel_churn_M100000_seed43__revised`
- `workload_cancel_churn_M100000_seed44__baseline`
- `workload_cancel_churn_M100000_seed44__revised`
- `workload_mixed_M100000_seed44__revised`
- `workload_sweep_M100000_seed42__baseline`
- `workload_sweep_M100000_seed42__revised`
- `workload_sweep_M100000_seed43__baseline`
- `workload_sweep_M100000_seed43__revised`
- `workload_sweep_M100000_seed44__baseline`
- `workload_sweep_M100000_seed44__revised`

### Short-budget follow-up (2026-11-26)

The original `full_20261125` stop manifest remains historical: its 13
configurations were never attempted under that run. A separate run,
`coverage_recovery_short_20261126_1232`, attempted `engine_replay` for all 13
under the distinct `phase-primary-30s` policy. Each version had a 30-second
enforced worker deadline and a sampled 4,096 MiB memory limit. The existing
phase worker performed its untimed warm-up and up to five timed repeats; raw
rows were retained and no incomplete set was summarized.

Ten configurations completed all five repeats. Three baseline sweep attempts
(`seed42`, `seed43`, and `seed44`, each M=100,000) timed out with zero completed
timed repeats. The other ten were the three revised sweep cases, all six
baseline/revised cancellation-churn cases, and revised mixed seed44. No
speedup is inferred for sweep: its baseline sets are incomplete. Mixed seed44
also has no baseline attempt under this policy. The cancellation-churn cases
have complete version pairs, but remain a separately labeled short-policy
measurement set.

For the queue-concentration comparison, the same short-policy engine-replay
phase was attempted on both versions for both 4- and 1,000-price inputs.
Revised completed five repeats for each. Baseline stopped at 2/5 repeats for
four prices and 1/5 for 1,000 prices, so there is no complete paired summary
for either concentration. The remaining old-policy gaps are baseline
`total_application` at both price counts and baseline `latency` at 1,000
prices. Fixed-book sell phases were already complete for both versions under
`phase-primary-60s`; they were not rerun.

The one-off execution command was:

```powershell
.\.venv\Scripts\python.exe results\coverage_recovery_execution.py
```

It reused checksum-verified M=100,000 and queue inputs from the original run
and invoked only the existing bounded `engine_replay` phase worker. Its
eight-minute controller cap allowed 30 seconds per attempt; the 19 attempts
finished in **278.79 seconds** (12 phase records completed, 7 stopped). The
exact per-attempt records and incremental status are under
`results/benchmarks/coverage_recovery_short_20261126_1232/`.
`results/coverage_recovery_execution.py` records the selected configuration
IDs, the exact generator command, policy, limits, and script hash. No engine
or benchmark implementation was changed.

One million-event feasibility was attempted once using `buildup`, seed 42.
Generation, including gzip writing and checksum calculation, took **18.06 s**;
the generated 13,153,228-byte input has SHA-256
`7419d40f1a55a7a5d475e6e1e4d134996fdaff31cd49c555d9880a91e588a3aa`.
Both versions used the same saved input and 30-second replay deadline. Baseline
timed out with 0/5 completed repeats; revised timed out with 1/5 (the single
completed replay took 10.044 s). Sampled peak working sets were about 985 MiB
and 1,273 MiB respectively, below the 4,096 MiB limit. This is an incomplete
feasibility investigation, not a five-repeat benchmark result. The generated
dataset remains in the ignored run input directory and was not committed.

An initial standard-CLI attempt was stopped before any measurement records
because `--scenarios` also generated fixed-book, queue, and anchored-churn
cases; its generated inputs and interruption note are preserved under
`coverage_short_20261126_1230/`. An initial one-off-script launch also failed
before run creation due to Python import-path setup; the corrected invocation
and failure evidence are retained in `coverage_recovery_setup_failure.txt`
and the separate console log.

Across compatible completed primary timing evidence, the dashboard displays
146 paired version/phase sets with matching inputs, policy, code hashes,
measurement definitions (or an explicit continuation-plan reuse decision for
legacy phases), and five raw repeats. This comprises 56 legacy
`aggregate-300s` pairs and 90 later `phase-primary-60s` pairs; the policies are
never merged. The `M=10,000`, buildup, seed-42 replay pair has
saved medians of **15.2705 s** (baseline) and **0.07537 s** (revised). This is
one observed paired result, not a general speedup claim: the matrix is
incomplete, historical and phase-level policies are not mixed, and other
workloads/sizes may differ. The Version A path repeatedly scans the active
list for duplicate IDs and scans/sorts eligible opposite orders; Version B
uses direct ID lookup and best-price queue selection. This is a plausible
code-level explanation for the observed buildup difference, not a claim that
the measurement alone proves causation.

On that same input and policy, the separately measured parse medians were
**0.09163 s** (baseline) and **0.05696 s** (revised). Parsing is not included
in the replay figure; it is displayed as its own phase in the dashboard.
The full-application phase is also retained separately and should not be
derived by adding phase medians.

For the saved 5,000-cycle anchored cancellation-churn case, the final
checkpoint had one active order and one occupied level in each implementation.
Traced current/peak allocation was 3,586/4,018 bytes for Version A and
5,826/8,882 bytes for Version B. The recorded physical-storage-entry count
was 1 and 9 respectively; this implementation-specific diagnostic is not a
direct comparison of total process memory.

The original aggregate diagnostic path repeatedly called canonical
`inspect_book()` while collecting counters, copying/sorting the whole book per
event. This made diagnostics dominate large runs and produced misleading
timeouts. The corrected protocol confines snapshot counters and cProfile to a
small representative workload; large-run state peaks use a lightweight
event-result ledger. Counter-derived visited-price and operation counts are
estimates, not exact executed-operation counts.

Primary timing includes validation, matching, mutation, and fill result
construction, but excludes input generation, correctness checking, book
inspection, and output history. Parsing, empty construction, replay, and total
application are separate phases. Latency uses per-event timers and nearest-rank
p95/p99; memory uses separate `tracemalloc` sessions with prepared inputs.
Traced memory excludes input allocations, native allocations, allocator
fragmentation, and total process memory. Sampled worker memory limits are
termination thresholds, not hard operating-system caps.

Saved profiling artifacts cover only the bounded representative workload.
The representative `workload_mixed_M1000_seed42` baseline/revised profile
files are under `results/benchmarks/full_20261125/artifacts/`.
The dashboard exposes raw records, units, measurement policies, filters, and
incomplete/stopped/missing statuses; it provides an explicit 4-versus-1,000
price-concentration table and does not fill missing timing values with zero.
Compatible paired speedups require complete five-repeat sets,
matching inputs and code hashes, and matching phase definitions/settings or an
explicit saved continuation-plan reuse decision for legacy aggregate phases.
The dashboard verification output before the short-budget follow-up recorded
732 full-matrix coverage rows, 98 distinct configurations, 13 never-attempted
configurations, and the 146 compatible pairs above. The refreshed
[`coverage.csv`](../results/coverage.csv) additionally records the 19
short-policy engine-replay attempts described above; these do not overwrite or
merge with the earlier evidence. No benchmarks were run while building or
verifying the dashboard.

## Limitations and remaining work

- The original full matrix remains incomplete. All 13 original never-attempted
  configuration IDs now have a separate short-policy replay attempt, but three
  baseline sweep attempts stopped before a timed repeat; all other phases
  remain governed by their original coverage statuses.
- The million-event feasibility attempt is incomplete: neither version
  produced five repeats, and baseline produced no timed repeat.
- Queue-concentration short-policy baseline sets are incomplete; the
  corresponding old-policy total-application and latency gaps remain.
- A stopped or incomplete repeat set has no reportable five-repeat median.
- Snapshot-derived small-workload counters are estimates.
- No result should be generalized to real exchange liquidity or production
  trading systems.
- AI assistance was used for implementation, tests, benchmark tooling,
  dashboard, and documentation. Suggestions were checked against the supplied
  contract; the original counter-heavy measurement design was corrected after
  observed diagnostic overhead. No result or speedup was invented.

The separate deferred check for document-embedded keyword instructions remains
pending. No full benchmark was run during final submission preparation.

## Earlier clean-copy checks (historical)

This earlier verification used a temporary copy with a new Python 3.14.7
environment. Installing pinned dependencies succeeded, `pip check` found no
broken requirements, and the complete suite passed **155 tests**. Baseline
and revised worked-example replays matched `worked_expected.json`: the sell
fills b1/b2/b3/b4 in order, leaves 4 BTC on b4, leaves the ask unchanged, and
produces `$359,400` gross proceeds. The documented smoke run completed 18/18
configurations and 140/140 phases in the temporary results directory.
Dashboard AppTests passed, and the Streamlit server health endpoint returned
HTTP 200. These checks predate the final correctness review; their 155-test
count is historical. Exact commands and output are saved in
`results/final_submission_verification.txt`.

The measured baseline/revised engines and the generator, benchmark harness,
and test files listed by the supplemental run all match their recorded SHA-256
hashes. The README manifest mismatch is expected: its hash changed only
because the authorized student quick-start was prepended; the supplied
specification text below it was preserved. Saved inputs use relative paths
and work in a fresh copy. Machine-specific interpreter and generator command
strings remain in execution metadata for provenance. No full benchmarks were
run during final verification.

An audit across historical benchmark metadata found no mismatches for either
engine or the workload generator. Earlier runs retain older hashes for
benchmark harness, metrics, and test files as the tooling evolved, including
the diagnostic-overhead correction. These records were not rewritten or
treated as current-code evidence; continuation eligibility remains subject to
the saved phase compatibility checks.

## Final index-based packaging verification

The final candidate was exported from the Git index into a fresh temporary
copy, excluding ignored and untracked files. The index copy contained 2,177
Assignment 1 files; a new Python 3.14.7 environment was created only in that
temporary copy. Pinned dependency installation succeeded and `pip check`
reported no broken requirements. The full suite passed **185 tests** in
62.04 seconds, and the focused dashboard AppTest suite passed **5 tests** in
73.81 seconds. Baseline and revised worked-example CLI outputs matched the
supplied expected fills, residual book, accepted sequence, and integer
proceeds. The dashboard server returned HTTP 200 and was stopped after the
health check.

Reference validation found no missing paths: all 5 report Markdown links,
7 unique result paths, 6,367 saved dashboard row-record references, and 179
latency-artifact references resolved in the index copy. The dashboard loaded
the saved evidence and its AppTests exercised rendering and filters. No
benchmark was run. Exact commands and outcomes are saved in
`results/final_packaging_verification.txt`.
