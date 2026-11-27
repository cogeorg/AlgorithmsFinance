# Assignment 1 completion checklist

## Complete locally

- [x] Work is isolated to `Submissions/LaviBen/Assignment1/` on the topic branch.
- [x] Course generator and fixtures are copied byte-for-byte with SHA-256.
- [x] Contract and independent tests predate both implementations.
- [x] The failing tests-first checkpoint commit is recorded and reproducible.
- [x] Baseline and revised matching algorithms are preserved.
- [x] Worked example, conservation, FIFO, crossing, cancellation, validation,
  immutability, differential, fixture, and regression tests pass.
- [x] Revision, invariants, complexity, limitations, and AI decisions are documented.
- [x] Deterministic workload preparation covers five families, three required
  sizes, seeds 42/43/44, queue concentration, and liquidation.
- [x] Timing includes raw repeats, medians, parsing, replay, total application,
  throughput, construction and individual sale phases.
- [x] Latency includes raw per-event values, p50/p95/p99, event types, and
  early/late windows in a separate instrumentation run.
- [x] Memory uses fresh `tracemalloc` runs with explicit boundaries,
  checkpoints, cancellation cleanup, final output alive, and time limits.
- [x] Stopped runs are labeled and preserved; no values are clamped,
  extrapolated, invented, or silently omitted.
- [x] Parse, replay, liquidation-build, sale, and object-cleanup lifecycle
  boundaries have deterministic regression coverage; unattempted work uses a
  null duration and partial summaries expose repeat coverage.
- [x] Dashboard and report builders load saved evidence only and are byte-stable.
- [x] Docker packaging is intentionally omitted because it is optional.

## Fresh-audit repairs completed

- [x] Preserve the current working tree and identify the reviewed baseline.
- [x] Record tests-first failures for every newly discovered defect.
- [x] Reject or explicitly disclose mismatched parse/replay repeat sets.
- [x] Bound operation-count diagnostics and preserve partial/stopped evidence.
- [x] Release liquidation correctness state before timing and memory phases.
- [x] Strengthen saved-report consistency validation.
- [x] Render a true latency distribution from saved samples only.
- [x] Freeze and enforce operation-specific direct-method behavior.
- [x] Add the missing validation, FIFO-symmetry, and residual-priority tests.
- [x] Run the complete corrected test suite (71 tests, 190.969 seconds).
- [x] Run an eight-dataset revision-3 smoke benchmark and validate all 232 records.
- [x] Update all documentation to match the corrected implementation.

## Required before submission

- [x] Explicitly authorize and create a new local commit containing the
  corrected measurement, dashboard, report, test, and documentation code.
- [x] Confirm the 73-dataset canonical grid and all recorded checksums/events.
- [x] Run replacement canonical five-repeat timing/latency/memory measurements
  from a clean tree.
- [x] Attempt the optional one-million-event case within the declared limit and
  retain stopped evidence if it is infeasible.
- [x] Generate `results/dashboard.html` and `REPORT.md` from replacement
  canonical results.
- [x] Verify the replacement dashboard visually and reproduce both generated
  artifacts byte-for-byte.
- [x] Refresh `results/CHECKSUMS.json` for the replacement raw report,
  dashboard, and root report.
- [x] Run the complete test suite (71 tests, 190.969 seconds) and final Git
  scope/secret checks on the submission candidate.
- [x] Record the new audited measurement commit in the replacement raw evidence
  and report. Commit `ffb474170b4849af850e31588f9a1a70dcf08da3` belongs only
  to the superseded archive.
- [x] Create the new immutable annotated audit/submission tag
  `laviben-assignment1-revision4-20261122`; do not move or reuse an earlier tag.
- [ ] Push only when Ben Lavi explicitly requests it; do not merge the pull request.
