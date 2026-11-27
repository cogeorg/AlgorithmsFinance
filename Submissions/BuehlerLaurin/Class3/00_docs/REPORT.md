# Report: Class 3 Lab 2
## Specification and model
See ../SPEC.md for slide quotations (Laurin's transcription), D1–D11 and own assumptions. Deterministic CRR American put, no dividends/frictions, ATM observed-price windows. One year selects 8,761 observations. Full files have 43,823 closes, so N=43,822. Missing hours are not filled. Elapsed UTC seconds define T using a Julian year; tree periods count observations.

## Correctness and test-first evidence
Saved 23 intended stub failures before A/data code, then 23 passing baseline checks including six mutants. Saved B/pipeline stub failures before implementing B; shared suite now has 36 passing tests, including 200 deterministic Hypothesis comparisons. The oracle recursively prices small trees with exact Fraction arithmetic through N=12, independently of the rolling-array code. TRACE.md derives both toy fractions by hand. Toy tolerances and four-decimal checks are unchanged.

Critical mutants independently corrupt q, discounting, early exercise, update order, zero-value ties and expiry boundary. Each is runnable and killed by its named assertion; the unmodified versions pass those same assertions. Validation has direct contract checks because A/B share it. Public pipeline tests establish that timed analysis calls the same calibrated pricing and first-exercise functions, and that a constant-price asset records an error while the next asset succeeds.

Induction argument: terminal payoff is correct. At each t, increasing j reads both old child values before overwriting needed inputs. A applies the recurrence node by node; B evaluates its layer in array operations. The maximum of continuation and intrinsic dominates intrinsic; induction versus European continuation establishes American>=European. With R>=1 and child values<=K, continuation<=K, hence V<=K. The last bound is specific to the nonnegative-rate workloads, not a generic negative-rate claim. Boundary aggregation considers all positive-intrinsic qualifying nodes; no exercise-contiguity assumption is used.

Full BTC1y A/B comparison initially produced identical value 16714.935270539554 with no boundary exceptions. The lattice revision is checked again against the saved full-window reference after measurement. Generic comparison permits only the specified reported near-tie decision exceptions and 1e-9*max(1,K) value tolerance.

## Numerical construction and exact ties
A retains the two-array induction but reconstructs each stock layer instead of using the slides' fragile edge propagation. Log-price guards map unrepresentable wings to 0/+inf; representable central nodes are calculated independently. At offset=0 return S0 exactly; otherwise prefer S0*exp(offset), falling back to a full log-price expression when required. Extreme tests reach both saturated wings and still recover central prices.

Claude's e^-657 underflow illustration was incorrect: this is a normal nonzero binary64 value. Normal/subnormal transition is near e^-708.396, zero rounding near e^-745. e^-876 is a genuine zero example. Repeated multiplication can also stall at inaccurate subnormals.

The tie test reproduced weighted continuation 50.00000000000001 instead of exact 50. The algebraically equivalent affine expression (down+q*(up-down))/R preserves that tie. Both versions retain strict positive intrinsic and exact >= comparison; tolerance is diagnostic only, not used to expand the exercise region.

## Algorithms and complexity
A stores S,V of N+1 plus boundary and near-tie arrays. It visits N(N+1)/2 backward nodes and N+1 leaves: worst-case Θ(N²) time, Θ(N) workspace under fixed-cost float arithmetic. No full tree is stored.

B first vectorized each layer. A subsequent measured revision exploits reciprocal CRR: S[t,j] depends on k=2j-t, with only 2N+1 distinct prices. An O(N) lattice caches these independently computed values and payoffs; each layer is a strided view. This is not a stored tree. General nonreciprocal valid inputs use direct stable layer construction. The V recurrence and boundary test remain vectorized. All buffers, lattice, diagnostics and outputs are O(N); visiting every node still takes Θ(N²).

M sequential assets cost Θ(sum N_i²) pricing time, O(max N_i + M) pricing/output-summary space. Full-file parsing temporarily retains L closes/timestamps/datetime objects, so primary whole-run memory is distinct from pricing workspace. Boundaries are serialized per asset in a separate artifact run, rather than accumulated for the batch.

## Profiling and revision
cProfile A BTC1y: 84.977 profiled seconds, 84.339 in pricing, about 38.38m exp calls and 76.76m max calls. These traced times are not speed measurements. The initial B median BTC1y was 1.072288 s; caching the lattice reduced this to 0.718781 s on the same input, with an O(N) memory tradeoff. Initial grid is explicitly marked interrupted; completed before-revision cells are retained and incomplete cells are excluded.

## Measurement protocol
Use bench.harness: one untimed warm-up, five timing repeats, median with all raw repeats retained. Timed function is the tested public analyze_many pipeline: loading/calibration/pricing/boundary/first exercise, sequential assets in one process, compact scalar summaries retained. Process startup/imports and CSV serialization are excluded. OS caches are not flushed, so this is a warm-cache experiment after warm-up. GC remains enabled. Parse+calibration, pricing and exercise phase instrumentation is a separate run; parse/calibration are combined because the public loader calibrates directly. Aggregate medians are not sums of medians of separate assets.

Tracemalloc is a separate run. Primary covers the whole public pipeline, including input and boundary allocations. Secondary starts from calibrated input and covers a pricing call including its returned boundary; the aggregate secondary column is the maximum of independently traced asset calls. Neither measure is process RSS. A BTC1y is timing-only for the ratio. Growth cells limit the entire child process to 60 s, including warm-up and all repeats; stopped cells have no median or ratio.

The final run stores exact source hashes, environment, tests, protocol, timing repeats, memory scopes, instrumented phases, per-asset values/exercise results and complete boundary CSVs. A timing is reused from the earlier same-machine run only after verifying unchanged A/data/common/pipeline source hashes. Both runs remain available with provenance. Human-only git means these measurements use a human commit plus dirty hashes, not a clean-commit claim.

## Results
Both recorded runs are **quick (dirty tree)** measurements: initial vectorization (`20261127T120831Z_279b029-dirty_fast_blocks12`, interrupted) and revised lattice (`20261127T121436Z_279b029-dirty_fast_blocks12`, complete required grid). These labels remain even after source/commit verification; there is no clean-tree measurement claim.
| Workload | Version | N | Assets | Median seconds | Whole-run peak bytes | Pricing peak bytes |
|---|---|---:|---:|---:|---:|---:|
| BTC1y | A | 8760 | 1 | 30.012675 | not measured | not measured |
| BTC1y | B | 8760 | 1 | 0.718781 | 7001865 | 852242 |
| BTC5y | B | 43822 | 1 | 7.199832 | 8685193 | 4217726 |
| ALL1y | B | 8760 | 40 | 26.580497 | 7048338 | 852368 |
| ALL5y | B | 43822 | 40 | 284.649042 | 8731641 | 4218020 |

BTC1y A/B median ratio: **41.75×** on these inputs and this machine. A timing is reused from the earlier same-machine run after A/data/common/pipeline hash checks. Both run folders and reuse provenance are retained.

- BTC1y: value **16714.9352705396 USDT**; first exercise **2026-06-02T14:00:00Z**, payoff **41588.71 USDT**.
- BTC5y: value **20719.7894300243 USDT**; first exercise **2022-06-18T06:00:00Z**, payoff **42121.23 USDT**.

| Version | N | Status | Median seconds |
|---|---:|---|---:|
| A | 1000 | ok | 0.416015 |
| A | 2000 | ok | 1.690320 |
| A | 4000 | ok | 6.303940 |
| A | 8000 | stopped | — |
| B | 1000 | ok | 0.033366 |
| B | 2000 | ok | 0.072495 |
| B | 4000 | ok | 0.179322 |
| B | 8000 | ok | 0.459377 |

Log-log least-squares slopes over completed growth cells: A=1.961, B=1.266. **A: quick, 3 sizes; 8k stopped at 60 s.** B's fitted slope rounds to **1.27** because per-layer NumPy overhead dominates at these small N: each layer pays Python-loop/ufunc dispatch, masking and reduction costs independent of its node count. Increasing N amortizes that overhead over longer vectors. The algorithm still evaluates each node in every layer, so work is **Θ(N²)**; the 1.27 fit over 1k–8k is not an asymptotic exponent claim. Stopped cells are excluded from slopes and ratios; their 60 s limit covers the complete child process, not one repeat.

Saved run: 03_results/runs/20261127T121436Z_279b029-dirty_fast_blocks12

## Limitations and next checkpoint
PDF not independently extracted; quoted slide transcription supplied by Laurin. S&P 500 excluded. Hash verification uses our own snapshot, not upstream authentication. Tracemalloc describes traced allocations, and warm caches/hardware/background activity constrain timing comparisons. Independent Claude audit/attack and fresh-environment hand-off verification remain later phases. Stop after Block 2.

## AI usage
See AI_LOG.md for accepted choices, corrected numerical claims, failed runs, tie debugging and measured revisions. No git writes or dependency installation.
