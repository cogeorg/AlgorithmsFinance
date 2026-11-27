# Report: Class 3 Lab 2
## Specification and model
See ../SPEC.md for quotations (Laurin's slide transcription), D1–D11 and scope. Deterministic CRR American put, no dividends/frictions, ATM observed-price windows. One year is 8,761 observations; full file uses actual rows.

## Correctness
No implementation or task-specific tests yet. Planned: independent small-N Fraction oracle, N=2 hand trace, invariants, differential checks, critical mutants and Claude audit/attack. TRACE is reserved for the baseline phase.

## Complexity predictions
Worst-case fixed-cost arithmetic prediction: Θ(N²) pricing time, Θ(N) workspace including boundary. N(N+1)/2 induction nodes, N+1 terminal nodes; two work arrays and one boundary output. No full tree. Candidate vectorization has the same asymptotic bounds. Full-run input residency is separate from pricing workspace.

## Runtime and memory
No measurements. Primary timing and separate tracemalloc peak cover loading through first exercise; secondary peak covers pricing including boundary. Batch processes assets sequentially. Actual N, counts and error rows required.

## Profiling and revision
Not started. Profile A before choosing B. No speed claims.

## Data and limitations
40 local CSVs inventoried; each 43,823 rows / 43,822 steps with one missing hour. Hash verification uses our own local snapshot, not an upstream manifest. PDF not independently extracted. S&P 500 excluded.
Numerical example corrected: exp(-657) is nonzero; exp(-876) is zero in binary64. Stable initialization and wing handling remain implementation work.

## AI usage
See AI_LOG.md. This session only scaffolds, specifies and verifies data/docs. No algorithm implementation or task-specific tests.
